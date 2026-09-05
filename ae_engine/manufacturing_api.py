# -*- coding: utf-8 -*-
"""Headless manufacturing boundary for the existing AE engine.

This module is the stable public boundary inside the ``ae_engine`` package.
External callers use finished-face Features; compatibility with legacy
unfolded exporter coordinates is contained here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Literal, Mapping

from . import ae
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
    CircleFeature,
    DoorIndicatorContext,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
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
from .sheetmetal_part_adapters import build_door_result, build_unknown_door_result, build_finished_reference_guide
from .cabinet_types import policy as cabinet_family_policy

_RESOURCE_LOCK = threading.RLock()
_FEATURE_TYPES = (CircleFeature, RectFeature, ProfileFeature)


def resolve_policy(context: ManufacturingContext | None = None) -> ManufacturingPolicy:
    """Resolve Factory Policy at the API boundary, never in external adapters."""
    ctx = context or ManufacturingContext()
    if ctx.policy is not None:
        return ctx.policy
    return ManufacturingPolicy(
        default_thickness=float(getattr(ae, "T", 2.0)),
        frame_width=float(getattr(ae, "FW", 25.0)),
        door_gap_w=float(getattr(ae, "door_gap_w_def", 0.0)),
        door_gap_h=float(getattr(ae, "door_gap_h_def", 0.0)),
        door_fold_left=float(getattr(ae, "door_fold_left_def", 19.0)),
        door_fold_right=float(getattr(ae, "door_fold_right_def", 19.0)),
        door_fold_top=float(getattr(ae, "door_fold_top_def", 19.0)),
        door_fold_bottom=float(getattr(ae, "door_fold_bottom_def", 19.0)),
        indicator_box_fold=float(getattr(ae, "indicator_box_fold_def", 49.0)),
        indicator_small_door_fold=float(getattr(ae, "indicator_small_door_fold_def", 19.0)),
        indicator_small_door_gap=float(getattr(ae, "indicator_small_door_gap_def", 3.5)),
    )


def _resource_root(context: ManufacturingContext) -> Path | None:
    if context.resource_root is None:
        return None
    return Path(context.resource_root).expanduser().resolve()


def _expected_baseline_path(model_name: str | None, filename: str, context: ManufacturingContext) -> Path | None:
    model = str(model_name or "").strip()
    if not model:
        return None
    with _scoped_ae_resource_root(context):
        if hasattr(ae, "baseline_expected_path"):
            expected = ae.baseline_expected_path(model, filename)
            return Path(expected) if expected else None
        if hasattr(ae, "baseline_part_path"):
            existing = ae.baseline_part_path(model, filename)
            return Path(existing) if existing else None
    return None


def _indicator_shared_expected_path(filename: str, context: ManufacturingContext, model_name: str | None = None) -> Path | None:
    model = str(model_name or "").strip()
    if model:
        return _expected_baseline_path(model, filename, context)
    with _scoped_ae_resource_root(context):
        resolver = getattr(ae, "indicator_shared_baseline_part_path", None)
        if resolver is None:
            raise RuntimeError("AE shared-baseline resolver is unavailable")
        path = resolver(filename, require_exists=False)
        return Path(path) if path else None


def _indicator_shared_existing_path(filename: str, context: ManufacturingContext, model_name: str | None = None) -> Path | None:
    expected = _indicator_shared_expected_path(filename, context, model_name=model_name)
    return expected if expected is not None and expected.is_file() else None


def expected_baseline_path_for(
    spec: PartSpec, context: ManufacturingContext | None = None
) -> Path | None:
    """Return the expected baseline path without requiring the file to exist."""
    ctx = context or ManufacturingContext()
    if isinstance(spec, DoorPartSpec):
        if spec.indicator_window_groups is not None:
            return _indicator_shared_expected_path("小門.dxf", ctx)
        return _expected_baseline_path(_door_baseline_model_name(spec.model_name), "門.dxf", ctx)
    if isinstance(spec, BoxBodyPartSpec):
        return _expected_baseline_path(spec.model_name, "箱身.dxf", ctx)
    if isinstance(spec, EndCapPartSpec):
        return _expected_baseline_path(spec.model_name, "封頭尾.dxf", ctx)
    if isinstance(spec, IndicatorBoxPartSpec):
        return _indicator_shared_expected_path("盒子.dxf", ctx, model_name=spec.model_name)
    return None


def _baseline_path(model_name: str | None, filename: str, context: ManufacturingContext) -> Path | None:
    expected = _expected_baseline_path(model_name, filename, context)
    return expected if expected is not None and expected.is_file() else None


def _door_baseline_model_name(model_name: str | None) -> str | None:
    return cabinet_family_policy.baseline_feature_model_name(model_name)


def _endcap_baseline_feature_model_name(model_name: str | None) -> str | None:
    """Return the model that owns shared EndCap baseline-hole features."""
    return cabinet_family_policy.baseline_feature_model_name(model_name)


def _door_nameplate_datum_top(spec: DoorPartSpec) -> float | None:
    if spec.nameplate_center_datum_top is not None:
        return float(spec.nameplate_center_datum_top)
    return cabinet_family_policy.door_nameplate_center_datum_top(spec.model_name)


@contextmanager
def _scoped_ae_resource_root(context: ManufacturingContext):
    root = _resource_root(context)
    if root is None or not hasattr(ae, "get_resource_path"):
        yield
        return
    with _RESOURCE_LOCK:
        previous = ae.get_resource_path

        def get_resource_path(relative_path):
            return str(root / relative_path)

        ae.get_resource_path = get_resource_path
        try:
            yield
        finally:
            ae.get_resource_path = previous


def _supported_kwargs(func, kwargs: dict) -> dict:
    """Filter kwargs only when a wrapped legacy function has a fixed signature."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    return {key: value for key, value in kwargs.items() if key in sig.parameters}


def _call(func, *args, **kwargs):
    return func(*args, **_supported_kwargs(func, kwargs))


def _has_named_parameter(func, name: str) -> bool:
    try:
        return name in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False


def _resolved_door_params(spec: DoorPartSpec, context: ManufacturingContext | None = None):
    policy = resolve_policy(context)
    return dict(
        w=float(spec.width), h=float(spec.height), t=float(spec.thickness), fw=float(spec.frame_width),
        gap_w=float(spec.gap_w if spec.gap_w is not None else policy.door_gap_w),
        gap_h=float(spec.gap_h if spec.gap_h is not None else policy.door_gap_h),
        fold_left=float(spec.fold_left if spec.fold_left is not None else policy.door_fold_left),
        fold_right=float(spec.fold_right if spec.fold_right is not None else policy.door_fold_right),
        fold_top=float(spec.fold_top if spec.fold_top is not None else policy.door_fold_top),
        fold_bottom=float(spec.fold_bottom if spec.fold_bottom is not None else policy.door_fold_bottom),
    )


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


def _as_feature(item):
    if isinstance(item, _FEATURE_TYPES):
        return item
    if isinstance(item, Mapping):
        return legacy_hole_to_feature(dict(item))
    raise TypeError(f"Unsupported FeatureLike: {type(item)!r}")


def _door_features_for_legacy_engine(spec: DoorPartSpec, context: ManufacturingContext | None = None):
    if spec.feature_space == "legacy_unfolded":
        return list(spec.features)
    if spec.feature_space != "finished_face":
        raise ValueError(f"Unsupported Door feature_space: {spec.feature_space!r}")
    if not spec.features:
        return []

    p = _resolved_door_params(spec, context)
    finished_w, finished_h = _call(
        ae.calculate_door_finished_size,
        p["w"], p["h"], p["fw"], p["gap_w"], p["gap_h"], p["t"],
        frame_edges=spec.frame_edges,
    )

    builder = build_unknown_door_result if spec.corner_policy is not None else build_door_result
    builder_kwargs = dict(
        w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
        gap_w=p["gap_w"], gap_h=p["gap_h"],
        fold_left=p["fold_left"], fold_right=p["fold_right"],
        fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
        frame_edges=spec.frame_edges,
    )
    if spec.corner_policy is not None:
        builder_kwargs["corner_policy"] = spec.corner_policy
    result = _call(builder, **builder_kwargs)
    guide = build_finished_reference_guide(
        "door", result, finished_width=float(finished_w), finished_height=float(finished_h)
    )
    mapped = []
    for raw in spec.features:
        feature = _as_feature(raw)
        local = feature_finished_point(feature, float(finished_w), float(finished_h))
        mapped.append(replace(
            feature,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(guide.min_point.x + local.x, guide.min_point.y + local.y),
        ))
    return mapped


def _endcap_feature_kwargs(spec: EndCapPartSpec, exporter):
    raw_features = []
    legacy_holes = []
    for raw in spec.holes:
        if isinstance(raw, _FEATURE_TYPES):
            raw_features.append(raw)
        elif isinstance(raw, Mapping):
            legacy_holes.append(dict(raw))
        else:
            raise TypeError(f"Unsupported FeatureLike: {type(raw)!r}")

    # Older split-project AE versions expose the authoritative finished-face
    # automatic_features resolver directly. Preserve that route when present.
    if _has_named_parameter(exporter, "automatic_features"):
        return {
            "holes": legacy_holes,
            "automatic_features": raw_features,
        }

    # Newer standalone AE collapsed GUI/automatic inputs into the legacy holes
    # compatibility input. Convert only at this API boundary.
    legacy_holes.extend(
        feature_to_legacy_hole(feature, float(spec.width), float(spec.depth))
        for feature in raw_features
    )
    return {"holes": legacy_holes}



