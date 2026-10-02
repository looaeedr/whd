# -*- coding: utf-8 -*-
from copy import deepcopy
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from ae_engine.corner_type_ui import (
    apply_box_assembly_type,
    assembly_type_from_corner_state,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    policy_from_corner_state,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CrossCornerMode,
    CornerDirection,
    box_body_height_from_corner_policies,
)


def _seg(length, angle=-90, *, core=None, key=None):
    row = {"len": float(length)}
    if angle is not None:
        row["angle"] = float(angle)
    if core:
        row["core"] = core
    if key:
        row["phase6_key"] = key
    return row


def five_segment_box():
    return [
        _seg(25, -90, key="fw_left"),
        _seg(246, -90, core="D", key="d_left"),
        _seg(396, -90, core="W", key="w"),
        _seg(246, -90, core="D", key="d_right"),
        _seg(25, None, key="fw_right"),
    ]


def base_snapshot():
    return {
        "w": 400, "h": 600, "d": 250, "t": 2, "fw": 25,
        "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
    }


def test_linked_five_segment_endcap_keeps_fw_25_as_its_own_dimension():
    linked = bridge.build_linked_endcap_xy_profiles(base_snapshot(), five_segment_box())

    head_y = linked["head"]["Y"]
    tail_y = linked["tail"]["Y"]
    head_fw = [row for row in head_y if row.get("phase6_key") == "fw"]
    tail_fw = [row for row in tail_y if row.get("phase6_key") == "fw"]

    assert len(head_fw) == len(tail_fw) == 1
    assert head_fw[0]["len"] == pytest.approx(25.0)
    assert tail_fw[0]["len"] == pytest.approx(25.0)
    assert not any(row.get("phase6_key") == "fw" and row["len"] == 41 for row in head_y + tail_y)


def test_five_segment_box_removes_endcap_outer_fold_and_keeps_every_remaining_bend_at_ninety_degrees():
    linked = bridge.build_linked_endcap_xy_profiles(base_snapshot(), five_segment_box())
    assert [row.get("phase6_key") for row in linked["head"]["Y"]] == ["fw", "endcap_d_core", "ybottom1"]
    assert [row.get("phase6_key") for row in linked["tail"]["Y"]] == ["ybottom1", "endcap_d_core", "fw"]

    for part in ("head", "tail"):
        profile = linked[part]["Y"]
        assert all(abs(float(row["angle"])) == pytest.approx(90.0) for row in profile[:-1])
        assert "angle" not in profile[-1]
        _boundaries, folded = bridge._phase6_profile_geometry(profile)
        vectors = [
            (folded[i + 1][0] - folded[i][0], folded[i + 1][1] - folded[i][1])
            for i in range(len(profile))
        ]
        for a, b in zip(vectors, vectors[1:]):
            dot = a[0] * b[0] + a[1] * b[1]
            assert dot == pytest.approx(0.0, abs=1e-7)


def test_read_endcap_profile_allows_linked_outer_fold_to_be_absent_and_reports_zero_legacy_top_fold():
    linked = bridge.build_linked_endcap_xy_profiles(base_snapshot(), five_segment_box())
    values = bridge.read_endcap_xy_profiles(linked["head"], base_snapshot())
    assert values["fw"] == pytest.approx(25.0)
    assert values["d"] == pytest.approx(250.0)
    assert values["ytop1"] == pytest.approx(0.0)
    assert values["ybottom1"] == pytest.approx(15.0)


def test_endcap_fw_defaults_to_box_but_can_be_unlinked_without_backwriting_global_fw():
    snapshot = base_snapshot()

    state = bridge.normalize_endcap_fw_state(snapshot)
    assert bridge.resolve_endcap_fw(snapshot, "head", state=state) == pytest.approx(25.0)
    assert bridge.resolve_endcap_fw(snapshot, "tail", state=state) == pytest.approx(25.0)

    bridge.set_endcap_fw_follow(state, "head", False, box_fw=25.0)
    bridge.set_endcap_fw_override(state, "head", 31.0)
    snapshot["fw"] = 30.0

    assert bridge.resolve_endcap_fw(snapshot, "head", state=state) == pytest.approx(31.0)
    assert bridge.resolve_endcap_fw(snapshot, "tail", state=state) == pytest.approx(30.0)
    assert snapshot["fw"] == pytest.approx(30.0)


