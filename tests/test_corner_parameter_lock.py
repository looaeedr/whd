from __future__ import annotations

from copy import deepcopy
import os

import pytest

import gui
import fold_designer_bridge as bridge


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _require_display():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")


def _select_head(app, root):
    app.notebook.select(app.tab_head)
    app.refresh_corner_type_panel()
    root.update_idletasks(); root.update()


def test_main_gui_corner_parameters_default_locked_and_unlock_does_not_mutate_state():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        _select_head(app, root)
        before = deepcopy(app._serialize_manual_corner_state())

        assert app._manual_corner_parameters_unlocked("head") is False
        assert app.manual_corner_param_frame.winfo_manager() == ""
        assert "🔒" in app.manual_corner_param_lock_button.cget("text")

        app.toggle_manual_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert app._manual_corner_parameters_unlocked("head") is True
        assert app.manual_corner_param_frame.winfo_manager() == "pack"
        assert "🔓" in app.manual_corner_param_lock_button.cget("text")
        assert app._serialize_manual_corner_state() == before

        app.toggle_manual_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert app.manual_corner_param_frame.winfo_manager() == ""
        assert app._serialize_manual_corner_state() == before
    finally:
        root.destroy()


def test_known_model_corner_type_stays_readonly_but_parameters_can_unlock():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        # Simulate an already-known production model without triggering external baseline file I/O.
        app.baseline_var = DummyVar("金庫型")
        assert not gui.is_unknown_model(app.baseline_var.get())
        _select_head(app, root)

        assert app._corner_part_type_editable("head") is False
        assert app._corner_part_parameters_unlockable("head") is True
        assert app.manual_corner_param_frame.winfo_manager() == ""
        app.toggle_manual_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert app.manual_corner_param_frame.winfo_manager() == "pack"
        # Known model keeps its CornerType default readonly while allowing fine-parameter edits.
        assert all(str(rb.cget("state")) == "disabled" for rb in app.manual_corner_type_buttons.values())
    finally:
        root.destroy()


def test_fixed_indicator_corner_has_no_unlock_path():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app._manual_corner_part_override = "indicator_box"
        app.refresh_corner_type_panel()
        root.update_idletasks(); root.update()
        assert app._corner_part_parameters_unlockable("indicator_box") is False
        assert app.manual_corner_param_lock_button.winfo_manager() == ""
        assert app.manual_corner_fixed_summary.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_3d_corner_parameters_default_locked_for_known_model_and_unlock_without_mutation():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()
        before = deepcopy(designer._phase6_corner_state)

        assert designer._phase6_corner_parameters_unlocked("head") is False
        assert designer.corner_param_lock_button is None
        assert "鎖定" in designer.parameter_lock_button.cget("text")
        # Locked 3D keeps only the fixed summary; advanced corner widgets are built on unlock.
        assert designer.corner_detail_frames == {}

        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert designer._phase6_corner_parameters_unlocked("head") is True
        assert "解鎖" in designer.parameter_lock_button.cget("text")
        assert any(frame.winfo_manager() == "grid" for frame in designer.corner_detail_frames.values())
        assert designer._phase6_corner_state == before
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_project_load_resets_transient_corner_parameter_locks(tmp_path):
    _require_display()
    import tkinter as tk
    import phase6_project_file as project

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        _select_head(app, root)
        app.toggle_manual_corner_parameter_lock()
        assert app._manual_corner_parameters_unlocked("head") is True

        snapshot = app._make_original_fold_designer_snapshot()
        payload = {"schema": project.PROJECT_SCHEMA, "saved_at": "now", "snapshot": snapshot, "final_geometry": {}}
        path = project.write_project(tmp_path / "lock-reset.p6fold", payload)

        app.load_phase6_project(path, open_designer=False)
        root.update_idletasks(); root.update()
        _select_head(app, root)
        assert app._manual_corner_parameters_unlocked("head") is False
        assert app.manual_corner_param_frame.winfo_manager() == ""
    finally:
        root.destroy()


def test_main_gui_locked_parameters_ignore_change_but_known_unlocked_can_adjust_amount():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        _select_head(app, root)
        # Bottom CROSS extra-cut has a real amount field in the default state.
        app.select_manual_corner("bottom")
        root.update_idletasks(); root.update()
        before = deepcopy(app.manual_corner_state["head"]["bottom_left"])
        before_type = before.type_id

        app.manual_corner_amount_var.set("9")
        app.on_manual_corner_parameter_changed()
        assert app.manual_corner_state["head"]["bottom_left"] == before

        app.toggle_manual_corner_parameter_lock()
        app.manual_corner_amount_var.set("1.75")
        app.on_manual_corner_parameter_changed()
        after = app.manual_corner_state["head"]["bottom_left"]
        assert after.type_id is before_type
        assert after.amount_t == pytest.approx(1.75)
    finally:
        root.destroy()