def _legacy_endcap_holes(spec: EndCapPartSpec):
    """Normalize EndCap FeatureLike values for the authoritative AE scene builder."""
    holes = []
    for raw in spec.holes:
        if isinstance(raw, _FEATURE_TYPES):
            holes.append(feature_to_legacy_hole(raw, float(spec.width), float(spec.depth)))
        elif isinstance(raw, Mapping):
            holes.append(dict(raw))
        else:
            raise TypeError(f"Unsupported FeatureLike: {type(raw)!r}")
    return holes


@dataclass(frozen=True)
class ResolvedEndCapRequest:
    """AE-owned normalized EndCap manufacturing request."""

    width: float
    depth: float
    thickness: float
    frame_width: float
    height: float | None
    model_name: str | None
    is_tail: bool
    fold_left: float
    fold_right: float
    nominal_fold_left: float
    nominal_fold_right: float
    box_body_formed_fw_left: float | None
    box_body_formed_fw_right: float | None
    fold_top: float
    fold_bottom: float
    x_topology: Literal["folded", "flat"]
    fold_profile_x: tuple[FoldProfileSegment, ...]
    fold_profile_y: tuple[FoldProfileSegment, ...]
    corner_policy: FourCornerTypePolicy | None
    assembly: EndCapAssemblySemantics | None
    depth_comp_t: float
    holes: tuple[FeatureLike, ...]


def _endcap_scalar(value: float | None, fallback: float) -> float:
    return float(fallback if value is None else value)


def resolve_endcap_request(spec: EndCapPartSpec) -> ResolvedEndCapRequest:
    """Resolve Fold Profile precedence at the AE boundary exactly once."""
    scalar_left = _endcap_scalar(spec.fold_left, ae.yl1_def)
    scalar_right = _endcap_scalar(spec.fold_right, ae.yr1_def)
    left = scalar_left
    right = scalar_right
    top = _endcap_scalar(spec.fold_top, ae.ytop1_def)
    bottom = _endcap_scalar(spec.fold_bottom, ae.ybottom1_def)

    x_rows = tuple(spec.fold_profile_x or ())
    flat_x = any(row.phase6_key == "endcap_w_flat" for row in x_rows)
    core_index = next(
        (index for index, row in enumerate(x_rows) if row.core == "W-2T"),
        None,
    )
    if flat_x:
        left = 0.0
        right = 0.0
    elif core_index is not None:
        left = sum(float(row.length) for row in x_rows[:core_index])
        right = sum(float(row.length) for row in x_rows[core_index + 1:])

    y_rows = tuple(spec.fold_profile_y or ())
    canonical_fw = next((float(row.length) for row in y_rows if row.phase6_key == "fw"), None)
    if y_rows:
        top = sum(
            float(row.length)
            for row in y_rows
            if row.phase6_key not in {"fw", "endcap_d_core", "ybottom1"}
        )
        bottom_rows = [row for row in y_rows if row.phase6_key == "ybottom1"]
        if bottom_rows:
            bottom = sum(float(row.length) for row in bottom_rows)

    assembly = None
    corner_policy = spec.corner_policy
    if corner_policy is not None and canonical_fw is not None:
        # Fold Profile rows are already in manufacturing/material dimension space.
        # GUI payloads may still carry operator/formed FW (e.g. Receiving 29),
        # but CornerType CUTTING must use the same material FW as the canonical
        # EndCap profile, otherwise raw relief and Certified Registry disagree.
        corner_policy = replace(corner_policy, fw=float(canonical_fw))
    if corner_policy is not None:
        assembly = resolve_endcap_policy_assembly_semantics(corner_policy)
        if assembly.x_topology == "flat":
            left = 0.0
            right = 0.0
            # CornerType is the mechanical source of truth for OVERLAY: stale
            # folded X editor rows must not re-introduce fictitious side bends.
            x_rows = ()
        elif flat_x:
            # Conversely, a stale OVERLAY flat profile must not remove the side
            # folds required by INSERT / INSERT_OVERLAY assembly semantics.
            left = scalar_left
            right = scalar_right
            x_rows = ()

    x_topology: Literal["folded", "flat"] = (
        assembly.x_topology
        if assembly is not None
        else ("flat" if flat_x else "folded")
    )

    return ResolvedEndCapRequest(
        width=float(spec.width),
        depth=float(spec.depth),
        thickness=float(spec.thickness),
        frame_width=float(spec.frame_width if canonical_fw is None else canonical_fw),
        height=None if spec.height is None else float(spec.height),
        model_name=spec.model_name,
        is_tail=bool(spec.is_tail),
        fold_left=left,
        fold_right=right,
        nominal_fold_left=scalar_left,
        nominal_fold_right=scalar_right,
        box_body_formed_fw_left=(None if spec.box_body_formed_fw_left is None else float(spec.box_body_formed_fw_left)),
        box_body_formed_fw_right=(None if spec.box_body_formed_fw_right is None else float(spec.box_body_formed_fw_right)),
        fold_top=top,
        fold_bottom=bottom,
        x_topology=x_topology,
        fold_profile_x=x_rows,
        fold_profile_y=y_rows,
        corner_policy=corner_policy,
        assembly=assembly,
        depth_comp_t=float(spec.depth_comp_t),
        holes=tuple(spec.holes or ()),
    )


def _baseline_endcap_holes_for_request(resolved, context: ManufacturingContext):
    """Map certified baseline EndCap CUTTING circles onto target family geometry."""
    model = _endcap_baseline_feature_model_name(resolved.model_name)
    if _baseline_path(model, "封頭尾.dxf", context) is None:
        return ()
    data = _call(
        ae.get_stretched_end_cap_data,
        model, resolved.width, resolved.height or resolved.depth, resolved.depth,
        resolved.thickness, resolved.frame_width, True, resolved.corner_policy,
        resolved.x_topology, resolved.box_body_formed_fw_left,
        resolved.box_body_formed_fw_right,
        depth_comp_t=resolved.depth_comp_t,
        target_fold_left=resolved.fold_left, target_fold_right=resolved.fold_right,
        target_fold_top=resolved.fold_top, target_fold_bottom=resolved.fold_bottom,
    )
    feature_scene = data.scene
    if not resolved.is_tail:
        feature_scene = ae.mirror_drawing_scene_y(
            feature_scene, float(data.params["total_depth"])
        )
    return tuple(
        primitive for primitive in feature_scene.primitives
        if isinstance(primitive, ae.CirclePrimitive)
        and str(primitive.layer).upper() == "CUTTING"
        and getattr(primitive, "source_type", None) == "baseline_endcap_hole"
    )


def _merge_baseline_endcap_holes(scene, holes):
    existing = {
        getattr(primitive, "source_id", None)
        for primitive in scene.primitives
        if isinstance(primitive, ae.CirclePrimitive)
        and getattr(primitive, "source_type", None) == "baseline_endcap_hole"
    }
    for primitive in holes:
        if primitive.source_id not in existing:
            scene.add(primitive)
            existing.add(primitive.source_id)
    return scene


def _scene_with_authoritative_fold_profiles(scene, profile_x=(), profile_y=()):
    """Replace only BEND primitives from arbitrary X/Y fold profiles.

    CUTTING/holes/CornerType remain owned by the manufacturing scene. New fold
    lines are clipped to the actual material polygon so retained/cut-away corner
    regions never receive a fictitious full-width bend.
    """
    if not profile_x and not profile_y:
        return scene
    from shapely.geometry import LineString
    from .sheetmetal_drawing import DrawingScene, LinePrimitive

    material = material_polygon_from_final_scene(scene)
    if material.is_empty:
        return scene
    minx, miny, maxx, maxy = map(float, material.bounds)
    result = DrawingScene()
    replace_x = bool(profile_x)
    replace_y = bool(profile_y)
    for primitive in scene.primitives:
        if isinstance(primitive, LinePrimitive) and str(primitive.layer).upper() == "BEND":
            dx = abs(float(primitive.p1.x) - float(primitive.p2.x))
            dy = abs(float(primitive.p1.y) - float(primitive.p2.y))
            is_vertical = dx <= 1e-9 and dy > 1e-9
            is_horizontal = dy <= 1e-9 and dx > 1e-9
            if (replace_x and is_vertical) or (replace_y and is_horizontal):
                continue
        result.add(primitive)

    def rows(profile):
        return list(profile or ())

    def length(row):
        return float(getattr(row, "length", row.get("len", 0.0) if isinstance(row, dict) else 0.0))

    def has_real_turn(row):
        angle = getattr(row, "angle", row.get("angle") if isinstance(row, dict) else None)
        if angle is None:
            return False
        try:
            return abs(float(angle)) > 1e-9
        except (TypeError, ValueError):
            return False

    def add_intersection(line):
        clipped = material.intersection(line)
        geoms = [clipped] if clipped.geom_type == "LineString" else list(getattr(clipped, "geoms", ()))
        for geom in geoms:
            if geom.geom_type != "LineString" or geom.length <= 1e-8:
                continue
            coords = list(geom.coords)
            if len(coords) >= 2:
                result.add_line(coords[0], coords[-1], layer="BEND")

    cursor = 0.0
    px = rows(profile_x)
    for row in px[:-1]:
        cursor += length(row)
        if has_real_turn(row):
            add_intersection(LineString([(cursor, miny - 1.0), (cursor, maxy + 1.0)]))

    cursor = 0.0
    py = rows(profile_y)
    for row in py[:-1]:
        cursor += length(row)
        if has_real_turn(row):
            add_intersection(LineString([(minx - 1.0, cursor), (maxx + 1.0, cursor)]))
    return result


