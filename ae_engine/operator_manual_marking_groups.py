"""#3413 manual MARKING groups on one Engine-qualified physical sheet.

A group is ONE ProfileFeature/Undo/persisted identity.  Member IDs and offsets
are local to its nominal center and pre-transform axes; changing spacing,
rotating or reflecting never reassigns member IDs or discards offsets.  The
stored physical ink is independently checked against the complete source arms
at every public production boundary.  No GUI/Tk dependency.
"""
from __future__ import annotations

from dataclasses import replace
from math import cos, sin, radians, hypot
from uuid import uuid4

from shapely.geometry import LineString, Point

from .sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from .sheetmetal_geometry import Vec2

MANUAL_GROUP_SOURCE = "WHD_MANUAL_MARKING_GROUP_V1"
KINDS = ("cross", "l", "pair_l", "quad_l")
MEMBERS = {
    "cross": ("cross",),
    "l": ("corner",),
    "pair_l": ("left", "right"),
    "quad_l": ("bottom_left", "bottom_right", "top_left", "top_right"),
}
_KEYS = ("kind", "group_id", "spacing_x", "spacing_y", "arm_x", "arm_y",
         "pattern", "dash", "gap", "angle", "mirror_vertical", "members")
_EPS = 1e-7


def is_manual_group(feature):
    return (getattr(feature, "source_type", None) == MANUAL_GROUP_SOURCE
            or isinstance(feature, dict) and feature.get("source_type") == MANUAL_GROUP_SOURCE)


def _finite(raw, field, *, positive=False):
    from .operator_manual_marking import _finite as validate
    return validate(raw, field, positive=positive)


def _parameters(feature):
    if (not isinstance(feature, ProfileFeature)
            or feature.source_type != MANUAL_GROUP_SOURCE
            or feature.layer != "MARKING"
            or feature.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE
            or feature.rotation_deg != 0
            or feature.points != ()):
        raise ValueError("MANUAL_GROUP_INVALID_FEATURE")
    params = tuple(feature.source_params)
    if tuple(k for k, _ in params) != _KEYS:
        raise ValueError("MANUAL_GROUP_SOURCE_FIELDS_CHANGED")
    row = dict(params)
    kind = row["kind"]
    if kind not in KINDS:
        raise ValueError("MANUAL_GROUP_UNKNOWN_KIND")
    if not isinstance(row["group_id"], str) or not row["group_id"]:
        raise ValueError("MANUAL_GROUP_MISSING_ID")
    # A group has no invented X/Y spacing defaults. Missing required
    # dimensions must be distinguished from malformed numeric inputs.
    if kind in ("pair_l", "quad_l") and row["spacing_x"] in ("", None):
        raise ValueError("MANUAL_GROUP_SPACING_X_REQUIRED")
    if kind == "quad_l" and row["spacing_y"] in ("", None):
        raise ValueError("MANUAL_GROUP_SPACING_Y_REQUIRED")
    for key in ("spacing_x", "spacing_y", "arm_x", "arm_y", "dash", "gap", "angle"):
        row[key] = _finite(row[key], key, positive=key in ("arm_x", "arm_y", "dash", "gap"))
    if kind in ("pair_l", "quad_l") and row["spacing_x"] <= 0:
        raise ValueError("MANUAL_GROUP_SPACING_X_REQUIRED")
    if kind == "quad_l" and row["spacing_y"] <= 0:
        raise ValueError("MANUAL_GROUP_SPACING_Y_REQUIRED")
    if row["spacing_x"] < 0 or row["spacing_y"] < 0:
        raise ValueError("MANUAL_GROUP_NEGATIVE_SPACING")
    if row["pattern"] not in ("solid", "dashed"):
        raise ValueError("MANUAL_GROUP_BAD_PATTERN")
    if type(row["mirror_vertical"]) is not bool:
        raise ValueError("MANUAL_GROUP_BAD_MIRROR")
    raw_members = row["members"]
    if not isinstance(raw_members, (tuple, list)):
        raise ValueError("MANUAL_GROUP_BAD_MEMBERS")
    members = []
    for item in raw_members:
        if not isinstance(item, (tuple, list)) or len(item) != 3:
            raise ValueError("MANUAL_GROUP_BAD_MEMBER_OFFSET")
        member_id, dx, dy = item
        if not isinstance(member_id, str):
            raise ValueError("MANUAL_GROUP_BAD_MEMBER_ID")
        members.append((member_id, _finite(dx, "offset_x"), _finite(dy, "offset_y")))
    if tuple(x[0] for x in members) != MEMBERS[kind]:
        raise ValueError("MANUAL_GROUP_MEMBER_IDS_CHANGED")
    row["members"] = tuple(members)
    _finite(feature.offset.x, "center_x")
    _finite(feature.offset.y, "center_y")
    return row