def test_linked_endcap_profiles_use_each_parts_effective_fw_not_one_absolute_global_value():
    snapshot = base_snapshot()
    state = bridge.normalize_endcap_fw_state(snapshot)
    bridge.set_endcap_fw_follow(state, "head", False, box_fw=25.0)
    bridge.set_endcap_fw_override(state, "head", 31.0)
    snapshot["endcap_fw"] = state

    linked = bridge.build_linked_endcap_xy_profiles(snapshot, five_segment_box())
    head_fw = next(row for row in linked["head"]["Y"] if row.get("phase6_key") == "fw")
    tail_fw = next(row for row in linked["tail"]["Y"] if row.get("phase6_key") == "fw")

    assert head_fw["len"] == pytest.approx(31.0)
    assert tail_fw["len"] == pytest.approx(25.0)


def test_fw_rows_are_structural_ui_fields_and_cannot_be_deleted_from_box_chain():
    assert bridge.can_remove_segment({"len": 12, "phase6_key": "extra"}) is True
    assert bridge.can_remove_segment({"len": 25, "phase6_key": "fw_left"}) is False
    assert bridge.can_remove_segment({"len": 25, "phase6_key": "fw_right"}) is False


@pytest.mark.parametrize(
    ("assembly_type", "expected_height", "bottom_direction", "bottom_amount_t"),
    [
        (CornerTypeId.INSERT, 600.0, CornerDirection.BOTH, 0.5),
        (CornerTypeId.OVERLAY, 596.0, CornerDirection.WIDTH, 1.5),
        (CornerTypeId.INSERT_OVERLAY, 596.0, CornerDirection.BOTH, 0.5),
    ],
)
def test_one_box_assembly_type_drives_both_endcaps_and_box_finished_height(
    assembly_type, expected_height, bottom_direction, bottom_amount_t
):
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])

    apply_box_assembly_type(
        state, pairs, assembly_type, reset_bottom_defaults=True
    )

    assert assembly_type_from_corner_state(state) is assembly_type
    for part in ("head", "tail"):
        assert state[part]["top_left"].type_id is assembly_type
        assert state[part]["top_right"].type_id is assembly_type
        assert state[part]["bottom_left"].type_id is CornerTypeId.CROSS
        assert state[part]["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT
        assert state[part]["bottom_left"].direction is bottom_direction
        assert state[part]["bottom_left"].amount_t == pytest.approx(bottom_amount_t)
        assert state[part]["bottom_right"].cross_mode is CrossCornerMode.EXTRA_CUT

    head = policy_from_corner_state(state["head"], fw=25)
    tail = policy_from_corner_state(state["tail"], fw=25)
    assert box_body_height_from_corner_policies(
        600, 2, head_corner_policy=head, tail_corner_policy=tail
    ) == pytest.approx(expected_height)


def test_changing_box_assembly_type_preserves_existing_left_right_parameters_when_type_matches():
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT_OVERLAY)
    pairs["head"]["top"] = False
    state["head"]["top_left"] = bridge.CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY, amount_t=1.25,
        secondary_retain_t=0.75, secondary_depth_t=2.5,
    )
    state["head"]["top_right"] = bridge.CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY, amount_t=1.75,
        secondary_retain_t=0.25, secondary_depth_t=3.0,
    )

    before = deepcopy(state["head"])
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT_OVERLAY)

    assert state["head"]["top_left"] == before["top_left"]
    assert state["head"]["top_right"] == before["top_right"]


