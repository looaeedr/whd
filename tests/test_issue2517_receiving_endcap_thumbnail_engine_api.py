"""#2517: headless Engine owns Receiving Head/Tail thumbnail feature shapes."""
from __future__ import annotations
import inspect
import math
import pytest
from ae_engine import manufacturing_api
from ae_engine.sheetmetal_feature_core import FeatureAnchor, CircleFeature, RectFeature, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import receiving_endcap_thumbnail as gui_thumb


def test_public_engine_source_feature_projection_and_existing_gui_delegate():
    features = (
        CircleFeature(diameter=20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(40, 30), layer="CUTTING"),
        RectFeature(width=40, height=20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(120, 60), layer="MARKING", rotation_deg=90),
    )
    result = manufacturing_api.receiving_endcap_feature_preview_shapes(features, 200, 100)
    assert result[1] == 0
    assert result[0][0] == ("circle", "CUTTING", (40, 30, 10))
    assert result[0][1][0:2] == ("path", "MARKING")
    assert set(result[0][1][2][0]) == {(130, 40), (130, 80), (110, 80), (110, 40)}
    assert gui_thumb.endcap_preview_geometry(features, 200, 100) == result


def test_public_engine_renders_saved_legacy_and_profile_layers_without_fabricating_geometry():
    legacy = {"type": "圓形", "x": 55, "y": 25,
              "params": {"diameter": 12, "layer": "CUTTING"}}
    profile = ProfileFeature(
        points=(Vec2(0, 0), Vec2(15, 0), Vec2(15, 15)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(20, 20),
        layer="CUTTING",
    )
    shapes, unsupported = manufacturing_api.receiving_endcap_feature_preview_shapes(
        (legacy, profile, {"tag": "unknown"}), 200, 100,
    )
    assert unsupported == 1
    assert shapes[0] == ("circle", "CUTTING", (55.0, 25.0, 6.0))
    assert shapes[1] == ("path", "CUTTING", (((20, 20), (35, 20), (35, 35)), True))


@pytest.mark.parametrize("width,depth", [(math.nan, 100), (200, math.inf), (0, 100), (-1, 100)])
def test_public_engine_fails_closed_on_invalid_preview_face(width, depth):
    with pytest.raises(ValueError, match="尺寸"):
        manufacturing_api.receiving_endcap_feature_preview_shapes((), width, depth)


def test_public_engine_rejects_non_feature_collection():
    with pytest.raises(ValueError, match="Feature 清單"):
        manufacturing_api.receiving_endcap_feature_preview_shapes(None, 200, 100)


def test_gui_contains_only_api_delegation_and_canvas_presentation_not_feature_rotation():
    source = inspect.getsource(gui_thumb)
    assert "manufacturing_api.receiving_endcap_feature_preview_shapes(" in source
    assert "feature_finished_point(" not in source
    assert "_rotate_local_point(" not in source
    assert "legacy_hole_to_feature(" not in source
    assert "paint_endcap_thumbnail(" in source