def _member_local_positions(p):
    sx = p["spacing_x"] / 2
    sy = p["spacing_y"] / 2
    origin = {
        "cross": (0.0, 0.0),
        "corner": (0.0, 0.0),
        "left": (-sx, 0.0),
        "right": (sx, 0.0),
        "bottom_left": (-sx, -sy),
        "bottom_right": (sx, -sy),
        "top_left": (-sx, sy),
        "top_right": (sx, sy),
    }
    return {
        member_id: Vec2(origin[member_id][0] + dx, origin[member_id][1] + dy)
        for member_id, dx, dy in p["members"]
    }


def _rotated_mirrored(point, p):
    angle = radians(p["angle"])
    x = point.x * cos(angle) - point.y * sin(angle)
    y = point.x * sin(angle) + point.y * cos(angle)
    if p["mirror_vertical"]:
        x = -x
    return Vec2(x, y)


def _local_strokes(p):
    centers = _member_local_positions(p)
    ax, ay = p["arm_x"], p["arm_y"]
    strokes = []
    for member_id, center in centers.items():
        if member_id == "cross":
            offsets = (((-ax / 2, 0), (ax / 2, 0)),
                       ((0, -ay / 2), (0, ay / 2)))
        else:
            vx = -1 if member_id in ("right", "bottom_right", "top_right") else 1
            vy = -1 if member_id in ("top_left", "top_right") else 1
            offsets = (((0, 0), (vx * ax, 0)),
                       ((0, 0), (0, vy * ay)))
        for a, b in offsets:
            start = _rotated_mirrored(Vec2(center.x + a[0], center.y + a[1]), p)
            end = _rotated_mirrored(Vec2(center.x + b[0], center.y + b[1]), p)
            strokes.append((member_id, start, end))
    return tuple(strokes)


def _canonical_ink(p):
    from .operator_manual_marking import _segments
    return tuple(("MARKING", pair, False)
                 for _id, start, end in _local_strokes(p)
                 for pair in _segments(start, end, p["pattern"], p["dash"], p["gap"]))


def _rebuild(feature, params):
    pairs = tuple((k, params[k]) for k in _KEYS)
    provisional = replace(feature, source_params=pairs, layered_profiles=())
    checked = _parameters(provisional)
    return replace(provisional, layered_profiles=_canonical_ink(checked))


def source_group(feature):
    """Validate the durable source and ALL real ink, including dash omissions.

    Return source kind, pattern and full-length real-world arm segments, never
    just the visible dash segments.
    """
    p = _parameters(feature)
    expected = _canonical_ink(p)
    actual = tuple(feature.layered_profiles)
    if len(actual) != len(expected):
        raise ValueError("MANUAL_GROUP_INK_CHANGED")
    for (layer, points, closed), (want_layer, want_points, want_closed) in zip(actual, expected):
        if layer != want_layer or type(closed) is not bool or closed != want_closed or len(points) != 2:
            raise ValueError("MANUAL_GROUP_INK_CHANGED")
        if any(hypot(a.x-b.x, a.y-b.y) > _EPS for a, b in zip(points, want_points)):
            raise ValueError("MANUAL_GROUP_INK_CHANGED")
    lines = tuple(
        LineString(((feature.offset.x + a.x, feature.offset.y + a.y),
                    (feature.offset.x + b.x, feature.offset.y + b.y)))
        for _id, a, b in _local_strokes(p)
    )
    return p["kind"], p["pattern"], lines


def group_parameters(feature):
    """Immutable-friendly operator projection; never expose mutable internals."""
    return dict(_parameters(feature))


