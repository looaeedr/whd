"""#3317 /派工 item 2: real Tk saved EndCap CHECK viewer, no manufacturing."""
from copy import deepcopy
import json

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.endcap_live_v_check_consumer import ATTR, KEY
from phase6_project_file import PROJECT_SCHEMA_V1, write_project, read_project


@pytest.fixture
def messages(monkeypatch):
    from tkinter import messagebox
    records = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: records.append(("info", args)))
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: records.append(("error", args)))
    return records


def _select_head(app):
    app.workspace_controller.set_active_part("head")
    app.manual_corner_pair_same["head"]["bottom"] = False
    app.manual_active_corner_var.set("bottom_left")


@pytest.mark.parametrize("saved_mode", ("RELIEF_HOLE", "ROUND_R"))
def test_native_saved_head_2d3d_reopen_ignores_unsaved_live_switch(tmp_path, messages, saved_mode):
    import tkinter as tk
    from gui import BoxCalculatorGUI

    root = tk.Tk()
    root.withdraw()
    fresh_root = None
    try:
        app = BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        _select_head(app)
        app.v_miter_gui_check_corners = {"head": {"bottom_left": "V_MITER_CHECK"}}
        app.v_miter_gui_first_bend_axes = {"head": {"bottom_left": "x"}}
        app.v_miter_gui_relief_modes = {"head": {"bottom_left": saved_mode}}
        app.v_miter_relief_mode_var.set(saved_mode)
        app.v_miter_capture_live_source_button.invoke()
        record = deepcopy(getattr(app, ATTR)["head"]["bottom_left"])
        assert record["first_bend_axis"] == "x"
        assert record["relief_mode"] == saved_mode

        saved = app._compose_phase6_project_snapshot_from_main_gui()
        assert saved[KEY]["head"]["bottom_left"] == record
        p = tmp_path / "saved-v-check.p6fold"
        write_project(p, {"schema": PROJECT_SCHEMA_V1, "snapshot": saved})
        original_bytes = p.read_bytes()
        opened = read_project(p)["snapshot"]
        assert opened[KEY] == saved[KEY]

        fresh_root = tk.Tk()
        fresh_root.withdraw()
        fresh = BoxCalculatorGUI(fresh_root)
        fresh._apply_phase6_project_snapshot(opened)
        _select_head(fresh)
        # Change current unsaved operator choice and relief, not the original
        # EndCap source/Fold. Viewer must consume ONLY the persisted record.
        fresh.v_miter_gui_first_bend_axes = {"head": {"bottom_left": "y"}}
        fresh.v_miter_gui_relief_modes = {
            "head": {"bottom_left": "ROUND_R" if saved_mode == "RELIEF_HOLE" else "RELIEF_HOLE"}
        }
        fresh.v_miter_relief_mode_var.set("ROUND_R" if saved_mode == "RELIEF_HOLE" else "RELIEF_HOLE")
        unsaved_axes = deepcopy(fresh.v_miter_gui_first_bend_axes)
        unsaved_relief = deepcopy(fresh.v_miter_gui_relief_modes)
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert not messages
        view = fresh._endcap_live_saved_check_window
        assert view.winfo_exists()
        assert "已保存試算／非加工" in view.title()
        view.update()
        # Real Tk user input is held by the modal CHECK; unlike merely
        # re-clicking, a physical W edit cannot be committed from main GUI.
        assert view.winfo_viewable() == 1
        assert view.grab_status() == "local"
        assert fresh_root.grab_current() is view
        assert "避空前，不含左圖所選圓角／孔" in (
            view._saved_endcap_check_3d_warning.cget("text")
        )
        assert "Pre-relief 3D" in view._saved_endcap_check_3d_figure.axes[0].get_title()
        assert "NO selected R / relief hole" in (
            view._saved_endcap_check_3d_figure.axes[0].get_title()
        )
        model = fresh._make_original_fold_designer_snapshot()
        spec, _ = fresh._fold_designer_part_spec_from_payload("head", model)
        source = fresh._query_fold_designer_render_data("head", model)
        replay = manufacturing_api.replay_endcap_live_v_miter_check_snapshot(
            spec, source, record)
        assert view._saved_endcap_check_replay == replay
        assert replay.first_bend_axis == "x"
        assert replay.factory_bottom_relief_check.relief_mode.value == saved_mode
        assert view._saved_endcap_check_scene is view._saved_endcap_check_replay.full_sheet_check_scene
        assert view._saved_endcap_check_scene.primitives == replay.full_sheet_check_scene.primitives
        assert {p.layer for p in view._saved_endcap_check_scene.primitives} <= {"CHECK", "DATUM"}
        assert len(view._saved_endcap_check_2d_canvas.find_all()) >= 5
        assert len(view._saved_endcap_check_3d_figure.axes) == 1
        assert len(view._saved_endcap_check_3d_figure.axes[0].collections) >= 2
        assert all(len(part) > 0 for part in view._saved_endcap_check_3d_triangles)
        # Proven old Engine limitation: relief changes 2D, not the pre-relief
        # formed true-T 3D. View must NEVER claim that it shows that hole/R.
        alternate = manufacturing_api.project_operator_v_miter_live_corner_check(
            spec, source, "bottom_left", first_bend_axis="x",
            relief_mode="ROUND_R" if saved_mode == "RELIEF_HOLE" else "RELIEF_HOLE",
        )
        assert (replay.factory_bottom_relief_check.corrected_remaining_outline
                != alternate.factory_bottom_relief_check.corrected_remaining_outline)
        assert (replay.factory_true_t_check.first_thick_solid_triangles
                == alternate.factory_true_t_check.first_thick_solid_triangles)
        assert (replay.factory_true_t_check.second_thick_solid_triangles
                == alternate.factory_true_t_check.second_thick_solid_triangles)
        assert (replay.first_physical_bend.p1.x == 15
                and replay.first_physical_bend.p2.x == 15)
        assert (replay.second_physical_bend.p1.y == 41
                and replay.second_physical_bend.p2.y == 41)
        assert getattr(fresh, ATTR)["head"]["bottom_left"] == record
        assert fresh.v_miter_gui_first_bend_axes == unsaved_axes
        assert fresh.v_miter_gui_relief_modes == unsaved_relief
        assert p.read_bytes() == original_bytes
        assert fresh_root.grab_current() is view
        from gui_modules.application.endcap_live_v_check_view import (
            close_saved_live_check_window,
        )
        close_saved_live_check_window(fresh)
        assert not view.winfo_exists()
        assert fresh_root.grab_current() is None
        # Reopen the already-saved preview: subsequent project switching
        # must destroy it even WITHOUT pressing the button again.
        fresh.v_miter_check_source_button.invoke()
        view = fresh._endcap_live_saved_check_window
        assert view.grab_status() == "local"

        # Next click with drifted physical source must kill the old view.
        corrupt = deepcopy(opened)
        corrupt[KEY]["head"]["bottom_left"]["source_fold_sha256"] = "0" * 64
        fresh._apply_phase6_project_snapshot(corrupt)
        assert not view.winfo_exists()
        _select_head(fresh)
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert messages and messages[-1][0] == "error"
        assert "V_MITER_LIVE_SOURCE_CHANGED" in messages[-1][1][1]
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None

        # A fresh, valid project switch cannot keep a previous window.
        fresh._apply_phase6_project_snapshot(opened)
        _select_head(fresh)
        fresh.v_miter_check_source_button.invoke()
        second_view = fresh._endcap_live_saved_check_window
        assert second_view.winfo_exists()
        legacy = deepcopy(opened)
        legacy.pop(KEY)
        fresh._apply_phase6_project_snapshot(legacy)
        assert not second_view.winfo_exists()
        _select_head(fresh)
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert messages and messages[-1][0] == "info"
    finally:
        if fresh_root is not None:
            fresh_root.destroy()
        root.destroy()
