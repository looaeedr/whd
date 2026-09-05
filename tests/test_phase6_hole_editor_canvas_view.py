from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature,
    FeatureAnchor,
    Vec2,
    feature_surface_from_rect,
)


def _guide():
    return SimpleNamespace(
        min_point=Vec2(0.0, 0.0),
        max_point=Vec2(100.0, 100.0),
        width=100.0,
        height=100.0,
    )


def _feature():
    return CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(50.0, 50.0),
    )


def _build_view(root):
    import tkinter as tk
    from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView

    canvas = tk.Canvas(root, width=640, height=520)
    canvas.pack()
    x_group = tk.Frame(canvas, width=180, height=82)
    y_group = tk.Frame(canvas, width=180, height=82)
    panel = tk.Frame(canvas, width=140, height=90)

    def draw_grid(canvas, w, h):
        canvas.create_line(0, 0, w, h, tags=("grid_probe",))

    def render_secondary_scene(canvas, scene, transform):
        canvas.create_text(10, 10, text="baseline", tags=("baseline_probe",))

    def render_resolved_features(canvas, features, transform, *, color="#ff9f0a"):
        for feature in features:
            center = getattr(feature, "center", None)
            radius = getattr(feature, "radius", 0.0)
            if center is None:
                continue
            cx, cy = transform.world_to_canvas(center)
            r = radius * transform.scale
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, tags=("feature_probe",))

    view = Phase6HoleEditorCanvasView(
        canvas,
        draw_grid=draw_grid,
        render_secondary_scene=render_secondary_scene,
        render_resolved_features=render_resolved_features,
        overlay_widgets={"x_group": x_group, "y_group": y_group, "panel": panel},
    )
    root.update_idletasks()
    return view, canvas, x_group, y_group, panel


def test_canvas_view_render_owns_transform_hit_test_and_overlay_visibility():
    import tkinter as tk
    from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame

    root = tk.Tk()
    try:
        view, canvas, x_group, y_group, panel = _build_view(root)
        feature = _feature()
        surface = feature_surface_from_rect("face", Vec2(0.0, 0.0), Vec2(100.0, 100.0))
        distances = SimpleNamespace(x_side="left", y_side="bottom")
        frame = HoleEditorCanvasFrame(
            surface=surface,
            features=[feature],
            width=100.0,
            height=100.0,
            reference_guide=_guide(),
            selected_index=0,
            reference_distances=distances,
            measure_guide=_guide(),
        )
        view.render(frame)
        root.update_idletasks()

        cx, cy = view.transform.world_to_canvas(Vec2(50.0, 50.0))
        world = view.canvas_to_world(cx, cy)
        assert world is not None
        assert world.x == pytest.approx(50.0)
        assert world.y == pytest.approx(50.0)
        assert view.hit_test(cx, cy) == 0
        assert x_group.place_info()
        assert y_group.place_info()
        assert panel.place_info()

        view.render(HoleEditorCanvasFrame(
            surface=surface,
            features=[feature],
            width=100.0,
            height=100.0,
            reference_guide=_guide(),
            selected_index=-1,
        ))
        root.update_idletasks()
        assert not x_group.place_info()
        assert not y_group.place_info()
        assert not panel.place_info()
    finally:
        root.destroy()


def test_canvas_view_extra_draw_runs_with_same_transform_and_viewport():
    import tkinter as tk
    from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame

    root = tk.Tk()
    try:
        view, canvas, *_ = _build_view(root)
        surface = feature_surface_from_rect("face", Vec2(0.0, 0.0), Vec2(100.0, 100.0))
        seen = []

        def extra(canvas, transform, cw, ch):
            seen.append((transform, cw, ch))
            canvas.create_text(20, 20, text="extra", tags=("extra_probe",))

        view.render(HoleEditorCanvasFrame(
            surface=surface,
            features=[],
            width=100.0,
            height=100.0,
            reference_guide=_guide(),
            selected_index=-1,
            extra_bounds=(-50.0, -20.0, 150.0, 120.0),
            draw_extra=extra,
        ))
        assert len(seen) == 1
        assert seen[0][0] is view.transform
        assert canvas.find_withtag("extra_probe")
    finally:
        root.destroy()


def test_canvas_view_module_has_no_manufacturing_or_project_owner_dependencies():
    tree = ast.parse(Path("phase6_hole_editor_canvas_view.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = (
        "gui",
        "ae_engine.manufacturing_api",
        "phase6_project",
        "phase6_settings",
        "phase6_designer_workspace",
    )
    assert not [name for name in imported if name.startswith(forbidden)]


def test_gui_editor_canvas_implementation_moves_behind_view_seam():
    tree = ast.parse(Path("gui.py").read_text(encoding="utf-8"))
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_open_unified_hole_editor"
    )
    nested_names = {
        node.name for node in ast.walk(method)
        if isinstance(node, ast.FunctionDef) and node is not method
    }
    assert "hide_overlays" not in nested_names
    assert "place_reference_overlays" not in nested_names
    assert "resolved_canvas_rect" not in nested_names
    assert "hit_index" not in nested_names

    assigned = set()
    for node in ast.walk(method):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
    assert "transform_box" not in assigned

    referenced_names = {node.id for node in ast.walk(method) if isinstance(node, ast.Name)}
    assert "resolve_surface_features" not in referenced_names
    assert "hit_test_resolved_features" not in referenced_names
    assert "CanvasTransform" not in referenced_names


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


def test_real_tk_canvas_hit_test_drag_and_cancel_all_roundtrip():
    import tkinter as tk

    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, feature_surface_from_rect

    root = tk.Tk()
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update()
        features = [
            CircleFeature(
                diameter=20.0,
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(50.0, 50.0),
            )
        ]
        surface = feature_surface_from_rect("test_face", Vec2(0.0, 0.0), Vec2(100.0, 100.0))
        app._open_unified_hole_editor(
            "door",
            "測試門板",
            surface,
            100.0,
            100.0,
            feature_list_override=features,
        )
        editor = app.last_unified_hole_editor
        root.update()
        canvases = [w for w in _walk_widgets(editor) if isinstance(w, tk.Canvas)]
        canvas = max(canvases, key=lambda w: w.winfo_width() * w.winfo_height())

        # The single existing hole is the only feature-sized oval before selection.
        ovals = [item for item in canvas.find_all() if canvas.type(item) == "oval"]
        assert ovals
        bbox = canvas.bbox(ovals[0])
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)

        original = features[0]
        canvas.event_generate("<Button-1>", x=cx, y=cy)
        root.update()
        canvas.event_generate("<B1-Motion>", x=cx + 45, y=cy)
        root.update()
        canvas.event_generate("<ButtonRelease-1>", x=cx + 45, y=cy)
        root.update()
        assert features[0] != original

        cancel_all = next(
            w for w in _walk_widgets(editor)
            if isinstance(w, tk.Button) and w.cget("text") == "取消全部"
        )
        cancel_all.invoke()
        root.update()
        assert len(features) == 1
        assert features[0] == original
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