def group_member_world_points(feature):
    p = _parameters(feature)
    return tuple((member_id,
                  Vec2(feature.offset.x + q.x, feature.offset.y + q.y))
                 for member_id, center in _member_local_positions(p).items()
                 for q in (_rotated_mirrored(center, p),))


def nearest_group_member(feature, point):
    if not isinstance(point, Vec2):
        raise ValueError("MANUAL_GROUP_EXPECTED_POINT")
    return min(group_member_world_points(feature),
               key=lambda member: hypot(point.x-member[1].x, point.y-member[1].y))[0]


def _apply(feature, changes, *, part_key=None, context=None, existing_features=None):
    p = _parameters(feature)
    p.update(changes)
    result = _rebuild(feature, p)
    if context is not None:
        from .operator_manual_marking import validate_physical_manual_markings
        if part_key != context.part_key or existing_features is None:
            raise ValueError("MANUAL_GROUP_PHYSICAL_ID_CHANGED")
        revised = tuple(result if f is feature else f for f in existing_features)
        if result not in revised:
            raise ValueError("MANUAL_GROUP_NOT_IN_SHEET")
        validate_physical_manual_markings(
            part_key, context.render_data, revised, surface=context.feature_surface,
            width=context.width, height=context.height,
        )
    return result


def create_physical_manual_marking_group(
    part_key, context, existing_features, *, kind, center,
    arm_x, arm_y, spacing_x=0, spacing_y=0, pattern="solid", dash=10, gap=5,
    angle=0, mirror_vertical=False,
):
    from .operator_manual_marking import (
        require_first_sheet_manual_marking_render, validate_physical_manual_markings,
    )
    if context is None or part_key != context.part_key:
        raise ValueError("MANUAL_GROUP_PHYSICAL_ID_CHANGED")
    require_first_sheet_manual_marking_render(part_key, context.render_data)
    if kind not in KINDS or not isinstance(center, Vec2):
        raise ValueError("MANUAL_GROUP_INVALID_KIND_OR_CENTER")
    params = dict(kind=kind, group_id=uuid4().hex,
                  spacing_x=spacing_x, spacing_y=spacing_y,
                  arm_x=arm_x, arm_y=arm_y, pattern=pattern, dash=dash, gap=gap,
                  angle=angle, mirror_vertical=mirror_vertical,
                  members=tuple((mid, 0.0, 0.0) for mid in MEMBERS[kind]))
    empty = ProfileFeature(
        points=(), anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=center, layer="MARKING", source_type=MANUAL_GROUP_SOURCE,
        rotation_deg=0,
    )
    result = _rebuild(empty, params)
    validate_physical_manual_markings(
        part_key, context.render_data, tuple(existing_features)+(result,),
        surface=context.feature_surface, width=context.width, height=context.height,
    )
    return result


def edit_physical_manual_group(feature, *, member_id=None, offset_x=None, offset_y=None,
                               spacing_x=None, spacing_y=None, arm_x=None, arm_y=None,
                               angle=None, mirror_vertical=None, center=None,
                               part_key=None, context=None, existing_features=None):
    p = _parameters(feature)
    changes = {}
    for key, value in (("spacing_x", spacing_x), ("spacing_y", spacing_y),
                       ("arm_x", arm_x), ("arm_y", arm_y), ("angle", angle),
                       ("mirror_vertical", mirror_vertical)):
        if value is not None:
            changes[key] = value
    if member_id is not None:
        if member_id not in MEMBERS[p["kind"]]:
            raise ValueError("MANUAL_GROUP_BAD_MEMBER_ID")
        changes["members"] = tuple(
            (mid, offset_x if mid == member_id and offset_x is not None else dx,
             offset_y if mid == member_id and offset_y is not None else dy)
            for mid, dx, dy in p["members"]
        )
    candidate = _apply(
        feature, changes, part_key=part_key, context=context,
        existing_features=existing_features,
    )
    if center is not None:
        if not isinstance(center, Vec2):
            raise ValueError("MANUAL_GROUP_EXPECTED_CENTER")
        candidate = replace(candidate, offset=center)
        if context is not None:
            from .operator_manual_marking import validate_physical_manual_markings
            updated = tuple(candidate if f is feature else f for f in existing_features)
            validate_physical_manual_markings(
                part_key, context.render_data, updated, surface=context.feature_surface,
                width=context.width, height=context.height,
            )
    return candidate
