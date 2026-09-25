from __future__ import annotations

from types import SimpleNamespace

import pytest

import gui
from ae_engine.sheetmetal_drawing import (
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)
from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect
from ae_engine.sheetmetal_geometry import Vec2


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return len(self.calls)

    def create_polygon(self, *args, **kwargs):
        return self._record("polygon", *args, **kwargs)

    def create_line(self, *args, **kwargs):
        return self._record("line", *args, **kwargs)

    def create_oval(self, *args, **kwargs):
        return self._record("oval", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)


class FakeTransform:
    scale = 10.0

    def world_to_canvas(self, point):
        return float(point.x) * 10.0, float(point.y) * 10.0


def test_task3_layout_reference_overlay_rects_exact_baseline():
    sizes = {
        "x_edge": (40, 20),
        "x_neighbor": (40, 20),
        "y_edge": (40, 20),
        "y_neighbor": (40, 20),
        "panel": (80, 40),
    }
    actual = gui.layout_reference_overlay_rects(
        400,
        300,
        crosshair=(200, 150),
        feature_rect=(180, 130, 220, 170),
        sizes=sizes,
        x_side="left",
        y_side="top",
        margin=8,
        gap=12,
    )
    assert actual == {
        "x_edge": (8.0, 8.0, 48.0, 28.0),
        "x_neighbor": (76.0, 140.0, 116.0, 160.0),
        "y_edge": (352.0, 8.0, 392.0, 28.0),
        "y_neighbor": (180.0, 66.0, 220.0, 86.0),
        "panel": (8.0, 252.0, 88.0, 292.0),
    }


def test_task3_structural_result_primitives_and_tags_are_stable():
    canvas = FakeCanvas()
    result = SimpleNamespace(
        outline=(Vec2(0, 0), Vec2(2, 0), Vec2(2, 1), Vec2(0, 1)),
        bends=(SimpleNamespace(p1=Vec2(0, 0.5), p2=Vec2(2, 0.5)),),
    )

    gui.render_structural_result(canvas, result, FakeTransform(), tags=("structural",))

    assert canvas.calls == [
        (
            "polygon",
            (0.0, 0.0, 20.0, 0.0, 20.0, 10.0, 0.0, 10.0),
            {"outline": "#30d158", "fill": "", "width": 2, "tags": ("structural",)},
        ),
        (
            "line",
            (0.0, 5.0, 20.0, 5.0),
            {
                "fill": "#0a84ff",
                "width": 1.5,
                "dash": (6, 4),
                "tags": ("structural",),
            },
        ),
    ]


def test_task3_secondary_scene_filters_primary_outline_and_bends(monkeypatch):
    scene = DrawingScene()
    primary = PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(1, 0), Vec2(1, 1)),
        layer="CUTTING",
        closed=True,
    )
    bend = LinePrimitive(Vec2(0, 0), Vec2(1, 0), "BEND")
    marking = LinePrimitive(Vec2(0, 1), Vec2(1, 1), "MARKING")
    secondary_cut = PolylinePrimitive(
        points=(Vec2(2, 2), Vec2(3, 2), Vec2(3, 3)),
        layer="CUTTING",
        closed=True,
    )
    scene.extend((primary, bend, marking, secondary_cut))
    captured = {}

    def fake_renderer(canvas, filtered_scene, transform):
        captured["canvas"] = canvas
        captured["scene"] = filtered_scene
        captured["transform"] = transform

    monkeypatch.setattr(gui, "render_drawing_scene", fake_renderer)
    canvas = FakeCanvas()
    transform = FakeTransform()

    gui.render_secondary_scene(canvas, scene, transform)

    assert captured["canvas"] is canvas
    assert captured["transform"] is transform
    assert captured["scene"].primitives == [marking, secondary_cut]


def test_task3_resolved_feature_layers_and_centerline_are_stable():
    canvas = FakeCanvas()
    features = (
        ResolvedCircle(
            center=Vec2(5, 6),
            radius=2,
            layer="BLIND_HOLE",
            add_centerline=True,
        ),
        ResolvedRect(
            center=Vec2(1, 1),
            width=2,
            height=4,
            layer="MARKING",
        ),
    )

    gui.render_resolved_features(canvas, features, FakeTransform())

    assert canvas.calls[0] == (
        "oval",
        (30.0, 40.0, 70.0, 80.0),
        {"outline": "#ff453a", "width": 2},
    )
    assert canvas.calls[1] == (
        "line",
        (30.0, 60.0, 70.0, 60.0),
        {"fill": "#bf5af2", "width": 1},
    )
    assert canvas.calls[2][0] == "polygon"
    assert canvas.calls[2][2] == {"outline": "#8e8e93", "fill": "", "width": 2}