def build_part_scene(
    spec: PartSpec, context: ManufacturingContext | None = None
):
    """Return the authoritative pre-serialization DrawingScene for one part.

    This is the rendering boundary shared by non-DXF consumers (notably Phase6
    3D).  All manufacturing semantics stay in AE/PartSpec; callers must not
    rebuild baseline geometry, CornerType, holes, or operation ownership.
    """
    ctx = context or ManufacturingContext()
    with _scoped_ae_resource_root(ctx):
        if isinstance(spec, DoorPartSpec):
            _validate_door_part_indicator_fit(spec, ctx)
            p = _resolved_door_params(spec, ctx)
            features = _door_features_for_legacy_engine(spec, ctx)
            is_small = spec.indicator_window_groups is not None
            baseline = (
                _indicator_shared_existing_path("小門.dxf", ctx)
                if is_small else _baseline_path(_door_baseline_model_name(spec.model_name), "門.dxf", ctx)
            )
            if baseline is not None:
                data = _call(
                    ae.get_stretched_door_data,
                    None if is_small else _door_baseline_model_name(spec.model_name),
                    p["w"], p["h"], p["t"], p["fw"],
                    p["gap_w"], p["gap_h"],
                    p["fold_left"], p["fold_right"], p["fold_top"], p["fold_bottom"],
                    spec.indicator_hole, spec.door_indicator, spec.door_indicator_offset,
                    frame_edges=spec.frame_edges,
                    indicator_window_groups=spec.indicator_window_groups,
                    corner_policy=spec.corner_policy,
                    nameplate_center_datum_top=_door_nameplate_datum_top(spec),
                )
                scene = ae.DrawingScene()
                scene.extend(data.scene.primitives)
                if features:
                    surface = ae.feature_surface_from_drawing_scene(
                        "indicator_door" if is_small else "door", data.scene
                    )
                    scene.extend(ae.resolved_features_to_primitives(
                        ae.resolve_surface_features(
                            surface, features, float(data.params["total_width"]),
                            float(data.params["total_depth"])
                        )
                    ))
                return scene
            if spec.corner_policy is not None:
                result = _call(
                    build_unknown_door_result,
                    w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                    gap_w=p["gap_w"], gap_h=p["gap_h"],
                    fold_left=p["fold_left"], fold_right=p["fold_right"],
                    fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
                    corner_policy=spec.corner_policy, frame_edges=spec.frame_edges,
                )
                return _call(
                    ae._build_door_scene,
                    w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                    gw=p["gap_w"], gh=p["gap_h"],
                    fl=p["fold_left"], fr=p["fold_right"],
                    ft=p["fold_top"], fb=p["fold_bottom"],
                    draw_stock=ctx.draw_stock, indicator_hole=spec.indicator_hole,
                    door_indicator=spec.door_indicator,
                    door_indicator_offset=spec.door_indicator_offset,
                    is_box_dist=spec.use_box_distance, user_features=features,
                    frame_edges=spec.frame_edges, structural_result=result,
                )
            return _call(
                ae._build_door_scene,
                w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                gw=p["gap_w"], gh=p["gap_h"],
                fl=p["fold_left"], fr=p["fold_right"],
                ft=p["fold_top"], fb=p["fold_bottom"],
                draw_stock=ctx.draw_stock, indicator_hole=spec.indicator_hole,
                door_indicator=spec.door_indicator,
                door_indicator_offset=spec.door_indicator_offset,
                is_box_dist=spec.use_box_distance, user_features=features,
                frame_edges=spec.frame_edges,
            )

        if isinstance(spec, BoxBodyPartSpec):
            return _call(
                ae._build_box_body_scene,
                w=spec.width, h=spec.height, d=spec.depth, t=spec.thickness,
                fw=spec.frame_width, zl1=spec.zl1, zl2=spec.zl2,
                zr1=spec.zr1, zr2=spec.zr2, z_comp=spec.z_comp,
                draw_stock=ctx.draw_stock, model_name=spec.model_name,
                user_features=list(spec.features),
                face_features={key: list(value) for key, value in spec.face_features.items()},
                head_corner_policy=spec.head_corner_policy,
                tail_corner_policy=spec.tail_corner_policy,
                fold_profile=spec.fold_profile or None,
            )

        if isinstance(spec, EndCapPartSpec):
            resolved = resolve_endcap_request(spec)
            common = dict(
                w=resolved.width, d=resolved.depth, t=resolved.thickness, fw=resolved.frame_width,
                yl1=resolved.fold_left, yr1=resolved.fold_right,
                nominal_yl1=resolved.nominal_fold_left, nominal_yr1=resolved.nominal_fold_right,
                box_body_formed_fw_left=resolved.box_body_formed_fw_left,
                box_body_formed_fw_right=resolved.box_body_formed_fw_right,
                ytop1=resolved.fold_top, ybottom1=resolved.fold_bottom,
                x_topology=resolved.x_topology, depth_comp_t=resolved.depth_comp_t,
                draw_stock=ctx.draw_stock, is_tail=resolved.is_tail,
                holes=_legacy_endcap_holes(spec),
            )
            baseline = _baseline_path(resolved.model_name, "封頭尾.dxf", ctx)
            used_stretched_baseline = (
                baseline is not None and abs(float(resolved.depth_comp_t) - 3.0) <= 1e-9
            )
            if used_stretched_baseline:
                data = _call(
                    ae._build_stretched_end_cap_scene,
                    resolved.model_name, resolved.width, resolved.height or resolved.depth, resolved.depth,
                    resolved.thickness, resolved.frame_width,
                    x_topology=resolved.x_topology,
                    box_body_formed_fw_left=resolved.box_body_formed_fw_left,
                    box_body_formed_fw_right=resolved.box_body_formed_fw_right,
                    draw_stock=ctx.draw_stock, is_tail=resolved.is_tail, holes=common["holes"],
                    corner_policy=resolved.corner_policy,
                )
                scene = data.scene
            elif resolved.corner_policy is not None:
                scene = _call(
                    ae._build_unknown_end_cap_scene,
                    corner_policy=resolved.corner_policy,
                    **common,
                )
            else:
                scene = _call(ae._build_end_cap_scene, **common)
            if not used_stretched_baseline:
                scene = _merge_baseline_endcap_holes(
                    scene, _baseline_endcap_holes_for_request(resolved, ctx)
                )
            return _scene_with_authoritative_fold_profiles(
                scene, resolved.fold_profile_x, resolved.fold_profile_y
            )

        if isinstance(spec, BasePlatePartSpec):
            if spec.corner_policy is not None:
                from .sheetmetal_part_adapters import build_unknown_base_plate_result
                result = _call(
                    build_unknown_base_plate_result,
                    w=spec.width, h=spec.height, t=spec.thickness,
                    shrink_top=spec.shrink_top, shrink_bottom=spec.shrink_bottom,
                    shrink_left=spec.shrink_left, shrink_right=spec.shrink_right,
                    bend=spec.bend, corner_policy=spec.corner_policy,
                )
            else:
                from .sheetmetal_part_adapters import build_base_plate_result
                result = _call(
                    build_base_plate_result,
                    w=spec.width, h=spec.height, t=spec.thickness,
                    shrink_top=spec.shrink_top, shrink_bottom=spec.shrink_bottom,
                    shrink_left=spec.shrink_left, shrink_right=spec.shrink_right,
                    bend=spec.bend,
                )
            if spec.box_body_fold_profile and spec.box_body_structure_state:
                from .box_body_structure import resolve_box_body_structure, apply_base_plate_structure_reliefs
                box_structure = resolve_box_body_structure(
                    spec.box_body_fold_profile, w=spec.width, h=spec.height, t=spec.thickness,
                    structure_state=spec.box_body_structure_state,
                )
                result = apply_base_plate_structure_reliefs(
                    result, box_w=spec.width, shrink_left=spec.shrink_left, shrink_right=spec.shrink_right,
                    thickness=spec.thickness, structure=box_structure,
                    structure_state=spec.box_body_structure_state,
                )
            return _call(
                ae._build_base_plate_scene,
                w=spec.width, h=spec.height, t=spec.thickness,
                st=spec.shrink_top, sb=spec.shrink_bottom,
                sl=spec.shrink_left, sr=spec.shrink_right, bend=spec.bend,
                draw_stock=ctx.draw_stock, user_features=list(spec.features),
                structural_result=result,
            )

        if isinstance(spec, IndicatorBoxPartSpec):
            data = _call(
                ae._build_stretched_indicator_box_scene,
                None, list(spec.layer_groups), spec.thickness,
                draw_stock=ctx.draw_stock, user_features=list(spec.features),
                corner_policy=spec.corner_policy,
            )
            return data.scene

    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


