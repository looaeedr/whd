"""Door and indicator manufacturing calculations and validation.

Depends only on baseline policy and engine/contracts; never imports manufacturing_api.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal, Mapping

from . import ae
from .dxf_serialization import save_scene_dxf
from . import manufacturing_verification as _manufacturing_verification
from . import manufacturing_export as _manufacturing_export
from . import manufacturing_requests as _manufacturing_requests
from . import manufacturing_render as _manufacturing_render
from .contracts import (
    FinalMaterialCollisionPart,
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    FeatureLike,
    FoldProfileSegment,
    IndicatorBoxPartSpec,
    ManufacturingContext,
    ManufacturingPolicy,
    PartExportResult,
    PartSpec,
)
from .sheetmetal_features import (
    BoxBodyFaceContext,
    CircleFeature,
    DoorIndicatorContext,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
    box_body_face_contexts_from_strip,
    feature_finished_point,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_door_indicator_layout,
)
from .sheetmetal_geometry import (
    EndCapAssemblySemantics,
    FourCornerTypePolicy,
    Vec2,
    resolve_endcap_policy_assembly_semantics,
)
from .sheetmetal_part_adapters import (
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_unknown_door_result,
    build_finished_reference_guide,
)
from .cabinet_types import policy as cabinet_family_policy

from .manufacturing_baseline_policy import resolve_policy, _call

def _resolved_door_params(spec: DoorPartSpec, context: ManufacturingContext | None = None):
    policy = resolve_policy(context)
    t = float(spec.thickness)
    material_fw = cabinet_family_policy.door_material_frame_width(
        spec.model_name, frame_width=float(spec.frame_width), thickness=t,
    )
    return dict(
        w=float(spec.width), h=float(spec.height), t=t, fw=material_fw,
        gap_w=float(spec.gap_w if spec.gap_w is not None else policy.door_gap_w),
        gap_h=float(spec.gap_h if spec.gap_h is not None else policy.door_gap_h),
        fold_left=float(spec.fold_left if spec.fold_left is not None else policy.door_fold_left),
        fold_right=float(spec.fold_right if spec.fold_right is not None else policy.door_fold_right),
        fold_top=float(spec.fold_top if spec.fold_top is not None else policy.door_fold_top),
        fold_bottom=float(spec.fold_bottom if spec.fold_bottom is not None else policy.door_fold_bottom),
    )


def _resolved_door_corner_policy(spec: DoorPartSpec, material_fw: float):
    if spec.corner_policy is None:
        return None
    return replace(spec.corner_policy, fw=float(material_fw))


def door_finished_face_size(
    spec: DoorPartSpec, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    p = _resolved_door_params(spec, context)
    return tuple(map(float, _call(
        ae.calculate_door_finished_size,
        p["w"], p["h"], p["fw"], p["gap_w"], p["gap_h"], p["t"],
        frame_edges=spec.frame_edges,
    )))


def door_indicator_offset_for_finished_center(
    spec: DoorPartSpec, groups, desired_center: Vec2,
    context: ManufacturingContext | None = None,
) -> Vec2:
    """Convert a desired finished-face center into AE's indicator layout offset."""
    finished_w, finished_h = door_finished_face_size(spec, context)
    local_context = DoorIndicatorContext(
        finished_width=float(finished_w), finished_height=float(finished_h),
        left_fold=0.0, bottom_fold=0.0,
    )
    base_center = local_context.group_center(tuple(int(v) for v in groups))
    return Vec2(
        float(desired_center.x) - float(base_center.x),
        float(desired_center.y) - float(base_center.y),
    )


