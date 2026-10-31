"""#2517: full Head/Tail X/Y Fold and four-mode FW belong to the Engine."""
from __future__ import annotations
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_geometry import CornerTypeId
from phase6_endcap_semantics import (
    normalize_endcap_fw_state as gui_fw_state,
    resolve_endcap_fw as gui_fw,
    resolve_box_assembly_type as gui_assembly,
    selection_from_raw as gui_corner,
)
from phase6_fold_profiles import build_endcap_xy_profiles as gui_profile


@pytest.mark.parametrize("family,depth_comp", [("受電箱", 2.0), ("金庫型", 3.0)])
@pytest.mark.parametrize("part", ("head", "tail"))
@pytest.mark.parametrize("mode", ("FOLLOW_BODY", "FOLLOW_HEAD", "FOLLOW_TAIL", "INDEPENDENT"))
def test_engine_full_endcap_x_y_fold_matches_phase6_and_family_fw(family, depth_comp, part, mode):
    snapshot = {
        "model": family, "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        "fw": 29.0, "yl1": 15.0, "yr1": 15.0,
        "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT_OVERLAY",
        "endcap_fw": {
            "mode": mode,
            "head": {"follow_box": False, "value": 37.0},
            "tail": {"follow_box": False, "value": 41.0},
        },
    }
    state = manufacturing_api.normalize_endcap_fw_state(snapshot)
    assert state == gui_fw_state(snapshot)
    fw = manufacturing_api.resolve_endcap_fw(snapshot, part)
    assert fw == gui_fw(snapshot, part)
    profile = manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key=part)
    assert profile == gui_profile(snapshot, part_key=part)
    assert len(profile["X"]) == 3 and len(profile["Y"]) == 4
    depth = next(row for row in profile["Y"] if row.get("phase6_key") == "endcap_d_core")
    assert depth["len"] == 350.0 - depth_comp * 2.0
    if mode == "FOLLOW_BODY":
        assert fw == 29.0
    elif mode == "FOLLOW_HEAD":
        assert fw == 37.0
    elif mode == "FOLLOW_TAIL":
        assert fw == 41.0
    else:
        assert fw == (37.0 if part == "head" else 41.0)
    expected_material_fw = fw - 4.0 if family == "受電箱" else fw
    assert next(row for row in profile["Y"] if row.get("phase6_key") == "fw")["len"] == expected_material_fw


@pytest.mark.parametrize("part", ["head", "tail"])
def test_overlay_has_genuine_one_segment_flat_x_and_native_tail_y(part):
    source = {
        "model": "金庫型", "w": 800.0, "d": 350.0, "t": 2.0,
        "fw": 25.0, "yl1": 15, "yr1": 15,
        "ytop1": 16, "ybottom1": 15, "assembly_type": "OVERLAY",
    }
    rows = manufacturing_api.build_endcap_xy_fold_profiles(source, part_key=part)
    assert [r["phase6_key"] for r in rows["X"]] == ["endcap_w_flat"]
    assert "angle" not in rows["X"][0]
    assert rows == gui_profile(source, part_key=part)
    assert [r["phase6_key"] for r in rows["Y"]] == (
        ["ybottom1", "endcap_d_core", "fw", "ytop1"] if part == "tail"
        else ["ytop1", "fw", "endcap_d_core", "ybottom1"]
    )


def test_legacy_corner_state_fallback_is_resolved_only_by_engine():
    source = {"corner_state": {
        "head": {"top_left": {"type_id": "OVERLAY"}, "top_right": {"type_id": "OVERLAY"}}
    }}
    assert manufacturing_api.resolve_endcap_assembly_type(source) is CornerTypeId.OVERLAY
    assert gui_assembly(source) is CornerTypeId.OVERLAY
    assert gui_corner({"type_id": "OVERLAY"}) == manufacturing_api.endcap_corner_selection_from_raw({"type_id": "OVERLAY"})


def test_phase6_has_only_public_endcap_fold_and_fw_callers():
    for function, public in (
        (gui_profile, "build_endcap_xy_fold_profiles"),
        (gui_fw, "resolve_endcap_fw"),
        (gui_fw_state, "normalize_endcap_fw_state"),
        (gui_assembly, "resolve_endcap_assembly_type"),
        (gui_corner, "endcap_corner_selection_from_raw"),
    ):
        source = inspect.getsource(function)
        assert "manufacturing_api." + public + "(" in source
    assert "from phase6_" not in inspect.getsource(manufacturing_api.build_endcap_xy_fold_profiles)
