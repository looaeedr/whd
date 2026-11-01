"""#2517 EndCap Head/Tail operator manufacturing PartSpec belongs to Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import build_endcap_operator_part_spec, manufacturing_api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.box_body_fold_profile import profile_to_fold_segments
from ae_engine.cabinet_types import policy as family_policy
from ae_engine import endcap_operator_part_spec as owner
from gui_modules.application import manufacturing_adapter as gui


def values(family):
    return {
        "model": family, "w": 800, "h": 1800, "d": 400, "t": 2,
        "fw": 29, "zl1": 15, "zr1": 15,
        "yl1": 17, "yr1": 18, "ytop1": 16, "ybottom1": 15,
    }


@pytest.mark.parametrize("family,depth_t", (("金庫型", 3.0), ("受電箱", 2.0)))
def test_real_head_tail_api_builds_immutable_canonical_request(family, depth_t):
    data = values(family)
    saved = deepcopy(data)
    folds = {
        "X": [{"phase6_key": "w", "len": 796, "core": "W"}],
        "Y": [{"phase6_key": "d", "len": 396, "core": "D"}],
    }
    # No operator-wrap change is required for ordinary Head/Tail construction.
    for tail in (False, True):
        got = build_endcap_operator_part_spec(
            data, model_name=family, is_tail=tail,
            holes=({"kind": "circle", "x": 1.0, "y": 2.0},),
            fold_profiles=folds,
        )
        assert isinstance(got, EndCapPartSpec)
        assert got.is_tail is tail
        assert (got.width, got.height, got.depth, got.thickness, got.frame_width) == (
            800.0, 1800.0, 400.0, 2.0, 29.0
        )
        assert (got.fold_left, got.fold_right, got.fold_top, got.fold_bottom) == (
            17.0, 18.0, 16.0, 15.0
        )
        assert got.fold_profile_x == profile_to_fold_segments(folds["X"])
        assert got.fold_profile_y == profile_to_fold_segments(folds["Y"])
        assert got.depth_comp_t == pytest.approx(depth_t)
        assert got.holes[0]["x"] == 1.0
        with pytest.raises(FrozenInstanceError):
            got.width = 999
    assert data == saved


def test_receiving_bottom_wrap_projection_remains_engine_owned(monkeypatch):
    seen = []
    monkeypatch.setattr(
        family_policy, "supports_bottom_wrap_controls",
        lambda source: source == "受電箱",
    )
    monkeypatch.setattr(
        owner, "resolve_endcap_bottom_wrap",
        lambda snapshot, part, *, state: (
            seen.append((snapshot, part, state)) or
            {"reserve_u": 4.5, "reserve_v": 6.5}
        ),
    )
    def reserve(source, state, *, reserve_u, reserve_v):
        assert source == "受電箱"
        return {**state, "reserve": (reserve_u, reserve_v)}
    monkeypatch.setattr(family_policy, "set_bottom_relief_reserves", reserve)
    structure = {"active_type": "three_piece"}
    original = deepcopy(structure)
    joints = ({"id": "joint_1", "relation": "WRAP"},)
    got = manufacturing_api.build_endcap_operator_part_spec(
        values("受電箱"), model_name="受電箱", is_tail=True, holes=(),
        box_body_structure_state=structure,
        assembly_joints=joints,
        endcap_bottom_wrap_state={"mode": "INDEPENDENT"},
        depth_comp_t=2.25,
        resolved_assembly_relief_cuts=(((0, 0), (2, 0), (1, 1)),),
    )
    assert got.depth_comp_t == 2.25
    assert got.box_body_structure_state["reserve"] == (4.5, 6.5)
    assert got.assembly_joints == joints
    assert got.resolved_assembly_relief_cuts == (((0.0, 0.0), (2.0, 0.0), (1.0, 1.0)),)
    assert seen == [({"model": "受電箱", "assembly_joints": joints},
                     "tail", {"mode": "INDEPENDENT"})]
    assert structure == original


def test_saved_source_round_trip_and_missing_dimensions_fail_closed():
    before = values("金庫型")
    saved = json.loads(json.dumps(before))
    assert build_endcap_operator_part_spec(
        saved, model_name="金庫型", is_tail=False, holes=()
    ) == build_endcap_operator_part_spec(
        before, model_name="金庫型", is_tail=False, holes=()
    )
    saved.pop("w")
    with pytest.raises(KeyError, match="w"):
        build_endcap_operator_part_spec(
            saved, model_name="金庫型", is_tail=False, holes=()
        )


def test_gui_adapter_forwards_only_real_operator_state(monkeypatch):
    sentinel = object()
    seen = []
    def engine(data, **kwargs):
        seen.append((data, kwargs))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "build_endcap_operator_part_spec", engine)
    controller = SimpleNamespace(box_body_structure_state=lambda: {"body": 1})
    host = SimpleNamespace(
        workspace_controller=controller,
        assembly_joint_state={"assembly_joints": [{"id": "J"}]},
        endcap_bottom_wrap_state={"mode": "FOLLOW_BODY"},
    )
    data = values("受電箱")
    result = gui._end_cap_part_spec_from_values(
        host, data, model_name="受電箱", is_tail=True, holes=(),
        fold_profiles={"Y": []},
    )
    assert result is sentinel
    assert len(seen) == 1 and seen[0][0] is data
    assert seen[0][1]["box_body_structure_state"] == {"body": 1}
    assert seen[0][1]["assembly_joints"] == [{"id": "J"}]
    assert seen[0][1]["endcap_bottom_wrap_state"] == {"mode": "FOLLOW_BODY"}
    source = inspect.getsource(gui._end_cap_part_spec_from_values)
    assert "manufacturing_api.build_endcap_operator_part_spec(" in source
    for forbidden in (
        "EndCapPartSpec(", "cabinet_family_policy",
        "set_bottom_relief_reserves(", "profile_to_fold_segments(",
        "resolve_endcap_bottom_wrap(",
    ):
        assert forbidden not in source
    engine_source = inspect.getsource(owner.build_endcap_operator_part_spec)
    assert "phase6_" not in engine_source and "tkinter" not in engine_source


def test_legacy_gui_implicit_structure_and_joint_readback_uses_same_engine():
    class Controller:
        def box_body_structure_state(self):
            return {"active_type": "integral"}
    host = SimpleNamespace(
        workspace_controller=Controller(),
        assembly_joint_state={"assembly_joints": []},
    )
    data = values("金庫型")
    got = gui._end_cap_part_spec_from_values(
        host, data, model_name="金庫型", is_tail=False, holes=(),
    )
    expected = build_endcap_operator_part_spec(
        data, model_name="金庫型", is_tail=False, holes=(),
        box_body_structure_state={"active_type": "integral"},
        assembly_joints=(),
    )
    assert got == expected
