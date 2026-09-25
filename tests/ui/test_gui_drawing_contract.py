from __future__ import annotations

from dataclasses import dataclass

import pytest

from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.drawing import (
    _corner_preview_canvas_point,
    _corner_preview_flip_y_for_target,
    render_drawing_scene,
)


@pytest.mark.parametrize(
    ("flip_y", "expected"),
    [
        pytest.param(True, (16.0, 68.0), id="top-style-flipped-y"),
        pytest.param(False, (16.0, 92.0), id="bottom-style-original-y"),
    ],
)
def test_corner_preview_projection_preserves_operator_orientation(flip_y, expected):
    point = Vec2(3.0, 4.0)

    actual = _corner_preview_canvas_point(
        point,
        ox=10.0,
        oy=100.0,
        scale=2.0,
        span=20.0,
        flip_y=flip_y,
    )

    assert actual == expected


@pytest.mark.parametrize(
    ("target_key", "expected"),
    [
        pytest.param("top", True, id="top"),
        pytest.param("top_left", True, id="top-left"),
        pytest.param("top_right", True, id="top-right"),
        pytest.param("bottom", False, id="bottom"),
        pytest.param("bottom_left", False, id="bottom-left"),
        pytest.param("bottom_right", False, id="bottom-right"),
        pytest.param("", True, id="empty-defaults-to-top-style"),
        pytest.param(None, True, id="none-defaults-to-top-style"),
        pytest.param("  bottom  ", False, id="whitespace-normalized"),
    ],
)
def test_corner_preview_target_family_preserves_flip_semantics(target_key, expected):
    assert _corner_preview_flip_y_for_target(target_key) is expected


@dataclass
class _RecordingTransform:
    scale: float = 2.0

    def world_to_canvas(self, point):
        return (1.0 + float(point.x) * self.scale, 100.0 - float(point.y) * self.scale)


class _RecordingCanvas:
    def __init__(self):
        self.calls = []

    def create_polygon(self, *args, **kwargs):
        self.calls.append(("polygon", args, kwargs))

    def create_line(self, *args, **kwargs):
        self.calls.append(("line", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.calls.append(("oval", args, kwargs))


def test_render_drawing_scene_preserves_semantic_projection_without_mutating_source():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (2, 0), (2, 1)], layer="CUTTING", closed=True)
    scene.add_line((0, 2), (2, 2), layer="MARKING")
    scene.add_line((0, 1), (2, 1), layer="BEND")
    scene.add_circle((1, 1), 0.5, layer="CUTTING")
    scene.add_line((0, 3), (2, 3), layer="DATUM")
    before = tuple(scene.primitives)
    canvas = _RecordingCanvas()

    render_drawing_scene(
        canvas,
        scene,
        _RecordingTransform(),
        skip_layers=("DATUM",),
    )

    assert tuple(scene.primitives) == before
    assert [name for name, _, _ in canvas.calls] == ["polygon", "line", "line", "oval"]

    polygon = canvas.calls[0]
    marking = canvas.calls[1]
    bend = canvas.calls[2]
    circle = canvas.calls[3]

    assert polygon[1] == (1.0, 100.0, 5.0, 100.0, 5.0, 98.0)
    assert marking[1] == (1.0, 96.0, 5.0, 96.0)
    assert bend[1] == (1.0, 98.0, 5.0, 98.0)
    assert circle[1] == (2.0, 97.0, 4.0, 99.0)

    assert polygon[2]["outline"] == "#30d158"
    assert marking[2]["fill"] == "#8e8e93"
    assert bend[2]["fill"] == "#0a84ff"
    assert circle[2]["outline"] == "#30d158"
    assert "dash" not in marking[2]
    assert bend[2].get("dash") == (6, 4)
