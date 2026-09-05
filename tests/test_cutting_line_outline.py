from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]
AE = ROOT / "ae_engine" / "ae.py"
GUI = ROOT / "gui.py"


def _load_function(path: Path, name: str, namespace: dict):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent(ast.get_source_segment(source, node))
            exec(code, namespace)
            return namespace[name]
    raise AssertionError(f"function not found: {name}")


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple
    layer: str
    closed: bool = False
    color: int | None = None


@dataclass(frozen=True)
class LinePrimitive:
    p1: Vec2
    p2: Vec2
    layer: str
    color: int | None = None


@dataclass(frozen=True)
class CirclePrimitive:
    center: Vec2
    radius: float
    layer: str
    color: int | None = None


class DrawingScene:
    def __init__(self):
        self.primitives = []

    def add(self, primitive):
        self.primitives.append(primitive)

    def add_line(self, p1, p2, *, layer, color=None):
        self.add(LinePrimitive(Vec2(*p1), Vec2(*p2), layer, color))

    def add_polyline(self, points, *, layer, closed=False, color=None):
        self.add(PolylinePrimitive(tuple(Vec2(*p) for p in points), layer, bool(closed), color))

    def add_circle(self, center, radius, *, layer, color=None):
        self.add(CirclePrimitive(Vec2(*center), float(radius), layer, color))


def _polygon_area(points):
    pts = list(points)
    return abs(sum(
        pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
        for i in range(len(pts))
    )) / 2.0


def _box_outline_lines():
    pts = [
        (47, 0), (349, 0), (349, 49), (396, 49), (396, 396), (349, 396),
        (349, 445), (47, 445), (47, 396), (0, 396), (0, 49), (47, 49),
    ]
    lines = []
    for i in range(len(pts)):
        a = Vec2(*pts[i])
        b = Vec2(*pts[(i + 1) % len(pts)])
        lines.append(LinePrimitive(a, b, "CUTTING"))
    return lines


def test_ae_primary_cutting_accepts_exploded_closed_line_outline():
    captured = {}

    def feature_surface_from_outline(surface_id, points):
        captured["points"] = tuple(points)
        return SimpleNamespace(surface_id=surface_id, outline=tuple(points))

    namespace = {
        "PolylinePrimitive": PolylinePrimitive,
        "LinePrimitive": LinePrimitive,
        "feature_surface_from_outline": feature_surface_from_outline,
    }
    fn = _load_function(AE, "_surface_from_scene_primary_cutting", namespace)
    lines = _box_outline_lines()
    scene = SimpleNamespace(primitives=[
        lines[7], lines[2], lines[10], lines[0], lines[5], lines[11],
        lines[4], lines[9], lines[1], lines[6], lines[3], lines[8],
    ])

    result = fn(scene, "indicator_box")

    assert result.surface_id == "indicator_box"
    assert _polygon_area(captured["points"]) == pytest.approx(167008.0)


def test_ae_primary_cutting_selects_largest_loop():
    captured = {}

    def feature_surface_from_outline(surface_id, points):
        captured["points"] = tuple(points)
        return SimpleNamespace(surface_id=surface_id, outline=tuple(points))

    namespace = {
        "PolylinePrimitive": PolylinePrimitive,
        "LinePrimitive": LinePrimitive,
        "feature_surface_from_outline": feature_surface_from_outline,
    }
    fn = _load_function(AE, "_surface_from_scene_primary_cutting", namespace)
    outer = [
        LinePrimitive(Vec2(0, 0), Vec2(100, 0), "CUTTING"),
        LinePrimitive(Vec2(100, 100), Vec2(0, 100), "CUTTING"),
        LinePrimitive(Vec2(100, 0), Vec2(100, 100), "CUTTING"),
        LinePrimitive(Vec2(0, 100), Vec2(0, 0), "CUTTING"),
    ]
    inner = [
        LinePrimitive(Vec2(40, 40), Vec2(60, 40), "CUTTING"),
        LinePrimitive(Vec2(60, 40), Vec2(60, 60), "CUTTING"),
        LinePrimitive(Vec2(60, 60), Vec2(40, 60), "CUTTING"),
        LinePrimitive(Vec2(40, 60), Vec2(40, 40), "CUTTING"),
    ]

    fn(SimpleNamespace(primitives=inner + outer), "panel")

    assert _polygon_area(captured["points"]) == pytest.approx(10000.0)


def test_gui_feature_surface_delegates_to_ae_scene_outline_resolver():
    expected = object()

    class FakeAE:
        @staticmethod
        def feature_surface_from_drawing_scene(surface_id, scene):
            assert surface_id == "indicator_box"
            assert len(scene.primitives) == 12
            return expected

    namespace = {
        "ae": FakeAE,
        "PolylinePrimitive": PolylinePrimitive,
        "feature_surface_from_outline": lambda *_: None,
    }
    fn = _load_function(GUI, "feature_surface_from_drawing_scene", namespace)
    scene = SimpleNamespace(primitives=_box_outline_lines())

    assert fn("indicator_box", scene) is expected


def test_stretched_indicator_box_accepts_line_based_cutting_outline(tmp_path):
    path = tmp_path / "盒子.dxf"
    doc = ezdxf.new("R2010")
    for layer in ("CUTTING", "BEND"):
        if layer not in doc.layers:
            doc.layers.add(layer)
    msp = doc.modelspace()
    for line in _box_outline_lines():
        msp.add_line((line.p1.x, line.p1.y), (line.p2.x, line.p2.y), dxfattribs={"layer": "CUTTING"})
    for a, b in [((49,0),(49,445)), ((347,0),(347,445)), ((0,49),(396,49)), ((0,396),(396,396))]:
        msp.add_line(a, b, dxfattribs={"layer": "BEND"})
    doc.saveas(path)

    formula_scene = DrawingScene()
    formula_data = SimpleNamespace(scene=formula_scene, params={"w": 396.0, "h": 445.0})
    surface_calls = []

    namespace = {
        "get_indicator_box_data": lambda *args, **kwargs: formula_data,
        "indicator_box_fold_def": 49.0,
        "indicator_shared_baseline_part_path": lambda filename, require_exists=True: str(path),
        "indicator_shared_baseline_model_name": lambda: "共用",
        "ezdxf": ezdxf,
        "DrawingScene": DrawingScene,
        "PolylinePrimitive": PolylinePrimitive,
        "LinePrimitive": LinePrimitive,
        "CirclePrimitive": CirclePrimitive,
        "SceneData": lambda **kwargs: SimpleNamespace(**kwargs),
        "_surface_from_scene_primary_cutting": lambda scene, sid: surface_calls.append((scene, sid)) or object(),
    }
    fn = _load_function(AE, "get_stretched_indicator_box_data", namespace)

    result = fn(None, (1,), 2.0)

    assert result.params["baseline_width"] == pytest.approx(396.0)
    assert result.params["baseline_height"] == pytest.approx(445.0)
    assert surface_calls and surface_calls[-1][1] == "indicator_box"
