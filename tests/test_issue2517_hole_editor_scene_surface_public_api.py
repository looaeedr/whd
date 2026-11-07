# -*- coding: utf-8 -*-
"""#2517 Hole Editor DrawingScene primary CUTTING FeatureSurface public API."""
from inspect import getsource

import ae_engine
import pytest
from ae_engine import manufacturing_api
from ae_engine.ae_door_indicator import feature_surface_from_drawing_scene as owner
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _closed_polyline():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        "CUTTING", closed=True,
    ))
    return scene


def _exploded_cutting():
    scene = DrawingScene()
    points = (Vec2(0, 0), Vec2(120, 0), Vec2(120, 80), Vec2(0, 80))
    for i, point in enumerate(points):
        scene.add(LinePrimitive(point, points[(i + 1) % 4], "CUTTING"))
    return scene


def test_public_root_facade_original_engine_function_identity():
    assert manufacturing_api.operator_feature_surface_from_drawing_scene is owner
    assert ae_engine.operator_feature_surface_from_drawing_scene is owner
    assert "operator_feature_surface_from_drawing_scene" in ae_engine.__all__


@pytest.mark.parametrize("factory", [_closed_polyline, _exploded_cutting])
def test_original_canonical_cutting_contour_and_source_are_unchanged(factory):
    scene = factory()
    before = tuple(scene.primitives)
    actual = manufacturing_api.operator_feature_surface_from_drawing_scene("door", scene)
    expected = owner("door", scene)
    assert actual.surface_id == "door"
    assert actual.outline == expected.outline
    assert actual.polygon.equals(expected.polygon)
    assert actual.polygon.area > 0
    assert tuple(scene.primitives) == before


def test_invalid_source_rejected_without_producing_fake_surface():
    scene = DrawingScene()
    scene.add(LinePrimitive(Vec2(0, 0), Vec2(100, 0), "CUTTING"))
    before = tuple(scene.primitives)
    with pytest.raises(ValueError, match="no primary CUTTING outline"):
        manufacturing_api.operator_feature_surface_from_drawing_scene("door", scene)
    assert tuple(scene.primitives) == before


def test_real_gui_wrapper_no_longer_injects_private_ae(monkeypatch):
    import gui
    called = []

    def record(surface_id, scene):
        called.append((surface_id, scene))
        return "surface"

    monkeypatch.setattr(gui, "_feature_surface_from_drawing_scene_impl", record)
    original = _closed_polyline()
    assert gui.feature_surface_from_drawing_scene("door", original) == "surface"
    assert called == [("door", original)]
    assert "ae_module=ae" not in getsource(gui.feature_surface_from_drawing_scene)


def test_renderer_consumes_engine_public_api_without_low_level_ae(monkeypatch):
    from gui_modules.rendering import canvas_2d
    calls = []

    def public(surface_id, scene):
        calls.append((surface_id, scene))
        return owner(surface_id, scene)

    monkeypatch.setattr(manufacturing_api, "operator_feature_surface_from_drawing_scene", public)
    original = _exploded_cutting()
    result = canvas_2d.feature_surface_from_drawing_scene("door", original)
    assert result.polygon.area == pytest.approx(9600)
    assert calls == [("door", original)]
    assert "import ae_engine.ae" not in getsource(canvas_2d)
