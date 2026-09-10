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
    root.update_idletasks(); root.update()
    return root, app, gui


def test_corner_data_box_body_consumes_authoritative_render_without_caller_structural_rebuild(monkeypatch):
    import fold_designer_bridge as bridge

    root, app, gui = _make_app()
    designer = None
    try:
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        root.update_idletasks(); root.update()

        calls = {"authoritative": 0}
        real_authoritative = app._authoritative_render_data

        def capture_authoritative(spec, context):
            calls["authoritative"] += 1
            return real_authoritative(spec, context)

        def forbidden(*_args, **_kwargs):
            raise AssertionError("corner-data 2D must not rebuild Box Body structural geometry")

        monkeypatch.setattr(app, "_authoritative_render_data", capture_authoritative)
        monkeypatch.setattr(gui, "build_box_body_result_from_fold_profile", forbidden)
        monkeypatch.setattr(gui, "build_box_body_result", forbidden)

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        assert bridge._phase6_select_corner_data_part(designer, "box_body") == "box_body"
        projection = bridge._phase6_corner_data_unfold_projection(designer)

        assert projection is not None
        assert projection.part_key == "box_body"
        assert projection.render_data is not None
        assert calls["authoritative"] >= 1
        contexts = projection.render_data.box_body_face_contexts
        assert set(contexts) == {"left", "back", "right"}
        minx, _miny, maxx, _maxy = map(float, projection.render_data.material.bounds)
        assert (maxx - minx) > 500.0 + 2.0 * 200.0
        assert not hasattr(app, "notebook")
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_receiving_corner_data_box_body_uses_same_authoritative_context_projection(monkeypatch):
    import fold_designer_bridge as bridge

    root, app, gui = _make_app()
    designer = None
    try:
        app.baseline_var.set("受電箱")
        app.on_baseline_changed()
        root.update_idletasks(); root.update()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("Receiving corner-data 2D must not call GUI structural builders")

        monkeypatch.setattr(gui, "build_box_body_result_from_fold_profile", forbidden)
        monkeypatch.setattr(gui, "build_box_body_result", forbidden)

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bundle = bridge._phase6_query_assembly_render_data(designer)
        bridge._phase6_show_corner_data(designer)
        resolved = bridge._phase6_select_corner_data_part(designer, "box_body")
        projection = bridge._phase6_corner_data_unfold_projection(designer)

        # Receiving keeps one top-level 箱身 selector, but its authoritative
        # manufacturing identity is one of the three physical child plates.
        assert resolved == "box_body:left_side"
        assert projection is not None
        assert projection.part_key == resolved
        aggregate = next(part for part in bundle.assembly_parts if part.part_key == "box_body").render_data
        expected = next(piece.render_data for piece in aggregate.pieces if piece.role == "left_side")
        assert projection.render_data.material.equals(expected.material)
        assert app.workspace_controller.box_body_profile()
        assert projection.render_data is bridge._phase6_corner_data_unfold_projection(designer).render_data
        assert not hasattr(app, "notebook")
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()