@dataclass(frozen=True)
class FoldGuide:
    """One authoritative final BEND segment.

    ``axis`` is the unfolded coordinate changed by the fold: ``x`` for a
    vertical BEND line and ``y`` for a horizontal BEND line. ``span_start`` /
    ``span_end`` are the orthogonal coordinates over which that physical bend
    actually exists.  Retained corner material outside this span must not
    receive that particular fold.
    """
    axis: str
    position: float
    span_start: float
    span_end: float


def fold_guides_from_final_scene(scene):
    """Extract normalized physical fold coverage from final BEND primitives."""
    from .sheetmetal_drawing import LinePrimitive

    guides = []
    for primitive in getattr(scene, "primitives", ()):
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(getattr(primitive, "layer", "")).upper() != "BEND":
            continue
        x1, y1 = float(primitive.p1.x), float(primitive.p1.y)
        x2, y2 = float(primitive.p2.x), float(primitive.p2.y)
        if abs(x1 - x2) <= 1e-7 and abs(y1 - y2) > 1e-9:
            guides.append(FoldGuide("x", (x1 + x2) / 2.0, min(y1, y2), max(y1, y2)))
        elif abs(y1 - y2) <= 1e-7 and abs(x1 - x2) > 1e-9:
            guides.append(FoldGuide("y", (y1 + y2) / 2.0, min(x1, x2), max(x1, x2)))
    return tuple(guides)


@dataclass(frozen=True)
class MaterialSegment:
    """One traceable unfolded-material segment used to derive blank envelope."""
    axis: str
    name: str
    length: float
    source: str

    def __post_init__(self):
        object.__setattr__(self, "axis", str(self.axis).upper())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "length", max(0.0, float(self.length)))
        object.__setattr__(self, "source", str(self.source))


