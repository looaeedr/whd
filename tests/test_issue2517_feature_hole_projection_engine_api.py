"""#2517 Engine, not GUI, projects finished-face features into legacy hole preview."""
from __future__ import annotations

import inspect

from ae_engine import manufacturing_api, project_finished_features_to_legacy_renderer_holes
from ae_engine.sheetmetal_features import CircleFeature, RectFeature, ProfileFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
import fold_designer_bridge as bridge


def _features():
    return (
        CircleFeature(diameter=6, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(10, 20)),
        ProfileFeature(
            points=(Vec2(1, 2), Vec2(3, 4)),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(0, 0),
        ),
        RectFeature(width=12, height=8, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(3, -2)),
    )


def test_engine_projects_supported_holes_without_inventing_profile_geometry():
    rows = project_finished_features_to_legacy_renderer_holes(_features(), 400, 600)
    assert rows == [
        {"type": "圓孔", "name": "孔1", "x": 10, "y": 20, "d1": 6, "d2": 0},
        {"type": "方孔", "name": "孔2", "x": 203, "y": 298, "d1": 12, "d2": 8},
    ]
    assert project_finished_features_to_legacy_renderer_holes is manufacturing_api.project_finished_features_to_legacy_renderer_holes
    assert bridge.project_features_to_original_holes(_features(), 400, 600) == rows
    assert project_finished_features_to_legacy_renderer_holes([], 400, 600) == []


def test_finished_face_anchor_and_original_features_remain_immutable():
    feature = CircleFeature(
        diameter=9, anchor=FeatureAnchor.TOP_LEFT,
        offset=Vec2(11, -6), layer="BLIND_HOLE",
    )
    original = (feature,)
    before = repr(feature)
    rows = project_finished_features_to_legacy_renderer_holes(original, 400, 600)
    assert rows == [
        {"type": "圓孔", "name": "孔1", "x": 11, "y": 594, "d1": 9, "d2": 0}
    ]
    assert repr(feature) == before
    assert original == (feature,)


def test_gui_projection_only_calls_public_engine_api(monkeypatch):
    calls = []
    def fake_engine(features, width, height):
        calls.append((features, width, height))
        return [{"type": "sentinel"}]
    monkeypatch.setattr(manufacturing_api, "project_finished_features_to_legacy_renderer_holes", fake_engine)
    features = _features()
    assert bridge.project_features_to_original_holes(features, 200, 300) == [{"type": "sentinel"}]
    assert calls == [(features, 200, 300)]
    source = inspect.getsource(bridge.project_features_to_original_holes)
    assert "manufacturing_api.project_finished_features_to_legacy_renderer_holes(" in source
    assert "feature_finished_point(" not in source
    assert "_ui_len(" not in source
    assert "CircleFeature" not in source
