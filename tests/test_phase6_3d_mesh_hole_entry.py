# -*- coding: utf-8 -*-
"""3D sheet double-click must select the actual visible FinalScene Part ID."""
from types import SimpleNamespace

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backend_bases import MouseEvent
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from phase6_final_scene_renderer import Phase6FinalSceneRenderer


def _scene():
    fig = Figure(figsize=(5, 4), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d")
    ax.set(xlim=(0, 1), ylim=(0, 1), zlim=(0, 1))
    view = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax, canvas=canvas))
    tri = [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]]
    mesh = Poly3DCollection(tri, facecolor="#bbbbbb")
    ax.add_collection3d(mesh)
    canvas.draw()
    return canvas, ax, view, mesh


def _event_at_surface(canvas, mesh, *, dblclick=True, button=1):
    # Use the collection's *rendered* 2D path, not a hard-coded screen point.
    path = mesh.get_paths()[0]
    a, b, c = path.vertices[:3]
    centroid = (a + b + c) / 3
    x, y = mesh.get_transform().transform(centroid)
    return MouseEvent(
        "button_press_event", canvas, x, y,
        button=button, dblclick=dblclick,
    )


def test_3d_mesh_double_click_resolves_actual_visible_part_not_selector():
    canvas, ax, view, mesh = _scene()
    calls = []
    view._hole_pick_artists = [(mesh, "inner_door:upper:panel")]
    view.set_hole_double_click_handler(calls.append)
    assert view.on_hole_mesh_double_click(
        _event_at_surface(canvas, mesh),
    ) == "inner_door:upper:panel"
    assert calls == ["inner_door:upper:panel"]


def test_3d_single_click_right_click_and_blank_are_noops():
    canvas, ax, view, mesh = _scene()
    calls = []
    view._hole_pick_artists = [(mesh, "door")]
    view.set_hole_double_click_handler(calls.append)
    assert view.on_hole_mesh_double_click(
        _event_at_surface(canvas, mesh, dblclick=False),
    ) is None
    assert view.on_hole_mesh_double_click(
        _event_at_surface(canvas, mesh, button=3),
    ) is None
    blank = MouseEvent("button_press_event", canvas, 0, 0, button=1, dblclick=True)
    assert view.on_hole_mesh_double_click(blank) is None
    assert calls == []


def test_3d_overlap_selects_frontmost_artist_and_never_hidden_piece():
    canvas, ax, view, near = _scene()
    far = Poly3DCollection(
        [[(0, 0, 0.3), (1, 0, 0.3), (0, 1, 0.3)]],
        facecolor="#aaaaaa",
    )
    ax.add_collection3d(far)
    canvas.draw()
    # This is the *draw-time* 3D depth ordering of the visible skins.
    near.set_zorder(9.0)
    far.set_zorder(2.0)
    view._hole_pick_artists = [(far, "box_body:back"), (near, "door")]
    calls = []
    view.set_hole_double_click_handler(calls.append)
    result = view.on_hole_mesh_double_click(_event_at_surface(canvas, near))
    assert result == "door"
    assert calls == ["door"]
    near.set_visible(False)
    assert view.on_hole_mesh_double_click(_event_at_surface(canvas, far)) == "box_body:back"


def test_3d_mpl_backend_double_click_is_registered_once():
    canvas, ax, view, mesh = _scene()
    calls = []
    view._hole_pick_artists = [(mesh, "door")]
    view.set_hole_double_click_handler(calls.append)
    cid = view._hole_double_click_cid
    view.set_hole_double_click_handler(calls.append)
    assert cid is not None and view._hole_double_click_cid == cid
    canvas.callbacks.process(
        "button_press_event", _event_at_surface(canvas, mesh),
    )
    assert calls == ["door"]


def test_rendered_scene_pick_entries_replaced_on_redraw_or_empty():
    canvas, ax, view, mesh = _scene()
    view._hole_pick_artists = [(mesh, "old-part")]
    assert view.render(None) == []
    assert view._hole_pick_artists == []


@pytest.mark.skipif(__import__("os").environ.get("DISPLAY") is None,
                    reason="real Tk display required")
def test_real_3d_single_part_surface_routes_to_original_hole_editor(monkeypatch):
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("door")
        root.update_idletasks()
        root.update()
        owner = designer.final_scene_view
        assert owner._hole_double_click_cid is not None
        artists = [(poly, key) for poly, key in owner._hole_pick_artists if key == "door"]
        assert artists, "3D true rendered Door CUTTING mesh has no selectable identity"
        poly, key = artists[0]
        received = []
        monkeypatch.setattr(app, "open_part_hole_editor",
                            lambda part: received.append(part))
        # User would double-click this physical material screen path.
        designer.renderer.canvas.callbacks.process(
            "button_press_event",
            _event_at_surface(designer.renderer.canvas, poly),
        )
        root.update_idletasks()
        root.update()
        assert received == ["door"]
    finally:
        root.destroy()
