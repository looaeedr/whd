# -*- coding: utf-8 -*-
"""Fail-closed operator Door indicator position drafting via canonical Engine geometry.

Only source validation lives here. The actual distance-to-offset and clamp
are the same sheetmetal_features owner used by the Door preview/physical holes.
"""
from __future__ import annotations

import math

from .fold_designer_snapshot_dimensions import normalize_fold_designer_indicator_offsets
from .sheetmetal_features import (
    DoorIndicatorContext, DoorIndicatorLayout, DoorIndicatorPosition,
    measure_door_indicator_position, door_indicator_offset_for_position,
)
from .sheetmetal_geometry import Vec2
from .sheetmetal_part_adapters import DoorFrameEdges


def _finite_input(value, label, *, positive=False, nonnegative=False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"DOOR_INDICATOR_POSITION_{label}_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"DOOR_INDICATOR_POSITION_{label}_INVALID") from exc
    if (not math.isfinite(number)
            or (positive and number <= 0.0)
            or (nonnegative and number < 0.0)):
        raise ValueError(f"DOOR_INDICATOR_POSITION_{label}_INVALID")
    return number


def _validated_source(
    context, *, frame_width, thickness, use_box_distance, gap_w, gap_h, frame_edges,
):
    if not isinstance(context, DoorIndicatorContext):
        raise ValueError("DOOR_INDICATOR_POSITION_CONTEXT_INVALID")
    if type(use_box_distance) is not bool:
        raise ValueError("DOOR_INDICATOR_POSITION_DISTANCE_MODE_INVALID")
    # A missing source means the existing four-sided default. A malformed
    # supplied frame must not silently become four supported finished edges.
    if frame_edges is not None:
        if not isinstance(frame_edges, DoorFrameEdges) or any(
            type(getattr(frame_edges, edge)) is not bool
            for edge in ("left", "right", "top", "bottom")
        ):
            raise ValueError("DOOR_INDICATOR_POSITION_FRAME_EDGES_INVALID")
    for key, positive in (("finished_width", True), ("finished_height", True),
                          ("left_fold", False), ("bottom_fold", False)):
        _finite_input(getattr(context, key), "CONTEXT", positive=positive)
    if context.center_override is not None:
        if not isinstance(context.center_override, Vec2):
            raise ValueError("DOOR_INDICATOR_POSITION_CONTEXT_INVALID")
        _finite_input(context.center_override.x, "CONTEXT")
        _finite_input(context.center_override.y, "CONTEXT")
    return (
        _finite_input(frame_width, "FRAME_WIDTH", nonnegative=True),
        _finite_input(thickness, "THICKNESS", positive=True),
        _finite_input(gap_w, "GAP_W", nonnegative=True),
        _finite_input(gap_h, "GAP_H", nonnegative=True),
    )


def project_operator_door_indicator_position(
    layout: DoorIndicatorLayout,
    context: DoorIndicatorContext, *, frame_width, thickness,
    use_box_distance, frame_edges=None, gap_w=3.5, gap_h=3.5,
) -> DoorIndicatorPosition:
    """Read the original canonical Door distance as a verified operator projection."""
    fw, t, gw, gh = _validated_source(
        context, frame_width=frame_width, thickness=thickness,
        use_box_distance=use_box_distance, gap_w=gap_w, gap_h=gap_h,
        frame_edges=frame_edges,
    )
    if not isinstance(layout, DoorIndicatorLayout) or layout.context != context:
        raise ValueError("DOOR_INDICATOR_POSITION_LAYOUT_INVALID")
    for point in (layout.left_lamp_center, layout.top_lamp_center):
        if not isinstance(point, Vec2):
            raise ValueError("DOOR_INDICATOR_POSITION_LAYOUT_INVALID")
        _finite_input(point.x, "LAYOUT")
        _finite_input(point.y, "LAYOUT")
    result = measure_door_indicator_position(
        layout, context, frame_width=fw, thickness=t,
        use_box_distance=use_box_distance, frame_edges=frame_edges,
        gap_w=gw, gap_h=gh,
    )
    for coordinate in (result.reference_x, result.reference_y,
                       result.target_x, result.target_y,
                       result.distance_x, result.distance_y):
        _finite_input(coordinate, "RESULT")
    return result


def propose_operator_door_indicator_offset_candidate(
    context: DoorIndicatorContext, layer_groups, *, x_distance, y_distance,
    frame_width, thickness, use_box_distance, frame_edges=None,
    gap_w=3.5, gap_h=3.5,
) -> Vec2:
    """Return a detached physical offset only after all live inputs are valid.

    Never writes a saved snapshot or GUI state; its caller installs both axes
    only after a complete validated candidate exists.
    """
    fw, t, gw, gh = _validated_source(
        context, frame_width=frame_width, thickness=thickness,
        use_box_distance=use_box_distance, gap_w=gap_w, gap_h=gap_h,
        frame_edges=frame_edges,
    )
    x, y = normalize_fold_designer_indicator_offsets(x_distance, y_distance)
    candidate = door_indicator_offset_for_position(
        context, layer_groups, x_distance=x, y_distance=y,
        frame_width=fw, thickness=t, use_box_distance=use_box_distance,
        frame_edges=frame_edges, gap_w=gw, gap_h=gh,
    )
    if not isinstance(candidate, Vec2):
        raise ValueError("DOOR_INDICATOR_POSITION_CANDIDATE_INVALID")
    _finite_input(candidate.x, "CANDIDATE")
    _finite_input(candidate.y, "CANDIDATE")
    return candidate
