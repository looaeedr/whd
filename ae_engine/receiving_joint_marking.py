# -*- coding: utf-8 -*-
"""Receiving Joint Placement MARKING production activation.

This module owns the first production policy only. It consumes authoritative
physical-part regions/placements and enriches the locator FinalScene. DXF
serialization remains downstream and geometry-neutral.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .assembly_contact import resolve_legal_coplanar_contact
from .assembly_geometry import (
    folded_mesh_with_flat_uv_from_polygon,
    resolve_physical_mating_region,
    world_skin_with_flat_uv,
)
from .assembly_marking_geometry import (
    backproject_locator_world_points,
    resolve_contact_local_frame,
    resolve_side_boundary_pair,
)
from .cabinet_types import policy as cabinet_family_policy
from .contracts import (
    FoldProfileSegment,
    JointMarkingFailurePolicy,
    JointMarkingPolicy,
    JointMarkingProductionStatus,
    ResolvedJointMarkingResult,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
    ResolvedPhysicalMatingRegion,
)
from .door_dividers import (
    derive_box_body_dividers,
    resolve_inner_door_lower_frame_role,
)
from .inner_door_frames import (
    LOWER_TERMINAL_FACE,
    derive_all_inner_door_frames,
    inner_door_frame_mating_region,
    inner_door_frame_stable_id,
)
from .joint_marking_policy import (
    stable_joint_mark_id,
    validate_expected_region_coverage,
)
from .sheetmetal_drawing import DrawingScene, LinePrimitive


RECEIVING_POLICY_ID = "RECEIVING_INNER_DOOR_VERTICAL_FRAME_TO_SHARED_DIVIDER_V1"
GATE_B_STATE = "JOINT_PLACEMENT_MARKING_PRODUCTION_ENABLED"
ALLOW_EXPORT_WITH_DIAGNOSTIC = "ALLOW_EXPORT_WITH_DIAGNOSTIC"

PRODUCTION_JOINT_MARKING_FAILURE_POLICY = JointMarkingFailurePolicy(
    disposition=ALLOW_EXPORT_WITH_DIAGNOSTIC,
)

RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY = JointMarkingPolicy(
    policy_id=RECEIVING_POLICY_ID,
    revision=1,
    enabled=True,
    locator_selector="RECEIVING_SHARED_HORIZONTAL_DIVIDER",
    attached_selector="RECEIVING_INNER_DOOR_VERTICAL_FRAME",
    locator_contact_region="CORE_PHYSICAL_SEGMENT",
    attached_contact_region=LOWER_TERMINAL_FACE,
    footprint_mode="SIDE_BOUNDARY_PAIR",
    boundary_frame_contract={
        "frame_version": "CONTACT_LOCAL_FRAME_V1",
        "basis_part": "LOCATOR",
        "basis_contact_region": "CORE_PHYSICAL_SEGMENT",
        "longitudinal_flat_axis": "+X",
        "cross_flat_axis": "+Y",
        "normal_rule": "LOCATOR_TO_ATTACHED",
        "handedness_rule": "FLAT_BASIS_PRESERVING",
        "negative_role": "SIDE_NEGATIVE",
        "positive_role": "SIDE_POSITIVE",
    },
    contact_span_contract="EXPECTED_REGION_COVERAGE",
    allowed_overlap_contract="NONE",
)


@dataclass(frozen=True)
class ReceivingJointMarkingResolution:
    geometry: ResolvedManufacturingGeometry
    results: tuple[ResolvedJointMarkingResult, ...]
    status: JointMarkingProductionStatus


def resolve_joint_marking_production_status() -> JointMarkingProductionStatus:
    return JointMarkingProductionStatus(
        gate_state=GATE_B_STATE,
        activation_enabled=True,
        export_disposition=PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition,
        production_policy_count=1,
    )


def joint_marking_export_summary(results) -> tuple[dict[str, object], ...]:
    """Return the machine-readable export/manufacturing summary required by EC-12."""
    rows = []
    for item in tuple(results or ()):
        if not isinstance(item, ResolvedJointMarkingResult):
            raise TypeError(
                "joint marking summary requires ResolvedJointMarkingResult values"
            )
        rows.append(
            {
                "policy_id": str(item.policy_id),
                "policy_revision": int(item.policy_revision),
                "locator_part_id": str(item.locator_part_id),
                "attached_part_id": str(item.attached_part_id),
                "status": str(item.status),
                "diagnostic_code": item.diagnostic_code,
                "export_disposition": str(item.export_disposition),
            }
        )
    return tuple(rows)


def _fail(
    *,
    locator_part_id: str,
    attached_part_id: str,
    diagnostic_code: str,
    detail: str,
    evidence: Mapping[str, object] | None = None,
) -> ResolvedJointMarkingResult:
    return ResolvedJointMarkingResult(
        policy_id=RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY.policy_id,
        policy_revision=RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY.revision,
        locator_part_id=str(locator_part_id or ""),
        attached_part_id=str(attached_part_id or ""),
        status="SKIPPED_FAIL_CLOSED",
        mark_ids=(),
        diagnostic_code=str(diagnostic_code),
        diagnostic_detail=str(detail or ""),
        export_disposition=PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition,
        evidence=dict(evidence or {}),
    )


def _part_map(
    geometry: ResolvedManufacturingGeometry,
) -> dict[str, ResolvedManufacturingPart]:
    return {
        str(part.part_key): part
        for part in tuple(geometry.parts or ())
    }


def _normalized_columns(
    snapshot,
) -> tuple[tuple[float, tuple[float, ...]], ...]:
    return tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in tuple(
            dict(snapshot or {}).get("door_layout_columns") or ()
        )
    )


def _inner_door_items(snapshot) -> tuple[dict[str, object], ...]:
    rows = []
    for raw in tuple(dict(snapshot or {}).get("inner_doors") or ()):
        if isinstance(raw, Mapping):
            item = dict(raw)
            stable_id = str(item.get("stable_id") or "").strip()
            if stable_id:
                rows.append(item)
    return tuple(rows)


def _derived_receiving_parts(snapshot):
    """Derive semantic topology owners; never invent missing geometry."""
    data = dict(snapshot or {})
    t = float(data.get("t", 2.0))
    fw = float(data.get("fw", 29.0))
    scope = (
        str(data.get("door_layout_scope") or "receiving-main").strip()
        or "receiving-main"
    )
    dividers = derive_box_body_dividers(
        _normalized_columns(data),
        depth=float(data.get("d", 0.0)),
        thickness=t,
        layout_scope=scope,
        handle_edges=dict(data.get("door_handle_edges") or {}),
        model_name="受電箱",
        frame_width=fw,
    )
    frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(data)
    frames = derive_all_inner_door_frames(frame_sets)
    return tuple(dividers), tuple(frames)


def _sub3(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add3(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale3(v, k):
    return tuple(float(v[i]) * float(k) for i in range(3))


def _dot3(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross3(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm3(v):
    return math.sqrt(sum(float(value) * float(value) for value in v))


def _normalize3(v):
    magnitude = _norm3(v)
    if magnitude <= 1e-12:
        raise ValueError("degenerate physical-face vector")
    return tuple(float(value) / magnitude for value in v)


def _triangle_normal3(triangle):
    a, b, c = tuple(triangle)
    return _normalize3(_cross3(_sub3(b, a), _sub3(c, a)))


def _plane_basis3(normal):
    n = _normalize3(normal)
    reference = min(
        (
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        key=lambda axis: abs(_dot3(axis, n)),
    )
    u = _normalize3(_cross3(reference, n))
    v = _normalize3(_cross3(n, u))
    return u, v


def _resolve_divider_core_support_region(
    divider,
    part: ResolvedManufacturingPart,
    *,
    dimensions,
    sheet_thickness: float,
    attached_outward_normal,
) -> ResolvedPhysicalMatingRegion:
    render_data = part.render_data
    mapped = tuple(
        folded_mesh_with_flat_uv_from_polygon(
            render_data.material,
            tuple(divider.fold_profile),
            (
                FoldProfileSegment(
                    length=float(divider.span),
                    angle=None,
                    phase6_key="divider_span",
                ),
            ),
            fold_guides=tuple(
                getattr(render_data, "fold_guides", ()) or ()
            ),
        )
    )
    skins = tuple(
        world_skin_with_flat_uv(
            mapped,
            str(part.placement),
            dimensions,
            offset=tuple(part.offset),
            sheet_thickness=float(sheet_thickness),
        )
    )
    core = dict(
        divider.physical_geometry_contract["core_physical_segment"]
    )
    band_start, band_end = map(float, core["flat_band"])
    selected = []
    selected_normal = None
    target_normal = _normalize3(attached_outward_normal)

    for record in skins:
        centroid_x = (
            sum(float(point[0]) for point in record.flat) / 3.0
        )
        if not (
            band_start + 1e-8
            < centroid_x
            < band_end - 1e-8
        ):
            continue
        mid_normal = _triangle_normal3(record.world)
        outward = tuple(
            float(record.side) * value for value in mid_normal
        )
        if _norm3(_add3(outward, target_normal)) <= 1e-6:
            selected.append(record)
            selected_normal = outward

    if not selected or selected_normal is None:
        raise ValueError(
            "authoritative Divider core support skin is unresolved"
        )

    origin = tuple(float(v) for v in selected[0].world[0])
    axis_u, axis_v = _plane_basis3(selected_normal)

    def project(point):
        delta = _sub3(point, origin)
        return (
            _dot3(delta, axis_u),
            _dot3(delta, axis_v),
        )

    polygons = [
        Polygon(tuple(project(point) for point in record.world))
        for record in selected
    ]
    face = unary_union(polygons)
    if (
        str(getattr(face, "geom_type", "")) != "Polygon"
        or float(face.area) <= 0.0
    ):
        raise ValueError(
            "authoritative Divider core support face "
            "is not one bounded polygon"
        )

    world_polygon = tuple(
        _add3(
            origin,
            _add3(
                _scale3(axis_u, float(x)),
                _scale3(axis_v, float(y)),
            ),
        )
        for x, y in tuple(face.exterior.coords)[:-1]
    )
    return ResolvedPhysicalMatingRegion(
        part_id=str(divider.stable_id),
        region_id="CORE_PHYSICAL_SEGMENT",
        region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=(origin, tuple(selected_normal)),
        outward_normal=tuple(selected_normal),
        world_polygon=world_polygon,
        flat_mapping=tuple(selected),
        provenance={
            "source": (
                "DIVIDER_CORE_PHYSICAL_SEGMENT_MAPPED_SKIN"
            ),
            "flat_band": (band_start, band_end),
            "placement": str(part.placement),
        },
    )


def _marking_line_signature(p1, p2):
    a = (
        round(float(p1[0]), 9),
        round(float(p1[1]), 9),
    )
    b = (
        round(float(p2[0]), 9),
        round(float(p2[1]), 9),
    )
    return tuple(sorted((a, b)))


def _clean_prior_joint_markings(render_data):
    metadata = dict(
        getattr(render_data, "metadata", {}) or {}
    )
    prior = tuple(metadata.get("joint_markings") or ())
    owned = {
        _marking_line_signature(row["p1"], row["p2"])
        for row in prior
        if isinstance(row, Mapping)
        and str(row.get("source") or "")
        == "JOINT_PLACEMENT_MARKING"
        and row.get("p1") is not None
        and row.get("p2") is not None
    }
    scene = DrawingScene()
    for primitive in tuple(
        getattr(render_data.scene, "primitives", ()) or ()
    ):
        if (
            isinstance(primitive, LinePrimitive)
            and str(primitive.layer) == "MARKING"
            and _marking_line_signature(
                (primitive.p1.x, primitive.p1.y),
                (primitive.p2.x, primitive.p2.y),
            )
            in owned
        ):
            continue
        scene.add(primitive)
    metadata["joint_markings"] = tuple(
        row
        for row in prior
        if not (
            isinstance(row, Mapping)
            and str(row.get("source") or "")
            == "JOINT_PLACEMENT_MARKING"
        )
    )
    return scene, metadata


def _clean_geometry_prior_joint_markings(
    geometry: ResolvedManufacturingGeometry,
) -> ResolvedManufacturingGeometry:
    parts = []
    for part in tuple(geometry.parts or ()):
        scene, metadata = _clean_prior_joint_markings(
            part.render_data
        )
        if (
            scene.primitives
            == list(
                getattr(part.render_data.scene, "primitives", ())
                or ()
            )
            and metadata
            == dict(
                getattr(part.render_data, "metadata", {})
                or {}
            )
        ):
            parts.append(part)
            continue
        parts.append(
            replace(
                part,
                render_data=replace(
                    part.render_data,
                    scene=scene,
                    metadata=metadata,
                ),
            )
        )
    diagnostics = tuple(
        item
        for item in tuple(geometry.diagnostics or ())
        if not isinstance(item, ResolvedJointMarkingResult)
    )
    return replace(
        geometry,
        parts=tuple(parts),
        diagnostics=diagnostics,
    )


def _replace_part(
    geometry: ResolvedManufacturingGeometry,
    part_key: str,
    render_data,
) -> ResolvedManufacturingGeometry:
    parts = tuple(
        replace(part, render_data=render_data)
        if str(part.part_key) == str(part_key)
        else part
        for part in tuple(geometry.parts or ())
    )
    return replace(geometry, parts=parts)


def _solve_one(
    *,
    geometry,
    divider,
    frame,
    dimensions,
    sheet_thickness,
):
    policy = RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY
    locator_id = str(divider.stable_id)
    attached_id = str(frame.stable_id)
    parts = _part_map(geometry)
    locator_part = parts.get(locator_id)
    if locator_part is None:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="LOCATOR_MISSING",
                detail=(
                    "exact shared Divider physical part is absent "
                    "from resolved manufacturing geometry"
                ),
            ),
            (),
        )
    attached_part = parts.get(attached_id)
    if attached_part is None:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="ATTACHED_MISSING",
                detail=(
                    "authoritative vertical frame physical part "
                    "is absent from resolved manufacturing geometry"
                ),
            ),
            (),
        )

    try:
        attached = resolve_physical_mating_region(
            part_id=attached_id,
            semantic=inner_door_frame_mating_region(
                frame,
                LOWER_TERMINAL_FACE,
            ),
            render_data=attached_part.render_data,
            x_profile=tuple(frame.fold_profile),
            y_profile=(
                FoldProfileSegment(
                    length=float(frame.span),
                    angle=None,
                    phase6_key="frame_span",
                ),
            ),
            placement=str(attached_part.placement),
            dimensions=dimensions,
            offset=tuple(attached_part.offset),
            sheet_thickness=float(sheet_thickness),
        )
    except (TypeError, ValueError) as exc:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="MATING_REGION_UNRESOLVED",
                detail=str(exc),
            ),
            (),
        )

    try:
        locator = _resolve_divider_core_support_region(
            divider,
            locator_part,
            dimensions=dimensions,
            sheet_thickness=float(sheet_thickness),
            attached_outward_normal=attached.outward_normal,
        )
    except (TypeError, ValueError) as exc:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="MATING_REGION_UNRESOLVED",
                detail=str(exc),
            ),
            (),
        )

    contact_result = resolve_legal_coplanar_contact(
        locator,
        attached,
        allowed_overlap_mode=policy.allowed_overlap_contract,
    )
    if (
        contact_result.status != "LEGAL_CONTACT"
        or contact_result.contact is None
    ):
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code=str(
                    contact_result.diagnostic_code
                    or "CONTACT_NOT_FOUND"
                ),
                detail=(
                    "legal coplanar contact could not be resolved"
                ),
                evidence=dict(contact_result.evidence or {}),
            ),
            (),
        )
    contact = contact_result.contact

    coverage = validate_expected_region_coverage(
        attached,
        contact.overlap_world,
    )
    if coverage.status != "COVERED":
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code=str(
                    coverage.diagnostic_code
                    or "CONTACT_SPAN_BELOW_MINIMUM"
                ),
                detail=(
                    "expected terminal region is not fully covered"
                ),
                evidence=dict(coverage.evidence or {}),
            ),
            (),
        )

    frame_result = resolve_contact_local_frame(
        contact,
        longitudinal_flat_axis=str(
            policy.boundary_frame_contract[
                "longitudinal_flat_axis"
            ]
        ),
        cross_flat_axis=str(
            policy.boundary_frame_contract[
                "cross_flat_axis"
            ]
        ),
    )
    if (
        frame_result.status != "RESOLVED"
        or frame_result.frame is None
    ):
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code=str(
                    frame_result.diagnostic_code
                    or "BOUNDARY_FRAME_UNRESOLVED"
                ),
                detail=(
                    "contact-local frame could not be resolved"
                ),
                evidence=dict(frame_result.evidence or {}),
            ),
            (),
        )

    pair_result = resolve_side_boundary_pair(
        contact,
        frame_result.frame,
    )
    if (
        pair_result.status != "RESOLVED"
        or pair_result.pair is None
    ):
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code=str(
                    pair_result.diagnostic_code
                    or "BOUNDARY_PAIR_AMBIGUOUS"
                ),
                detail=(
                    "SIDE_BOUNDARY_PAIR could not be resolved"
                ),
                evidence=dict(pair_result.evidence or {}),
            ),
            (),
        )

    line_rows = []
    mark_ids = []
    for boundary in (
        pair_result.pair.negative,
        pair_result.pair.positive,
    ):
        back = backproject_locator_world_points(
            contact,
            boundary.world_segment,
        )
        if (
            back.status != "RESOLVED"
            or len(back.flat_points) != 2
        ):
            return (
                _fail(
                    locator_part_id=locator_id,
                    attached_part_id=attached_id,
                    diagnostic_code="BACKPROJECTION_FAILED",
                    detail="locator-only backprojection failed",
                    evidence=dict(back.evidence or {}),
                ),
                (),
            )
        p1, p2 = tuple(back.flat_points)
        line = LineString((p1, p2))
        material = locator_part.render_data.material
        if (
            line.is_empty
            or float(line.length) <= 0.0
            or not material.covers(line)
        ):
            return (
                _fail(
                    locator_part_id=locator_id,
                    attached_part_id=attached_id,
                    diagnostic_code=(
                        "MARK_OUTSIDE_FINAL_MATERIAL"
                    ),
                    detail=(
                        "resolved mark is outside locator Final "
                        "Material or crosses a CUTTING void"
                    ),
                ),
                (),
            )
        role = str(boundary.role)
        mark_id = stable_joint_mark_id(
            policy.policy_id,
            locator_id,
            attached_id,
            role,
        )
        mark_ids.append(mark_id)
        line_rows.append(
            {
                "mark_id": mark_id,
                "boundary_role": role,
                "locator_part_id": locator_id,
                "attached_part_id": attached_id,
                "p1": (
                    float(p1[0]),
                    float(p1[1]),
                ),
                "p2": (
                    float(p2[0]),
                    float(p2[1]),
                ),
                "source": "JOINT_PLACEMENT_MARKING",
            }
        )

    return (
        ResolvedJointMarkingResult(
            policy_id=policy.policy_id,
            policy_revision=policy.revision,
            locator_part_id=locator_id,
            attached_part_id=attached_id,
            status="EMITTED",
            mark_ids=tuple(mark_ids),
            diagnostic_code=None,
            diagnostic_detail="",
            export_disposition=(
                PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition
            ),
            evidence={
                "locator_region": locator.region_id,
                "attached_region": attached.region_id,
                "footprint_mode": policy.footprint_mode,
                "contact_span_contract": (
                    policy.contact_span_contract
                ),
                "boundary_frame_contract": dict(
                    policy.boundary_frame_contract
                ),
            },
        ),
        tuple(line_rows),
    )


def resolve_receiving_joint_markings(
    snapshot,
    geometry: ResolvedManufacturingGeometry,
    *,
    dimensions,
    sheet_thickness: float,
    cabinet_family="受電箱",
) -> ReceivingJointMarkingResolution:
    if not isinstance(
        geometry,
        ResolvedManufacturingGeometry,
    ):
        raise TypeError(
            "geometry must be ResolvedManufacturingGeometry"
        )

    status = resolve_joint_marking_production_status()
    geometry = _clean_geometry_prior_joint_markings(
        geometry
    )
    family = str(
        cabinet_family
        or dict(snapshot or {}).get("model")
        or ""
    ).strip()
    if family != "受電箱":
        return ReceivingJointMarkingResolution(
            geometry=geometry,
            results=(),
            status=status,
        )

    items = _inner_door_items(snapshot)
    if not items:
        return ReceivingJointMarkingResolution(
            geometry=geometry,
            results=(),
            status=status,
        )

    try:
        dividers, frames = _derived_receiving_parts(
            snapshot
        )
    except (TypeError, ValueError) as exc:
        results = []
        for item in items:
            door_id = str(item["stable_id"])
            for side in ("left", "right"):
                results.append(
                    _fail(
                        locator_part_id="",
                        attached_part_id=(
                            inner_door_frame_stable_id(
                                door_id,
                                side,
                            )
                        ),
                        diagnostic_code="STALE_STABLE_ID",
                        detail=str(exc),
                    )
                )
        return ReceivingJointMarkingResolution(
            geometry=replace(
                geometry,
                diagnostics=(
                    tuple(geometry.diagnostics or ())
                    + tuple(results)
                ),
            ),
            results=tuple(results),
            status=status,
        )

    frame_by_id = {
        str(frame.stable_id): frame
        for frame in frames
    }
    divider_by_id = {
        str(divider.stable_id): divider
        for divider in dividers
    }
    all_results = []
    lines_by_locator = {}

    for item in items:
        door_id = str(item["stable_id"])
        previous = dict(
            item.get("lower_frame_role") or {}
        )
        role = resolve_inner_door_lower_frame_role(
            door_id,
            dividers,
            previous_divider_stable_id=(
                str(
                    previous.get("divider_stable_id")
                    or ""
                ).strip()
                or None
            ),
        )
        attached_ids = tuple(
            inner_door_frame_stable_id(
                door_id,
                side,
            )
            for side in ("left", "right")
        )
        if role is None:
            for attached_id in attached_ids:
                all_results.append(
                    _fail(
                        locator_part_id=str(
                            previous.get(
                                "divider_stable_id"
                            )
                            or ""
                        ),
                        attached_part_id=attached_id,
                        diagnostic_code="STALE_STABLE_ID",
                        detail=(
                            "inner-door shared horizontal "
                            "Divider stable ID is not valid "
                            "in current topology"
                        ),
                    )
                )
            continue

        divider = divider_by_id.get(
            str(role.divider_stable_id)
        )
        if divider is None:
            for attached_id in attached_ids:
                all_results.append(
                    _fail(
                        locator_part_id=str(
                            role.divider_stable_id
                        ),
                        attached_part_id=attached_id,
                        diagnostic_code="LOCATOR_MISSING",
                        detail=(
                            "shared Divider semantic owner "
                            "is absent"
                        ),
                    )
                )
            continue

        for attached_id in attached_ids:
            frame = frame_by_id.get(attached_id)
            if frame is None:
                all_results.append(
                    _fail(
                        locator_part_id=str(
                            divider.stable_id
                        ),
                        attached_part_id=attached_id,
                        diagnostic_code="ATTACHED_MISSING",
                        detail=(
                            "left/right physical frame "
                            "semantic owner is absent"
                        ),
                    )
                )
                continue
            result, line_rows = _solve_one(
                geometry=geometry,
                divider=divider,
                frame=frame,
                dimensions=dimensions,
                sheet_thickness=float(
                    sheet_thickness
                ),
            )
            all_results.append(result)
            if line_rows:
                lines_by_locator.setdefault(
                    str(divider.stable_id),
                    [],
                ).extend(line_rows)

    enriched = geometry
    for locator_id, rows in sorted(
        lines_by_locator.items()
    ):
        locator_part = _part_map(enriched).get(
            locator_id
        )
        if locator_part is None:
            continue
        scene, metadata = _clean_prior_joint_markings(
            locator_part.render_data
        )
        ordered = tuple(
            sorted(
                rows,
                key=lambda row: (
                    str(row["attached_part_id"]),
                    str(row["boundary_role"]),
                    str(row["mark_id"]),
                ),
            )
        )
        for row in ordered:
            scene.add_line(
                row["p1"],
                row["p2"],
                layer="MARKING",
            )
        metadata["joint_markings"] = (
            tuple(
                metadata.get(
                    "joint_markings"
                )
                or ()
            )
            + ordered
        )
        enriched = _replace_part(
            enriched,
            locator_id,
            replace(
                locator_part.render_data,
                scene=scene,
                metadata=metadata,
            ),
        )

    enriched = replace(
        enriched,
        diagnostics=(
            tuple(enriched.diagnostics or ())
            + tuple(all_results)
        ),
    )
    return ReceivingJointMarkingResolution(
        geometry=enriched,
        results=tuple(all_results),
        status=status,
    )


__all__ = [
    "ALLOW_EXPORT_WITH_DIAGNOSTIC",
    "GATE_B_STATE",
    "PRODUCTION_JOINT_MARKING_FAILURE_POLICY",
    "RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY",
    "ReceivingJointMarkingResolution",
    "joint_marking_export_summary",
    "resolve_joint_marking_production_status",
    "resolve_receiving_joint_markings",
]
