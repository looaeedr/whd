from __future__ import annotations

from dataclasses import dataclass

import pytest

import gui
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_geometry import Vec2


@pytest.mark.parametrize(
    ("flip_y", "expected"),
    [
        pytest.param(True, (16.0, 68.0), id="top-style-flipped-y"),
        pytest.param(False, (16.0, 92.0), id="bottom-style-original-y"),
    ],
)
def test_corner_preview_canvas_point_characterizes_current_projection(flip_y, expected):
    point = Vec2(3.0, 4.0)

    actual = gui._corner_preview_canvas_point(
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
def test_corner_preview_flip_y_characterizes_target_matrix(target_key, expected):
    assert gui._corner_preview_flip_y_for_target(target_key) is expected


def test_project_toolbar_presentation_characterizes_current_contract():
    assert gui._project_toolbar_presentation() == {
        "actions": (
            ("open", "開啟專案", "secondary"),
            ("save", "儲存專案", "primary"),
            ("save_as", "另存新檔", "secondary"),
        ),
        "primary_action": "save",
        "toolbar_padx": 10,
        "toolbar_pady": 4,
        "button_padx": 8,
        "button_pady": 2,
        "title": "WHD｜箱體板金工程工作台",
        "subtitle": "專案・板件・圖面・製造輸出",
    }


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


def test_render_drawing_scene_characterizes_canvas_projection_and_layer_styles():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (2, 0), (2, 1)], layer="CUTTING", closed=True)
    scene.add_polyline([(0, 2), (2, 2)], layer="MARKING", closed=False)
    scene.add_line((0, 1), (2, 1), layer="BEND")
    scene.add_circle((1, 1), 0.5, layer="CUTTING")
    scene.add_line((0, 3), (2, 3), layer="DATUM")
    before = tuple(scene.primitives)
    canvas = _RecordingCanvas()

    gui.render_drawing_scene(
        canvas,
        scene,
        _RecordingTransform(),
        skip_layers=("DATUM",),
    )

    assert tuple(scene.primitives) == before
    assert canvas.calls == [
        (
            "polygon",
            (1.0, 100.0, 5.0, 100.0, 5.0, 98.0),
            {"outline": "#30d158", "fill": "", "width": 2},
        ),
        (
            "line",
            (1.0, 96.0, 5.0, 96.0),
            {"fill": "#8e8e93", "width": 1.5},
        ),
        (
            "line",
            (1.0, 98.0, 5.0, 98.0),
            {"fill": "#0a84ff", "width": 1.5, "dash": (6, 4)},
        ),
        (
            "oval",
            (2.0, 97.0, 4.0, 99.0),
            {"outline": "#30d158", "width": 1.5},
        ),
    ]
