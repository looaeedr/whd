"""#3317 scoped Custom Tail two-corner CHECK: one true source, atomic pair, real Tk.

The two resulting 2D drawings stay separate. The actual source's shared Y
BEND identity is asserted; a unified post-two-V 3D is NOT claimed.
"""
from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import filedialog, messagebox

import pytest

from ae_engine import manufacturing_api as api
from gui import BoxCalculatorGUI
from gui_modules.application.endcap_live_v_check_consumer import (
    ATTR, KEY, _selected_source,
)
from gui_modules.application.endcap_live_v_check_view import (
    close_saved_live_check_window,
)
from phase6_project_file import read_project

CORNERS = ("bottom_left", "bottom_right")


def _make_tail_pair(app, mode):
    app.baseline_var.set("自訂")
    app.w_var.set("400")
    app.d_var.set("250")
    app.t_var.set("2")
    app.workspace_controller.set_active_part("tail")
    # The real manual corner radio commits both V CHECK choices atomically.
    app.manual_corner_pair_same["tail"]["bottom"] = True
    app.select_manual_corner("bottom")
    app.refresh_corner_type_panel()
    assert app.manual_active_corner_var.get() == "bottom"
    assert app.v_miter_gui_check_radio.cget("state") == "normal"
    app.v_miter_gui_check_radio.invoke()
    assert app.v_miter_gui_check_corners["tail"] == dict.fromkeys(
        CORNERS, "V_MITER_CHECK"
    )
    assert not app.v_miter_gui_first_bend_axes
    app.v_miter_first_bend_axis_var.set("x")
    app.set_v_miter_gui_first_bend_axis()
    assert app.v_miter_gui_first_bend_axes["tail"] == dict.fromkeys(CORNERS, "x")
    app.v_miter_relief_mode_var.set(mode)
    app.set_v_miter_gui_relief_mode()


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_custom_tail_native_pair_save_new_main_gui_open_view_and_fail_closed(
    tmp_path, monkeypatch, mode,
):
    messages = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kw: messages.append(("info", args)))
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kw: messages.append(("error", args)))
    project = tmp_path / f"tail-original-double-v-{mode}.p6fold"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(project))
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(project))

    root = tk.Tk()
    root.withdraw()
    fresh_root = None
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, mode)
        snap = app._make_original_fold_designer_snapshot()
        part, corner, spec, source = _selected_source(app, snap)
        assert (part, corner) == ("tail", "bottom")
        assert spec.is_tail and spec.model_name is None
        left = api.project_operator_v_miter_live_corner_check(
            spec, source, CORNERS[0], first_bend_axis="x", relief_mode=mode,
        )
        right = api.project_operator_v_miter_live_corner_check(
            spec, source, CORNERS[1], first_bend_axis="x", relief_mode=mode,
        )
        assert left.first_physical_bend is not right.first_physical_bend
        assert left.first_physical_bend.p1.x == pytest.approx(15.0)
        assert right.first_physical_bend.p1.x == pytest.approx(407.0)
        assert left.second_physical_bend is right.second_physical_bend
        assert left.second_physical_bend.p1.y == pytest.approx(15.0)
        # Two independently solved single-corner checks cannot be joined into
        # an entire post-two-V formed 3D by concatenating their triangles.
        before = deepcopy(getattr(app, ATTR, {}))
        assert not before.get("tail")
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()
        assert not any(kind == "error" for kind, _ in messages), messages
        records = deepcopy(getattr(app, ATTR)["tail"])
        assert set(records) == set(CORNERS)
        assert {r["first_bend_axis"] for r in records.values()} == {"x"}
        assert {r["relief_mode"] for r in records.values()} == {mode}
        assert records["bottom_left"]["source_fold_sha256"] != records[
            "bottom_right"
        ]["source_fold_sha256"]

        # Right hand source not selected => NEVER publish a partial left row.
        app.v_miter_gui_first_bend_axes["tail"].pop("bottom_right")
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()
        assert any(kind == "error" for kind, _ in messages)
        assert getattr(app, ATTR)["tail"] == records
        app.v_miter_gui_first_bend_axes["tail"]["bottom_right"] = "x"

        # Use real main toolbar project Save As and a second real GUI Open.
        messages.clear()
        app.project_save_as_button.invoke()
        assert project.is_file(), messages
        assert not any(kind == "error" for kind, _ in messages), messages
        original_bytes = project.read_bytes()
        saved = read_project(project)["snapshot"]
        assert saved[KEY]["tail"] == records
        assert saved["v_miter_gui_check_corners"]["tail"] == dict.fromkeys(
            CORNERS, "V_MITER_CHECK"
        )
        assert saved["v_miter_gui_first_bend_axes"]["tail"] == dict.fromkeys(CORNERS, "x")

        fresh_root = tk.Tk()
        fresh_root.withdraw()
        fresh = BoxCalculatorGUI(fresh_root)
        messages.clear()
        fresh.project_open_button.invoke()
        assert not any(kind == "error" for kind, _ in messages), messages
        fresh.workspace_controller.set_active_part("tail")
        assert fresh.manual_corner_pair_same["tail"]["bottom"] is True
        fresh.select_manual_corner("bottom")
        reopened = fresh._make_original_fold_designer_snapshot()
        assert reopened["v_miter_gui_check_corners"]["tail"] == dict.fromkeys(
            CORNERS, "V_MITER_CHECK"
        )
        _, _, new_spec, new_render = _selected_source(fresh, reopened)
        assert new_spec.is_tail and new_spec.model_name is None
        assert new_render.scene.primitives
        assert getattr(fresh, ATTR)["tail"] == records

        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert not any(kind == "error" for kind, _ in messages), messages
        window = fresh._endcap_live_saved_check_window
        window.update()
        assert window.winfo_viewable() == 1
        assert window.grab_status() == "local"
        assert "左下與右下" in window.title()
        pair_replays = window._saved_endcap_pair_replays
        assert set(pair_replays) == set(CORNERS)
        assert pair_replays["bottom_left"].second_physical_bend is (
            pair_replays["bottom_right"].second_physical_bend
        )
        assert window._saved_endcap_pair_3d_figure is None
        assert "不提供雙角合成 3D" in window._saved_endcap_pair_3d_warning.cget("text")
        assert len(window._saved_endcap_pair_2d_canvases) == 2
        assert all(len(x.find_all()) >= 5 for x in
                   window._saved_endcap_pair_2d_canvases.values())
        assert pair_replays["bottom_left"].full_sheet_check_scene is not (
            pair_replays["bottom_right"].full_sheet_check_scene
        )
        assert project.read_bytes() == original_bytes
        close_saved_live_check_window(fresh)
        assert not window.winfo_exists()

        # A current selection change in EITHER half invalidates the pair.
        for side in CORNERS:
            fresh.v_miter_gui_check_corners["tail"].pop(side)
            messages.clear()
            fresh.v_miter_check_source_button.invoke()
            assert any(kind == "error" for kind, _ in messages)
            assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
            fresh.v_miter_gui_check_corners["tail"][side] = "V_MITER_CHECK"
        # A changed per-corner relief choice also rejects both, rather
        # than silently rendering an obsolete local R/hole selection.
        changed_mode = "RELIEF_HOLE" if mode == "ROUND_R" else "ROUND_R"
        fresh.v_miter_gui_relief_modes["tail"]["bottom_right"] = changed_mode
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert any(kind == "error" and "SELECTION_CHANGED" in args[1]
                   for kind, args in messages)
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        fresh.v_miter_gui_relief_modes["tail"]["bottom_right"] = mode

        # A changed original physical Tail W/BEND invalidates both views.
        fresh.w_var.set("410")
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert any(kind == "error" and "V_MITER_LIVE_SOURCE_CHANGED" in args[1]
                   for kind, args in messages), messages
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert getattr(fresh, ATTR)["tail"] == records
        assert project.read_bytes() == original_bytes

        # Restore physical width and verify old source is valid again before
        # editing its real authored Tail lower Y Fold (not the CHECK draft).
        fresh.w_var.set("400")
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert not any(kind == "error" for kind, _ in messages), messages
        close_saved_live_check_window(fresh)
        profiles = fresh.workspace_controller.part_profiles_snapshot()
        authored = deepcopy(profiles["tail"])
        lower = [row for row in authored["Y"]
                 if row.get("phase6_key") == "ybottom1"]
        assert len(lower) == 1 and lower[0]["angle"] == pytest.approx(-90)
        lower[0]["angle"] = -75.5
        profiles["tail"] = authored
        workspace = fresh.workspace_controller.workspace_snapshot()
        workspace["part_profiles"] = profiles
        fresh.workspace_controller.commit_workspace(workspace)
        _, _, modified_spec, _ = _selected_source(
            fresh, fresh._make_original_fold_designer_snapshot()
        )
        assert any(row.phase6_key == "ybottom1" and row.angle == -75.5
                   for row in modified_spec.fold_profile_y)
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert any(kind == "error" and "V_MITER_LIVE_SOURCE_CHANGED" in args[1]
                   for kind, args in messages), messages
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert getattr(fresh, ATTR)["tail"] == records
        assert project.read_bytes() == original_bytes
    finally:
        if fresh_root is not None:
            fresh_root.destroy()
        root.destroy()


def test_tail_pair_engine_never_infers_order_or_uses_two_unrelated_sheets():
    from ae_engine.sheetmetal_geometry_core import GeometryError
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, source = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        modes = dict.fromkeys(CORNERS, "ROUND_R")
        with pytest.raises(GeometryError, match="EXPLICIT_CUSTOM_X_FIRST_REQUIRED"):
            api.capture_endcap_live_v_miter_bottom_pair_snapshots(
                spec, source,
                first_bend_axes={"bottom_left": "x"},
                relief_modes=modes,
            )
        with pytest.raises(GeometryError, match="EXPLICIT_CUSTOM_X_FIRST_REQUIRED"):
            api.capture_endcap_live_v_miter_bottom_pair_snapshots(
                spec, source,
                first_bend_axes={"bottom_left": "x", "bottom_right": "y"},
                relief_modes=modes,
            )
    finally:
        root.destroy()
