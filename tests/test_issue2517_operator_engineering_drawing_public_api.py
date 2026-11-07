"""#2517: Door/indicator/base annotation projection uses only public Engine API."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.geometry import box

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.engineering_drawing import build_engineering_drawing_projection
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import door_render_host_adapter as host


def _render_data():
    scene = DrawingScene()
    scene.add(LinePrimitive(Vec2(0.0, 0.0), Vec2(100.0, 0.0), "CUTTING"))
    return SimpleNamespace(scene=scene, material=box(0.0, 0.0, 100.0, 60.0))


def test_original_engine_projection_callable_is_identical_across_public_exports():
    assert manufacturing_api.project_operator_engineering_drawing_annotations is build_engineering_drawing_projection
    assert ae_engine.project_operator_engineering_drawing_annotations is build_engineering_drawing_projection
    assert "project_operator_engineering_drawing_annotations" in ae_engine.__all__


@pytest.mark.parametrize("part_key", ("door", "base_plate", "indicator_door"))
def test_public_annotation_projection_preserves_canonical_scene_and_original_result(part_key):
    source = _render_data()
    before = deepcopy(tuple(source.scene.primitives))
    public = manufacturing_api.project_operator_engineering_drawing_annotations(
        source, part_key=part_key,
    )
    original = build_engineering_drawing_projection(source, part_key=part_key)
    assert public == original
    assert public.part_key == part_key
    assert public.primitives
    assert all(getattr(p, "layer", "") in {"DIMENSION", "TEXT"} for p in public.primitives)
    assert tuple(source.scene.primitives) == before


@pytest.mark.parametrize("invalid", (None, object(), SimpleNamespace(scene=None, material=None)))
def test_public_annotation_projection_rejects_noncanonical_source_without_fallback(invalid):
    with pytest.raises(ValueError, match="canonical PartRenderData"):
        manufacturing_api.project_operator_engineering_drawing_annotations(invalid)


def test_gui_annotation_adapter_delegates_public_engine_projection(monkeypatch):
    from gui_modules.application import door_render_host_adapter

    calls = []

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return "rendered"

    monkeypatch.setattr(door_render_host_adapter, "_draw_phase6_annotation_projection_impl", capture)
    scene = _render_data()
    canvas, transform = object(), object()
    result = host._draw_phase6_annotation_projection(
        canvas, scene, transform, part_key="door", strict=True,
    )
    assert result == "rendered"
    assert len(calls) == 1
    assert calls[0][0] == (canvas, scene, transform)
    assert calls[0][1] == {
        "part_key": "door",
        "strict": True,
        "projection_builder": manufacturing_api.project_operator_engineering_drawing_annotations,
    }


def test_gui_canvas_transform_is_the_existing_public_engine_type(monkeypatch):
    captured = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return "viewport"

    monkeypatch.setattr(host, "_phase6_2d_material_viewport_impl", capture)
    assert host._phase6_2d_material_viewport((0, 0, 100, 60), 640, 480) == "viewport"
    assert captured["transform_type"] is manufacturing_api.CanvasTransform


def test_gui_source_never_imports_engineering_drawing_or_internal_canvas_transform():
    source = Path(host.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module in {"ae_engine.engineering_drawing", "ae_engine.sheetmetal_features"}
        for node in ast.walk(tree)
    )
    assert "manufacturing_api.project_operator_engineering_drawing_annotations" in source
    assert "manufacturing_api.CanvasTransform" in source
