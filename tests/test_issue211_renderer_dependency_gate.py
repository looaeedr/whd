from pathlib import Path
from types import SimpleNamespace
import ast

import gui_modules.render_2d as render_2d

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive


SAFE_HELPERS = (
    "_draw_layout_resolved_features",
    "_draw_layout_baseline_secondary",
    "draw_grid",
)


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return len(self.calls)

    def create_line(self, *args, **kwargs):
        return self._record("line", *args, **kwargs)

    def create_oval(self, *args, **kwargs):
        return self._record("oval", *args, **kwargs)

    def create_polygon(self, *args, **kwargs):
        return self._record("polygon", *args, **kwargs)


def _instance(cls, **attrs):
    value = object.__new__(cls)
    for name, item in attrs.items():
        object.__setattr__(value, name, item)
    return value


def test_behavior_draw_grid_preserves_current_canvas_contract():
    import gui

    canvas = RecordingCanvas()
    render_2d.draw_grid(object(), canvas, 100, 90, tags=("grid",))

    assert [name for name, _, _ in canvas.calls] == ["line"] * 6
    assert canvas.calls[0][1] == (0, 0, 0, 90)
    assert canvas.calls[2][1] == (80, 0, 80, 90)
    assert canvas.calls[3][1] == (0, 0, 100, 0)
    assert canvas.calls[-1][1] == (0, 80, 100, 80)
    assert all(call[2]["fill"] == "#1c1c22" for call in canvas.calls)
    assert all(call[2]["width"] == 1 for call in canvas.calls)
    assert all(call[2]["tags"] == ("grid",) for call in canvas.calls)


def test_behavior_resolved_feature_projection_preserves_current_primitives():
    import gui

    circle = ResolvedCircle(
        center=Vec2(10.0, 5.0), radius=2.0, layer="CUTTING", add_centerline=True,
    )
    rect = ResolvedRect(
        center=Vec2(3.0, 3.0), width=2.0, height=2.0, layer="MARKING",
    )
    profile = ResolvedProfile(
        points=(Vec2(6.0, 1.0), Vec2(8.0, 1.0), Vec2(8.0, 3.0)),
        layer="BLIND_HOLE",
        layered_profiles=(("DATUM", (Vec2(6.0, 2.0), Vec2(8.0, 2.0)), False),),
    )
    canvas = RecordingCanvas()

    render_2d._draw_layout_resolved_features(
        canvas, (circle, rect, profile), 20.0, 10.0, (0.0, 0.0, 200.0, 100.0), "cell",
    )

    assert [name for name, _, _ in canvas.calls] == ["oval", "line", "polygon", "polygon", "line"]
    assert canvas.calls[0][2]["outline"] == "#ff9f0a"
    assert canvas.calls[1][2]["fill"] == "#bf5af2"
    assert canvas.calls[2][2]["outline"] == "#8e8e93"
    assert canvas.calls[3][2]["outline"] == "#ff453a"
    assert canvas.calls[4][2]["fill"] == "#bf5af2"
    assert all("cell" in call[2]["tags"] for call in canvas.calls)


def test_behavior_baseline_secondary_skips_primary_outline_and_bend_layers():
    import gui

    outline = _instance(
        PolylinePrimitive,
        points=(Vec2(0.0, 0.0), Vec2(20.0, 0.0), Vec2(20.0, 10.0), Vec2(0.0, 10.0)),
        layer="CUTTING", closed=True,
    )
    marking = _instance(
        LinePrimitive,
        p1=Vec2(1.0, 1.0), p2=Vec2(5.0, 1.0), layer="MARKING",
    )
    bend = _instance(
        LinePrimitive,
        p1=Vec2(2.0, 0.0), p2=Vec2(2.0, 10.0), layer="BEND",
    )
    hole = _instance(
        CirclePrimitive,
        center=Vec2(10.0, 5.0), radius=1.0, layer="CUTTING",
    )
    scene = SimpleNamespace(primitives=(outline, marking, bend, hole))
    canvas = RecordingCanvas()

    render_2d._draw_layout_baseline_secondary(
        canvas, scene, 20.0, 10.0, (0.0, 0.0, 200.0, 100.0), "baseline",
    )

    assert [name for name, _, _ in canvas.calls] == ["line", "oval"]
    assert canvas.calls[0][2]["fill"] == "#8e8e93"
    assert canvas.calls[1][2]["outline"] == "#64d2ff"
    assert all("baseline" in call[2]["tags"] for call in canvas.calls)


def test_structure_safe_helpers_move_to_render_2d_without_reverse_gui_dependency():
    module_path = Path("gui_modules/render_2d.py")
    assert module_path.is_file(), "T7 first cut requires gui_modules/render_2d.py"
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    module_functions = {
        node.name
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(SAFE_HELPERS) <= module_functions
    assert "import gui" not in module_source
    assert "from gui import" not in module_source


def test_structure_phase6_host_no_longer_defines_safe_helper_bodies():
    gui_source = Path("gui.py").read_text(encoding="utf-8")
    tree = ast.parse(gui_source)
    host = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost")
    methods = {
        node.name
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(SAFE_HELPERS).isdisjoint(methods)
    assert "from gui_modules.render_2d import" in gui_source


def test_structure_existing_3d_deep_module_remains_the_only_new_3d_owner():
    view_source = Path("phase6_final_scene_view.py").read_text(encoding="utf-8")
    renderer_source = Path("phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    view_tree = ast.parse(view_source)
    renderer_tree = ast.parse(renderer_source)
    assert any(
        isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneViewAdapter"
        for node in view_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneRenderer"
        for node in renderer_tree.body
    )
    assert "must not build PartSpec" in view_source or "不得建立 PartSpec" in view_source
    assert not Path("gui_modules/render_3d.py").exists()
