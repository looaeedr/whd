"""#2517 EndCap Head/Tail operator manufacturing PartSpec belongs to Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import ast
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
    assert seen[0][1]["assembly_joint_state"] == {"assembly_joints": [{"id": "J"}]}
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
    # Fold Profile's persisted "phase6_key" is a data field, not a reverse
    # Python dependency. Verify actual imports instead of matching strings.
    imports = []
    for node in ast.walk(ast.parse(engine_source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(
        name == "tkinter" or name.startswith((
            "tkinter.", "phase6_", "gui_modules", "fold_designer_bridge",
        ))
        for name in imports
    )


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


def test_legacy_saved_joint_schema_version_survives_gui_to_engine(monkeypatch):
    snapshots = []
    monkeypatch.setattr(
        family_policy, "supports_bottom_wrap_controls", lambda _: True,
    )
    monkeypatch.setattr(
        owner, "resolve_endcap_bottom_wrap",
        lambda snapshot, key, *, state: (
            snapshots.append(dict(snapshot)) or
            {"reserve_u": 2.0, "reserve_v": 1.0}
        ),
    )
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(box_body_structure_state=lambda: {}),
        assembly_joint_state={
            "assembly_joint_schema_version": 3,
            "assembly_joints": ({"id": "HEAD_BOTTOM", "relation": "WRAP"},),
        },
    )
    got = gui._end_cap_part_spec_from_values(
        host, values("受電箱"), model_name="受電箱", is_tail=False, holes=(),
    )
    assert isinstance(got, EndCapPartSpec)
    assert snapshots[0]["assembly_joint_schema_version"] == 3
    assert snapshots[0]["assembly_joints"] == got.assembly_joints


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,invalid", (
    ("w", True), ("h", float("nan")), ("d", 0),
    ("t", False), ("fw", float("inf")),
    ("yl1", True), ("yr1", float("nan")),
    ("ytop1", float("inf")), ("ybottom1", False),
    ("zl1", "1e309"), ("zr1", True),
))
def test_gui_and_engine_reject_untrusted_head_tail_source_before_partspec(
    family, field, invalid, tmp_path,
):
    data = values(family)
    data[field] = invalid
    before = repr(data)
    with pytest.raises((TypeError, ValueError)):
        manufacturing_api.build_endcap_operator_part_spec(
            data, model_name=family, is_tail=False, holes=(),
        )
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            box_body_structure_state=lambda: {},
        ),
        assembly_joint_state={},
    )
    with pytest.raises((TypeError, ValueError)):
        gui._end_cap_part_spec_from_values(
            host, data, model_name=family, is_tail=False, holes=(),
        )
    assert repr(data) == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_head_tail_boolean_identity_and_valid_numeric_source_are_engine_owned(
    family,
):
    data = values(family)
    data.update(w="800.25", yl1="-17.5", zr1="0")
    before = deepcopy(data)
    head = manufacturing_api.build_endcap_operator_part_spec(
        data, model_name=family, is_tail="false", holes=(),
    )
    tail = manufacturing_api.build_endcap_operator_part_spec(
        data, model_name=family, is_tail="true", holes=(),
    )
    assert head.is_tail is False and tail.is_tail is True
    assert head.width == tail.width == 800.25
    assert head.fold_left == -17.5 and tail.box_fold_right == 0.0
    assert data == before
    with pytest.raises(ValueError):
        manufacturing_api.build_endcap_operator_part_spec(
            data, model_name=family, is_tail="not-a-boolean", holes=(),
        )


@pytest.mark.parametrize("option,invalid", (
    ("depth_comp_t", True),
    ("depth_comp_t", float("nan")),
    ("box_body_formed_fw_left", False),
    ("box_body_formed_fw_right", float("inf")),
))
def test_head_tail_optional_manufacturing_numbers_must_be_finite(
    option, invalid,
):
    with pytest.raises((TypeError, ValueError)):
        manufacturing_api.build_endcap_operator_part_spec(
            values("金庫型"), model_name="金庫型",
            is_tail=False, holes=(), **{option: invalid},
        )


@pytest.mark.parametrize("raw,expected_tail", [
    (False, False), (True, True), ("false", False), ("true", True),
    ("OFF", False), ("ON", True), (0, False), (1, True),
])
def test_main_gui_endcap_raw_role_selects_matching_engine_physical_sources(
    monkeypatch, raw, expected_tail,
):
    """Prior bool("false") chose Tail holes/profiles before Engine normalized it."""
    events = []
    head_hole, tail_hole = {"source": "head"}, {"source": "tail"}
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            profile_for=lambda role: (events.append(("profile", role)) or {}),
            box_body_profile=lambda: (),
            box_body_structure_state=lambda: {},
        ),
        _effective_endcap_fw=lambda role, fw: (
            events.append(("fw", role)) or fw
        ),
        _current_box_assembly_type=lambda: "INTEGRAL",
        _resolved_committed_assembly_relief_cuts=lambda *args: (),
        _manual_corner_policy=lambda *args: None,
        _end_cap_depth_comp_t_for_family=lambda *_: 3.0,
        _baseline_source_model=lambda: "金庫型",
        head_holes=(head_hole,),
        tail_holes=(tail_hole,),
        _end_cap_part_spec_from_values=lambda val, **kwargs:
            manufacturing_api.build_endcap_operator_part_spec(
                val, model_name=kwargs["model_name"],
                is_tail=kwargs["is_tail"], holes=kwargs["holes"],
            ),
    )
    monkeypatch.setattr(
        gui, "_endcap_profiles_for_assembly",
        lambda source, profiles, assembly_type, role: profiles,
    )
    spec = gui._end_cap_part_spec(host, values("金庫型"), is_tail=raw)
    expected_role = "tail" if expected_tail else "head"
    assert spec.is_tail is expected_tail
    assert spec.holes == ((tail_hole,) if expected_tail else (head_hole,))
    assert events == [("profile", expected_role), ("fw", expected_role)]


@pytest.mark.parametrize("bad", [None, "bad", "2", 2, -1, float("nan"), [], {}])
def test_main_gui_invalid_endcap_role_fails_before_any_side_selection(bad):
    """Invalid physical role cannot read Head/Tail cached Fold or holes."""
    side_reads = []
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            profile_for=lambda role: side_reads.append(role),
        ),
    )
    with pytest.raises(ValueError, match="布林值"):
        gui._end_cap_part_spec(host, values("金庫型"), is_tail=bad)
    assert side_reads == []


@pytest.mark.parametrize("raw,tail", [("false", False), ("true", True)])
def test_main_gui_endcap_preview_uses_canonical_engine_partspec_role(raw, tail):
    from gui_modules.application.render_snapshots import end_cap_render_snapshot

    physical = []
    def part_spec(val, *, is_tail):
        spec = manufacturing_api.build_endcap_operator_part_spec(
            val, model_name="金庫型", is_tail=is_tail, holes=(),
        )
        physical.append(spec)
        return spec

    host = SimpleNamespace(
        _baseline_source_model=lambda: "金庫型",
        _end_cap_part_spec=part_spec,
        _manufacturing_context=lambda *, draw_stock: object(),
        _authoritative_render_data=lambda spec, context: SimpleNamespace(
            material=SimpleNamespace(bounds=(0, 0, 100, 200)),
        ),
        baseline_var=SimpleNamespace(get=lambda: "金庫型"),
    )
    projected = end_cap_render_snapshot(host, values("金庫型"), is_tail=raw)
    assert physical[0].is_tail is tail
    assert projected["is_tail"] is physical[0].is_tail
    assert projected["bounds"] == (0.0, 0.0, 100.0, 200.0)
    assert "bool(is_tail)" not in inspect.getsource(end_cap_render_snapshot)
