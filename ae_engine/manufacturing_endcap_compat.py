"""Legacy feature and EndCap request compatibility for manufacturing.

Adapts canonical specs to legacy AE inputs without owning scene/export orchestration.
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

from .manufacturing_baseline_policy import (
    _baseline_path,
    _endcap_baseline_feature_model_name,
    _call,
    _has_named_parameter,
)
from .manufacturing_door_indicator import _resolved_door_params, _resolved_door_corner_policy
from .manufacturing_render_data import material_polygon_from_final_scene

_FEATURE_TYPES = (CircleFeature, RectFeature, ProfileFeature)

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

    corner_policy = _resolved_door_corner_policy(spec, p["fw"])
    builder = build_unknown_door_result if corner_policy is not None else build_door_result
    builder_kwargs = dict(
        w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
        gap_w=p["gap_w"], gap_h=p["gap_h"],
        fold_left=p["fold_left"], fold_right=p["fold_right"],
        fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
        frame_edges=spec.frame_edges,
    )
    if corner_policy is not None:
        builder_kwargs["corner_policy"] = corner_policy
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


ResolvedEndCapRequest = _manufacturing_requests.ResolvedEndCapRequest


def _endcap_scalar(value: float | None, fallback: float) -> float:
    return float(fallback if value is None else value)


def resolve_endcap_request(spec: EndCapPartSpec) -> ResolvedEndCapRequest:
    """Resolve EndCap request precedence through the bounded request owner."""
    return _manufacturing_requests.resolve_endcap_request(
        spec,
        endcap_scalar=_endcap_scalar,
        default_fold_left=ae.yl1_def,
        default_fold_right=ae.yr1_def,
        default_fold_top=ae.ytop1_def,
        default_fold_bottom=ae.ybottom1_def,
        resolve_assembly_semantics=resolve_endcap_policy_assembly_semantics,
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
