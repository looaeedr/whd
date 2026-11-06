# -*- coding: utf-8 -*-
"""Engine-owned, headless projection of saved EndCap feature coordinates.

This derives an operator thumbnail's read-only source-feature outlines. It is
NOT canonical CUTTING/FinalScene, a certification or a DXF export capability.
"""
from __future__ import annotations

from math import isfinite
from .sheetmetal_feature_core import (
    CircleFeature, RectFeature, ProfileFeature,
    feature_finished_point, _rotate_local_point,
)
from .sheetmetal_geometry import Vec2


def _known_feature(item):
    if isinstance(item, (CircleFeature, RectFeature, ProfileFeature)):
        return item
    if isinstance(item, dict) and {"type", "x", "y", "params"} <= set(item):
        # Legacy hole editor payloads carry real coordinates/parameters.
        from ae_engine.sheetmetal_features import legacy_hole_to_feature
        return legacy_hole_to_feature(item)
    return None


def receiving_endcap_feature_preview_shapes(features, width, depth):
    """A testable list of real source circles and contours with their layers.

    Unsupported values are reported rather than drawn as invented features.
    Coordinates are in finished-face units, Y positive upward.
    """
    w, d = float(width), float(depth)
    if not all(isfinite(v) and v > 0 for v in (w, d)):
        raise ValueError("缺少有效封頭尾尺寸，無法預覽")
    if not isinstance(features, (list, tuple)):
        raise ValueError("封頭尾孔位必須是 Feature 清單")
    shapes, unsupported = [], 0
    for original in features:
        try:
            feature = _known_feature(original)
            if feature is None:
                unsupported += 1
                continue
            center = feature_finished_point(feature, w, d)
            layer = str(feature.layer)
            if isinstance(feature, CircleFeature):
                radius = float(feature.diameter) / 2
                if radius <= 0 or not isfinite(radius):
                    raise ValueError("invalid radius")
                shapes.append(("circle", layer, (center.x, center.y, radius)))
                continue
            if isinstance(feature, RectFeature):
                hw, hh = float(feature.width) / 2, float(feature.height) / 2
                if min(hw, hh) <= 0 or not all(map(isfinite, (hw, hh))):
                    raise ValueError("invalid rectangle")
                corners = (Vec2(-hw, -hh), Vec2(hw, -hh),
                           Vec2(hw, hh), Vec2(-hw, hh))
                vertices = tuple(
                    (center.x + _rotate_local_point(p, feature.rotation_deg).x,
                     center.y + _rotate_local_point(p, feature.rotation_deg).y)
                    for p in corners
                )
                shapes.append(("path", layer, (vertices, True)))
                continue
            if isinstance(feature, ProfileFeature):
                contours = feature.layered_profiles or (
                    (layer, feature.points, len(feature.points) >= 3),
                )
                if not contours:
                    raise ValueError("empty profile")
                for contour_layer, points, closed in contours:
                    if len(points) < 2:
                        raise ValueError("short profile")
                    vertices = tuple(
                        (center.x + _rotate_local_point(p, feature.rotation_deg).x,
                         center.y + _rotate_local_point(p, feature.rotation_deg).y)
                        for p in points
                    )
                    shapes.append(("path", str(contour_layer), (vertices, bool(closed))))
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
            unsupported += 1
    return tuple(shapes), unsupported


