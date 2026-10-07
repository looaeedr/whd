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
