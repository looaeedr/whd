"""Baseline/resource policy and legacy-call adaptation for manufacturing.

This module is upstream of the stable manufacturing_api facade and does not import it.
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

from .manufacturing_render_data import (
    PartRenderData,
    fold_guides_from_final_scene,
    material_polygon_from_final_scene,
)

_RESOURCE_LOCK = threading.RLock()

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


def _extract_endcap_shared_6p4_mother_rule(path: Path) -> dict[str, object] | None:
    """Extract the semantic Ø6.4 mother offset from EndCap baseline geometry.

    The datum is the center of the post-relief straight segment carrying the
    shared Ø6.4 pair.  The returned offset is local (axial, inward), never raw
    DXF XY, so parts with different overall widths can consume the same rule.
    """
    from math import hypot

    from ae_engine.baseline_source import load_baseline_dxf_source
    from shapely.geometry import Polygon

    doc = load_baseline_dxf_source(path)
    msp = doc.modelspace()
    outlines = list(msp.query('LWPOLYLINE[layer=="CUTTING"]'))
    if not outlines:
        return None

    polygons = []
    for entity in outlines:
        pts = [(float(x), float(y)) for x, y, *_ in entity.get_points()]
        if len(pts) < 3:
            continue
        polygon = Polygon(pts)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty and float(polygon.area) > 1e-9:
            polygons.append((float(polygon.area), polygon, pts))
    if not polygons:
        return None
    _area, outer, pts = max(polygons, key=lambda row: row[0])
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]

    holes = [
        entity for entity in msp.query("CIRCLE")
        if abs(float(entity.dxf.radius) - 3.2) <= 1e-6
    ]
    if len(holes) < 2:
        return None

    candidates = []
    for p, q in zip(pts, pts[1:]):
        vx, vy = float(q[0] - p[0]), float(q[1] - p[1])
        length = hypot(vx, vy)
        if length <= 1e-9:
            continue
        tangent = (vx / length, vy / length)
        center = ((float(p[0]) + float(q[0])) / 2.0, (float(p[1]) + float(q[1])) / 2.0)
        nearby = []
        for entity in holes:
            x, y = float(entity.dxf.center.x), float(entity.dxf.center.y)
            axial = (x - center[0]) * tangent[0] + (y - center[1]) * tangent[1]
            perpendicular = abs(
                (x - center[0]) * (-tangent[1]) + (y - center[1]) * tangent[0]
            )
            if abs(axial) <= length / 2.0 + 1e-6:
                nearby.append((perpendicular, axial, entity))
        if len(nearby) < 2:
            continue
        nearby.sort(key=lambda row: row[0])
        selected = nearby[:2]
        candidates.append((
            sum(row[0] for row in selected) / 2.0,
            center,
            tangent,
            length,
            selected,
        ))
    if not candidates:
        return None

    _distance, center, tangent, length, selected = min(candidates, key=lambda row: row[0])
    # Canonical tangent orientation: lexicographically positive.
    if tangent[0] < -1e-9 or (abs(tangent[0]) <= 1e-9 and tangent[1] < 0.0):
        tangent = (-tangent[0], -tangent[1])

    centroid = (float(outer.centroid.x), float(outer.centroid.y))
    normal = (-tangent[1], tangent[0])
    if (
        (centroid[0] - center[0]) * normal[0]
        + (centroid[1] - center[1]) * normal[1]
    ) < 0.0:
        inward = (-normal[0], -normal[1])
    else:
        inward = normal

    ranked = []
    for _perpendicular, _old_axial, entity in selected:
        x, y = float(entity.dxf.center.x), float(entity.dxf.center.y)
        axial = (x - center[0]) * tangent[0] + (y - center[1]) * tangent[1]
        inward_offset = (x - center[0]) * inward[0] + (y - center[1]) * inward[1]
        ranked.append((axial, inward_offset, entity))
    axial, inward_offset, mother = max(ranked, key=lambda row: row[0])

    return {
        "datum_kind": "POST_RELIEF_CENTER_SPAN_CENTER",
        "source_file": "封頭尾.dxf",
        "source_handle": str(getattr(mother.dxf, "handle", "") or ""),
        "axial_offset": float(axial),
        "inward_offset": float(inward_offset),
        "source_segment_length": float(length),
    }


def _divider_post_relief_center_frame(material):
    """Return canonical Divider post-relief center, tangent and inward axes."""
    minx, _miny, _maxx, _maxy = map(float, material.bounds)
    coords = list(material.exterior.coords)
    candidates = []
    for p, q in zip(coords, coords[1:]):
        if abs(float(p[0]) - minx) > 1e-5 or abs(float(q[0]) - minx) > 1e-5:
            continue
        length = abs(float(q[1]) - float(p[1]))
        if length > 1e-6:
            candidates.append((length, p, q))
    if not candidates:
        raise ValueError("Divider post-relief center span unavailable")
    _length, p, q = max(candidates, key=lambda row: row[0])
    y0, y1 = sorted((float(p[1]), float(q[1])))
    return (
        (float(minx), (y0 + y1) / 2.0),
        (0.0, 1.0),
        (1.0, 0.0),
    )


def apply_divider_endcap_shared_6p4_datum(render_data: "PartRenderData") -> "PartRenderData":
    """Rigidly translate Divider A/B/C to the EndCap mother datum.

    The outer relief is already final when this runs.  Only the three baseline
    Ø6.4 circles move; their internal A→B / A→C vectors remain untouched.
    """
    from .sheetmetal_drawing import CirclePrimitive, DrawingScene

    metadata = dict(getattr(render_data, "metadata", {}) or {})
    mother = dict(metadata.get("endcap_shared_6p4_mother_rule") or {})
    if not mother:
        return render_data

    holes = [
        primitive for primitive in getattr(render_data.scene, "primitives", ())
        if isinstance(primitive, CirclePrimitive)
        and str(getattr(primitive, "source_type", "")) == "baseline_divider_hole"
        and abs(float(primitive.radius) - 3.2) <= 1e-6
    ]
    if len(holes) != 3:
        raise ValueError(f"Receiving Divider shared Ø6.4 requires exactly 3 baseline holes, got {len(holes)}")

    anchor = min(holes, key=lambda primitive: float(primitive.center.x))
    center, tangent, inward = _divider_post_relief_center_frame(render_data.material)
    target = (
        center[0]
        + float(mother["axial_offset"]) * tangent[0]
        + float(mother["inward_offset"]) * inward[0],
        center[1]
        + float(mother["axial_offset"]) * tangent[1]
        + float(mother["inward_offset"]) * inward[1],
    )
    delta = (
        float(target[0]) - float(anchor.center.x),
        float(target[1]) - float(anchor.center.y),
    )

    original_vectors = tuple(
        (
            str(getattr(hole, "source_id", "") or ""),
            float(hole.center.x) - float(anchor.center.x),
            float(hole.center.y) - float(anchor.center.y),
        )
        for hole in holes
        if hole is not anchor
    )
    moved_ids = {id(hole) for hole in holes}
    scene = DrawingScene()
    for primitive in getattr(render_data.scene, "primitives", ()):
        if id(primitive) in moved_ids:
            primitive = replace(
                primitive,
                center=Vec2(
                    float(primitive.center.x) + delta[0],
                    float(primitive.center.y) + delta[1],
                ),
            )
        scene.add(primitive)

    metadata["divider_endcap_shared_6p4_datum"] = {
        "datum_kind": "POST_RELIEF_CENTER_SPAN_CENTER",
        "mother_source_file": str(mother.get("source_file") or "封頭尾.dxf"),
        "mother_source_handle": str(mother.get("source_handle") or ""),
        "mother_axial_offset": float(mother["axial_offset"]),
        "mother_inward_offset": float(mother["inward_offset"]),
        "divider_center": tuple(float(v) for v in center),
        "anchor_before": (float(anchor.center.x), float(anchor.center.y)),
        "anchor_after": (float(target[0]), float(target[1])),
        "rigid_delta": tuple(float(v) for v in delta),
        "relative_vectors": original_vectors,
    }
    return replace(
        render_data,
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=metadata,
    )


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
