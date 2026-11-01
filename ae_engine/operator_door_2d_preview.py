# -*- coding: utf-8 -*-
"""Engine projections for the operator door 2D divider/frame and indicator guides.

Only immutable geometry-derived view facts leave this module. GUI selects what
to draw, but never reconstructs Door cell boundaries, Family physical frames,
3D placement, or indicator reference distances from an internal formula.
"""
from __future__ import annotations

from .ae import FW as default_frame_width
from . import assembly_placement, door_dividers, inner_door_frames
from .cabinet_types import policy as cabinet_family_policy
from .sheetmetal_features import (
    DoorIndicatorContext,
    measure_door_indicator_position,
    resolve_door_indicator_dimension_guides,
    resolve_door_indicator_layout,
)
from .sheetmetal_geometry import Vec2


def project_operator_door_divider_frame_preview(
    project_snapshot, columns, val, *, layout_scope="main",
    handle_edges=None, model_name="",
):
    """Preserve legacy independent divider and inner-door-frame preview guards."""
    t_val = float(val.get("t", 2.0))
    total_w = float(project_snapshot.get("w", val.get("w", 0.0)))
    total_h = float(project_snapshot.get("h", val.get("h", 0.0)))
    divider_payloads = []
    frame_payloads = []

    try:
        normalized = tuple(
            (float(c[0]), tuple(float(h) for h in c[1])) for c in columns
        )
        dividers = door_dividers.derive_box_body_dividers(
            normalized,
            depth=float(val.get("d", 350.0)),
            thickness=t_val,
            layout_scope=layout_scope,
            handle_edges=handle_edges,
            model_name=model_name,
            frame_width=float(val.get("fw", default_frame_width)),
        )
        for div in dividers:
            placement = assembly_placement.resolve_assembly_placement(project_snapshot, div.stable_id)
            divider_payloads.append({
                "axis": str(div.axis),
                "span": float(div.span),
                "formed_core_depth": float(div.formed_core_depth),
                "world_offset": tuple(float(v) for v in placement.world_offset),
            })
    except Exception:
        pass

    try:
        if cabinet_family_policy.has_inner_door_frame_derivation(project_snapshot):
            frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(project_snapshot)
            for fset in frame_sets:
                for side in tuple(fset.included_sides):
                    if side not in {"top", "left", "right"}:
                        continue
                    stable_id = inner_door_frames.inner_door_frame_stable_id(fset.inner_door_id, side)
                    placement = assembly_placement.resolve_assembly_placement(project_snapshot, stable_id)
                    frame_payloads.append({
                        "side": str(side),
                        "span": float(fset.spans[side]),
                        "world_offset": tuple(float(v) for v in placement.world_offset),
                    })
    except Exception:
        pass

    return {
        "total_w": total_w,
        "total_h": total_h,
        "dividers": tuple(divider_payloads),
        "frames": tuple(frame_payloads),
    }



def project_operator_door_indicator_guides(
    finished_size, door_values, indicator_groups, spec, *,
    offset_x=0.0, offset_y=0.0,
):
    """Return canonical context/layout and X/Y guides; absent if not drawable."""
    indicator_context = None
    indicator_layout = None
    x_guide = None
    y_guide = None
    indicator_groups = tuple(indicator_groups or ())
    if indicator_groups:
        try:
            finished_w, finished_h = finished_size
            indicator_context = DoorIndicatorContext(
                finished_width=finished_w,
                finished_height=finished_h,
                left_fold=door_values["door_fold_l"],
                bottom_fold=door_values["door_fold_b"],
            )
            indicator_layout = resolve_door_indicator_layout(
                indicator_context,
                indicator_groups,
                Vec2(offset_x, offset_y),
            )
            position = measure_door_indicator_position(
                indicator_layout,
                indicator_context,
                frame_width=door_values["fw"],
                thickness=door_values["t"],
                use_box_distance=spec.use_box_distance,
                frame_edges=spec.frame_edges,
                gap_w=door_values["door_gap_w"],
                gap_h=door_values["door_gap_h"],
            )
            x_guide, y_guide = resolve_door_indicator_dimension_guides(position)
        except Exception:
            indicator_context = None
            indicator_layout = None
            x_guide = None
            y_guide = None


    return indicator_context, indicator_layout, x_guide, y_guide
