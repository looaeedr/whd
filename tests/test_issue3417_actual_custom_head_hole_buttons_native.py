"""#3417 exact native GUI EndCap far-hole Save/Open/replay regression.

This test uses the real Custom main Tk app, the owner's part_features and
part_profiles, actual capture/view buttons, and project read/write; no direct
viewer call, no manual model_name or Fold profile rewriting.
"""
from copy import deepcopy
import tkinter as tk

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import CirclePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry_core import Vec2
from gui_modules.application.endcap_live_v_check_consumer import ATTR, KEY, _selected_source
from gui_modules.application.endcap_live_v_check_view import close_saved_live_check_window
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


def _circle(dx=0):
    return CircleFeature(
        diameter=6, anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(dx, 0), layer="CUTTING",
    )


def _head(app):
    app.workspace_controller.set_active_part("head")
    app.manual_corner_pair_same["head"]["bottom"] = False
    app.manual_active_corner_var.set("bottom_left")
    app.v_miter_gui_check_corners = {"head": {"bottom_left": "V_MITER_CHECK"}}
    app.v_miter_gui_first_bend_axes = {"head": {"bottom_left": "x"}}
    app.v_miter_gui_relief_modes = {"head": {"bottom_left": "ROUND_R"}}
    app.v_miter_relief_mode_var.set("ROUND_R")


def _install_via_existing_editor_owner(app, feature):
    # The real endcap Hole Editor commits to surface_features; the workspace
    # controller is its persisted source for physical part_features.
    app.surface_features["head"] = [feature]
    parts = app.workspace_controller.part_features_snapshot()
    parts["head"] = [feature]
    app.workspace_controller.replace_part_features(parts)


def _source_circle(scene):
    rows = [p for p in scene.primitives
            if p.layer == "CUTTING" and isinstance(p, CirclePrimitive)]
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_real_custom_head_hole_capture_save_new_tk_open_view_and_move_reject(
    tmp_path, monkeypatch, mode,
):
    from tkinter import messagebox
    from gui import BoxCalculatorGUI

    messages = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args: messages.append(("error", args)))
    monkeypatch.setattr(messagebox, "showinfo", lambda *args: messages.append(("info", args)))

    root = tk.Tk()
    root.withdraw()
    fresh_root = None
    try:
        app = BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.w_var.set("400")
        app.d_var.set("250")
        app.t_var.set("2")
        _head(app)
        _install_via_existing_editor_owner(app, _circle())
        app.v_miter_relief_mode_var.set(mode)
        snapshot = app._make_original_fold_designer_snapshot()
        assert len(snapshot["part_features"]["head"]) == 1
        # A Custom Main Tk may have no authored part_profiles yet; the
        # existing Factory Fold is still real. Never fabricate or clear it.
        source_profiles = deepcopy(snapshot.get("part_profiles", {}).get("head"))
        _, _, native_spec, native = _selected_source(app, snapshot)
        assert native_spec.model_name is None  # native Custom owner normalization
        # The builder's untouched native Fold chains are our only source.
        # They must roundtrip unchanged (asserted below).
        assert native_spec.holes == (_circle(),)
        circle = _source_circle(native.scene)
        assert circle.radius == 3
        assert (circle.center.x, circle.center.y) == pytest.approx((211, 162))
        assert len(native.material.interiors) == 1
        assert _source_circle(api.build_operator_part_render_data(native_spec).scene) == circle
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()  # actual main-GUI save source
        assert not any(kind == "error" for kind, _ in messages), messages
        record = deepcopy(getattr(app, ATTR)["head"]["bottom_left"])
        assert record["relief_mode"] == mode and record["first_bend_axis"] == "x"
        saved = app._compose_phase6_project_snapshot_from_main_gui()
        assert saved[KEY]["head"]["bottom_left"] == record
        path = tmp_path / "custom-native-hole.p6fold"
        write_project(path, {"schema": PROJECT_SCHEMA_V1, "snapshot": saved})
        original_bytes = path.read_bytes()
        opened = read_project(path)["snapshot"]
        assert len(opened["part_features"]["head"]) == 1
        assert opened[KEY]["head"]["bottom_left"] == record

        fresh_root = tk.Tk()
        fresh_root.withdraw()
        fresh = BoxCalculatorGUI(fresh_root)
        fresh._apply_phase6_project_snapshot(opened)
        _head(fresh)
        fresh.v_miter_relief_mode_var.set("ROUND_R" if mode == "RELIEF_HOLE" else "RELIEF_HOLE")
        replay_snapshot = fresh._make_original_fold_designer_snapshot()
        _, _, reopened_spec, reopened = _selected_source(fresh, replay_snapshot)
        assert reopened_spec.model_name is None
        assert reopened_spec.fold_profile_x == native_spec.fold_profile_x
        assert reopened_spec.fold_profile_y == native_spec.fold_profile_y
        assert deepcopy(replay_snapshot.get("part_profiles", {}).get("head")) == source_profiles
        assert reopened_spec.holes == native_spec.holes
        assert _source_circle(reopened.scene) == circle
        messages.clear()
        fresh.v_miter_check_source_button.invoke()  # actual saved-view button
        assert not any(kind == "error" for kind, _ in messages), messages
        win = fresh._endcap_live_saved_check_window
        win.update()
        assert win.winfo_viewable() == 1 and win.grab_status() == "local"
        assert win._saved_endcap_check_replay.factory_true_t_check is None
        assert win._saved_endcap_check_3d_figure is None
        assert "不提供含孔厚板 3D" in win._saved_endcap_check_3d_warning.cget("text")
        assert {(p.center.x, p.center.y, p.radius) for p in
                win._saved_endcap_check_scene.primitives
                if isinstance(p, CirclePrimitive) and p.layer == "CHECK"} == {
                    (circle.center.x, circle.center.y, circle.radius)
                }
        assert path.read_bytes() == original_bytes
        close_saved_live_check_window(fresh)
        assert not win.winfo_exists()
        _install_via_existing_editor_owner(fresh, _circle(13))
        changed = fresh._make_original_fold_designer_snapshot()
        assert _source_circle(_selected_source(fresh, changed)[3].scene).center.x == pytest.approx(
            circle.center.x + 13
        )
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert messages and messages[-1][0] == "error"
        assert "V_MITER_LIVE_SOURCE_CHANGED" in messages[-1][1][1]
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert path.read_bytes() == original_bytes
    finally:
        if fresh_root is not None:
            fresh_root.destroy()
        root.destroy()


def test_named_head_with_circle_does_not_acquire_custom_live_check(monkeypatch):
    from dataclasses import replace
    from ae_engine.v_miter_existing_circle_check import qualify_live_endcap_circle_source
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.manufacturing_render_data import PartRenderData
    from ae_engine.sheetmetal_drawing import DrawingScene
    from ae_engine.sheetmetal_geometry_core import GeometryError
    spec = EndCapPartSpec(width=400, depth=250, thickness=2, frame_width=25,
                          model_name="受電箱", holes=(_circle(),))
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"):
        qualify_live_endcap_circle_source(
            spec, PartRenderData(scene=DrawingScene([]), material=object())
        )