def test_operator_box_body_finished_dimensions_are_single_part_folded_outside_dimensions():
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT_OVERLAY)
    raw = {
        part: {corner: bridge._phase6_selection_to_raw(selection) for corner, selection in corners.items()}
        for part, corners in state.items()
    }
    holder = SimpleNamespace(
        active_part_key="box_body",
        _phase6_input_snapshot={"w": 400, "h": 600, "d": 250, "t": 2, "fw": 25},
        _settings_values={"w": 400, "h": 600, "d": 250, "t": 2, "fw": 25},
        _phase6_corner_state=raw,
    )

    assert bridge._phase6_operator_finished_dimensions(holder) == pytest.approx((400, 596, 250))


def test_legacy_project_migrates_box_assembly_type_from_endcap_top_corner_state():
    snapshot = {
        "corner_state": {
            "head": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 1.0},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.5},
            },
            "tail": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 2.0},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.0},
            },
        }
    }
    assert bridge.resolve_box_assembly_type(snapshot) is CornerTypeId.OVERLAY


def test_explicit_assembly_intent_mirror_wins_over_legacy_top_corner_projection():
    snapshot = {
        "assembly_type": "INSERT",
        "corner_state": {
            "head": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 1.25},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.75},
            },
            "tail": {
                "top_left": {"type_id": "OVERLAY", "amount_t": 1.5},
                "top_right": {"type_id": "OVERLAY", "amount_t": 1.0},
            },
        },
    }
    assert bridge.resolve_box_assembly_type(snapshot) is CornerTypeId.INSERT


def test_explicit_box_assembly_type_remains_legacy_intent_mirror_when_top_corners_are_missing():
    snapshot = {"assembly_type": "INSERT", "corner_state": {}}
    assert bridge.resolve_box_assembly_type(snapshot) is CornerTypeId.INSERT


def test_apply_box_assembly_type_to_raw_state_keeps_per_side_parameters_when_type_unchanged():
    raw = {
        "head": {
            "top_left": {"type_id": "INSERT_OVERLAY", "amount_t": 1.25, "secondary_retain_t": .75, "secondary_depth_t": 2.5},
            "top_right": {"type_id": "INSERT_OVERLAY", "amount_t": 1.75, "secondary_retain_t": .25, "secondary_depth_t": 3.0},
        },
        "tail": {},
    }
    pairs = {"head": {"top": False, "bottom": True}, "tail": {"top": True, "bottom": True}}
    bridge.apply_box_assembly_type_to_raw_state(raw, pairs, CornerTypeId.INSERT_OVERLAY)
    assert raw["head"]["top_left"]["amount_t"] == pytest.approx(1.25)
    assert raw["head"]["top_right"]["amount_t"] == pytest.approx(1.75)
    assert raw["tail"]["top_left"]["type_id"] == "INSERT_OVERLAY"
    assert raw["tail"]["bottom_left"]["cross_mode"] == "extra_cut"


def test_part_can_be_selected_then_deleted_without_activation():
    calls = []
    class Button:
        def configure(self, **kw):
            calls.append(kw)
        def state(self, *args, **kwargs):
            return None
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        part_var=SimpleNamespace(set=lambda value: calls.append(value)),
        part_buttons={"box_body": Button(), "head": Button(), "tail": Button()},
        edit_selected_part_button=Button(),
        delete_selected_part_button=Button(),
        _refresh_part_buttons=lambda: None,
        _refresh_add_part_menu=lambda: None,
        show_home=lambda: workspace.show_home(),
    )
    holder._refresh_part_button_states = lambda: bridge._fix11_refresh_part_button_states(holder)
    holder.remove_part = lambda key: bridge._fix11_remove_part(holder, key)

    assert bridge._fix11_select_part(holder, "tail") is True
    assert workspace.selected_part == "tail"
    assert workspace.active_part == "box_body"  # selection did not enter Tail page
    assert bridge._fix11_remove_selected_part(holder) is True
    assert "tail" not in workspace.available_parts
    assert workspace.active_part == "box_body"