@dataclass(frozen=True)
class UnfoldedBlankTopology:
    """Canonical physical-piece blank envelope derived from material chains."""
    piece_id: str
    x_segments: tuple[MaterialSegment, ...]
    y_segments: tuple[MaterialSegment, ...]
    source: str
    revision: int = 1

    @property
    def width(self) -> float:
        return sum(float(item.length) for item in self.x_segments)

    @property
    def height(self) -> float:
        return sum(float(item.length) for item in self.y_segments)

    @property
    def fingerprint(self) -> str:
        payload = {
            "piece_id": self.piece_id, "source": self.source, "revision": int(self.revision),
            "x": [(s.name, round(float(s.length), 9), s.source) for s in self.x_segments],
            "y": [(s.name, round(float(s.length), 9), s.source) for s in self.y_segments],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _profile_material_segments(axis: str, rows, *, source: str) -> tuple[MaterialSegment, ...]:
    result = []
    for index, row in enumerate(tuple(rows or ())):
        name = str(getattr(row, "phase6_key", None) or getattr(row, "core", None) or f"segment_{index}")
        result.append(MaterialSegment(axis, name, float(getattr(row, "length", 0.0)), source))
    return tuple(result)


@dataclass(frozen=True)
class PartRenderData:
    """Manufacturing-owned geometry ready for non-DXF renderers.

    ``material`` is the already-resolved sheet material polygon.  A renderer may
    triangulate/fold it, but must not rediscover holes, baseline entities or
    CornerType semantics from ``scene``. ``fold_guides`` carries the exact
    finite BEND coverage from the same final scene so retained material is not
    folded across a gap where no bend physically exists.
    """
    scene: object
    material: object
    fold_guides: tuple[FoldGuide, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    unfolded_topology: UnfoldedBlankTopology | None = None


def collision_part_from_render_data(
    part_id: str, render_data: PartRenderData, *, true_thickness: float = 0.0,
    resolved_joints=(), legal_contact_semantics=(), solver_constraints=(), piece_transform=None,
) -> FinalMaterialCollisionPart:
    """Project committed render data into the neutral collision contract."""
    return FinalMaterialCollisionPart(
        part_id=str(part_id),
        material=render_data.material,
        scene=render_data.scene,
        fold_guides=tuple(render_data.fold_guides or ()),
        unfolded_topology=render_data.unfolded_topology,
        true_thickness=float(true_thickness),
        piece_transform=piece_transform,
        resolved_joints=tuple(resolved_joints or ()),
        legal_contact_semantics=tuple(legal_contact_semantics or ()),
        solver_constraints=tuple(solver_constraints or ()),
        diagnostic_metadata=dict(render_data.metadata or {}),
    )


@dataclass(frozen=True)
class UnfoldedBlankInfo:
    """Canonical unfolded material envelope measured from final material."""
    part_key: str
    width: float
    height: float
    area: float
    bounds: tuple[float, float, float, float]
    material_bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    topology_fingerprint: str = ""
    topology_source: str = ""


def _measure_one_unfolded_blank(render_data, *, part_key: str) -> UnfoldedBlankInfo:
    material = getattr(render_data, "material", None)
    if material is None or bool(getattr(material, "is_empty", True)):
        raise ValueError(f"unfolded material unavailable: {part_key}")
    minx, miny, maxx, maxy = map(float, material.bounds)
    topology = getattr(render_data, "unfolded_topology", None)
    if topology is None:
        # Compatibility for externally-created legacy PartRenderData. Production
        # builders below attach a traceable topology and never rely on this path.
        width = max(0.0, maxx - minx)
        height = max(0.0, maxy - miny)
        fingerprint = ""
        source = "LEGACY_FINAL_BOUNDS"
    else:
        width = float(topology.width)
        height = float(topology.height)
        fingerprint = str(topology.fingerprint)
        source = str(topology.source)
    return UnfoldedBlankInfo(
        part_key=str(part_key),
        width=width,
        height=height,
        area=float(material.area),
        bounds=(minx, miny, maxx, maxy),
        material_bounds=(minx, miny, maxx, maxy),
        topology_fingerprint=fingerprint,
        topology_source=source,
    )


def measure_unfolded_blanks(render_data, *, part_key: str = "") -> tuple[UnfoldedBlankInfo, ...]:
    """Measure every physical sheet from canonical final material.

    Multi-piece Box Body data is intentionally measured piece-by-piece; the
    exploded preview envelope is display-only and is never a manufacturable blank.
    """
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if pieces:
        root = str(part_key or "box_body")
        return tuple(
            _measure_one_unfolded_blank(
                piece.render_data,
                part_key=f"{root}:{piece.key}",
            )
            for piece in pieces
        )
    return (_measure_one_unfolded_blank(render_data, part_key=str(part_key or "part")),)


@dataclass(frozen=True)
class BoxBodyPieceRenderData:
    """One independently manufacturable physical Box Body piece."""
    key: str
    role: str
    formed_w_start: float
    formed_w_end: float
    fold_profile: tuple[FoldProfileSegment, ...]
    render_data: PartRenderData
    formed_outer_width: float | None = None
    formed_outer_height: float | None = None

    @property
    def formed_outer_dimensions(self) -> tuple[float, float]:
        width = (float(self.formed_w_end) - float(self.formed_w_start)) if self.formed_outer_width is None else float(self.formed_outer_width)
        if self.formed_outer_height is not None:
            height = float(self.formed_outer_height)
        else:
            topology = getattr(self.render_data, "unfolded_topology", None)
            height = float(topology.height) if topology is not None else float(self.render_data.material.bounds[3] - self.render_data.material.bounds[1])
        return width, height

    @property
    def material_dimensions(self) -> tuple[float, float]:
        topology = getattr(self.render_data, "unfolded_topology", None)
        if topology is not None:
            return float(topology.width), float(topology.height)
        minx, miny, maxx, maxy = map(float, self.render_data.material.bounds)
        return maxx - minx, maxy - miny


@dataclass(frozen=True)
class BoxBodyStructureRenderData:
    """Resolved multi-piece Box Body manufacturing data from one structure state.

    ``preview_render_data`` is an exploded 2D scene only. 3D uses ``pieces``
    and their own fold profiles to assemble the physical panels in world space.
    """
    structure_type: object
    pieces: tuple[BoxBodyPieceRenderData, ...]
    preview_render_data: PartRenderData
    warnings: tuple[object, ...] = ()

    @property
    def scene(self):
        return self.preview_render_data.scene

    @property
    def material(self):
        return self.preview_render_data.material

    @property
    def fold_guides(self):
        return self.preview_render_data.fold_guides


def material_polygon_from_final_scene(scene):
    """Resolve final material once at the manufacturing boundary.

    AE scene builders emit the authoritative structural CUTTING outline first.
    Later CUTTING contours are manufacturing cut-outs/features.  Some legacy
    stretched baselines can also carry a mapped copy of the old structural
    outline; a same-sheet-bounds contour is therefore ignored rather than
    interpreted as one giant hole.
    """
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import polygonize, unary_union
    from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive

    primary = None
    secondary = []
    linework = []
    for primitive in getattr(scene, "primitives", ()):
        if str(getattr(primitive, "layer", "")).upper() != "CUTTING":
            continue
        if isinstance(primitive, PolylinePrimitive):
            pts = [(float(p.x), float(p.y)) for p in primitive.points]
            if primitive.closed and len(pts) >= 3:
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or poly.area <= 1e-9:
                    continue
                if primary is None:
                    primary = poly
                else:
                    secondary.append(poly)
            elif len(pts) >= 2:
                linework.extend(
                    LineString((a, b)) for a, b in zip(pts, pts[1:]) if a != b
                )
        elif isinstance(primitive, LinePrimitive):
            a = (float(primitive.p1.x), float(primitive.p1.y))
            b = (float(primitive.p2.x), float(primitive.p2.y))
            if a != b:
                linework.append(LineString((a, b)))
        elif isinstance(primitive, CirclePrimitive) and float(primitive.radius) > 0:
            secondary.append(
                Point(float(primitive.center.x), float(primitive.center.y)).buffer(
                    float(primitive.radius), quad_segs=32
                )
            )

    if primary is None:
        if linework:
            polys = [p for p in polygonize(unary_union(linework)) if p.area > 1e-9]
            if polys:
                primary = max(polys, key=lambda p: float(p.area))
                secondary.extend(p for p in polys if p is not primary)
        if primary is None:
            raise ValueError("final DrawingScene has no structural CUTTING outline")
    elif linework:
        # Baseline CUTTING often arrives as exploded LINE/ARC segments.  The 2D
        # preview can look perfectly closed even when adjacent DXF endpoints are
        # separated by a few hundredths of a millimetre; exact polygonize then
        # misses the contour and 3D stays solid.  Snap only segment endpoints
        # within a tiny manufacturing tolerance before polygonizing.
        from collections import defaultdict
        from math import floor, hypot

        minx0, miny0, maxx0, maxy0 = map(float, primary.bounds)
        span = max(maxx0 - minx0, maxy0 - miny0, 1.0)
        endpoint_tol = max(0.05, min(0.25, span * 2.0e-4))

        endpoints = []
        coords_by_line = []
        for line in linework:
            coords = list(line.coords)
            coords_by_line.append(coords)
            endpoints.extend([tuple(map(float, coords[0])), tuple(map(float, coords[-1]))])

        parent = list(range(len(endpoints)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri

        buckets = defaultdict(list)
        cell = endpoint_tol
        for i, (x, y) in enumerate(endpoints):
            gx, gy = int(floor(x / cell)), int(floor(y / cell))
            for nx in (gx - 1, gx, gx + 1):
                for ny in (gy - 1, gy, gy + 1):
                    for j in buckets.get((nx, ny), ()):
                        qx, qy = endpoints[j]
                        if hypot(x - qx, y - qy) <= endpoint_tol:
                            union(i, j)
            buckets[(gx, gy)].append(i)

        grouped = defaultdict(list)
        for i, point in enumerate(endpoints):
            grouped[find(i)].append(point)
        snapped_point = {}
        for root, pts in grouped.items():
            snapped_point[root] = (
                sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts),
            )

        snapped_lines = []
        for line_index, coords in enumerate(coords_by_line):
            a = snapped_point[find(line_index * 2)]
            b = snapped_point[find(line_index * 2 + 1)]
            if a == b:
                continue
            mapped = [a] + [tuple(map(float, pt)) for pt in coords[1:-1]] + [b]
            snapped_lines.append(LineString(mapped))

        secondary.extend(
            p for p in polygonize(unary_union(snapped_lines)) if p.area > 1e-9
        )

    minx, miny, maxx, maxy = map(float, primary.bounds)
    sx, sy = max(1.0, maxx - minx), max(1.0, maxy - miny)
    tolx, toly = max(1e-6, sx * 1e-4), max(1e-6, sy * 1e-4)

    holes = []
    for candidate in secondary:
        if candidate.is_empty or candidate.area <= 1e-9:
            continue
        cb = tuple(map(float, candidate.bounds))
        same_sheet_bounds = (
            abs(cb[0] - minx) <= tolx and abs(cb[1] - miny) <= toly and
            abs(cb[2] - maxx) <= tolx and abs(cb[3] - maxy) <= toly
        )
        if same_sheet_bounds:
            continue
        if primary.buffer(1e-7).covers(candidate.representative_point()):
            holes.append(candidate.intersection(primary))

    material = primary if not holes else primary.difference(unary_union(holes))
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty:
        raise ValueError("final material is empty")
    return material


def _translated_scene(scene, dx: float, dy: float = 0.0):
    from .sheetmetal_drawing import (
        DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive, TextPrimitive,
    )
    from .sheetmetal_geometry import Vec2
    def point(p):
        return Vec2(float(p.x) + float(dx), float(p.y) + float(dy))
    out = DrawingScene()
    for primitive in scene.primitives:
        if isinstance(primitive, PolylinePrimitive):
            out.add(PolylinePrimitive(tuple(point(p) for p in primitive.points), primitive.layer, primitive.closed, primitive.color))
        elif isinstance(primitive, LinePrimitive):
            out.add(LinePrimitive(point(primitive.p1), point(primitive.p2), primitive.layer, primitive.color))
        elif isinstance(primitive, CirclePrimitive):
            out.add(CirclePrimitive(point(primitive.center), primitive.radius, primitive.layer, primitive.color,
                                    primitive.source_type, primitive.source_id))
        elif isinstance(primitive, TextPrimitive):
            out.add(TextPrimitive(primitive.text, point(primitive.insert), primitive.layer, primitive.char_height, primitive.attachment_point, primitive.color))
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive)!r}")
    return out


def _exploded_box_body_preview(pieces, *, gap=30.0):
    from .sheetmetal_drawing import DrawingScene
    from shapely.affinity import translate as shp_translate
    from shapely.ops import unary_union
    scene = DrawingScene()
    materials = []
    cursor = 0.0
    for piece in pieces:
        minx, _miny, maxx, _maxy = map(float, piece.render_data.material.bounds)
        dx = cursor - minx
        moved = _translated_scene(piece.render_data.scene, dx)
        scene.extend(moved.primitives)
        materials.append(shp_translate(piece.render_data.material, xoff=dx))
        cursor += (maxx - minx) + float(gap)
    material = unary_union(materials)
    return PartRenderData(scene=scene, material=material, fold_guides=())


def build_inner_door_frame_render_data(frame) -> PartRenderData:
    """Build one inner-door frame FinalScene from its canonical physical part.

    This consumes the already-derived positive material chain. The signed chain
    remains metadata/direction semantics; no negative material length enters the
    drawing or manufacturing topology.
    """
    from .inner_door_frames import InnerDoorFramePart
    from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives
    from .sheetmetal_geometry import FoldSegment, StripFoldChain, build_strip_outline, build_strip_bend_segments
    from .sheetmetal_part_adapters import StructuralGeometryResult

    if not isinstance(frame, InnerDoorFramePart):
        raise TypeError("frame must be InnerDoorFramePart")
    chain = StripFoldChain(
        segments=tuple(
            FoldSegment(str(row.phase6_key or f"segment_{index}"), float(row.length), 0.0)
            for index, row in enumerate(frame.fold_profile)
        ),
        height=float(frame.span),
    )
    structural = StructuralGeometryResult(
        outline=tuple(build_strip_outline(chain)),
        bends=tuple(build_strip_bend_segments(chain)),
        width=float(chain.total_width),
        height=float(chain.height),
        topology=chain,
    )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural))
    topology = UnfoldedBlankTopology(
        piece_id=str(frame.stable_id),
        x_segments=tuple(
            MaterialSegment("X", str(row.phase6_key or f"segment_{index}"), float(row.length), "INNER_DOOR_FRAME_FOLD_CHAIN")
            for index, row in enumerate(frame.fold_profile)
        ),
        y_segments=(MaterialSegment("Y", "frame_span", float(frame.span), "INNER_DOOR_FRAME_EXPLICIT_SPAN"),),
        source="INNER_DOOR_FRAME_FOLD_CHAIN", revision=1,
    )
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={
            "stable_id": str(frame.stable_id),
            "inner_door_id": str(frame.inner_door_id),
            "frame_side": str(frame.side),
            "signed_fold_chain": tuple(float(v) for v in frame.signed_fold_chain),
            "material_lengths": tuple(float(v) for v in frame.material_lengths),
            "fold_profile": tuple(frame.fold_profile),
        },
        unfolded_topology=topology,
    )


