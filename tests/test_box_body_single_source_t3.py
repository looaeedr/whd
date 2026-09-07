from __future__ import annotations

import os
import pytest


pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")


def _make_app():
    import tkinter as tk
    import gui
    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    root.deiconify()
    root.geometry("1200x800")
    app.notebook.select(app.tab_z)
    root.update_idletasks(); root.update()
    return root, app, gui


def test_draw_box_body_consumes_authoritative_render_without_caller_structural_rebuild(monkeypatch):
    root, app, gui = _make_app()
    try:
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        root.update_idletasks(); root.update()
        val = app.get_float_values()

        calls = {"authoritative": 0}
        real_authoritative = app._authoritative_render_data

        def capture_authoritative(spec, context):
            calls["authoritative"] += 1
            return real_authoritative(spec, context)

        def forbidden(*_args, **_kwargs):
            raise AssertionError("draw_box_body must not rebuild Box Body structural geometry")

        monkeypatch.setattr(app, "_authoritative_render_data", capture_authoritative)
        monkeypatch.setattr(gui, "build_box_body_result_from_fold_profile", forbidden)
        monkeypatch.setattr(gui, "build_box_body_result", forbidden)

        app.draw_box_body(val)

        assert calls["authoritative"] == 1
        assert set(app.box_body_face_bounds) == {"left", "back", "right"}
        overview = app.last_box_body_face_overview
        assert overview["mode"] == "unfolded_with_face_hit_zones"
        assert set(overview["contexts"]) == {"left", "back", "right"}
        assert overview["unfolded_size"][0] > val["w"] + 2.0 * val["d"]

        bend_items = [
            item for item in app.canvas_z.find_all()
            if app.canvas_z.type(item) == "line"
            and app.canvas_z.itemcget(item, "fill") == "#0a84ff"
        ]
        assert bend_items
    finally:
        root.destroy()


def test_receiving_draw_box_body_uses_same_authoritative_context_projection(monkeypatch):
    root, app, gui = _make_app()
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        val = app.get_float_values()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("Receiving Main 2D must not call GUI structural builders")

        monkeypatch.setattr(gui, "build_box_body_result_from_fold_profile", forbidden)
        monkeypatch.setattr(gui, "build_box_body_result", forbidden)

        app.draw_box_body(val)

        assert set(app.box_body_face_bounds) == {"left", "back", "right"}
        contexts = app.last_box_body_face_overview["contexts"]
        assert set(contexts) == {"left", "back", "right"}
        assert app.workspace_controller.box_body_profile()
    finally:
        root.destroy()