def test_main_2d_box_finished_height_uses_same_corner_occupancy_before_phase6_commit(monkeypatch):
    import gui

    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT)

    holder = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: "自訂"),
        manual_corner_state=state,
    )
    holder._manual_corner_policy = lambda part_key, fw: gui.BoxCalculatorGUI._manual_corner_policy(holder, part_key, fw)
    holder._box_body_corner_policies = lambda fw: gui.BoxCalculatorGUI._box_body_corner_policies(holder, fw)
    height = gui.BoxCalculatorGUI._box_body_finished_height(holder, {"h": 600.0, "t": 2.0, "fw": 25.0})
    assert height == pytest.approx(600.0)

    apply_box_assembly_type(state, pairs, CornerTypeId.OVERLAY)
    height = gui.BoxCalculatorGUI._box_body_finished_height(holder, {"h": 600.0, "t": 2.0, "fw": 25.0})
    assert height == pytest.approx(596.0)


def test_authoritative_render_cache_reuses_one_manufacturing_result(monkeypatch):
    import gui
    from ae_engine import manufacturing_api

    calls = []
    sentinel = object()
    monkeypatch.setattr(
        manufacturing_api,
        "build_part_render_data",
        lambda spec, ctx: calls.append((spec, ctx)) or sentinel,
    )
    holder = SimpleNamespace(_authoritative_part_render_cache={})
    spec = ("same-spec", 1)
    context = ("same-context", 2)

    first = gui.BoxCalculatorGUI._authoritative_render_data(holder, spec, context)
    second = gui.BoxCalculatorGUI._authoritative_render_data(holder, spec, context)

    assert first is sentinel
    assert second is sentinel
    assert len(calls) == 1


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_main_2d_fw_operator_flow_pairs_then_splits_and_box_reclaims():
    import gui
    holder = SimpleNamespace(
        fw_z_var=DummyVar("25"), fw_head_var=DummyVar("25"), fw_tail_var=DummyVar("25"),
        fw_head_follow_var=DummyVar(True), fw_tail_follow_var=DummyVar(True),
        endcap_fw_state=bridge.normalize_endcap_fw_state({"fw": 25.0}),
        _authoritative_part_render_cache={"old": object()},
        _fold_designer_number_text=lambda value: str(int(value)) if float(value).is_integer() else str(value),
        _request_phase6_update=lambda *args, **kwargs: None,
        update_calculations=lambda: None,
    )
    holder._effective_endcap_fw = lambda part: gui.BoxCalculatorGUI._effective_endcap_fw(holder, part)
    holder._sync_endcap_fw_controls = lambda: gui.BoxCalculatorGUI._sync_endcap_fw_controls(holder)

    holder.fw_head_var.set("31")
    gui.BoxCalculatorGUI.on_fw_selected(holder, "head")
    assert holder.fw_head_var.get() == "31"
    assert holder.fw_tail_var.get() == "31"
    assert holder.endcap_fw_state["mode"] == "FOLLOW_HEAD"

    holder.fw_tail_var.set("29")
    gui.BoxCalculatorGUI.on_fw_selected(holder, "tail")
    assert holder.fw_head_var.get() == "31"
    assert holder.fw_tail_var.get() == "29"
    assert holder.endcap_fw_state["mode"] == "INDEPENDENT"

    holder.fw_z_var.set("30")
    gui.BoxCalculatorGUI.on_fw_selected(holder, "z")
    assert holder.fw_head_var.get() == "30"
    assert holder.fw_tail_var.get() == "30"
    assert holder.fw_z_var.get() == "30"
    assert holder.endcap_fw_state["mode"] == "FOLLOW_BODY"


