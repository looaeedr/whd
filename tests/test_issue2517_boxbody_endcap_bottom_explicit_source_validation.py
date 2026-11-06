"""#2517: explicit Head/Tail ybottom1 may not bypass validated physical Fold."""
from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
import ae_engine.box_body_operator_part_spec as owner


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _snapshot():
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved["model"] = "受電箱"
    saved["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        role: api.build_endcap_xy_fold_profiles(saved, part_key=role)
        for role in ("head", "tail")
    }
    return saved


def _build(saved, *, profiles=True, **override):
    return api.build_box_body_operator_part_spec(
        saved, model_name="受電箱",
        fold_profile=saved["box_body_fold_profile"],
        structure_state=saved["box_body_structure_state"],
        endcap_y_profiles=(
            {role: saved["endcap_fold_profiles"][role]["Y"]
             for role in ("head", "tail")}
            if profiles else None
        ),
        snapshot=saved, **override,
    )


@pytest.mark.parametrize("value", (0, 0.0, 19, 22.5, "20.25", " 17 ", -0.0))
@pytest.mark.parametrize("field", ("head_ybottom1", "tail_ybottom1"))
def test_valid_explicit_lower_fold_override_retains_existing_numeric_semantics(field, value):
    saved = _snapshot()
    before = deepcopy(saved)
    physical = _build(saved, **{field: value})
    assert getattr(physical, field) == pytest.approx(float(value))
    other_field = "tail_ybottom1" if field == "head_ybottom1" else "head_ybottom1"
    expected = api.project_manufacturing_endcap_bottom_fold_inputs(
        saved["endcap_fold_profiles"],
    )
    assert getattr(physical, other_field) == expected[other_field]
    assert saved == before


@pytest.mark.parametrize("bad", (
    True, False, -1, "-2.5", float("-inf"), float("inf"), float("nan"),
    "nan", "inf", "", "bad", [], {}, 10 ** 400,
))
@pytest.mark.parametrize("field", ("head_ybottom1", "tail_ybottom1"))
def test_invalid_explicit_override_cannot_be_cast_to_fabricated_manufacturing_length(field, bad):
    saved = _snapshot()
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="ENDCAP_BOTTOM_FOLD_SOURCE_INVALID"):
        _build(saved, **{field: bad})
    assert saved == before


@pytest.mark.parametrize("invalid", (
    True, False, -1, "-1", "bad", None, float("nan"),
    float("inf"), [], {},
))
def test_legacy_settings_fallback_uses_same_source_validation(invalid):
    saved = _snapshot()
    saved["ybottom1"] = invalid
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="ENDCAP_BOTTOM_FOLD_SOURCE_INVALID"):
        _build(saved, profiles=False)
    assert saved == before


def test_existing_endcap_fold_has_priority_over_other_valid_legacy_fallback():
    saved = _snapshot()
    saved["ybottom1"] = 10.0
    before = deepcopy(saved)
    spec = _build(saved)
    actual = api.project_manufacturing_endcap_bottom_fold_inputs(
        saved["endcap_fold_profiles"],
    )
    assert spec.head_ybottom1 == actual["head_ybottom1"]
    assert spec.tail_ybottom1 == actual["tail_ybottom1"]
    assert saved == before


def test_valid_explicit_head_tail_lower_fold_builds_real_verified_boxbody_dxf(tmp_path):
    saved = _snapshot()
    body = _build(saved, head_ybottom1="20", tail_ybottom1="27")
    assert (body.head_ybottom1, body.tail_ybottom1) == (20.0, 27.0)
    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "physical-bottom-datum-revision", "Set1", "Bay1",
        ),
        confirmed_parts=(("box_body", body),),
    )
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: None,
    )
    assert result.physical_dxf_roundtrip_verified
    assert len(result.output_files) == 3
    for filename in result.output_files.values():
        doc = ezdxf.readfile(filename)
        assert "CUTTING" in {item.dxf.layer for item in doc.modelspace()}


def test_boxbody_public_source_reads_validated_override_and_legacy_fallback():
    source = inspect.getsource(owner.build_box_body_operator_part_spec)
    fallback = inspect.getsource(owner._endcap_lower_outside_value)
    assert "_confirmed_endcap_lower_length(head_ybottom1)" in source
    assert "_confirmed_endcap_lower_length(tail_ybottom1)" in source
    assert "_confirmed_endcap_lower_length(" in fallback
    assert "float(head_ybottom1)" not in source
    assert "float(tail_ybottom1)" not in source
