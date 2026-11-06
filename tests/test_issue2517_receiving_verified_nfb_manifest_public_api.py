# -*- coding: utf-8 -*-
"""#2517 legacy verified NFB physical-role and readiness must stay in Engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine import receiving_nfb_export_manifest as original
from tests.test_issue1501_nfb_export_manifest import _prepared


@pytest.mark.parametrize("color30,color150", [(0, 1), (1, 1), (0, 0)])
def test_verified_manifest_public_projection_matches_canonical_engine_scope(
    tmp_path, color30, color150,
):
    kwargs = _prepared(tmp_path, color30=color30, color150=color150)
    scope = kwargs["scope"]
    physical = (
        original.NfbActualPart(scope.inner_door_part_id, original.INNER_DOOR),
        *(original.NfbActualPart(part, original.BASE_PLATE)
          for part in scope.base_plate_part_ids),
        *(original.NfbActualPart(part, original.MIDDLE_PLATE)
          for part in scope.middle_plate_part_ids),
    )
    canonical = original.derive_nfb_partial_export_manifest(
        **{key: value for key, value in kwargs.items()
           if key not in ("actual_parts", "proven_unaffected_part_ids")},
        actual_parts=physical,
    )
    before = canonical.report()
    result = manufacturing_api.project_receiving_verified_nfb_partial_manifest(
        scope=scope,
        saved_bay=kwargs["saved_bay"],
        set_brand=kwargs["set_brand"],
        source_inventory=kwargs["source_inventory"],
        verified_inner_door=kwargs["verified_inner_door"],
        source_path=kwargs["source_path"],
    )
    assert {k: result[k] for k in before} == before
    assert result["status"] == (
        "WHOLE_READY" if canonical.whole_ready else "PARTIAL_ONLY"
    )
    assert result["reason"] == (
        "僅限以下已核實的實體板件；PAD 與整櫃焊接工藝另行驗收"
        if canonical.authorized_part_ids else "尚無可放行 NFB 加工板件"
    )
    assert {row["part_id"] for row in result["rows"]} == {
        scope.inner_door_part_id, *scope.base_plate_part_ids,
        *scope.middle_plate_part_ids,
    }
    assert result["assembly_status"] == (
        "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY"
    )


def test_stale_verified_nfb_dxf_source_cannot_be_displayed_as_ready(tmp_path):
    kwargs = _prepared(tmp_path)
    kwargs["source_path"].write_bytes(b"stale-different-dxf")
    result = manufacturing_api.project_receiving_verified_nfb_partial_manifest(
        scope=kwargs["scope"], saved_bay=kwargs["saved_bay"],
        set_brand=kwargs["set_brand"],
        source_inventory=kwargs["source_inventory"],
        verified_inner_door=kwargs["verified_inner_door"],
        source_path=kwargs["source_path"],
    )
    assert result["status"] == "PARTIAL_ONLY"
    assert "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in result["unresolved_dependencies"]
    assert not result["whole_ready"]


def test_missing_physical_scope_fails_closed_not_minted(monkeypatch):
    with pytest.raises(TypeError, match="NFB actual physical scope required"):
        manufacturing_api.project_receiving_verified_nfb_partial_manifest(
            scope=object(), saved_bay={"stable_id": "bay"},
            set_brand="士林", source_inventory=None,
            verified_inner_door=None, source_path=None,
        )


def test_gui_receipt_manifest_has_no_physical_part_role_authority():
    src = (
        Path(__file__).resolve().parents[1] /
        "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    begin = src.index("        def physical_manifest(")
    end = src.index("        def export_partial_nfb_inner_door(", begin)
    source = src[begin:end]
    assert "manufacturing_api.project_receiving_verified_nfb_partial_manifest(" in source
    assert "NfbActualPart(" not in source
    assert "derive_nfb_partial_export_manifest(" not in source
    assert "from ae_engine.receiving_nfb_export_manifest import" not in source
    assert "manifest.whole_ready" not in source
    assert manufacturing_api.project_receiving_verified_nfb_partial_manifest is (
        original.project_receiving_verified_nfb_partial_manifest
    )