def test_phase6_workspace_persists_endcap_fw_link_state():
    from phase6_designer_workspace import Phase6DesignerWorkspace
    owner = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"], "active_part": "head", "part_profiles": {}
    })
    holder = SimpleNamespace(
        designer_workspace=owner,
        _phase6_assembly_type=CornerTypeId.INSERT_OVERLAY,
        _phase6_endcap_fw_state={
            "head": {"follow_box": False, "value": 31.0},
            "tail": {"follow_box": True, "value": 25.0},
        },
        _phase6_input_snapshot={"fw": 25},
        state=SimpleNamespace(profiles_vault={"箱身": five_segment_box()}),
    )
    workspace = bridge._phase6_collect_workspace_state(holder)
    assert workspace["endcap_fw"]["head"] == {"follow_box": False, "value": 31.0}
    assert workspace["endcap_fw"]["tail"]["follow_box"] is True


def test_refresh_linked_endcaps_uses_each_parts_fw_state_instead_of_global_fw_only(monkeypatch):
    class State:
        def __init__(self):
            self.profiles_vault = {"箱身": five_segment_box()}

    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail", "door"],
        "active_part": "door",
        "part_profiles": {"head": {}, "tail": {}, "door": {}},
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot=base_snapshot(),
        _settings_values={"w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 30.0},
        _phase6_endcap_fw_state={
            "head": {"follow_box": False, "value": 31.0},
            "tail": {"follow_box": True, "value": 25.0},
        },
        _phase6_box_whd={"w": 400, "h": 600, "d": 250},
        state=State(),
    )
    monkeypatch.setattr(bridge, "_phase6_recalculate_part_dimensions", lambda self: None)

    bridge._phase6_refresh_linked_part_profiles(holder, {"fw"})

    head_fw = next(row for row in workspace.profiles_for("head")["Y"] if row.get("phase6_key") == "fw")
    tail_fw = next(row for row in workspace.profiles_for("tail")["Y"] if row.get("phase6_key") == "fw")
    assert head_fw["len"] == pytest.approx(31.0)
    assert tail_fw["len"] == pytest.approx(30.0)
    assert holder._phase6_input_snapshot["fw"] == pytest.approx(30.0)


def test_saving_endcap_editor_routes_fw_to_override_without_backwriting_box_fw(monkeypatch):
    linked_snapshot = base_snapshot()
    linked_snapshot["fw"] = 30.0
    fw_state = {
        "head": {"follow_box": False, "value": 31.0},
        "tail": {"follow_box": True, "value": 30.0},
    }
    linked_snapshot["endcap_fw"] = deepcopy(fw_state)
    head = bridge.build_linked_endcap_xy_profiles(linked_snapshot, five_segment_box())["head"]
    # Simulate an operator changing only the detached Head FW in its own editor.
    for row in head["Y"]:
        if row.get("phase6_key") == "fw":
            row["len"] = 32.0

    captured = []
    monkeypatch.setattr(bridge, "_phase6_store_editor_values", lambda self, values, notify=True: captured.append(dict(values)))
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda self: None)
    monkeypatch.setattr(bridge, "build_endcap_profile", lambda snapshot: [])
    monkeypatch.setattr(bridge.original, "get_int", lambda value: int(float(value)))

    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {"head": deepcopy(head)},
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        bend_ui=SimpleNamespace(save=lambda: None),
        v_w=DummyVar("400"), v_h=DummyVar("600"), v_d=DummyVar("250"),
        state=SimpleNamespace(profiles=head, profiles_vault={}),
        _phase6_input_snapshot=linked_snapshot,
        _phase6_endcap_fw_state=deepcopy(fw_state),
    )

    bridge._fix11_save_current_part(holder, notify=False)

    assert holder._phase6_input_snapshot["fw"] == pytest.approx(30.0)
    assert holder._phase6_endcap_fw_state["head"] == {"follow_box": False, "value": 32.0}
    assert all("fw" not in values for values in captured)


