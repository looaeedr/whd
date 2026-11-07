"""#2517: GUI 2D physical Feature surface and BoxBody baseline are public Engine readbacks."""
from __future__ import annotations

import ast
from copy import deepcopy
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.ae_door_indicator import feature_surface_from_drawing_scene as canonical_scene_surface
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, resolved_features_to_primitives
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor, ResolvedCircle
from ae_engine.sheetmetal_feature_surface import feature_surface_from_rect, resolve_surface_features
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.rendering import canvas_2d


def _scene():
    scene = DrawingScene()
    scene.add(PolylinePrimitive((
        Vec2(0, 0), Vec2(150, 0), Vec2(150, 90), Vec2(0, 90)
    ), layer="CUTTING", closed=True))
    return scene


def _surface_and_hole():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(150, 90))
    feature = CircleFeature(
        diameter=20.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(70, 45),
    )
    return surface, feature


def test_public_scene_surface_same_canonical_engine_callable_and_physical_outline():
    assert api.project_operator_feature_surface_from_drawing_scene is canonical_scene_surface
    assert ae_engine.project_operator_feature_surface_from_drawing_scene is canonical_scene_surface
    assert "project_operator_feature_surface_from_drawing_scene" in ae_engine.__all__
    scene = _scene()
    before = deepcopy(tuple(scene.primitives))
    expected = canonical_scene_surface("door", scene)
    actual = api.project_operator_feature_surface_from_drawing_scene("door", scene)
    assert actual.surface_id == expected.surface_id
    assert tuple(actual.polygon.bounds) == tuple(expected.polygon.bounds) == (0, 0, 150, 90)
    assert tuple(scene.primitives) == before


def test_public_surface_rejects_no_cutting_without_mutating_scene():
    scene = DrawingScene()
    with pytest.raises(ValueError, match="no primary CUTTING outline"):
        api.project_operator_feature_surface_from_drawing_scene("door", scene)
    assert scene.primitives == []


def test_public_box_body_baseline_scene_matches_original_engine_primitives_and_is_detached():
    source = {
        "left": [ResolvedCircle(Vec2(20, 20), 5.0, "CUTTING", True, "baseline_hole")],
        "back": [ResolvedCircle(Vec2(60, 40), 3.0, "MARKING")],
        "right": [],
    }
    before = deepcopy(source)
    assert "project_operator_box_body_face_baseline_scene" in ae_engine.__all__
    assert ae_engine.project_operator_box_body_face_baseline_scene is api.project_operator_box_body_face_baseline_scene
    for key in ("left", "back"):
        expected = resolved_features_to_primitives(source[key])
        result = api.project_operator_box_body_face_baseline_scene(key, source)
        assert isinstance(result, DrawingScene)
        assert tuple(result.primitives) == expected
        result.primitives.clear()
        assert source == before
    assert api.project_operator_box_body_face_baseline_scene("right", source) is None
    assert api.project_operator_box_body_face_baseline_scene("left", {}) is None


@pytest.mark.parametrize("face,faces,error", (
    ("BAD", {"left": []}, ValueError),
    ("left", None, TypeError),
    ("left", {"left": "bad source"}, TypeError),
    ("left", {"left": [123]}, TypeError),
))
def test_baseline_scene_bad_identity_or_source_rejects_without_source_mutation(face, faces, error):
    before = deepcopy(faces)
    with pytest.raises(error):
        api.project_operator_box_body_face_baseline_scene(face, faces)
    assert faces == before


def test_shared_canvas_hole_preview_uses_public_engine_and_same_canonical_positions():
    surface, feature = _surface_and_hole()
    expected = tuple(resolve_surface_features(surface, [feature], 150, 90))
    assert inspect.signature(canvas_2d.render_surface_user_features).parameters[
        "resolver"
    ].default is api.resolve_hole_editor_canvas_features
    rendered = []
    canvas_2d.render_surface_user_features(
        object(), surface, [feature], 150, 90, object(),
        feature_renderer=lambda _canvas, features, _transform, **kw: rendered.append((features, kw)),
    )
    assert len(rendered) == 1
    assert rendered[0][0] == expected
    assert rendered[0][1] == {"color": "#ff9f0a"}