def test_task3_surface_feature_wrapper_delegates_existing_resolver(monkeypatch):
    captured = {}
    resolved = (object(),)

    def fake_resolver(surface, features, width, height):
        captured["resolver"] = (surface, features, width, height)
        return resolved

    def fake_renderer(canvas, features, transform, *, color):
        captured["renderer"] = (canvas, features, transform, color)

    monkeypatch.setattr(gui, "resolve_surface_features", fake_resolver)
    monkeypatch.setattr(gui, "render_resolved_features", fake_renderer)
    canvas = FakeCanvas()
    transform = FakeTransform()
    features = [object()]

    gui.render_surface_user_features(
        canvas, "surface", features, 120, 80, transform
    )

    assert captured["resolver"] == ("surface", features, 120, 80)
    assert captured["renderer"] == (canvas, resolved, transform, "#ff9f0a")


def test_task3_feature_surface_wrapper_delegates_ae_authority(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_authority(surface_id, scene):
        captured["args"] = (surface_id, scene)
        return sentinel

    monkeypatch.setattr(gui.ae, "feature_surface_from_drawing_scene", fake_authority)
    scene = object()

    actual = gui.feature_surface_from_drawing_scene("door:r1", scene)

    assert actual is sentinel
    assert captured["args"] == ("door:r1", scene)


def test_task3_annotation_projection_primitives_and_dimension_rotation(monkeypatch):
    plan = SimpleNamespace(
        overall_dimensions=(
            SimpleNamespace(semantic_id="dim-y", axis="y"),
        )
    )
    projection = SimpleNamespace(
        annotation_plan=plan,
        primitives=(
            LinePrimitive(Vec2(0, 0), Vec2(2, 0), "DIMENSION"),
            TextPrimitive(
                "100",
                Vec2(1, 2),
                "DIMENSION",
                char_height=3,
                attachment_point=5,
                semantic_id="dim-y",
            ),
            TextPrimitive(
                "NOTE",
                Vec2(3, 4),
                "ANNOTATION",
                char_height=3,
                attachment_point=1,
                semantic_id=None,
            ),
        ),
    )
    captured = {}

    def fake_builder(render_data, *, part_key, strict):
        captured["builder"] = (render_data, part_key, strict)
        return projection

    monkeypatch.setattr(gui, "build_engineering_drawing_projection", fake_builder)
    canvas = FakeCanvas()
    render_data = object()

    actual = gui._draw_phase6_annotation_projection(
        canvas,
        render_data,
        FakeTransform(),
        part_key="door",
        strict=True,
    )

    assert actual is projection
    assert captured["builder"] == (render_data, "door", True)
    assert canvas.calls[0] == (
        "line",
        (0.0, 0.0, 20.0, 0.0),
        {
            "fill": "#30d158",
            "width": 1.2,
            "tags": ("phase6_engineering_annotation", "dimension"),
        },
    )
    assert canvas.calls[1][0] == "text"
    assert canvas.calls[1][2]["angle"] == 90
    assert canvas.calls[1][2]["fill"] == "#30d158"
    assert canvas.calls[2][0] == "text"
    assert canvas.calls[2][2]["angle"] == 0
    assert canvas.calls[2][2]["fill"] == "#ffd60a"


def test_task3_corner_dimension_overlay_uses_existing_text_authority(monkeypatch):
    monkeypatch.setattr(
        gui,
        "render_data_corner_dimension_text",
        lambda render_data: "CORNER-SUMMARY",
    )
    canvas = FakeCanvas()
    render_data = object()

    actual = gui._draw_phase6_corner_dimension_overlay(
        canvas, render_data, 400
    )

    assert actual == "CORNER-SUMMARY"
    assert canvas.calls == [
        (
            "text",
            (375.0, 42),
            {
                "anchor": gui.tk.NE,
                "text": "CORNER-SUMMARY",
                "fill": "#ffd60a",
                "justify": gui.tk.RIGHT,
                "font": ("Microsoft JhengHei", 9, "bold"),
                "width": 184,
                "tags": ("phase6_corner_dimensions",),
            },
        )
    ]


def test_task3_material_viewport_exact_fit_is_stable():
    transform, left, bottom, scale, top = gui._phase6_2d_material_viewport(
        (0, 0, 100, 50), 400, 300
    )

    assert left == pytest.approx(106.0)
    assert bottom == pytest.approx(252.0)
    assert top == pytest.approx(175.0)
    assert scale == pytest.approx(1.54)
    assert transform.scale == pytest.approx(1.54)
    assert transform.origin_x == pytest.approx(106.0)
    assert transform.origin_y == pytest.approx(252.0)


def test_task3_y_mirrored_preview_transform_is_presentation_only():
    class Base:
        scale = 2.5

        def __init__(self):
            self.last = None

        def world_to_canvas(self, point):
            self.last = point
            return point.x + 10, point.y + 20

    base = Base()
    transform = gui._YMirroredPreviewTransform(base, 100)

    actual = transform.world_to_canvas(Vec2(3, 25))

    assert transform.scale == 2.5
    assert transform.height == 100.0
    assert base.last == Vec2(3, 75)
    assert actual == (13.0, 95.0)