def test_phase6_fw_detach_and_override_refreshes_active_endcap_without_changing_box_fw(monkeypatch):
    linked_snapshot = base_snapshot()
    linked_snapshot["fw"] = 30.0
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail"], "active_part": "head"
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot=linked_snapshot,
        _settings_values={"fw": 30.0},
        _phase6_endcap_fw_state={
            "head": {"follow_box": True, "value": 30.0},
            "tail": {"follow_box": True, "value": 30.0},
        },
        state=SimpleNamespace(profiles={"X": [], "Y": []}),
        bend_ui=SimpleNamespace(rebuild_tabs=lambda: None),
        do_update=lambda: None,
    )
    linked = {
        "head": {"X": [_seg(10, key="x")], "Y": [_seg(31, key="fw")]},
        "tail": {"X": [], "Y": [_seg(30, key="fw")]},
    }
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda self: linked)

    bridge._phase6_set_endcap_fw_follow(holder, "head", False)
    bridge._phase6_set_endcap_fw_override(holder, "head", 31.0)

    assert holder._phase6_input_snapshot["fw"] == pytest.approx(30.0)
    assert holder._phase6_endcap_fw_state["head"] == {"follow_box": False, "value": 31.0}
    assert holder._phase6_input_snapshot["endcap_fw"]["head"]["value"] == pytest.approx(31.0)
    assert holder.state.profiles["Y"][0]["len"] == pytest.approx(31.0)
    assert workspace.dirty is True


def test_main_2d_endcap_fw_controls_are_always_free_numeric_inputs():
    import gui
    class Combo:
        def __init__(self): self.last_state = None
        def configure(self, **kw): self.last_state = kw.get("state", self.last_state)
    head_combo, tail_combo = Combo(), Combo()
    holder = SimpleNamespace(
        fw_z_var=DummyVar("30"), fw_head_var=DummyVar("31"), fw_tail_var=DummyVar("30"),
        fw_head_follow_var=DummyVar(False), fw_tail_follow_var=DummyVar(True),
        endcap_fw_state={
            "head": {"follow_box": False, "value": 31.0},
            "tail": {"follow_box": True, "value": 30.0},
        },
        cb_fw_head=head_combo, cb_fw_tail=tail_combo,
        _fold_designer_number_text=lambda value: str(int(value)) if float(value).is_integer() else str(value),
    )
    holder._effective_endcap_fw = lambda part: gui.BoxCalculatorGUI._effective_endcap_fw(holder, part)

    gui.BoxCalculatorGUI._sync_endcap_fw_controls(holder)

    assert head_combo.last_state == "normal"
    assert tail_combo.last_state == "normal"


def test_operator_finished_dimensions_measure_folded_final_mesh_envelope_not_snapshot_formula():
    from shapely.geometry import box

    x_profile = five_segment_box()
    y_profile = [{"len": 596.0}]
    triangles = bridge._phase6_folded_mesh_from_polygon(
        box(0.0, 0.0, 938.0, 596.0), x_profile, y_profile
    )
    holder = SimpleNamespace(
        active_part_key="box_body",
        _phase6_input_snapshot={"w": 999, "h": 888, "d": 777, "t": 2, "fw": 25},
        _settings_values={"w": 999, "h": 888, "d": 777, "t": 2, "fw": 25},
        _phase6_corner_state={},
    )

    assert bridge._phase6_operator_finished_dimensions(
        holder, triangles=triangles
    ) == pytest.approx((400.0, 596.0, 250.0))


def test_explicit_overlay_selection_defaults_endcap_bottom_to_width_extra_cut_1_5t():
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])

    # Simulate a real assembly transition: the previous state already carries
    # the normal existing EndCap bottom default, then the operator explicitly
    # chooses OVERLAY.
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT_OVERLAY)
    apply_box_assembly_type(
        state, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True
    )

    for part in ("head", "tail"):
        for key in ("bottom_left", "bottom_right"):
            bottom = state[part][key]
            assert bottom.type_id is CornerTypeId.CROSS
            assert bottom.cross_mode is CrossCornerMode.EXTRA_CUT
            assert bottom.direction is CornerDirection.WIDTH
            assert bottom.amount_t == pytest.approx(1.5)