def build_box_body_divider_render_data(divider) -> PartRenderData:
    """Build one canonical box-body divider from its resolved material chain."""
    from .door_dividers import BoxBodyDividerPart
    from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives
    from .sheetmetal_geometry import FoldSegment, StripFoldChain, build_strip_outline, build_strip_bend_segments
    from .sheetmetal_part_adapters import StructuralGeometryResult

    if not isinstance(divider, BoxBodyDividerPart):
        raise TypeError("divider must be BoxBodyDividerPart")
    chain = StripFoldChain(
        segments=tuple(
            FoldSegment(str(row.phase6_key or f"segment_{index}"), float(row.length), 0.0)
            for index, row in enumerate(divider.fold_profile)
        ),
        height=float(divider.span),
    )
    structural = StructuralGeometryResult(
        outline=tuple(build_strip_outline(chain)),
        bends=tuple(build_strip_bend_segments(chain)),
        width=float(chain.total_width),
        height=float(chain.height),
        topology=chain,
    )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural))
    topology = UnfoldedBlankTopology(
        piece_id=str(divider.stable_id),
        x_segments=tuple(
            MaterialSegment("X", str(row.phase6_key or f"segment_{index}"), float(row.length), "BOX_BODY_DIVIDER_FOLD_CHAIN")
            for index, row in enumerate(divider.fold_profile)
        ),
        y_segments=(MaterialSegment("Y", "divider_span", float(divider.span), "DOOR_LAYOUT_BOUNDARY_SPAN"),),
        source="BOX_BODY_DIVIDER_FOLD_CHAIN", revision=1,
    )
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={
            "stable_id": str(divider.stable_id),
            "owner": "box_body",
            "axis": str(divider.axis),
            "boundary_key": str(divider.boundary_key),
            "handle_side": bool(divider.handle_side),
            "formed_core_depth": float(divider.formed_core_depth),
            "signed_fold_chain": tuple(float(v) for v in divider.signed_fold_chain),
            "material_lengths": tuple(float(v) for v in divider.material_lengths),
            "adjacent_cells": tuple(divider.adjacent_cells),
        },
        unfolded_topology=topology,
    )


def build_box_body_structure_render_data(
    spec: BoxBodyPartSpec, context: ManufacturingContext | None = None
) -> BoxBodyStructureRenderData:
    """Resolve Box Body structure into independent authoritative FinalScenes.

    This is the multi-piece manufacturing boundary. The legacy integral path is
    intentionally still available through ``build_part_render_data``.
    """
    from .box_body_structure import (
        resolve_box_body_structure,
        resolve_box_body_piece_face_features,
    )
    from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives, resolved_features_to_primitives

    ctx = context or ManufacturingContext()
    if not spec.fold_profile:
        raise ValueError("多件式箱身需要權威 Fold Profile")
    structure = resolve_box_body_structure(
        spec.fold_profile,
        w=float(spec.width), h=float(spec.height), t=float(spec.thickness), d=float(spec.depth),
        structure_state=spec.structure_state,
        head_corner_policy=spec.head_corner_policy, tail_corner_policy=spec.tail_corner_policy,
        head_ybottom1=float(spec.head_ybottom1), tail_ybottom1=float(spec.tail_ybottom1),
    )
    feature_stores = resolve_box_body_piece_face_features(
        structure, face_features=spec.face_features,
        w=float(spec.width), h=float(spec.height), d=float(spec.depth), t=float(spec.thickness),
        head_corner_policy=spec.head_corner_policy, tail_corner_policy=spec.tail_corner_policy,
    )
    pieces = []
    for piece in structure.pieces:
        scene = DrawingScene()
        if ctx.draw_stock:
            scene.add(ae.build_stock_outline(piece.structural.width, piece.structural.height))
        scene.extend(structural_result_to_primitives(piece.structural))
        resolved_features = tuple(feature_stores.get(piece.key, ()) or ())
        if resolved_features:
            scene.extend(resolved_features_to_primitives(resolved_features))
        piece_x = _profile_material_segments("X", tuple(piece.fold_profile or ()), source="BOX_BODY_PIECE_FOLD_PROFILE")
        if not piece_x:
            piece_x = (MaterialSegment("X", "piece_width", float(piece.structural.width), "BOX_BODY_STRUCTURAL_RESULT"),)
        topology = UnfoldedBlankTopology(
            piece_id=str(piece.key),
            x_segments=piece_x,
            y_segments=(MaterialSegment("Y", "piece_height", float(piece.structural.height), "BOX_BODY_STRUCTURAL_RESULT"),),
            source="BOX_BODY_PHYSICAL_PIECE", revision=1,
        )
        render_data = PartRenderData(
            scene=scene,
            material=material_polygon_from_final_scene(scene),
            fold_guides=fold_guides_from_final_scene(scene),
            unfolded_topology=topology,
        )
        pieces.append(BoxBodyPieceRenderData(
            key=piece.key, role=piece.role,
            formed_w_start=float(piece.formed_w_start), formed_w_end=float(piece.formed_w_end),
            fold_profile=tuple(piece.fold_profile), render_data=render_data,
            formed_outer_width=float(piece.formed_outer_dimensions[0]),
            formed_outer_height=float(piece.formed_outer_dimensions[1]),
        ))
    piece_tuple = tuple(pieces)
    return BoxBodyStructureRenderData(
        structure_type=structure.structure_type, pieces=piece_tuple,
        preview_render_data=_exploded_box_body_preview(piece_tuple),
        warnings=tuple(structure.warnings),
    )


def generate_box_body_structure_parts(
    spec: BoxBodyPartSpec,
    output_dir: str | os.PathLike[str],
    context: ManufacturingContext | None = None,
) -> tuple[PartExportResult, ...]:
    """Export every physical Box Body piece from the same resolved FinalScenes."""
    ctx = context or ManufacturingContext()
    data = build_box_body_structure_render_data(spec, ctx)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    labels = {
        "left": "左箱身", "right": "右箱身", "middle": "中箱身",
        "left_side": "左側板", "right_side": "右側板", "back": "後面板",
        "integral": "箱身",
    }
    results = []
    for piece in data.pieces:
        name = labels.get(piece.role, piece.key) + ".dxf"
        path = root / name
        save_part_render_data_dxf(piece.render_data, path, overwrite=bool(ctx.overwrite))
        results.append(PartExportResult(
            part_kind=piece.key, output_path=str(path),
            exporter_name="final_scene_box_body_structure_export", used_baseline=False,
            baseline_path=None, expected_baseline_path=None,
        ))
    return tuple(results)




def _resolved_endcap_bottom_joint_relation(spec: EndCapPartSpec):
    """Return the explicit BOTTOM relation for this EndCap, or None.

    This intentionally ignores receiving.bottom_external_wrap: that field is a
    legacy persistence/geometry mirror and is not an assembly source of truth.
    """
    from .assembly_joint import AssemblyJoint, AssemblyJointRelation

    part_key = "tail" if bool(spec.is_tail) else "head"
    for raw in tuple(getattr(spec, "assembly_joints", ()) or ()):
        try:
            joint = raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        except Exception:
            continue
        if str(getattr(joint, "subject_part", "")) != part_key and str(getattr(joint, "target_part", "")) != part_key:
            continue
        edge = str(getattr(joint, "edge", "") or "").upper()
        if edge != "BOTTOM":
            continue
        relation = getattr(joint, "relation", None)
        try:
            return relation if isinstance(relation, AssemblyJointRelation) else AssemblyJointRelation(str(relation))
        except Exception:
            return None
    return None


