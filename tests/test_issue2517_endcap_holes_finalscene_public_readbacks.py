"""#2517: main GUI EndCap hole replay and FinalScene dimensions use public Engine.

The physical Feature and finished mesh are authoritative; legacy GUI EndCap
hole dicts and dimension labels are read-only projections of those sources.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, FeatureAnchor,
    feature_to_legacy_hole as engine_projection,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.display_dimensions import resolve_operator_finished_dimensions as owner
from gui_modules.application import lifecycle as lifecycle_gui
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin
import phase6_project_file as project


def _endcap_features():
    return (
        CircleFeature(
            diameter=12.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(40.0, 45.0),
            layer="CUTTING",
            source_type="圓形",
        ),
        RectFeature(
            width=18.0, height=24.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(60.0, 80.0),
            layer="CUTTING",
            source_type="方形",
        ),
    )


def _formed_face():
    return [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 20.0, 0.0))]


@pytest.mark.parametrize("feature", _endcap_features())
def test_public_legacy_endcap_hole_projection_matches_original_physical_feature(feature):
    before = deepcopy(feature)
    assert api.feature_to_legacy_hole is engine_projection
    projected = api.feature_to_legacy_hole(feature, 400.0, 200.0)
    assert projected == engine_projection(feature, 400.0, 200.0)
    assert projected["x"] == feature.offset.x
    assert projected["y"] == feature.offset.y
    assert feature == before
    projected["params"]["custom-view-only"] = "not a Feature mutation"
    assert feature == before


def test_actual_saved_endcap_features_reload_and_keep_same_2d_legacy_readback(tmp_path):
    head, tail = _endcap_features()
    source = {
        "model": "金庫型", "w": 400.0, "h": 500.0,
        "d": 200.0, "t": 2.0, "fw": 25.0,
        "existing_parts": ["box_body", "head", "tail"],
        "part_features": {"head": [head], "tail": [tail]},
    }
    before = deepcopy(source)
    target = project.write_project(
        tmp_path / "endcap-readback.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    saved = project.read_project(target)["snapshot"]
    assert source == before
    assert saved["part_features"]["head"] == [head]
    assert saved["part_features"]["tail"] == [tail]
    for role, feature in (("head", head), ("tail", tail)):
        loaded = saved["part_features"][role][0]
        assert api.feature_to_legacy_hole(loaded, saved["w"], saved["d"]) == (
            engine_projection(feature, 400.0, 200.0)
        )


def test_invalid_endcap_projection_cannot_modify_canonical_features():
    features = _endcap_features()
    before = deepcopy(features)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        api.feature_to_legacy_hole(object(), 400.0, 200.0)
    assert features == before


def test_all_main_gui_endcap_restore_paths_use_public_feature_projection():
    source = Path(lifecycle_gui.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.sheetmetal_features"
        and any(alias.name == "feature_to_legacy_hole" for alias in node.names)
        for node in ast.walk(tree)
    )
    public = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "manufacturing_api"
        and n.func.attr == "project_operator_endcap_legacy_hole_rows"
    ]
    # Three GUI operations each stage *both* physical EndCap roles before
    # committing either legacy cache; direct six-per-hole writes are forbidden.
    assert len(public) == 3
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "manufacturing_api"
        and n.func.attr == "feature_to_legacy_hole"
        for n in ast.walk(tree)
    )
    assert not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "feature_to_legacy_hole"
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("part_key,expected", (
    ("box_body", (10.0, 20.0, 4.0)),
    ("door", (10.0, 20.0)),
))
def test_finalscene_gui_finished_dimensions_delegate_to_public_engine(
    monkeypatch, part_key, expected,
):
    triangles = _formed_face()
    before = deepcopy(triangles)
    request = SimpleNamespace(
        part_key=part_key, thickness=2.0,
        finished_dimensions=(99.0, 77.0),
    )
    observed = []

    def public(*args, **kwargs):
        observed.append((args, kwargs))
        return owner(*args, **kwargs)

    monkeypatch.setattr(api, "resolve_operator_finished_dimensions", public)
    result = Phase6FinalSceneRenderHelpersMixin._resolved_finished_dimensions(
        object(), request, triangles,
    )
    assert result == expected
    assert observed == [((part_key,), {
        "triangles": triangles, "thickness": 2.0,
        "fallback_dimensions": (99.0, 77.0),
    })]
    assert triangles == before


def test_finalscene_invalid_world_mesh_fails_closed_without_source_change():
    triangles = [[(0, 0, 0), (10, 0, 0)]]
    before = deepcopy(triangles)
    request = SimpleNamespace(
        part_key="box_body", thickness=2.0, finished_dimensions=(1.0, 1.0),
    )
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        Phase6FinalSceneRenderHelpersMixin._resolved_finished_dimensions(
            object(), request, triangles,
        )
    assert triangles == before


def test_finalscene_gui_does_not_import_private_finished_dimension_solver():
    from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin as mixin
    path = Path(__import__("phase6_final_scene_render_helpers").__file__)
    source = path.read_text(encoding="utf-8")
    assert "from ae_engine.display_dimensions import" not in source
    assert "manufacturing_api.resolve_operator_finished_dimensions(" in source
    assert callable(mixin._resolved_finished_dimensions)
