"""#2517: Hole Editor Canvas must consume public Engine feature geometry, not private solvers."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
    feature_reference_anchor, feature_reference_point,
    hit_test_resolved_features, resolve_surface_features,
)


def _circle(x=50.0, y=50.0, *, source_params=()):
    return CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y),
        source_params=tuple(source_params),
    )


@pytest.mark.parametrize("model_name", ["金庫型", "受電箱"])
def test_engine_canvas_projection_matches_canonical_geometry_for_both_families(model_name):
    # The resolved feature placement is generic and does not silently change
    # depending on the caller's cabinet model. Physical source remains Engine.
    surface = feature_surface_from_rect(model_name, Vec2(0, 0), Vec2(100, 100))
    feature = _circle()
    expected = tuple(resolve_surface_features(surface, [feature], 100, 100))
    actual = manufacturing_api.resolve_hole_editor_canvas_features(surface, [feature], 100, 100)
    assert isinstance(actual, tuple)
    assert actual == expected
    assert actual[0].center == Vec2(50, 50)
    assert manufacturing_api.hole_editor_canvas_reference_point(feature, 100, 100) == feature_reference_point(
        feature, feature_reference_anchor(feature), 100, 100,
    )
    probe = Vec2(50, 50)
    assert manufacturing_api.hit_test_hole_editor_canvas_features(probe, actual, tolerance=2.0) == hit_test_resolved_features(
        probe, expected, tolerance=2.0,
    ) == 0


def test_engine_canvas_rejects_invalid_holes_and_invalid_reference():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 100))
    with pytest.raises(ValueError, match="outside feature surface"):
        manufacturing_api.resolve_hole_editor_canvas_features(surface, [_circle(5, 50)], 100, 100)
    with pytest.raises(ValueError, match="invalid feature reference_anchor"):
        manufacturing_api.hole_editor_canvas_reference_point(
            _circle(source_params=(("reference_anchor", "not-an-anchor"),)), 100, 100,
        )
    with pytest.raises(ValueError, match="nonboolean"):
        manufacturing_api.hit_test_hole_editor_canvas_features(Vec2(50, 50), (), tolerance=True)


def test_canvas_view_delegates_feature_sources_to_public_engine_boundary():
    source = Path("phase6_hole_editor_canvas_view.py").read_text(encoding="utf-8")
    imports = [node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    assert "ae_engine.sheetmetal_features" not in imports
    assert "from ae_engine import manufacturing_api as _engine" in source
    assert "_engine.resolve_hole_editor_canvas_features(" in source
    assert "_engine.hole_editor_canvas_reference_point(" in source
    assert "_engine.hit_test_hole_editor_canvas_features(" in source
    assert "resolve_surface_features(" not in source
    assert "hit_test_resolved_features(" not in source