def test_gui_main_and_canvas_surface_and_baseline_delegate_to_public_api(monkeypatch):
    import gui

    calls = []
    sentry = object()

    def project_surface(surface_id, scene):
        calls.append(("surface", surface_id, scene))
        return sentry

    monkeypatch.setattr(api, "project_operator_feature_surface_from_drawing_scene", project_surface)
    scene = _scene()
    assert canvas_2d.feature_surface_from_drawing_scene("door", scene) is sentry
    assert gui.feature_surface_from_drawing_scene("door", scene) is sentry
    assert calls == [("surface", "door", scene), ("surface", "door", scene)]

    captured = {}

    def render(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(gui, "_render_surface_user_features_impl", render)
    surface, feature = _surface_and_hole()
    canvas, transform = object(), object()
    gui.render_surface_user_features(canvas, surface, [feature], 150, 90, transform)
    assert captured["args"] == (canvas, surface, [feature], 150, 90, transform)
    assert captured["kwargs"]["resolver"] is api.resolve_hole_editor_canvas_features

    before = {"left": [ResolvedCircle(Vec2(22, 23), 4)]}
    host = SimpleNamespace(_box_body_baseline_faces=lambda val: before)
    def baseline_projection(face_key, faces):
        captured["face_key"] = face_key
        captured["faces"] = faces
        return sentry
    monkeypatch.setattr(api, "project_operator_box_body_face_baseline_scene", baseline_projection)
    assert gui.Phase6ApplicationHost._box_body_face_baseline_scene(host, "left", {}) is sentry
    assert captured["face_key"] == "left"
    assert captured["faces"] is before


def test_2d_gui_sources_no_longer_import_internal_physical_resolvers():
    import gui

    for module in (gui, canvas_2d):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert "ae_engine.ae_door_indicator" not in modules
        if module is canvas_2d:
            assert "import ae_engine.ae as ae" not in source
        assert "resolver=resolve_surface_features" not in source
    source = Path(gui.__file__).read_text(encoding="utf-8")
    assert hasattr(gui, "ae")  # required by legacy HoleEditorCompositionDependencies
    assert "ae_module=ae" not in inspect.getsource(gui.feature_surface_from_drawing_scene)
    assert "resolved_features_to_primitives(resolved)" not in source
    assert "manufacturing_api.project_operator_box_body_face_baseline_scene(" in source



def test_hole_editor_catalog_root_is_same_engine_owner_without_private_ae_dependency(monkeypatch):
    from ae_engine import ae
    from gui_modules.editors import hole_editor_composition as composition

    assert api.operator_hole_catalog_root_path is ae.baseline_hole_catalog_root_path
    assert ae_engine.operator_hole_catalog_root_path is ae.baseline_hole_catalog_root_path
    assert "operator_hole_catalog_root_path" in ae_engine.__all__
    assert api.operator_hole_catalog_root_path() == ae.baseline_hole_catalog_root_path()
    assert "ae" not in composition.HoleEditorCompositionDependencies.REQUIRED

    source = Path(composition.__file__).read_text(encoding="utf-8")
    assert "d.manufacturing_api.operator_hole_catalog_root_path()" in source
    assert "d.ae.baseline_hole_catalog_root_path()" not in source
    assert source.count("d.manufacturing_api.operator_hole_catalog_root_path()") == 1


def test_hole_editor_catalog_root_uses_public_engine_when_preparing_model(monkeypatch):
    from gui_modules.editors import hole_editor_composition as composition

    token = object()
    calls = []

    class SessionFactory:
        @staticmethod
        def create(*args, **kwargs):
            return token

    class Catalog:
        shape = "circle"
        diameter = 20.0
        name = "engine-catalog"
        process = "CUTTING"

    def public_root():
        calls.append("public-root")
        return "shared-source-root"

    def load_catalog(root):
        calls.append(("catalog", root))
        return [Catalog()]

    def load_pipe_catalog(root):
        calls.append(("pipe", root))
        return []

    monkeypatch.setattr(api, "operator_hole_catalog_root_path", public_root)
    host = SimpleNamespace(surface_features={"door": []})
    d = SimpleNamespace(
        _HoleEditorSessionFactory=SessionFactory,
        manufacturing_api=api,
        load_hole_catalog=load_catalog,
        load_pipe_catalog=load_pipe_catalog,
    )
    state = SimpleNamespace(
        host=host, d=d, part_key="door", feature_list_override=None,
        reference_guide=object(),
    )
    composition._prepare_model(state)
    assert state.hole_session is token
    assert state.general_catalog_defs[0].name == "engine-catalog"
    assert calls == ["public-root", ("catalog", "shared-source-root"), ("pipe", "shared-source-root")]
