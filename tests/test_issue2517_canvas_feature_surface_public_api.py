"""#2517: GUI Canvas and Hole Editor consume public Engine surface/catalog sources."""
from __future__ import annotations

import ast
from copy import deepcopy
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import ae, manufacturing_api as api
from ae_engine.ae_door_indicator import feature_surface_from_drawing_scene as owner_surface
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_feature_surface import feature_surface_from_rect, resolve_surface_features
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.rendering import canvas_2d


def _scene():
    scene = DrawingScene()
    scene.add(PolylinePrimitive((
        Vec2(0, 0), Vec2(150, 0), Vec2(150, 90), Vec2(0, 90),
    ), layer="CUTTING", closed=True))
    return scene


def _surface_and_hole():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(150, 90))
    feature = CircleFeature(
        diameter=20.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(70, 45),
    )
    return surface, feature


def test_public_scene_surface_is_original_engine_callable_and_matches_real_cutting():
    assert api.project_operator_feature_surface_from_drawing_scene is owner_surface
    assert ae_engine.project_operator_feature_surface_from_drawing_scene is owner_surface
    assert "project_operator_feature_surface_from_drawing_scene" in ae_engine.__all__
    scene = _scene()
    old = deepcopy(tuple(scene.primitives))
    expected = owner_surface("door", scene)
    actual = api.project_operator_feature_surface_from_drawing_scene("door", scene)
    assert actual.surface_id == expected.surface_id
    assert tuple(actual.polygon.bounds) == tuple(expected.polygon.bounds) == (0, 0, 150, 90)
    assert tuple(scene.primitives) == old


def test_invalid_cutting_has_no_implicit_fallback_or_source_mutation():
    scene = DrawingScene()
    with pytest.raises(ValueError, match="no primary CUTTING outline"):
        api.project_operator_feature_surface_from_drawing_scene("door", scene)
    assert scene.primitives == []


def test_canvas_preview_uses_public_engine_with_original_finished_face_coordinates():
    surface, feature = _surface_and_hole()
    expected = tuple(resolve_surface_features(surface, [feature], 150, 90))
    assert inspect.signature(canvas_2d.render_surface_user_features).parameters["resolver"].default is (
        api.resolve_hole_editor_canvas_features
    )
    observed = []
    canvas_2d.render_surface_user_features(
        object(), surface, [feature], 150, 90, object(),
        feature_renderer=lambda _canvas, features, _transform, **kw: observed.append((features, kw)),
    )
    assert observed == [(expected, {"color": "#ff9f0a"})]


def test_main_gui_delegates_2d_canvas_and_cutting_surface_via_public_api(monkeypatch):
    import gui

    token = object()
    calls = []
    monkeypatch.setattr(api, "project_operator_feature_surface_from_drawing_scene", (
        lambda surface_id, scene: calls.append((surface_id, scene)) or token
    ))
    scene = _scene()
    assert canvas_2d.feature_surface_from_drawing_scene("door", scene) is token
    assert gui.feature_surface_from_drawing_scene("door", scene) is token
    assert calls == [("door", scene), ("door", scene)]

    captured = {}

    def capture(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(gui, "_render_surface_user_features_impl", capture)
    surface, feature = _surface_and_hole()
    ui_canvas, transform = object(), object()
    gui.render_surface_user_features(ui_canvas, surface, [feature], 150, 90, transform)
    assert captured["args"] == (ui_canvas, surface, [feature], 150, 90, transform)
    assert captured["kwargs"]["resolver"] is api.resolve_hole_editor_canvas_features


def test_original_hole_catalog_source_and_root_public_export_stay_identical():
    assert api.operator_hole_catalog_root_path is ae.baseline_hole_catalog_root_path
    assert ae_engine.operator_hole_catalog_root_path is ae.baseline_hole_catalog_root_path
    assert "operator_hole_catalog_root_path" in ae_engine.__all__
    assert api.operator_hole_catalog_root_path() == ae.baseline_hole_catalog_root_path()


def test_hole_editor_catalog_uses_public_engine_source_without_main_ae(monkeypatch):
    from gui_modules.editors import hole_editor_composition as comp

    assert "ae" not in comp.HoleEditorCompositionDependencies.REQUIRED
    source = Path(comp.__file__).read_text(encoding="utf-8")
    assert "d.manufacturing_api.operator_hole_catalog_root_path()" in source
    assert "d.ae.baseline_hole_catalog_root_path()" not in source

    marker = object()
    seen = []

    class SessionFactory:
        @staticmethod
        def create(*args, **kwargs):
            return marker

    class Catalog:
        shape = "circle"
        diameter = 20.0
        name = "engine"
        process = "CUTTING"

    def source_root():
        seen.append("root")
        return "engine-source"

    monkeypatch.setattr(api, "operator_hole_catalog_root_path", source_root)
    d = SimpleNamespace(
        _HoleEditorSessionFactory=SessionFactory,
        manufacturing_api=api,
        load_hole_catalog=lambda root: seen.append(("catalog", root)) or [Catalog()],
        load_pipe_catalog=lambda root: seen.append(("pipe", root)) or [],
    )
    state = SimpleNamespace(
        host=SimpleNamespace(surface_features={"door": []}),
        d=d, part_key="door", feature_list_override=None, reference_guide=object(),
    )
    comp._prepare_model(state)
    assert state.hole_session is marker
    assert seen == ["root", ("catalog", "engine-source"), ("pipe", "engine-source")]


def test_gui_2d_source_contains_no_private_ae_or_resolvers():
    import gui

    for mod in (gui, canvas_2d):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "import ae_engine.ae as ae" not in source
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert "ae_engine.ae_door_indicator" not in imports
        assert "resolver=resolve_surface_features" not in source
    main = Path(gui.__file__).read_text(encoding="utf-8")
    assert "manufacturing_api.project_operator_resolved_feature_drawing_primitives(resolved)" in main
