"""#2517: Body PartSpec and GUI manufacturing must share saved EndCap BEND source."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
import ae_engine.box_body_operator_part_spec as box_owner
import ae_engine.endcap_xy_readback as endcap_owner


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _saved():
    values = family_policy.apply_fresh_family_defaults({}, "受電箱")
    values.update(SOURCE)
    values["model"] = "受電箱"
    values["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    values["box_body_fold_profile"] = api.build_box_body_fold_profile(values)
    values["endcap_fold_profiles"] = {
        key: api.build_endcap_xy_fold_profiles(values, part_key=key)
        for key in ("head", "tail")
    }
    values["endcap_corner_policies"] = {
        key: family_policy.endcap_corner_policy(
            "受電箱", frame_width=values["fw"], thickness=values["t"],
            state=values["box_body_structure_state"],
        )
        for key in ("head", "tail")
    }
    return values


def _bottom(snapshot, role):
    return next(
        seg for seg in snapshot["endcap_fold_profiles"][role]["Y"]
        if seg.get("phase6_key") == "ybottom1"
    )


def _body(snapshot):
    return api.build_box_body_operator_part_spec(
        snapshot, model_name="受電箱",
        fold_profile=snapshot["box_body_fold_profile"],
        structure_state=snapshot["box_body_structure_state"],
        endcap_y_profiles={
            role: snapshot["endcap_fold_profiles"][role]["Y"]
            for role in ("head", "tail")
        },
        snapshot=snapshot,
    )


@pytest.mark.parametrize("ui_add", [0, 2.0, 4, "2", "4.0", -1.0])
def test_boxbody_and_adapter_project_same_authored_bottom_material_outside(ui_add):
    saved = _saved()
    _bottom(saved, "head")["ui_len_add"] = ui_add
    before = deepcopy(saved)
    projected = api.project_manufacturing_endcap_bottom_fold_inputs(
        saved["endcap_fold_profiles"],
    )
    body = _body(saved)
    assert body.head_ybottom1 == projected["head_ybottom1"]
    assert body.tail_ybottom1 == projected["tail_ybottom1"]
    assert saved == before


@pytest.mark.parametrize("invalid", [
    None, True, False, "invalid", "", "nan", "inf",
    float("nan"), float("inf"), float("-inf"), [], {},
])
@pytest.mark.parametrize("role", ("head", "tail"))
def test_invalid_explicit_bend_compensation_fails_both_manufacturing_paths(
    invalid, role,
):
    saved = _saved()
    _bottom(saved, role)["ui_len_add"] = invalid
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="ENDCAP_BOTTOM_FOLD_SOURCE_INVALID"):
        api.project_manufacturing_endcap_bottom_fold_inputs(
            saved["endcap_fold_profiles"],
        )
    with pytest.raises(ValueError, match="ENDCAP_BOTTOM_FOLD_SOURCE_INVALID"):
        _body(saved)
    with pytest.raises(ValueError, match="ENDCAP_BOTTOM_FOLD_SOURCE_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
        )
    assert saved == before


def test_only_absent_legacy_compensation_defaults_to_zero_without_mutating():
    saved = _saved()
    for role in ("head", "tail"):
        _bottom(saved, role).pop("ui_len_add", None)
    original = deepcopy(saved)
    projected = api.project_manufacturing_endcap_bottom_fold_inputs(
        saved["endcap_fold_profiles"],
    )
    body = _body(saved)
    assert body.head_ybottom1 == projected["head_ybottom1"]
    assert body.tail_ybottom1 == projected["tail_ybottom1"]
    assert saved == original


def test_saved_verified_real_dxf_uses_same_endcap_lower_fold_source(tmp_path):
    saved = _saved()
    _bottom(saved, "head")["ui_len_add"] = 2.0
    _bottom(saved, "tail")["ui_len_add"] = 4.0
    frozen = deepcopy(saved)
    part_specs = api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
    )
    body = dict(part_specs)["box_body"]
    projected = api.project_manufacturing_endcap_bottom_fold_inputs(
        saved["endcap_fold_profiles"],
    )
    assert (body.head_ybottom1, body.tail_ybottom1) == (
        projected["head_ybottom1"], projected["tail_ybottom1"],
    )
    bay = ManufacturingResolvedBayInput(
        family="receiving",
        source=ManufacturingSourceIdentity(
            "P1", "endcap-bottom-revision", "set-a", "bay-1",
        ),
        confirmed_parts=part_specs,
    )
    output = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: None,
    )
    assert output.physical_dxf_roundtrip_verified
    assert len(output.output_files) == 5
    for filename in output.output_files.values():
        assert "CUTTING" in {
            entity.dxf.layer for entity in ezdxf.readfile(filename).modelspace()
        }
    assert saved == frozen


def test_both_manufacturing_sources_use_one_engine_endcap_fold_readback():
    box = inspect.getsource(box_owner._endcap_lower_outside_value)
    assert "project_manufacturing_endcap_bottom_fold_inputs(" in box
    assert "fold_material_segment_outside_length(" not in box
    read = inspect.getsource(endcap_owner.project_manufacturing_endcap_bottom_fold_inputs)
    assert '("len", "ui_len_add")' in read