def _replace_receiving_bottom_relief_from_registry(render_data, spec: EndCapPartSpec):
    """Replace the legacy receiving bottom corner cut with certified Joint geometry.

    Receiving lower external wrap is a dedicated lower-face manufacturing relation.
    It is independent from the EndCap's INSERT / OVERLAY / INSERT_OVERLAY selector;
    those high-level intents must not choose or redefine the WRAP relief algorithm.
    """
    if not spec.box_body_structure_state:
        return render_data
    try:
        from .assembly_joint import AssemblyJointRelation
        if not cabinet_family_policy.bottom_relief_registry_applicable(
            spec.model_name, spec.box_body_structure_state
        ):
            return render_data
        if _resolved_endcap_bottom_joint_relation(spec) is not AssemblyJointRelation.WRAP:
            return render_data
    except Exception:
        return render_data

    policy = spec.corner_policy
    if policy is None:
        return render_data

    from shapely.ops import unary_union
    from .assembly_collision import _corner_name_for_component, _scene_with_replaced_primary_cutting
    from .assembly_geometry import restore_unrelieved_endcap_material
    from .certified_relief_registry import lookup_certified_endcap_relief

    resolved = resolve_endcap_request(spec)
    certified = lookup_certified_endcap_relief(
        assembly_intent=policy.bottom_left.type_id,
        endcap_render_data=render_data,
        box_body_x_profile=(),
        endcap_x_profile=resolved.fold_profile_x,
        endcap_y_profile=resolved.fold_profile_y,
        sheet_thickness=resolved.thickness,
        cabinet_family=spec.model_name or "ANY",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=spec.box_body_structure_state,
    )
    if certified is None:
        return render_data

    restored = restore_unrelieved_endcap_material(render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return render_data
    legacy_removed = restored.difference(render_data.material)
    components = (legacy_removed,) if getattr(legacy_removed, "geom_type", "") == "Polygon" else tuple(
        geom for geom in getattr(legacy_removed, "geoms", ())
        if getattr(geom, "geom_type", "") == "Polygon" and float(geom.area) > 1e-9
    )
    bottom_names = {str(item.corner_name) for item in tuple(certified.corner_reliefs or ())}
    retained = []
    for component in components:
        corner_name = _corner_name_for_component(component, restored.bounds)
        if corner_name not in bottom_names:
            retained.append(component)
    all_cuts = tuple(retained) + tuple(certified.cut_polygons or ())
    solved_material = restored.difference(unary_union(all_cuts)) if all_cuts else restored
    if solved_material.is_empty:
        raise ValueError("certified receiving bottom relief removed all EndCap material")
    if not solved_material.is_valid:
        solved_material = solved_material.buffer(0)
    solved_scene = _scene_with_replaced_primary_cutting(render_data.scene, solved_material)
    solved_scene = _scene_with_authoritative_fold_profiles(
        solved_scene, resolved.fold_profile_x, resolved.fold_profile_y
    )
    metadata = dict(getattr(render_data, "metadata", {}) or {})
    metadata["receiving_bottom_relief_rule"] = {
        "rule_id": certified.rule_id,
        "revision": certified.rule_revision,
        "trust_level": certified.trust_level.value,
        "geometry_evidence": dict(certified.geometry_evidence or {}),
    }
    return PartRenderData(
        scene=solved_scene,
        material=material_polygon_from_final_scene(solved_scene),
        fold_guides=fold_guides_from_final_scene(solved_scene),
        metadata=metadata,
        unfolded_topology=getattr(render_data, "unfolded_topology", None),
    )

def _unfolded_topology_for_spec(spec: PartSpec, *, piece_id: str = "") -> UnfoldedBlankTopology | None:
    """Build blank envelope only from authoritative PartSpec/Fold Profile semantics."""
    if isinstance(spec, EndCapPartSpec):
        resolved = resolve_endcap_request(spec)
        x_rows = tuple(resolved.fold_profile_x or ())
        y_rows = tuple(resolved.fold_profile_y or ())
        if not x_rows:
            if resolved.x_topology == "flat":
                x_rows = (FoldProfileSegment(resolved.width, phase6_key="endcap_w_flat"),)
            else:
                # Scalar compatibility: explicit physical segments, not relieved polygon bounds.
                core = max(0.0, resolved.width - 4.0 * resolved.thickness)
                x_rows = (
                    FoldProfileSegment(resolved.nominal_fold_left, phase6_key="yl1"),
                    FoldProfileSegment(core, phase6_key="endcap_w_core"),
                    FoldProfileSegment(resolved.nominal_fold_right, phase6_key="yr1"),
                )
        if not y_rows:
            core = max(0.0, resolved.depth - resolved.depth_comp_t * resolved.thickness)
            y_rows = (
                FoldProfileSegment(resolved.fold_top, phase6_key="ytop1"),
                FoldProfileSegment(resolved.frame_width, phase6_key="fw"),
                FoldProfileSegment(core, phase6_key="endcap_d_core"),
                FoldProfileSegment(resolved.fold_bottom, phase6_key="ybottom1"),
            )
        return UnfoldedBlankTopology(
            piece_id=str(piece_id or ("tail" if resolved.is_tail else "head")),
            x_segments=_profile_material_segments("X", x_rows, source="ENDCAP_FOLD_PROFILE"),
            y_segments=_profile_material_segments("Y", y_rows, source="ENDCAP_FOLD_PROFILE"),
            source="ENDCAP_FOLD_PROFILE", revision=1,
        )
    if isinstance(spec, BoxBodyPartSpec) and spec.fold_profile:
        return UnfoldedBlankTopology(
            piece_id=str(piece_id or "box_body"),
            x_segments=_profile_material_segments("X", spec.fold_profile, source="BOX_BODY_FOLD_PROFILE"),
            y_segments=(MaterialSegment("Y", "box_body_height", float(spec.height), "BOX_BODY_PART_SPEC"),),
            source="BOX_BODY_FOLD_PROFILE", revision=1,
        )
    return None


def build_part_render_data(
    spec: PartSpec, context: ManufacturingContext | None = None
) -> PartRenderData:
    """Return final manufacturing material + scene for pure renderers."""
    scene = build_part_scene(spec, context)
    metadata = {}
    if isinstance(spec, EndCapPartSpec):
        metadata = {
            "nominal_fold_left": _endcap_scalar(spec.fold_left, ae.yl1_def),
            "nominal_fold_right": _endcap_scalar(spec.fold_right, ae.yr1_def),
        }
    render_data = PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=metadata,
        unfolded_topology=_unfolded_topology_for_spec(spec),
    )
    if isinstance(spec, EndCapPartSpec):
        render_data = _replace_receiving_bottom_relief_from_registry(render_data, spec)
    if isinstance(spec, EndCapPartSpec) and tuple(getattr(spec, "resolved_assembly_relief_cuts", ()) or ()):
        from shapely.geometry import Polygon
        from .assembly_collision import (
            _scene_with_replaced_primary_cutting,
            apply_verified_endcap_relief_material,
        )

        cut_polygons = []
        for coords in tuple(spec.resolved_assembly_relief_cuts or ()):
            if len(coords) < 3:
                continue
            polygon = Polygon([(float(x), float(y)) for x, y in coords])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty and float(polygon.area) > 1e-9:
                cut_polygons.append(polygon)
        if cut_polygons:
            solved_material = apply_verified_endcap_relief_material(
                render_data.material, cut_polygons
            )
            if solved_material.is_empty:
                raise ValueError("verified EndCap assembly relief removed all material")
            solved_scene = _scene_with_replaced_primary_cutting(render_data.scene, solved_material)
            resolved = resolve_endcap_request(spec)
            solved_scene = _scene_with_authoritative_fold_profiles(
                solved_scene, resolved.fold_profile_x, resolved.fold_profile_y
            )
            render_data = PartRenderData(
                scene=solved_scene,
                material=material_polygon_from_final_scene(solved_scene),
                fold_guides=fold_guides_from_final_scene(solved_scene),
                metadata=dict(getattr(render_data, "metadata", {}) or {}),
                unfolded_topology=getattr(render_data, "unfolded_topology", None),
            )
    request = getattr(spec, "assembly_relief", None)
    if request is not None and getattr(request, "enabled", True):
        from .assembly_collision import solve_boxbody_endcap_relief

        if isinstance(spec, EndCapPartSpec):
            box_render = build_part_render_data(request.box_body, context)
            solution = solve_boxbody_endcap_relief(
                box_body_render_data=box_render,
                endcap_render_data=render_data,
                clearance=float(request.clearance),
            )
            if not solution.verified:
                raise ValueError("EndCap assembly collision relief failed verification")
            render_data = solution.solved_render_data
    return render_data