def indicator_box_unfolded_size(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    """Return the shared indicator-box unfolded blank size."""
    normalized = tuple(int(v) for v in groups)
    if not normalized or any(v <= 0 for v in normalized):
        raise ValueError("指示燈盒至少需要一層且每層組數必須大於 0")
    data = ae.get_indicator_box_data(normalized, float(thickness))
    return float(data.params["w"]), float(data.params["h"])


def indicator_box_finished_face_size(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    """Return the assembled outside face of the shared indicator box."""
    policy = resolve_policy(context)
    total_w, total_h = indicator_box_unfolded_size(groups, thickness=thickness, context=context)
    t = float(thickness)
    fold = float(policy.indicator_box_fold)
    finished_w = total_w - 2.0 * fold + t
    finished_h = total_h - 2.0 * fold + t
    if finished_w <= 0 or finished_h <= 0:
        raise ValueError("指示燈盒成品尺寸無效")
    return finished_w, finished_h


def indicator_box_opening_size(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    """Return the box inner clear opening; this is also the main-Door cutout.

    Single source of truth:
    box unfolded -> box finished outside face -> subtract one sheet thickness
    from each side -> inner clear opening.
    """
    finished_w, finished_h = indicator_box_finished_face_size(
        groups, thickness=thickness, context=context
    )
    t = float(thickness)
    opening_w = finished_w - 2.0 * t
    opening_h = finished_h - 2.0 * t
    if opening_w <= 0 or opening_h <= 0:
        raise ValueError("指示燈盒內部淨開口尺寸無效")
    return opening_w, opening_h


def indicator_small_door_finished_size(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    """Small-door finished face = box inner opening minus the configured gap per side."""
    policy = resolve_policy(context)
    opening_w, opening_h = indicator_box_opening_size(
        groups, thickness=thickness, context=context
    )
    gap = float(policy.indicator_small_door_gap)
    finished_w = opening_w - 2.0 * gap
    finished_h = opening_h - 2.0 * gap
    if finished_w <= 0 or finished_h <= 0:
        raise ValueError("指示燈小門成品尺寸無效")
    return finished_w, finished_h


def indicator_box_opening_feature(
    groups, *, thickness: float, center: Vec2, context: ManufacturingContext | None = None
) -> RectFeature:
    opening_w, opening_h = indicator_box_opening_size(
        groups, thickness=thickness, context=context
    )
    return RectFeature(
        width=opening_w, height=opening_h,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(float(center.x), float(center.y)),
        layer="CUTTING", source_type="indicator_box_opening",
    )


def validate_door_indicator_fit(
    *,
    mode: str,
    groups,
    finished_width: float,
    finished_height: float,
    thickness: float,
    offset=(0.0, 0.0),
    context: ManufacturingContext | None = None,
) -> tuple[float, float]:
    """Reject Door-owned indicator geometry that does not fit its finished face.

    Returns the physical footprint W/H when valid.  ``indicator`` measures the
    real generated lamps/nameplate/MARKING circles including radii;
    ``indicator_box`` measures the box finished-face size, not its unfolded blank.
    """
    mode = str(mode or "none")
    fw = float(finished_width)
    fh = float(finished_height)
    t = float(thickness)
    if fw <= 0 or fh <= 0:
        raise ValueError("門板成品尺寸必須大於 0")
    if mode == "none":
        return (0.0, 0.0)

    normalized_groups = tuple(int(v) for v in groups)
    if not normalized_groups or any(v <= 0 for v in normalized_groups):
        raise ValueError("指示燈層/組數必須大於 0")
    ox, oy = float(offset[0]), float(offset[1])
    tol = 1e-6

    if mode == "indicator":
        door_context = DoorIndicatorContext(
            finished_width=fw, finished_height=fh, left_fold=0.0, bottom_fold=0.0
        )
        layout = resolve_door_indicator_layout(door_context, normalized_groups, Vec2(ox, oy))
        features = tuple(layout.features)
        if not features:
            return (0.0, 0.0)
        min_x = min(float(f.center.x) - float(f.radius) for f in features)
        max_x = max(float(f.center.x) + float(f.radius) for f in features)
        min_y = min(float(f.center.y) - float(f.radius) for f in features)
        max_y = max(float(f.center.y) + float(f.radius) for f in features)
        footprint = (max_x - min_x, max_y - min_y)
        if min_x < -tol or min_y < -tol or max_x > fw + tol or max_y > fh + tol:
            raise ValueError(
                f"指示燈排列超出門板範圍：配置 {footprint[0]:g}×{footprint[1]:g} mm，"
                f"門成品 {fw:g}×{fh:g} mm，位置 X={ox:g} Y={oy:g}"
            )
        return footprint

    if mode == "indicator_box":
        policy = resolve_policy(context)
        data = ae.get_indicator_box_data(normalized_groups, t)
        total_w = float(data.params["w"])
        total_h = float(data.params["h"])
        box_w = total_w - 2.0 * float(policy.indicator_box_fold) + t
        box_h = total_h - 2.0 * float(policy.indicator_box_fold) + t
        if box_w <= 0 or box_h <= 0:
            raise ValueError("指示燈盒成品尺寸無效")
        cx = fw / 2.0 + ox
        cy = fh / 2.0 + oy
        min_x, max_x = cx - box_w / 2.0, cx + box_w / 2.0
        min_y, max_y = cy - box_h / 2.0, cy + box_h / 2.0
        if min_x < -tol or min_y < -tol or max_x > fw + tol or max_y > fh + tol:
            raise ValueError(
                f"指示燈盒超出門板範圍：盒子成品 {box_w:g}×{box_h:g} mm，"
                f"門成品 {fw:g}×{fh:g} mm，位置 X={ox:g} Y={oy:g}"
            )
        return (box_w, box_h)

    raise ValueError(f"Unsupported door indicator mode: {mode!r}")


def _validate_door_part_indicator_fit(
    spec: DoorPartSpec, context: ManufacturingContext | None = None
) -> tuple[float, float] | None:
    """Final headless safety gate used immediately before any Door export."""
    if spec.door_indicator is None and spec.indicator_hole is None:
        return None
    finished_w, finished_h = door_finished_face_size(spec, context)
    if spec.door_indicator is not None:
        return validate_door_indicator_fit(
            mode="indicator", groups=spec.door_indicator,
            finished_width=finished_w, finished_height=finished_h,
            thickness=spec.thickness, offset=spec.door_indicator_offset, context=context,
        )
    hole_w, hole_h = (float(spec.indicator_hole[0]), float(spec.indicator_hole[1]))
    # The Door opening is the box finished face minus one thickness on each side.
    box_w, box_h = hole_w + 2.0 * float(spec.thickness), hole_h + 2.0 * float(spec.thickness)
    ox, oy = map(float, spec.door_indicator_offset)
    cx, cy = finished_w / 2.0 + ox, finished_h / 2.0 + oy
    tol = 1e-6
    if (
        cx - box_w / 2.0 < -tol or cy - box_h / 2.0 < -tol
        or cx + box_w / 2.0 > finished_w + tol or cy + box_h / 2.0 > finished_h + tol
    ):
        raise ValueError(
            f"指示燈盒超出門板範圍：盒子成品 {box_w:g}×{box_h:g} mm，"
            f"門成品 {finished_w:g}×{finished_h:g} mm，位置 X={ox:g} Y={oy:g}"
        )
    return (box_w, box_h)


def indicator_small_door_spec(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> DoorPartSpec:
    policy = resolve_policy(context)
    groups = tuple(int(v) for v in groups)
    finished_w, finished_h = indicator_small_door_finished_size(
        groups, thickness=float(thickness), context=context
    )
    t = float(thickness)
    source_w = finished_w + (policy.frame_width + 2.0 * t) * 2.0 + policy.door_gap_w * 2.0
    source_h = finished_h + (policy.frame_width + 2.0 * t) * 2.0 + policy.door_gap_h * 2.0
    fold = float(policy.indicator_small_door_fold)
    return DoorPartSpec(
        width=source_w, height=source_h, thickness=t,
        frame_width=float(policy.frame_width), model_name=None,
        gap_w=float(policy.door_gap_w), gap_h=float(policy.door_gap_h),
        fold_left=fold, fold_right=fold, fold_top=fold, fold_bottom=fold,
        indicator_window_groups=groups,
    )


def indicator_small_door_unfolded_size(
    groups, *, thickness: float, context: ManufacturingContext | None = None
) -> tuple[float, float]:
    """Return the small-door blank generated from the linked finished size."""
    spec = indicator_small_door_spec(groups, thickness=thickness, context=context)
    return tuple(map(float, _call(
        ae.calculate_door_blank_size,
        spec.width, spec.height, spec.thickness, spec.frame_width,
        spec.gap_w, spec.gap_h,
        spec.fold_left, spec.fold_right, spec.fold_top, spec.fold_bottom,
        frame_edges=spec.frame_edges,
    )))
