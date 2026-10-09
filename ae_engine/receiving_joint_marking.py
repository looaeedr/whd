# -*- coding: utf-8 -*-
"""Receiving receiver/mother-plate Joint Placement MARKING.

The manufacturing locator is the *receiving mother plate*, never the attached
inner-door frame. Markings require demonstrated physical mating first; the
locator's authoritative world/flat mapping is then used only to register the
verified contact footprint for manufacturing. A detached frame must not create
a plausible-looking projected mark. Composite Box Body side plates retain
piece-level ownership (``box_body:left_side`` / ``box_body:right_side``).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
from typing import Mapping

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .cabinet_types import policy as cabinet_family_policy
from .contracts import (
    FoldProfileSegment,
    JointMarkingFailurePolicy,
    JointMarkingPolicy,
    JointMarkingProductionStatus,
    PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
    ResolvedJointMarkingResult,
    ResolvedLegalContact,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
    ResolvedPhysicalMatingRegion,
)
from .inner_door_frames import (
    LOWER_TERMINAL_FACE,
    derive_all_inner_door_frames,
    inner_door_frame_mating_region,
    inner_door_frame_stable_id,
)
from .joint_marking_policy import stable_joint_mark_id
from .manufacturing_scene_access import (
    owner_render_data,
    replace_owner_render_data,
)
from .sheetmetal_drawing import DrawingScene, LinePrimitive


RECEIVING_POLICY_ID = "RECEIVING_INNER_DOOR_MOTHER_PLATE_CONTACT_V3"
GATE_B_STATE = "JOINT_PLACEMENT_MARKING_PRODUCTION_ENABLED"
ALLOW_EXPORT_WITH_DIAGNOSTIC = "ALLOW_EXPORT_WITH_DIAGNOSTIC"

PRODUCTION_JOINT_MARKING_FAILURE_POLICY = JointMarkingFailurePolicy(
    disposition=ALLOW_EXPORT_WITH_DIAGNOSTIC,
)

RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY = JointMarkingPolicy(
    policy_id=RECEIVING_POLICY_ID,
    revision=3,
    enabled=True,
    locator_selector="RECEIVING_MOTHER_PLATE",
    attached_selector="RECEIVING_INNER_DOOR_FRAME",
    locator_contact_region="FINAL_MATERIAL_PHYSICAL_SKIN",
    attached_contact_region="FRAME_PHYSICAL_MATING_SKIN",
    footprint_mode="ACTUAL_CONTACT_BOUNDARY",
    boundary_frame_contract={
        "frame_version": "MOTHER_PLATE_CONTACT_BOUNDARY_V1",
        "basis_part": "LOCATOR",
        "boundary_source": "CANONICAL_ASSEMBLY_PHYSICAL_GEOMETRY",
        "backprojection": "LOCATOR_WORLD_TO_FLAT_UV",
    },
    contact_span_contract="PHYSICAL_CONTACT_OVERLAP",
    allowed_overlap_contract="NONE",
)

# Compatibility names retained for import stability only.  They intentionally
# resolve to the receiver-owned V3 policy so old callers cannot reactivate the
# superseded frame-owned V2 interpretation.
RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY = (
    RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
)
RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY = (
    RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
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


def _inner_door_items(snapshot) -> tuple[dict[str, object], ...]:
    rows = []
    for raw in tuple(dict(snapshot or {}).get("inner_doors") or ()):
        if isinstance(raw, Mapping):
            item = dict(raw)
            if str(item.get("stable_id") or "").strip():
                rows.append(item)
    return tuple(rows)


def _derived_receiving_frames(snapshot):
    frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(
        dict(snapshot or {})
    )
    return tuple(derive_all_inner_door_frames(frame_sets))


def _part_map(
    geometry: ResolvedManufacturingGeometry,
) -> dict[str, ResolvedManufacturingPart]:
    return {
        str(part.part_key): part
        for part in tuple(geometry.parts or ())
    }


def _marking_line_signature(p1, p2):
    a = (round(float(p1[0]), 9), round(float(p1[1]), 9))
    b = (round(float(p2[0]), 9), round(float(p2[1]), 9))
    return tuple(sorted((a, b)))


def _clean_prior_joint_markings(render_data):
    metadata = dict(getattr(render_data, "metadata", {}) or {})
    prior = tuple(metadata.get("joint_markings") or ())
    owned = {
        _marking_line_signature(row["p1"], row["p2"])
        for row in prior
        if isinstance(row, Mapping)
        and str(row.get("source") or "") == "JOINT_PLACEMENT_MARKING"
        and row.get("p1") is not None
        and row.get("p2") is not None
    }
    scene = DrawingScene()
    for primitive in tuple(getattr(render_data.scene, "primitives", ()) or ()):
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
            and str(row.get("source") or "") == "JOINT_PLACEMENT_MARKING"
        )
    )
    return scene, metadata


def _clean_render_data(render_data):
    """Remove only marks owned by this feature, including composite pieces."""
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if pieces:
        cleaned = []
        changed = False
        for piece in pieces:
            piece_render = piece.render_data
            scene, metadata = _clean_prior_joint_markings(piece_render)
            new_render = replace(piece_render, scene=scene, metadata=metadata)
            cleaned.append(replace(piece, render_data=new_render))
            changed = changed or new_render != piece_render
        if not changed:
            return render_data
        from .manufacturing_render_data import build_exploded_box_body_preview

        cleaned = tuple(cleaned)
        return replace(
            render_data,
            pieces=cleaned,
            preview_render_data=build_exploded_box_body_preview(cleaned),
        )

    if not hasattr(render_data, "metadata"):
        return render_data
    scene, metadata = _clean_prior_joint_markings(render_data)
    return replace(render_data, scene=scene, metadata=metadata)


def _clean_geometry_prior_joint_markings(
    geometry: ResolvedManufacturingGeometry,
) -> ResolvedManufacturingGeometry:
    parts = tuple(
        replace(part, render_data=_clean_render_data(part.render_data))
        for part in tuple(geometry.parts or ())
    )
    diagnostics = tuple(
        item
        for item in tuple(geometry.diagnostics or ())
        if not isinstance(item, ResolvedJointMarkingResult)
    )
    return replace(geometry, parts=parts, diagnostics=diagnostics)


def _fail(
    *,
    locator_part_id: str,
    attached_part_id: str,
    diagnostic_code: str,
    detail: str,
    evidence: Mapping[str, object] | None = None,
) -> ResolvedJointMarkingResult:
    policy = RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
    return ResolvedJointMarkingResult(
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        locator_part_id=str(locator_part_id or ""),
        attached_part_id=str(attached_part_id or ""),
        status="SKIPPED_FAIL_CLOSED",
        mark_ids=(),
        diagnostic_code=str(diagnostic_code),
        diagnostic_detail=str(detail or ""),
        export_disposition=PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition,
        evidence=dict(evidence or {}),
    )


# DM8-C1: all 3D vector math and triangle normals use the neutral owner.
from .assembly_marking_geometry import (
    canonical_unit_normal,
    triangle_unit_normal,
    vector_add as _add,
    vector_sub as _sub,
    vector_scale as _scale,
    vector_dot as _dot,
    vector_cross as _cross,
    vector_norm as _norm,
    vector_unit,
)


def _unit(a):
    return vector_unit(
        a,
        tolerance=PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance,
        error_message="degenerate geometry direction",
    )


_triangle_normal = partial(
    triangle_unit_normal,
    tolerance=PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance,
    error_message="degenerate geometry direction",
)


def _outward_normal(record):
    return tuple(float(record.side) * value for value in _triangle_normal(record.world))


def _plane_basis(normal):
    n = _unit(normal)
    reference = min(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        key=lambda axis: abs(_dot(axis, n)),
    )
    u = _unit(_cross(reference, n))
    v = _unit(_cross(n, u))
    return u, v


def _project_point(point, origin, u, v):
    delta = _sub(point, origin)
    return (_dot(delta, u), _dot(delta, v))


def _world_point(x, y, origin, u, v):
    return _add(origin, _add(_scale(u, x), _scale(v, y)))


def _canonical_plane_normal(normal):
    return canonical_unit_normal(
        normal,
        direction_tolerance=PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon,
        norm_tolerance=PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance,
        error_message="degenerate geometry direction",
    )


def _mapped_plane_groups(records):
    """Group mapped skin triangles by actual plane and physical outward side."""
    groups = {}
    for record in tuple(records or ()):
        world = tuple(getattr(record, "world", ()) or ())
        if len(world) != 3:
            continue
        canonical = _canonical_plane_normal(_triangle_normal(world))
        plane_d = _dot(canonical, world[0])
        outward = _outward_normal(record)
        key = (
            tuple(round(float(v), 7) for v in canonical),
            round(float(plane_d), 7),
            tuple(round(float(v), 7) for v in outward),
        )
        groups.setdefault(key, []).append(record)
    return tuple(tuple(rows) for _key, rows in sorted(groups.items(), key=lambda item: item[0]))


def _group_world_polygon(records, *, origin, u, v):
    polygons = []
    for record in tuple(records or ()):
        coords = tuple(_project_point(point, origin, u, v) for point in record.world)
        polygon = Polygon(coords)
        if polygon.is_valid and not polygon.is_empty and float(polygon.area) > 1e-9:
            polygons.append(polygon)
    if not polygons:
        raise ValueError("physical skin plane has no bounded mapped polygon")
    return unary_union(polygons)


def _geometry_centroid(records):
    points = [
        tuple(float(v) for v in point)
        for record in tuple(records or ())
        for point in tuple(getattr(record, "world", ()) or ())
    ]
    if not points:
        raise ValueError("physical geometry is empty")
    count = float(len(points))
    return tuple(sum(point[i] for point in points) / count for i in range(3))


def _polygon_world_exterior(polygon, *, origin, u, v):
    if str(getattr(polygon, "geom_type", "")) != "Polygon":
        polygons = [
            part for part in tuple(getattr(polygon, "geoms", ()) or ())
            if str(getattr(part, "geom_type", "")) == "Polygon"
        ]
        if len(polygons) != 1:
            raise ValueError("mating footprint is not one connected contact region")
        polygon = polygons[0]
    return tuple(
        _world_point(float(x), float(y), origin, u, v)
        for x, y in tuple(polygon.exterior.coords)[:-1]
    )


def _projected_mating_contact(
    *, locator_id: str, attached_id: str, locator_mapping, attached_mapping,
    sheet_thickness: float,
):
    """Resolve a *verified* physical face mate before flat UV registration.

    The world mapping here contains the *already thickened physical skins*,
    not sheet mid-surfaces (see world_skin_with_flat_uv). Opposed mating
    physical skins must therefore share the same support plane within the
    production coplanarity tolerance. Any nonzero physical separation beyond
    that tolerance is a real gap or misassembly, not a permitted projection.

    The locator-plane footprint is retained solely as the manufacturing UV
    carrier after this physical precondition has been proved.
    """
    locator_records = tuple(locator_mapping or ())
    attached_records = tuple(attached_mapping or ())
    if not locator_records or not attached_records:
        raise ValueError("mapped physical skins are missing")

    locator_center = _geometry_centroid(locator_records)
    attached_center = _geometry_centroid(attached_records)
    toward_attached = _unit(_sub(attached_center, locator_center))
    epsilon = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon)
    contact_tolerance = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.coplanar_distance_tolerance)
    if float(sheet_thickness) <= 0:
        raise ValueError("physical mating requires positive sheet thickness")

    candidates = []
    for locator_group in _mapped_plane_groups(locator_records):
        locator_outward = _unit(_outward_normal(locator_group[0]))
        locator_alignment = _dot(locator_outward, toward_attached)
        if locator_alignment <= 0.0:
            continue
        locator_origin = tuple(float(v) for v in locator_group[0].world[0])
        plane_normal = _canonical_plane_normal(_triangle_normal(locator_group[0].world))
        u, v = _plane_basis(plane_normal)
        locator_poly = _group_world_polygon(locator_group, origin=locator_origin, u=u, v=v)

        for attached_group in _mapped_plane_groups(attached_records):
            attached_outward = _unit(_outward_normal(attached_group[0]))
            if _dot(attached_outward, toward_attached) >= 0.0:
                continue
            attached_plane_normal = _canonical_plane_normal(_triangle_normal(attached_group[0].world))
            parallel = abs(_dot(plane_normal, attached_plane_normal))
            if parallel < 1.0 - 1e-6:
                continue
            projected = _group_world_polygon(attached_group, origin=locator_origin, u=u, v=v)
            overlap = locator_poly.intersection(projected)
            if overlap.is_empty or float(getattr(overlap, "area", 0.0)) <= epsilon:
                continue
            separation = abs(
                _dot(_sub(attached_group[0].world[0], locator_origin), plane_normal)
            )
            # Mapped skins have *already* been offset by +/- T/2.  A face
            # mate requires actual coplanarity; distant parallel skin faces
            # must not be made into contacts by footprint projection.
            if separation > contact_tolerance:
                continue
            candidates.append(
                (
                    -float(locator_alignment),
                    float(separation),
                    -float(overlap.area),
                    locator_group,
                    attached_group,
                    locator_origin,
                    plane_normal,
                    u,
                    v,
                    overlap,
                )
            )

    if not candidates:
        raise ValueError("no physical mother-plate/frame face contact (noncoplanar or missing overlap)")
    candidates.sort(key=lambda row: row[:3])
    chosen = candidates[0]
    (
        neg_alignment,
        separation,
        _neg_area,
        locator_group,
        attached_group,
        locator_origin,
        plane_normal,
        u,
        v,
        overlap,
    ) = chosen
    locator_outward = _unit(_outward_normal(locator_group[0]))
    attached_outward = tuple(-value for value in locator_outward)
    overlap_world = _polygon_world_exterior(
        overlap, origin=locator_origin, u=u, v=v
    )

    locator_region = ResolvedPhysicalMatingRegion(
        part_id=str(locator_id),
        region_id="FACING_MOTHER_PLATE_SKIN",
        region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=(locator_origin, locator_outward),
        outward_normal=locator_outward,
        world_polygon=overlap_world,
        flat_mapping=tuple(locator_group),
        provenance={
            "source": "CANONICAL_FACING_PHYSICAL_SKIN",
            "geometry_owner": str(locator_id),
        },
    )
    projected_attached = ResolvedPhysicalMatingRegion(
        part_id=str(attached_id),
        region_id="PROJECTED_FRAME_MATING_SKIN",
        region_role="ATTACHED_MATING_FOOTPRINT",
        physical_face_kind="PLACEMENT_PROJECTED_MAPPED_SKIN",
        supporting_plane=(locator_origin, attached_outward),
        outward_normal=attached_outward,
        world_polygon=overlap_world,
        flat_mapping=None,
        provenance={
            "source": "CANONICAL_FRAME_PHYSICAL_SKIN_ORTHOGONAL_REGISTRATION",
            "original_plane_separation": float(separation),
            "locator_alignment": float(-neg_alignment),
            "attached_mapping_record_count": len(attached_group),
        },
    )
    return ResolvedLegalContact(
        locator_part_id=str(locator_id),
        attached_part_id=str(attached_id),
        locator_region=locator_region,
        attached_region=projected_attached,
        contact_plane=(locator_origin, locator_outward),
        locator_outward_normal=locator_outward,
        attached_outward_normal=attached_outward,
        overlap_world=overlap_world,
        locator_flat_mapping=tuple(locator_group),
        evidence={
            "contact_mode": "VERIFIED_SKIN_TO_SKIN_CONTACT_UV_REGISTRATION",
            "projection_distance": float(separation),
            "physical_skin_clearance": float(separation),
            "locator_alignment": float(-neg_alignment),
            "overlap_area": float(overlap.area),
            "locator_mapping_record_count": len(locator_group),
            "attached_mapping_record_count": len(attached_group),
        },
    )


def _divider_core_support_region(
    *, divider, locator_mapping, attached_outward_normal
):
    records = tuple(locator_mapping or ())
    core = dict(divider.physical_geometry_contract["core_physical_segment"])
    band_start, band_end = map(float, core["flat_band"])
    selected = []
    selected_normal = None
    for record in records:
        centroid_x = sum(float(point[0]) for point in record.flat) / 3.0
        if not (band_start + 1e-8 < centroid_x < band_end - 1e-8):
            continue
        outward = _unit(_outward_normal(record))
        if _norm(_add(outward, attached_outward_normal)) <= 1e-6:
            selected.append(record)
            selected_normal = outward
    if not selected or selected_normal is None:
        raise ValueError("actual Divider core support skin opposite frame terminal is absent")

    origin = tuple(float(v) for v in selected[0].world[0])
    u, v = _plane_basis(selected_normal)
    face = _group_world_polygon(selected, origin=origin, u=u, v=v)
    world_polygon = _polygon_world_exterior(face, origin=origin, u=u, v=v)
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
            "source": "DIVIDER_CORE_PHYSICAL_SEGMENT_MAPPED_SKIN",
            "flat_band": (band_start, band_end),
        },
    )


def _divider_contact(
    *, geometry, world, divider, frame, dimensions, sheet_thickness
):
    from .assembly_contact import resolve_legal_coplanar_contact
    from .assembly_geometry import resolve_physical_mating_region

    frame_part = _part_map(geometry).get(str(frame.stable_id))
    if frame_part is None:
        raise KeyError(str(frame.stable_id))
    attached = resolve_physical_mating_region(
        part_id=str(frame.stable_id),
        semantic=inner_door_frame_mating_region(frame, LOWER_TERMINAL_FACE),
        render_data=frame_part.render_data,
        x_profile=tuple(frame.fold_profile),
        y_profile=(
            FoldProfileSegment(
                length=float(frame.span), angle=None, phase6_key="frame_span"
            ),
        ),
        placement=frame_part.placement,
        dimensions=dimensions,
        offset=frame_part.offset,
        sheet_thickness=sheet_thickness,
    )
    locator = _divider_core_support_region(
        divider=divider,
        locator_mapping=world["mapped_skin_triangles_by_part"].get(
            str(divider.stable_id), ()
        ),
        attached_outward_normal=attached.outward_normal,
    )
    result = resolve_legal_coplanar_contact(locator, attached)
    if result.status != "LEGAL_CONTACT" or result.contact is None:
        raise ValueError(
            f"Divider/frame physical contact unresolved: {result.diagnostic_code}"
        )
    return result.contact


def _longest_contact_boundary(contact: ResolvedLegalContact):
    points = tuple(tuple(float(v) for v in p) for p in tuple(contact.overlap_world or ()))
    if len(points) < 3:
        raise ValueError("physical contact overlap has no bounded boundary")
    rows = []
    for index, a in enumerate(points):
        b = points[(index + 1) % len(points)]
        length = _norm(_sub(b, a))
        if length <= 1e-9:
            continue
        signature = tuple(round(v, 9) for point in sorted((a, b)) for v in point)
        rows.append((-float(length), signature, a, b))
    if not rows:
        raise ValueError("physical contact boundary is degenerate")
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows[0][2], rows[0][3]


def _backproject_contact_boundary(contact):
    from .assembly_marking_geometry import backproject_locator_world_points

    world_segment = _longest_contact_boundary(contact)
    projected = backproject_locator_world_points(contact, world_segment)
    if projected.status != "RESOLVED" or len(projected.flat_points) != 2:
        raise ValueError(
            f"contact boundary backprojection failed: {projected.diagnostic_code}"
        )
    return world_segment, tuple(projected.flat_points)


def _mark_row(
    *, locator_id: str, attached_id: str, boundary_role: str, contact
):
    world_segment, flat_segment = _backproject_contact_boundary(contact)
    p1, p2 = flat_segment
    data = {
        "mark_id": stable_joint_mark_id(
            RECEIVING_POLICY_ID, locator_id, attached_id, boundary_role
        ),
        "boundary_role": str(boundary_role),
        "locator_part_id": str(locator_id),
        "attached_part_id": str(attached_id),
        "p1": tuple(float(v) for v in p1),
        "p2": tuple(float(v) for v in p2),
        "world_p1": tuple(float(v) for v in world_segment[0]),
        "world_p2": tuple(float(v) for v in world_segment[1]),
        "source": "JOINT_PLACEMENT_MARKING",
        "geometry_source": "RECEIVER_MATING_CONTACT_BACKPROJECTION",
        "contact_mode": str(dict(contact.evidence or {}).get("contact_mode") or "LEGAL_CONTACT"),
    }
    return data


def _emitted_result(*, locator_id, attached_id, row, contact):
    policy = RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
    return ResolvedJointMarkingResult(
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        locator_part_id=str(locator_id),
        attached_part_id=str(attached_id),
        status="EMITTED",
        mark_ids=(str(row["mark_id"]),),
        diagnostic_code=None,
        diagnostic_detail="",
        export_disposition=PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition,
        evidence={
            "locator_region": str(getattr(contact.locator_region, "region_id", "")),
            "attached_region": str(getattr(contact.attached_region, "region_id", "")),
            "footprint_mode": "ACTUAL_CONTACT_BOUNDARY",
            "geometry_owner": str(locator_id),
            "contact_evidence": dict(contact.evidence or {}),
            "world_boundary": (row["world_p1"], row["world_p2"]),
            "flat_boundary": (row["p1"], row["p2"]),
        },
    )


def _write_rows(geometry, rows_by_owner):
    enriched = geometry
    for owner_key, rows in sorted(rows_by_owner.items()):
        data = owner_render_data(enriched, owner_key)
        if data is None:
            continue
        scene, metadata = _clean_prior_joint_markings(data)
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
        material = data.material
        for row in ordered:
            line = LineString((row["p1"], row["p2"]))
            if line.is_empty or float(line.length) <= 1e-9 or not material.covers(line):
                raise ValueError(f"mark outside Final Material: {owner_key}")
            scene.add_line(row["p1"], row["p2"], layer="MARKING")
        metadata["joint_markings"] = tuple(metadata.get("joint_markings") or ()) + ordered
        enriched = replace_owner_render_data(
            enriched,
            owner_key,
            replace(data, scene=scene, metadata=metadata),
        )
    return enriched


def resolve_receiving_joint_markings(
    snapshot,
    geometry: ResolvedManufacturingGeometry,
    *,
    dimensions,
    sheet_thickness: float,
    cabinet_family="受電箱",
    world_geometry=None,
) -> ReceivingJointMarkingResolution:
    """Emit receiver-owned Receiving inner-door placement MARKING."""
    if not isinstance(geometry, ResolvedManufacturingGeometry):
        raise TypeError("geometry must be ResolvedManufacturingGeometry")

    status = resolve_joint_marking_production_status()
    geometry = _clean_geometry_prior_joint_markings(geometry)
    family = str(cabinet_family or dict(snapshot or {}).get("model") or "").strip()
    if family != "受電箱":
        return ReceivingJointMarkingResolution(geometry=geometry, results=(), status=status)

    items = _inner_door_items(snapshot)
    if not items:
        return ReceivingJointMarkingResolution(geometry=geometry, results=(), status=status)

    try:
        frames = _derived_receiving_frames(snapshot)
    except (TypeError, ValueError) as exc:
        results = []
        for item in items:
            door_id = str(item["stable_id"])
            for side in tuple(item.get("included_frame_sides") or ("top", "left", "right")):
                if str(side) not in {"top", "left", "right"}:
                    continue
                results.append(
                    _fail(
                        locator_part_id="",
                        attached_part_id=inner_door_frame_stable_id(door_id, str(side)),
                        diagnostic_code="STALE_STABLE_ID",
                        detail=str(exc),
                    )
                )
        return ReceivingJointMarkingResolution(
            geometry=replace(
                geometry,
                diagnostics=tuple(geometry.diagnostics or ()) + tuple(results),
            ),
            results=tuple(results),
            status=status,
        )

    frame_by_id = {str(frame.stable_id): frame for frame in frames}
    try:
        if world_geometry is None:
            from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry

            world = _phase6_build_joint_world_geometry(
                tuple(geometry.parts or ()), dimensions, float(sheet_thickness)
            )
        else:
            world = dict(world_geometry)
    except Exception as exc:
        results = tuple(
            _fail(
                locator_part_id="",
                attached_part_id=str(frame.stable_id),
                diagnostic_code="PLACEMENT_UNRESOLVED",
                detail=str(exc),
            )
            for frame in frames
        )
        return ReceivingJointMarkingResolution(
            geometry=replace(
                geometry,
                diagnostics=tuple(geometry.diagnostics or ()) + results,
            ),
            results=results,
            status=status,
        )

    from .door_dividers import derive_box_body_dividers

    snapshot_map = dict(snapshot or {})
    dimensions = tuple(dimensions or ())
    dividers = derive_box_body_dividers(
        snapshot_map.get("door_layout_columns") or (),
        depth=float(snapshot_map.get("d", dimensions[2] if len(dimensions) > 2 else 0.0)),
        thickness=float(sheet_thickness),
        layout_scope=str(snapshot_map.get("door_layout_scope") or "receiving-main"),
        model_name=str(snapshot_map.get("model") or "受電箱"),
        frame_width=float(snapshot_map.get("fw", 29.0)),
    )
    divider_by_id = {str(row.stable_id): row for row in dividers}

    rows_by_owner = {}
    results = []
    for item in items:
        door_id = str(item["stable_id"])
        included = {
            str(side).strip().lower()
            for side in tuple(item.get("included_frame_sides") or ("top", "left", "right"))
        }
        lower_role = dict(item.get("lower_frame_role") or {})
        divider_id = str(lower_role.get("divider_stable_id") or "")
        divider = divider_by_id.get(divider_id)
        if divider is None:
            from .door_dividers import resolve_inner_door_lower_frame_role

            resolved_role = resolve_inner_door_lower_frame_role(
                door_id,
                tuple(divider_by_id.values()),
                previous_divider_stable_id=(divider_id or None),
            )
            if resolved_role is not None:
                divider_id = str(resolved_role.divider_stable_id)
                divider = divider_by_id.get(divider_id)

        for side in ("left", "right", "top"):
            if side not in included:
                continue
            frame_id = inner_door_frame_stable_id(door_id, side)
            frame = frame_by_id.get(frame_id)
            if frame is None or _part_map(geometry).get(frame_id) is None:
                results.append(
                    _fail(
                        locator_part_id="",
                        attached_part_id=frame_id,
                        diagnostic_code="ATTACHED_MISSING",
                        detail="requested Receiving inner-door frame physical part is absent",
                    )
                )
                continue

            targets = []
            if side in {"left", "right"}:
                if divider is not None:
                    targets.append((divider_id, "UPPER_HORIZONTAL", "DIVIDER"))
                targets.append((f"box_body:{side}_side", "SIDE_POSITIVE", "MOTHER_PLATE"))
            else:
                targets.append(("head", "UPPER_HORIZONTAL", "MOTHER_PLATE"))

            for locator_id, boundary_role, mode in targets:
                if owner_render_data(geometry, locator_id) is None:
                    results.append(
                        _fail(
                            locator_part_id=locator_id,
                            attached_part_id=frame_id,
                            diagnostic_code="LOCATOR_MISSING",
                            detail=f"Receiving mother-plate owner is absent: {locator_id}",
                        )
                    )
                    continue
                try:
                    if mode == "DIVIDER":
                        contact = _divider_contact(
                            geometry=geometry,
                            world=world,
                            divider=divider,
                            frame=frame,
                            dimensions=dimensions,
                            sheet_thickness=float(sheet_thickness),
                        )
                    else:
                        contact = _projected_mating_contact(
                            locator_id=locator_id,
                            attached_id=frame_id,
                            locator_mapping=world["mapped_skin_triangles_by_part"].get(locator_id, ()),
                            attached_mapping=world["mapped_skin_triangles_by_part"].get(frame_id, ()),
                            sheet_thickness=float(sheet_thickness),
                        )
                    row = _mark_row(
                        locator_id=locator_id,
                        attached_id=frame_id,
                        boundary_role=boundary_role,
                        contact=contact,
                    )
                    # Fail before writeback when the contact-derived line cannot
                    # land on the true locator mother plate.
                    owner_data = owner_render_data(geometry, locator_id)
                    line = LineString((row["p1"], row["p2"]))
                    if not owner_data.material.covers(line):
                        raise ValueError("contact boundary is outside locator Final Material")
                    rows_by_owner.setdefault(locator_id, []).append(row)
                    results.append(
                        _emitted_result(
                            locator_id=locator_id,
                            attached_id=frame_id,
                            row=row,
                            contact=contact,
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    results.append(
                        _fail(
                            locator_part_id=locator_id,
                            attached_part_id=frame_id,
                            diagnostic_code=(
                                "CONTACT_NOT_FOUND"
                                if "contact" in str(exc).lower() or "mating" in str(exc).lower()
                                else "BACKPROJECTION_FAILED"
                            ),
                            detail=str(exc),
                            evidence={"receiver_mode": mode},
                        )
                    )

    try:
        enriched = _write_rows(geometry, rows_by_owner)
    except (KeyError, TypeError, ValueError) as exc:
        # Atomic activation: if any staged receiver line cannot be written to its
        # canonical owner, expose diagnostics but do not publish half a marking set.
        failed = tuple(
            _fail(
                locator_part_id=str(result.locator_part_id),
                attached_part_id=str(result.attached_part_id),
                diagnostic_code="MARK_OUTSIDE_FINAL_MATERIAL",
                detail=str(exc),
            )
            if result.status == "EMITTED"
            else result
            for result in results
        )
        enriched = geometry
        results = list(failed)

    enriched = replace(
        enriched,
        diagnostics=tuple(enriched.diagnostics or ()) + tuple(results),
    )
    return ReceivingJointMarkingResolution(
        geometry=enriched,
        results=tuple(results),
        status=status,
    )


__all__ = [
    "ALLOW_EXPORT_WITH_DIAGNOSTIC",
    "GATE_B_STATE",
    "PRODUCTION_JOINT_MARKING_FAILURE_POLICY",
    "RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY",
    "RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY",
    "RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY",
    "ReceivingJointMarkingResolution",
    "joint_marking_export_summary",
    "resolve_joint_marking_production_status",
    "resolve_receiving_joint_markings",
]
