# -*- coding: utf-8 -*-
"""#2517: committed numeric NFB physical-source diagnostics belong to Engine."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_v5_diagnostics as engine
from ae_engine.cabinet_types import policy
from ae_engine.receiving_layout import new_receiving_layout
from tests.test_issue1504_ac09_ac24_current_csv_live_diagnostics import _bay


def test_unsubmitted_preview_detaches_only_the_selected_real_bay():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout["sets"][0]["bays"][0]["nfb_config_submitted"] = True
    before = deepcopy(layout)
    preview = api.project_receiving_nfb_unsubmitted_preview_layout(
        layout, set_index=0, bay_index=0,
    )
    assert preview["sets"][0]["bays"][0]["nfb_config_submitted"] is False
    assert layout == before
    assert preview["sets"] is not layout["sets"]
    assert preview["sets"][0]["bays"][0] is not layout["sets"][0]["bays"][0]
    assert api.project_receiving_nfb_unsubmitted_preview_layout is (
        engine.project_receiving_nfb_unsubmitted_preview_layout
    )


@pytest.mark.parametrize("set_index,bay_index", [
    (True, 0), (0, True), (0.0, 0), (0, 0.0),
    (-1, 0), (0, -1), (1, 0), (0, 1),
])
def test_preview_rejects_nonphysical_set_bay_identity(set_index, bay_index):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    before = deepcopy(layout)
    with pytest.raises(ValueError, match="NFB_PREVIEW_PHYSICAL_BAY_REQUIRED"):
        api.project_receiving_nfb_unsubmitted_preview_layout(
            layout, set_index=set_index, bay_index=bay_index,
        )
    assert layout == before


def test_v5_scoped_diagnostics_receives_actual_engine_door_base_and_unrelated_head(
    monkeypatch,
):
    from ae_engine import receiving_base_plate_config as base
    snapshot = {"model": "受電箱"}
    monkeypatch.setattr(
        policy, "derive_inner_door_panels",
        lambda source: (SimpleNamespace(stable_id="inner_door:upper",
                                        cell_key="0:0"),),
    )
    monkeypatch.setattr(base, "receiving_base_plate_values",
                        lambda source: {"height": 300})
    shown_parts = (
        SimpleNamespace(part_key="head", render_data=SimpleNamespace(scene=object())),
        SimpleNamespace(part_key="base_plate", render_data=SimpleNamespace(scene=object())),
    )
    view = api.project_receiving_current_v5_nfb_physical_diagnostics(
        _bay(), physical_snapshot=snapshot,
        set_id="real-set", bay_id="real-bay", version_id="inner-version",
        physical_parts=shown_parts,
    )
    assert view["status"] == "CSV_V5_SCOPED_DIAGNOSTIC"
    assert view["set_id"] == "real-set" and view["bay_id"] == "real-bay"
    assert view["version_id"] == "inner-version"
    rows = {item["part_id"]: item for item in view["part_rows"]}
    assert set(rows) == {"inner_door:upper", "base_plate", "head"}
    assert rows["head"]["status"] == "NFB_UNAFFECTED"
    assert not rows["head"]["nfb_affected"]
    assert rows["inner_door:upper"]["nfb_affected"]
    assert view["manufacturing_ready"] is False
    assert view["actual_export_count"] is None


def test_v5_two_tiers_require_engine_real_tier_physical_sources(monkeypatch):
    from ae_engine import receiving_nfb_layer_physical_parts as tiers
    snapshot = {"model": "受電箱"}
    monkeypatch.setattr(
        policy, "derive_inner_door_panels",
        lambda source: (SimpleNamespace(stable_id="inner_door:upper",
                                        cell_key="0:0"),),
    )
    seen = []
    def real_tier_parts(source, *, require_source_z):
        assert source is snapshot
        seen.append(require_source_z)
        return {
            index: SimpleNamespace(physical_id=f"base_plate:nfb_layer:{index}")
            for index in (0, 1)
        }
    monkeypatch.setattr(tiers, "source_receiving_nfb_tier_base_specs",
                        real_tier_parts)
    view = api.project_receiving_current_v5_nfb_physical_diagnostics(
        _bay(count=2), physical_snapshot=snapshot,
        set_id="real-set", bay_id="real-bay", version_id="inner-version",
    )
    assert seen == [False]
    assert {r["part_id"] for r in view["part_rows"]} == {
        "inner_door:upper", "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    }
    assert all(r["nfb_affected"] for r in view["part_rows"])
    assert "NFB_REAL_BASE_PLATE_SOURCE_MISSING" not in view["unresolved_dependencies"]
    assert view["manufacturing_ready"] is False


def test_missing_physical_sources_fail_closed_and_report_both_roles(monkeypatch):
    from ae_engine import receiving_base_plate_config as base
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda _: ())
    monkeypatch.setattr(base, "receiving_base_plate_values", lambda _: None)
    view = api.project_receiving_current_v5_nfb_physical_diagnostics(
        _bay(), physical_snapshot={"model": "受電箱"},
        set_id="real-set", bay_id="real-bay", version_id=None,
        physical_parts=(SimpleNamespace(part_key="untrusted"),),
    )
    assert view["derived_state"] == "DRAFT"
    assert "NFB_REAL_INNER_DOOR_SOURCE_MISSING" in view["unresolved_dependencies"]
    assert "NFB_REAL_BASE_PLATE_SOURCE_MISSING" in view["unresolved_dependencies"]
    assert not view["part_rows"]
    assert view["manufacturing_ready"] is False


def test_gui_manifest_source_and_preview_use_public_engine_only():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    start = source.index("        def physical_manifest(")
    end = source.index("        def export_partial_nfb_inner_door(", start)
    subset = source[start:end]
    assert "manufacturing_api.project_receiving_nfb_unsubmitted_preview_layout(" in subset
    assert "manufacturing_api.project_receiving_current_v5_nfb_physical_diagnostics(" in subset
    assert "current_v5_nfb_diagnostics(" not in subset
    assert "actual_unrelated_nfb_scene_parts(" not in subset
    assert "derive_inner_door_panels(" not in subset
    assert "source_receiving_nfb_tier_base_specs(" not in subset
    assert "preview_bay[\"nfb_config_submitted\"]=False" not in subset
    assert "manufacturing_api.project_receiving_bay_legacy_aliases(" in source
    assert api.project_receiving_current_v5_nfb_physical_diagnostics is (
        engine.project_receiving_current_v5_nfb_physical_diagnostics
    )
