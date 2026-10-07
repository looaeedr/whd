from __future__ import annotations

import inspect

from ae_engine import sheetmetal_features
from ae_engine import sheetmetal_feature_core


def test_issue1347_core_owner_preserves_public_feature_types():
    assert sheetmetal_features.FeatureAnchor is sheetmetal_feature_core.FeatureAnchor
    assert sheetmetal_features.CircleFeature is sheetmetal_feature_core.CircleFeature
    assert sheetmetal_features.ResolvedRect is sheetmetal_feature_core.ResolvedRect
    assert sheetmetal_features.BoxBodyFaceContext is sheetmetal_feature_core.BoxBodyFaceContext
    assert sheetmetal_features.resolve_box_body_face_features is sheetmetal_feature_core.resolve_box_body_face_features


def test_issue1347_core_owner_is_one_way_and_reduces_facade():
    facade = inspect.getsource(sheetmetal_features)
    owner = inspect.getsource(sheetmetal_feature_core)
    assert len(facade.splitlines()) < 1700
    assert len(owner.splitlines()) < 400
    assert "class CircleFeature" not in facade
    assert "class CircleFeature" in owner
    assert "from .sheetmetal_features import" not in owner
    assert "import ae_engine.sheetmetal_features" not in owner


def test_issue1347_surface_owner_is_extracted_one_way():
    from ae_engine import sheetmetal_feature_surface
    assert sheetmetal_features.FeatureSurface is sheetmetal_feature_surface.FeatureSurface
    assert sheetmetal_features.feature_surface_from_rect is sheetmetal_feature_surface.feature_surface_from_rect
    assert sheetmetal_features.move_feature_within_surface is sheetmetal_feature_surface.move_feature_within_surface
    assert sheetmetal_features.build_feature_placement_guides is sheetmetal_feature_surface.build_feature_placement_guides
    assert len(inspect.getsource(sheetmetal_features).splitlines()) < 1400
    owner = inspect.getsource(sheetmetal_feature_surface)
    assert "from .sheetmetal_features import" not in owner
    assert "import ae_engine.sheetmetal_features" not in owner


def test_issue1347_reference_owner_is_extracted_one_way():
    from ae_engine import sheetmetal_feature_reference
    assert sheetmetal_features.ReferenceAnchor is sheetmetal_feature_reference.ReferenceAnchor
    assert sheetmetal_features.reference_distances is sheetmetal_feature_reference.reference_distances
    assert sheetmetal_features.generate_round_fill is sheetmetal_feature_reference.generate_round_fill
    assert sheetmetal_features.generate_round_refill is sheetmetal_feature_reference.generate_round_refill
    assert len(inspect.getsource(sheetmetal_features).splitlines()) < 1050
    owner = inspect.getsource(sheetmetal_feature_reference)
    assert "from .sheetmetal_features import" not in owner
    assert "import ae_engine.sheetmetal_features" not in owner