def test_3d_known_model_locked_guard_and_unlocked_parameter_edit_preserves_type():
    _require_display()
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()
        before = deepcopy(designer._phase6_corner_state["head"]["bottom_left"])

        # Locked mode does not build advanced corner parameter widgets at all;
        # therefore there is no hidden editable variable that can mutate state.
        assert designer.corner_amount_vars == {}
        assert designer._phase6_corner_state["head"]["bottom_left"] == before

        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()
        target = "bottom" if "bottom" in designer.corner_amount_vars else "bottom_left"
        designer.corner_amount_vars[target].set("1.75")
        bridge._phase6_corner_target_var_changed(designer, "head", target)
        after = designer._phase6_corner_state["head"]["bottom_left"]
        assert after["type_id"] == before["type_id"]
        assert float(after["amount_t"]) == pytest.approx(1.75)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_known_model_unlocked_corner_parameters_are_serialized_and_reach_main_part_specs():
    _require_display()
    import tkinter as tk
    from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        # Simulate one approved fine-parameter override while keeping the known type fixed.
        sel = CornerTypeSelection(
            CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
            direction=CornerDirection.BOTH, amount_t=1.75,
        )
        app.manual_corner_state["head"]["bottom_left"] = sel
        app.manual_corner_state["head"]["bottom_right"] = sel

        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["corner_state"]["head"]["bottom_left"]["amount_t"] == pytest.approx(1.75)

        val = {
            "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
            "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
            "zl1": 15.0, "zr1": 15.0,
        }
        spec = app._end_cap_part_spec(val, is_tail=False)
        assert spec.model_name == "金庫型"
        assert spec.corner_policy is not None
        assert spec.corner_policy.bottom_left.amount_t == pytest.approx(1.75)
    finally:
        root.destroy()


def test_known_model_corner_policy_reaches_door_baseplate_box_and_3d_payload():
    _require_display()
    import tkinter as tk
    from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        door_sel = CornerTypeSelection(
            CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN,
            direction=CornerDirection.WIDTH, amount_t=1.25,
        )
        base_sel = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
        for k in app.manual_corner_state["door"]:
            app.manual_corner_state["door"][k] = door_sel
            app.manual_corner_state["base_plate"][k] = base_sel

        vals = {
            "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
            "door_gap_w": 3.5, "door_gap_h": 3.5,
            "door_fold_l": 19.0, "door_fold_r": 15.0,
            "door_fold_t": 15.0, "door_fold_b": 15.0,
            "base_plate_shrink_top": 5.0, "base_plate_shrink_bottom": 5.0,
            "base_plate_shrink_left": 5.0, "base_plate_shrink_right": 5.0,
            "base_plate_bend": 20.0,
        }
        assert app._single_door_part_spec(vals).corner_policy is not None
        assert app._base_plate_part_spec(vals).corner_policy is not None
        head_policy, tail_policy = app._box_body_corner_policies(25.0)
        assert head_policy is not None and tail_policy is not None

        snap = app._make_original_fold_designer_snapshot()
        spec3d, _ = app._fold_designer_part_spec_from_payload("door", snap)
        assert spec3d.model_name == "金庫型"
        assert spec3d.corner_policy is not None
        assert spec3d.corner_policy.top_left.amount_t == pytest.approx(1.25)
    finally:
        root.destroy()


def test_known_baseline_corner_override_keeps_stretched_endcap_and_door_paths(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from ae_engine import manufacturing_api
    from ae_engine.contracts import EndCapPartSpec, DoorPartSpec, ManufacturingContext
    from ae_engine.corner_type_ui import known_model_corner_state, policy_from_corner_state
    from ae_engine.sheetmetal_drawing import DrawingScene

    policy = policy_from_corner_state(known_model_corner_state(["head"])["head"], fw=25.0)
    monkeypatch.setattr(manufacturing_api, "_baseline_path", lambda *args, **kwargs: Path("/fake/baseline.dxf"))

    endcap_seen = {}
    def fake_stretched_endcap(*args, **kwargs):
        endcap_seen.update(kwargs)
        return SimpleNamespace(scene=DrawingScene())
    monkeypatch.setattr(manufacturing_api.ae, "_build_stretched_end_cap_scene", fake_stretched_endcap)
    monkeypatch.setattr(
        manufacturing_api.ae, "_build_unknown_end_cap_scene",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("known baseline must not fall back to unknown endcap")),
    )
    endcap = EndCapPartSpec(
        width=400, height=250, depth=250, thickness=2, frame_width=25,
        model_name="金庫型", fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=policy,
    )
    manufacturing_api.build_part_scene(endcap, ManufacturingContext())
    assert endcap_seen["corner_policy"] == policy

    door_policy = policy_from_corner_state(known_model_corner_state(["door"])["door"], fw=25.0)
    door_seen = {}
    def fake_stretched_door(*args, **kwargs):
        door_seen.update(kwargs)
        return SimpleNamespace(scene=DrawingScene(), params={"total_width": 400.0, "total_depth": 600.0})
    monkeypatch.setattr(manufacturing_api.ae, "get_stretched_door_data", fake_stretched_door)
    monkeypatch.setattr(
        manufacturing_api, "build_unknown_door_result",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("known baseline must not fall back to unknown door")),
    )
    door = DoorPartSpec(
        width=400, height=600, thickness=2, frame_width=25, model_name="金庫型",
        gap_w=3.5, gap_h=3.5, fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        corner_policy=door_policy,
    )
    manufacturing_api.build_part_scene(door, ManufacturingContext())
    assert door_seen["corner_policy"] == door_policy