def save_part_render_data_dxf(
    render_data: PartRenderData,
    output_path: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> str:
    """Serialize an already-built authoritative FinalScene to DXF.

    This function deliberately does *not* rebuild PartSpec geometry.  It is the
    shared sink for 2D/3D/export consumers that already hold PartRenderData.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(str(destination))

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.tmp-",
        suffix=destination.suffix or ".dxf",
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        ae._save_scene_dxf(str(temp_path), render_data.scene)
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return str(destination)

def _door_export(spec: DoorPartSpec, filepath: str, context: ManufacturingContext):
    _validate_door_part_indicator_fit(spec, context)
    is_indicator_small_door = spec.indicator_window_groups is not None
    if is_indicator_small_door:
        expected = _indicator_shared_expected_path("小門.dxf", context)
        baseline = _indicator_shared_existing_path("小門.dxf", context)
    else:
        expected = _expected_baseline_path(spec.model_name, "門.dxf", context)
        baseline = expected if expected is not None and expected.is_file() else None
    p = _resolved_door_params(spec, context)
    common = dict(
        W_val=p["w"],
        H_val=p["h"],
        T_val=p["t"],
        FW_val=p["fw"],
        draw_stock=context.draw_stock,
        indicator_hole=spec.indicator_hole,
        door_indicator=spec.door_indicator,
        door_indicator_offset=spec.door_indicator_offset,
        is_box_dist=spec.use_box_distance,
        user_features=_door_features_for_legacy_engine(spec, context),
        frame_edges=spec.frame_edges,
    )
    if baseline is not None:
        _call(
            ae.export_stretched_door_dxf,
            filepath,
            None if is_indicator_small_door else str(spec.model_name),
            gap_w_val=p["gap_w"],
            gap_h_val=p["gap_h"],
            fl_val=p["fold_left"],
            fr_val=p["fold_right"],
            ft_val=p["fold_top"],
            fb_val=p["fold_bottom"],
            indicator_window_groups=spec.indicator_window_groups,
            corner_policy=spec.corner_policy,
            **common,
        )
        return "export_stretched_door_dxf", baseline, expected
    if spec.corner_policy is not None:
        _call(
            ae.export_unknown_door_dxf,
            filepath,
            corner_policy=spec.corner_policy,
            gap_w=p["gap_w"], gap_h=p["gap_h"],
            fold_left=p["fold_left"], fold_right=p["fold_right"],
            fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
            **common,
        )
        return "export_unknown_door_dxf", None, None

    _call(
        ae.export_door_dxf,
        filepath,
        gap_w=p["gap_w"],
        gap_h=p["gap_h"],
        fold_left=p["fold_left"],
        fold_right=p["fold_right"],
        fold_top=p["fold_top"],
        fold_bottom=p["fold_bottom"],
        **common,
    )
    return "export_door_dxf", None, expected


def _box_body_export(spec: BoxBodyPartSpec, filepath: str, context: ManufacturingContext):
    expected = _expected_baseline_path(spec.model_name, "箱身.dxf", context)
    baseline = expected if expected is not None and expected.is_file() else None
    _call(
        ae.export_box_body_dxf,
        filepath,
        W_val=spec.width,
        H_val=spec.height,
        D_val=spec.depth,
        T_val=spec.thickness,
        FW_val=spec.frame_width,
        zl1=spec.zl1,
        zl2=spec.zl2,
        zr1=spec.zr1,
        zr2=spec.zr2,
        z_comp=spec.z_comp,
        draw_stock=context.draw_stock,
        model_name=spec.model_name,
        user_features=list(spec.features),
        face_features={key: list(value) for key, value in spec.face_features.items()},
        head_corner_policy=spec.head_corner_policy,
        tail_corner_policy=spec.tail_corner_policy,
        fold_profile=spec.fold_profile or None,
    )
    return "export_box_body_dxf", baseline, expected


def _end_cap_export(spec: EndCapPartSpec, filepath: str, context: ManufacturingContext):
    """Export EndCap through the legacy AE API unless caller supplied resolved geometry.

    The headless adapter contract requires all GUI dimensions and normalized holes to
    cross the public ``export_end_cap_dxf`` seam.  Fully resolved Phase6 geometry still
    serializes the shared Final Scene so 2D/3D/export stay identical.
    """
    # Export must share the same EndCap resolver validation as 2D/3D.
    # Legacy formula export may still consume scalar requests for compatibility,
    # but invalid CornerType assembly semantics must fail before any DXF is written.
    resolve_endcap_request(spec)
    expected = _expected_baseline_path(spec.model_name, "封頭尾.dxf", context)
    baseline = expected if expected is not None and expected.is_file() else None
    has_resolved_geometry = bool(
        spec.corner_policy is not None
        or spec.fold_profile_x or spec.fold_profile_y
        or spec.resolved_assembly_relief_cuts
        or spec.assembly_relief is not None
    )
    if has_resolved_geometry:
        render_data = build_part_render_data(spec, context)
        ae._save_scene_dxf(filepath, render_data.scene)
        return "final_scene_end_cap_export", baseline, expected
    if baseline is not None:
        _call(
            ae.export_stretched_end_cap_dxf,
            filepath, spec.model_name,
            W_val=spec.width, H_val=spec.height, D_val=spec.depth,
            T_val=spec.thickness, FW_val=spec.frame_width,
            draw_stock=context.draw_stock, is_tail=spec.is_tail,
            holes=_legacy_endcap_holes(spec), corner_policy=spec.corner_policy,
        )
        return "export_stretched_end_cap_dxf", baseline, expected
    _call(
        ae.export_end_cap_dxf,
        filepath,
        W_val=spec.width, H_val=spec.height, D_val=spec.depth,
        T_val=spec.thickness, FW_val=spec.frame_width,
        yl1=spec.fold_left, yr1=spec.fold_right,
        ytop1=spec.fold_top, ybottom1=spec.fold_bottom,
        zl1=spec.box_fold_left, zr1=spec.box_fold_right,
        draw_stock=context.draw_stock, is_tail=spec.is_tail,
        holes=_legacy_endcap_holes(spec),
    )
    return "export_end_cap_dxf", baseline, expected


def _base_plate_export(spec: BasePlatePartSpec, filepath: str, context: ManufacturingContext):
    if spec.box_body_fold_profile and spec.box_body_structure_state:
        render_data = build_part_render_data(spec, context)
        ae._save_scene_dxf(filepath, render_data.scene)
        return "final_scene_base_plate_structure_export", None, None
    exporter = ae.export_unknown_base_plate_dxf if spec.corner_policy is not None else ae.export_base_plate_dxf
    kwargs = {"corner_policy": spec.corner_policy} if spec.corner_policy is not None else {}
    _call(
        exporter,
        filepath,
        **kwargs,
        W_val=spec.width,
        H_val=spec.height,
        T_val=spec.thickness,
        shrink_top=spec.shrink_top,
        shrink_bottom=spec.shrink_bottom,
        shrink_left=spec.shrink_left,
        shrink_right=spec.shrink_right,
        bend=spec.bend,
        draw_stock=context.draw_stock,
        user_features=list(spec.features),
    )
    return ("export_unknown_base_plate_dxf" if spec.corner_policy is not None else "export_base_plate_dxf"), None, None


def _indicator_box_export(spec: IndicatorBoxPartSpec, filepath: str, context: ManufacturingContext):
    # Indicator boxes are globally shared parts.  Manufacturing owns only the part role;
    # AE owns discovery of the actual shared baseline folder under the scoped resource root.
    expected = _indicator_shared_expected_path("盒子.dxf", context)
    baseline = _indicator_shared_existing_path("盒子.dxf", context)
    if baseline is None:
        raise FileNotFoundError(f"AE_BASELINE_MISSING: {expected}")
    _call(
        ae.export_stretched_indicator_box_dxf,
        filepath, None, list(spec.layer_groups),
        T_val=spec.thickness,
        draw_stock=context.draw_stock,
        user_features=list(spec.features),
        corner_policy=spec.corner_policy,
    )
    return "export_stretched_indicator_box_dxf", baseline, expected


def _part_kind(spec: PartSpec) -> str:
    if isinstance(spec, DoorPartSpec):
        return "door"
    if isinstance(spec, BoxBodyPartSpec):
        return "box_body"
    if isinstance(spec, EndCapPartSpec):
        return "end_cap_tail" if spec.is_tail else "end_cap_head"
    if isinstance(spec, BasePlatePartSpec):
        return "base_plate"
    if isinstance(spec, IndicatorBoxPartSpec):
        return "indicator_box"
    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


def _export_to_temp(spec: PartSpec, temp_path: str, context: ManufacturingContext):
    if isinstance(spec, DoorPartSpec):
        return _door_export(spec, temp_path, context)
    if isinstance(spec, BoxBodyPartSpec):
        return _box_body_export(spec, temp_path, context)
    if isinstance(spec, EndCapPartSpec):
        return _end_cap_export(spec, temp_path, context)
    if isinstance(spec, BasePlatePartSpec):
        return _base_plate_export(spec, temp_path, context)
    if isinstance(spec, IndicatorBoxPartSpec):
        return _indicator_box_export(spec, temp_path, context)
    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


def generate_part(
    spec: PartSpec,
    output_path: str | os.PathLike[str],
    context: ManufacturingContext | None = None,
) -> PartExportResult:
    """Export one part without GUI dependency, replacing destination atomically."""
    ctx = context or ManufacturingContext()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not ctx.overwrite:
        raise FileExistsError(str(destination))

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.tmp-",
        suffix=destination.suffix or ".dxf",
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with _scoped_ae_resource_root(ctx):
            exporter_name, baseline, expected = _export_to_temp(spec, str(temp_path), ctx)
        os.replace(temp_path, destination)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise

    return PartExportResult(
        part_kind=_part_kind(spec),
        output_path=str(destination),
        exporter_name=exporter_name,
        used_baseline=baseline is not None,
        baseline_path=str(baseline) if baseline is not None else None,
        expected_baseline_path=str(expected) if expected is not None else None,
    )


def save_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> dict[str, str]:
    """Export the exact canonical ResolvedManufacturingGeometry to per-part DXF.

    This is intentionally a sink: it never reconstructs PartSpec or recomputes
    Corner/Relief.  Every file is serialized from the same PartRenderData already
    consumed by 2D/Single3D/Assembly3D.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    for part in tuple(getattr(resolved_geometry, "parts", ()) or ()):
        key = str(getattr(part, "part_key", "") or "").strip()
        if not key:
            raise ValueError("resolved manufacturing part missing part_key")
        render_data = getattr(part, "render_data", None)
        if render_data is None:
            raise ValueError(f"resolved manufacturing part missing render_data: {key}")
        # Piece-level canonical parts are not silently merged: each physical
        # piece is exported from its own already-resolved render_data.
        pieces = tuple(getattr(render_data, "pieces", ()) or ())
        if pieces:
            for index, piece in enumerate(pieces, start=1):
                piece_render = getattr(piece, "render_data", None)
                if piece_render is None:
                    raise ValueError(f"resolved piece missing render_data: {key}#{index}")
                piece_key = str(getattr(piece, "piece_key", "") or f"piece{index}")
                path = root / f"{key}__{piece_key}.dxf"
                outputs[f"{key}:{piece_key}"] = save_part_render_data_dxf(
                    piece_render, path, overwrite=overwrite
                )
        else:
            path = root / f"{key}.dxf"
            outputs[key] = save_part_render_data_dxf(render_data, path, overwrite=overwrite)
    return outputs


def resolved_manufacturing_nc_capability() -> dict[str, object]:
    """Report the current repository's production NC sink capability explicitly.

    PHASE6 currently has no production NC writer at the canonical FinalScene
    boundary.  Returning an explicit capability record prevents callers from
    inventing a second geometry path merely to claim NC support.
    """
    return {
        "available": False,
        "reason": "production NC sink is not implemented at the ResolvedManufacturingGeometry boundary",
        "canonical_input": "ResolvedManufacturingGeometry",
    }