def test_overlay_bottom_manual_edit_survives_ordinary_refresh_without_reapplying_default():
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(
        state, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True
    )

    manual = bridge.CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.HEIGHT,
        amount_t=2.25,
    )
    state["head"]["bottom_left"] = manual
    state["head"]["bottom_right"] = manual

    # Loading/rerendering/synchronizing the same assembly type must not act like
    # the operator selected OVERLAY again.
    apply_box_assembly_type(state, pairs, CornerTypeId.OVERLAY)

    assert state["head"]["bottom_left"] == manual
    assert state["head"]["bottom_right"] == manual


def test_overlay_bottom_manual_standard_survives_ordinary_refresh_until_explicit_reselect():
    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(
        state, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True
    )

    manual_standard = bridge.CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.STANDARD,
    )
    state["head"]["bottom_left"] = manual_standard
    state["head"]["bottom_right"] = manual_standard

    apply_box_assembly_type(state, pairs, CornerTypeId.OVERLAY)
    assert state["head"]["bottom_left"] == manual_standard
    assert state["head"]["bottom_right"] == manual_standard

    apply_box_assembly_type(
        state, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True
    )
    assert state["head"]["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT
    assert state["head"]["bottom_left"].direction is CornerDirection.WIDTH
    assert state["head"]["bottom_left"].amount_t == pytest.approx(1.5)


def test_endcap_fw_operator_state_machine_pair_then_split_then_box_reclaims():
    import phase6_endcap_semantics as semantics

    state = semantics.normalize_endcap_fw_state({"fw": 25.0})
    assert state["mode"] == "FOLLOW_BODY"

    semantics.commit_endcap_fw(state, "head", 31.0, box_fw=25.0)
    assert state["mode"] == "FOLLOW_HEAD"
    assert semantics.resolve_endcap_fw({"fw": 25.0}, "head", state=state) == pytest.approx(31.0)
    assert semantics.resolve_endcap_fw({"fw": 25.0}, "tail", state=state) == pytest.approx(31.0)

    # Editing the same leader keeps the pair linked to that leader.
    semantics.commit_endcap_fw(state, "head", 32.0, box_fw=25.0)
    assert state["mode"] == "FOLLOW_HEAD"
    assert state["head"]["value"] == pytest.approx(32.0)
    assert state["tail"]["value"] == pytest.approx(32.0)

    # Editing the other end cap breaks the pair; each value is now independent.
    semantics.commit_endcap_fw(state, "tail", 29.0, box_fw=25.0)
    assert state["mode"] == "INDEPENDENT"
    assert state["head"]["value"] == pytest.approx(32.0)
    assert state["tail"]["value"] == pytest.approx(29.0)

    # Re-entering the box FW is an explicit takeover even if its value is unchanged.
    semantics.commit_box_fw(state, 25.0)
    assert state["mode"] == "FOLLOW_BODY"
    assert semantics.resolve_endcap_fw({"fw": 25.0}, "head", state=state) == pytest.approx(25.0)
    assert semantics.resolve_endcap_fw({"fw": 25.0}, "tail", state=state) == pytest.approx(25.0)


def test_endcap_fw_operator_state_machine_is_symmetric_when_tail_is_edited_first():
    import phase6_endcap_semantics as semantics

    state = semantics.normalize_endcap_fw_state({"fw": 25.0})
    semantics.commit_endcap_fw(state, "tail", 30.0, box_fw=25.0)
    assert state["mode"] == "FOLLOW_TAIL"
    assert state["head"]["value"] == pytest.approx(30.0)
    assert state["tail"]["value"] == pytest.approx(30.0)

    semantics.commit_endcap_fw(state, "head", 28.0, box_fw=25.0)
    assert state["mode"] == "INDEPENDENT"
    assert state["head"]["value"] == pytest.approx(28.0)
    assert state["tail"]["value"] == pytest.approx(30.0)


def test_legacy_endcap_fw_snapshot_migrates_without_inventing_pair_following():
    import phase6_endcap_semantics as semantics

    state = semantics.normalize_endcap_fw_state({
        "fw": 25.0,
        "endcap_fw": {
            "head": {"follow_box": False, "value": 31.0},
            "tail": {"follow_box": True, "value": 25.0},
        },
    })
    assert state["mode"] == "INDEPENDENT"
    assert semantics.resolve_endcap_fw({"fw": 30.0}, "head", state=state) == pytest.approx(31.0)
    # Legacy per-part follow flags are preserved until the operator performs a
    # new four-state FW action; do not invent a Head/Tail leader during load.
    assert semantics.resolve_endcap_fw({"fw": 30.0}, "tail", state=state) == pytest.approx(30.0)


def test_3d_box_fw_edit_reclaims_both_endcaps_before_linked_rebuild(monkeypatch):
    from phase6_designer_workspace import Phase6DesignerWorkspace

    holder = SimpleNamespace(
        _settings_values={"w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0},
        _phase6_input_snapshot=base_snapshot(),
        _phase6_endcap_fw_state={
            "mode": "FOLLOW_HEAD",
            "head": {"follow_box": False, "value": 31.0},
            "tail": {"follow_box": False, "value": 31.0},
        },
        _phase6_box_whd={"w": 400, "h": 600, "d": 250},
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
        }),
        _phase6_applying_settings=False,
        _phase6_transactional_mode=True,
        _settings_change_callback=None,
    )
    monkeypatch.setattr(bridge, "_phase6_recalculate_part_dimensions", lambda self: None)
    seen = []
    monkeypatch.setattr(
        bridge, "_phase6_refresh_linked_part_profiles",
        lambda self, changed: seen.append((set(changed), deepcopy(self._phase6_endcap_fw_state))),
    )

    bridge._phase6_store_editor_values(holder, {"fw": 30.0}, notify=False)

    assert holder._phase6_endcap_fw_state["mode"] == "FOLLOW_BODY"
    assert holder._phase6_endcap_fw_state["head"] == {"follow_box": True, "value": 30.0}
    assert holder._phase6_endcap_fw_state["tail"] == {"follow_box": True, "value": 30.0}
    assert holder._phase6_input_snapshot["endcap_fw"]["mode"] == "FOLLOW_BODY"
    assert seen and seen[0][0] == {"fw"}
    assert seen[0][1]["head"]["value"] == pytest.approx(30.0)


def test_main_2d_invalid_endcap_fw_text_does_not_change_control_mode():
    import gui
    holder = SimpleNamespace(
        fw_z_var=DummyVar("25"), fw_head_var=DummyVar("abc"), fw_tail_var=DummyVar("25"),
        fw_head_follow_var=DummyVar(True), fw_tail_follow_var=DummyVar(True),
        endcap_fw_state=bridge.normalize_endcap_fw_state({"fw": 25.0}),
        _authoritative_part_render_cache={"old": object()},
        _fold_designer_number_text=lambda value: str(int(value)) if float(value).is_integer() else str(value),
        update_calculations=lambda: None,
    )
    holder._effective_endcap_fw = lambda part: gui.BoxCalculatorGUI._effective_endcap_fw(holder, part)
    holder._sync_endcap_fw_controls = lambda: gui.BoxCalculatorGUI._sync_endcap_fw_controls(holder)

    gui.BoxCalculatorGUI.on_fw_selected(holder, "head")

    assert holder.endcap_fw_state["mode"] == "FOLLOW_BODY"
    assert holder.fw_head_var.get() == "25"
    assert holder.fw_tail_var.get() == "25"
