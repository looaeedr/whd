"""#2517 single-part FinalScene annotation physical Fold source is Engine API."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    manufacturing_api, project_independent_scene_bend_segments,
    project_independent_scene_annotation_paths,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _scene():
    scene = DrawingScene()
    scene.add_line((20, 10), (20, 70), layer="BEND")
    scene.add_line((30, 20), (70, 20), layer="MARKING")
    scene.add_circle((50, 40), 10, layer="BLIND_HOLE")
    scene.add_polyline(((40, 20), (60, 20), (60, 50)), layer="MARKING", closed=True)
    return scene


def _args():
    return (
        _scene(), ({"len": 100.0, "core": "W"},),
        ({"len": 80.0, "core": "D"},), (),
    )


def test_true_BEND_only_uses_fold_core_local_coordinates():
    scene, x, y, guides = _args()
    actual = project_independent_scene_bend_segments(scene, x, y, guides)
    assert actual == (
        ((-30.0, -30.0, 0.0), (-30.0, 30.0, 0.0)),
    )
    assert manufacturing_api.project_independent_scene_bend_segments is (
        project_independent_scene_bend_segments
    )


def test_real_marking_and_blind_hole_preserve_shapes_layers_and_closure():
    scene, x, y, guides = _args()
    rows = project_independent_scene_annotation_paths(scene, x, y, guides)
    assert len(rows) == 3
    assert [layer for layer, _ in rows] == ["MARKING", "BLIND_HOLE", "MARKING"]
    assert rows[0][1] == ((-20.0, -20.0, 0.0), (20.0, -20.0, 0.0))
    assert len(rows[1][1]) == 65
    assert rows[1][1][0] == pytest.approx(rows[1][1][-1])
    assert rows[2][1][-1] == rows[2][1][0]
    assert len(rows[2][1]) == 4
    assert manufacturing_api.project_independent_scene_annotation_paths is (
        project_independent_scene_annotation_paths
    )


def test_no_primitives_never_manufactures_a_preview_fallback():
    empty = DrawingScene()
    _, x, y, guides = _args()
    assert project_independent_scene_bend_segments(empty, x, y, guides) == ()
    assert project_independent_scene_annotation_paths(empty, x, y, guides) == ()


def test_GUI_only_renders_canonical_bend_and_annotation_styles(monkeypatch):
    lines = []
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=SimpleNamespace(
        plot=lambda *args, **kwargs: lines.append((args, kwargs)),
    )))
    sentinel = (((1, 2, 3), (4, 5, 6)),)
    captured = []
    def bends(*args):
        captured.append(("bend", args))
        return sentinel
    def markings(*args):
        captured.append(("marking", args))
        return (
            ("MARKING", ((1, 2, 3), (4, 5, 6))),
            ("BLIND_HOLE", ((2, 3, 4), (5, 6, 7))),
        )
    monkeypatch.setattr(
        manufacturing_api, "project_independent_scene_bend_segments", bends,
    )
    monkeypatch.setattr(
        manufacturing_api, "project_independent_scene_annotation_paths", markings,
    )
    args = _args()
    Phase6FinalSceneRenderHelpersMixin._draw_scene_bends(host, *args)
    Phase6FinalSceneRenderHelpersMixin._draw_scene_markings(host, *args)
    assert captured == [("bend", args), ("marking", args)]
    assert len(lines) == 3
    assert lines[0] == (([1, 4], [2, 5], [3, 6]), {
        "color": "#2563eb", "linewidth": 1.15,
        "linestyle": "-", "alpha": 0.95,
    })
    assert lines[1][1] == {
        "color": "#f59e0b", "linewidth": 2.2,
        "linestyle": "-", "alpha": 1.0, "zorder": 20,
    }
    assert lines[2][1] == {
        "color": "#ef4444", "linewidth": 1.0,
        "linestyle": "--", "alpha": 0.9, "zorder": 8,
    }
    for func, port in (
        (Phase6FinalSceneRenderHelpersMixin._draw_scene_bends,
         "project_independent_scene_bend_segments"),
        (Phase6FinalSceneRenderHelpersMixin._draw_scene_markings,
         "project_independent_scene_annotation_paths"),
    ):
        source = inspect.getsource(func)
        assert f"manufacturing_api.{port}(" in source
        assert "self._map_xy(" not in source
        assert "math.cos(" not in source


def test_Engine_owner_has_no_Tk_or_Phase6_import():
    from ae_engine import final_scene_independent_annotations as owner
    source = inspect.getsource(owner)
    assert "tkinter" not in source
    assert "matplotlib" not in source
    assert "phase6_final_scene" not in source