def test_known_model_selection_and_project_load_enforce_factory_corner_type_but_keep_same_type_parameters():
    _require_display()
    import tkinter as tk
    from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var = DummyVar("金庫型")
        app.manual_corner_state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=9.0)
        app.manual_corner_state["head"]["top_right"] = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=9.0)
        app._enforce_known_model_corner_types(reset_all=True)
        assert app.manual_corner_state["head"]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY

        snapshot = app._make_original_fold_designer_snapshot()
        snapshot["corner_state"]["head"]["top_left"] = {
            "type_id": "OVERLAY", "amount_t": 9.0,
        }
        snapshot["corner_state"]["head"]["bottom_left"]["amount_t"] = 1.75
        app._apply_phase6_project_snapshot(snapshot)
        assert app.manual_corner_state["head"]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY
        assert app.manual_corner_state["head"]["bottom_left"].amount_t == pytest.approx(1.75)
    finally:
        root.destroy()


def test_receiving_bottom_wrap_controls_live_only_in_unlocked_3d_parameters_and_link_head_tail():
    _require_display()
    import tkinter as tk
    from phase6_endcap_semantics import commit_endcap_bottom_wrap_joint, resolve_endcap_bottom_wrap

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        joint_state = dict(app.assembly_joint_state or {})
        joint_state["model"] = "受電箱"
        joint_state["existing_parts"] = ["box_body", "head", "tail"]
        joint_state = commit_endcap_bottom_wrap_joint(joint_state, "head", True)
        joint_state = commit_endcap_bottom_wrap_joint(joint_state, "tail", True)
        app.assembly_joint_state = joint_state
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        # Entire settings center is hidden while the global parameter lock is closed.
        assert designer._phase6_parameters_unlocked is False
        assert designer.settings_center.winfo_manager() == ""

        bridge._phase6_toggle_parameter_panel(designer)
        root.update_idletasks(); root.update()
        assert designer.settings_center.winfo_manager() == "pack"
        assert designer.bottom_wrap_widget is not None
        assert designer.bottom_wrap_widget.winfo_manager() == "grid"
        assert designer.bottom_wrap_enabled_var is None
        assert float(designer.bottom_wrap_reserve_u_var.get()) == pytest.approx(2.0)
        assert float(designer.bottom_wrap_reserve_v_var.get()) == pytest.approx(1.0)
        # WRAP must not be injected into the Assembly Intent selector.
        assert "WRAP" not in tuple(bridge.ASSEMBLY_TYPE_LABELS.values())

        designer.bottom_wrap_reserve_u_var.set("3.5")
        bridge._phase6_commit_receiving_bottom_wrap_controls(
            designer, "head", designer.bottom_wrap_reserve_u_var, designer.bottom_wrap_reserve_v_var,
        )
        state = designer._phase6_endcap_bottom_wrap_state
        assert resolve_endcap_bottom_wrap({"model": "受電箱"}, "tail", state=state)["reserve_u"] == pytest.approx(3.5)

        # Editing the opposite side later splits the pair, matching existing EndCap linkage semantics.
        designer.activate_part("tail")
        root.update_idletasks(); root.update()
        designer.bottom_wrap_reserve_u_var.set("4")
        bridge._phase6_commit_receiving_bottom_wrap_controls(
            designer, "tail", designer.bottom_wrap_reserve_u_var, designer.bottom_wrap_reserve_v_var,
        )
        state = designer._phase6_endcap_bottom_wrap_state
        assert state["mode"] == "INDEPENDENT"
        assert resolve_endcap_bottom_wrap({"model": "受電箱"}, "head", state=state)["reserve_u"] == pytest.approx(3.5)
        assert resolve_endcap_bottom_wrap({"model": "受電箱"}, "tail", state=state)["reserve_u"] == pytest.approx(4.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
