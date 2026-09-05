# -*- coding: utf-8 -*-
"""Box Body / EndCap assembly collision relief solver.

This Module stays inside the manufacturing boundary. It consumes resolved
geometry and returns candidate 2D cuts; it does not know about GUI, DXF, or
renderer state.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from shapely.geometry.base import BaseGeometry


class AssemblyRole(str, Enum):
    BOX_BODY = "box_body"
    ENDCAP = "endcap"


class OwnershipAction(str, Enum):
    RETAIN = "retain"
    CUT = "cut"


@dataclass(frozen=True)
class AssemblyOwnershipPolicy:
    box_body: OwnershipAction
    endcap: OwnershipAction


@dataclass(frozen=True)
class CollisionRegion:
    region: object
    source_role: AssemblyRole
    target_role: AssemblyRole


@dataclass(frozen=True)
class ReliefCandidate:
    cut_polygon_2d: object
    clearance: float
    source_collision_area: float


@dataclass(frozen=True)
class EndCapReliefSolution:
    original_collision: CollisionRegion | None
    candidate: ReliefCandidate | None
    solved_render_data: object
    verified: bool
    trust_level: str = "PROVISIONAL_3D"
    rule_id: str | None = None
    rule_revision: int | None = None
    joint_signature: tuple[dict, ...] = ()
    shadow_validation: object | None = None


@dataclass(frozen=True)
class JointReliefOwnership:
    joint_id: str
    preserve_part: str
    relief_part: str
    reason: str


def joint_relief_ownership(joint) -> JointReliefOwnership:
    from .assembly_joint import AssemblyJointRelation
    relation = joint.relation if isinstance(joint.relation, AssemblyJointRelation) else AssemblyJointRelation(str(joint.relation))
    if relation is AssemblyJointRelation.INSERT:
        return JointReliefOwnership(joint.joint_id, joint.target_part, joint.subject_part, "INSERT_INSERTING_SUBJECT_RELIEF")
    if relation is AssemblyJointRelation.INSERT_OVERLAY:
        return JointReliefOwnership(joint.joint_id, joint.target_part, joint.subject_part, "INSERT_OVERLAY_INSERTION_RELIEF")
    if relation is AssemblyJointRelation.WRAP:
        return JointReliefOwnership(joint.joint_id, joint.subject_part, joint.target_part, "WRAP_WRAPPER_PRESERVED")
    return JointReliefOwnership(joint.joint_id, joint.subject_part, joint.target_part, "OVERLAY_OUTER_SUBJECT_PRESERVED")



from .assembly_geometry import (
    MeshInterferenceDiagnostic,
    detect_world_mesh_surface_interference,
    restore_unrelieved_endcap_material,
)


@dataclass(frozen=True)
class BoxBodyEndCapWorldMeshes:
    """Box Body and EndCap/Tail meshes resolved into one cabinet world space."""

    box_body_triangles: tuple
    endcap_triangles: tuple


def assemble_boxbody_endcap_world_meshes(
    *,
    box_body_triangles,
    endcap_triangles,
    finished_dimensions,
    endcap_placement="top",
    box_body_offset=(0.0, 0.0, 0.0),
    endcap_offset=(0.0, 0.0, 0.0),
    sheet_thickness=0.0,
) -> BoxBodyEndCapWorldMeshes:
    """Place Box Body and EndCap/Tail meshes in the shared assembly coordinates.

    This is intentionally separate from collision detection: it establishes the
    common spatial truth first.  The renderer and the later 2.5D/3D solver use
    the same pure placement transform from ``ae_engine.assembly_geometry``.
    """
    from .assembly_geometry import (
        place_assembly_triangles,
        place_endcap_against_box_body,
        thicken_triangle_surface,
    )

    box_body_world = place_assembly_triangles(
        box_body_triangles, "box_body", finished_dimensions, box_body_offset
    )
    endcap_surface = place_endcap_against_box_body(
        endcap_triangles,
        endcap_placement,
        box_body_world,
        endcap_offset,
        sheet_thickness=sheet_thickness,
    )
    endcap_world = thicken_triangle_surface(endcap_surface, sheet_thickness)
    return BoxBodyEndCapWorldMeshes(
        box_body_triangles=box_body_world,
        endcap_triangles=endcap_world,
    )


def assemble_boxbody_endcap_render_meshes(
    *,
    box_body_render_data,
    endcap_render_data,
    box_body_x_profile,
    endcap_x_profile,
    endcap_y_profile,
    finished_dimensions,
    endcap_placement="top",
    box_body_offset=(0.0, 0.0, 0.0),
    endcap_offset=(0.0, 0.0, 0.0),
    sheet_thickness=0.0,
) -> BoxBodyEndCapWorldMeshes:
    """Fold authoritative Box Body + EndCap data into one world assembly.

    The Box Body height axis is physically flat, so its Y profile comes from
    the resolved material height.  X folding is supplied by the authoritative
    Box Body Fold Profile.  EndCap/Tail uses its authoritative X/Y profiles.
    """
    from .assembly_geometry import folded_mesh_from_polygon

    _minx, miny, _maxx, maxy = map(float, box_body_render_data.material.bounds)
    body_y_profile = ({"len": max(0.0, maxy - miny), "core": True},)
    box_body_local = folded_mesh_from_polygon(
        box_body_render_data.material,
        box_body_x_profile,
        body_y_profile,
        fold_guides=tuple(getattr(box_body_render_data, "fold_guides", ()) or ()),
    )
    endcap_local = folded_mesh_from_polygon(
        endcap_render_data.material,
        endcap_x_profile,
        endcap_y_profile,
        fold_guides=tuple(getattr(endcap_render_data, "fold_guides", ()) or ()),
    )
    return assemble_boxbody_endcap_world_meshes(
        box_body_triangles=box_body_local,
        endcap_triangles=endcap_local,
        finished_dimensions=finished_dimensions,
        endcap_placement=endcap_placement,
        box_body_offset=box_body_offset,
        endcap_offset=endcap_offset,
        sheet_thickness=sheet_thickness,
    )


def default_boxbody_endcap_ownership() -> AssemblyOwnershipPolicy:
    return AssemblyOwnershipPolicy(
        box_body=OwnershipAction.RETAIN,
        endcap=OwnershipAction.CUT,
    )


def detect_planar_collision(*, box_body_material, endcap_material) -> CollisionRegion | None:
    overlap = box_body_material.intersection(endcap_material)
    if overlap.is_empty or float(overlap.area) <= 1e-9:
        return None
    return CollisionRegion(
        region=overlap,
        source_role=AssemblyRole.BOX_BODY,
        target_role=AssemblyRole.ENDCAP,
    )


def project_collision_to_endcap_relief(
    collision: CollisionRegion | None,
    policy: AssemblyOwnershipPolicy,
    *,
    clearance: float = 0.0,
    min_area: float = 1e-6,
) -> ReliefCandidate | None:
    if collision is None:
        return None
    if collision.target_role is not AssemblyRole.ENDCAP:
        return None
    if policy.endcap is not OwnershipAction.CUT:
        return None

    source_area = float(collision.region.area)
    if source_area <= min_area:
        return None

    cut_polygon: BaseGeometry = collision.region
    if clearance > 0.0:
        cut_polygon = cut_polygon.buffer(float(clearance))
    if cut_polygon.is_empty:
        return None

    return ReliefCandidate(
        cut_polygon_2d=cut_polygon,
        clearance=float(clearance),
        source_collision_area=source_area,
    )


def _polygon_for_exterior(material):
    from shapely.geometry import MultiPolygon, Polygon

    if isinstance(material, Polygon):
        return material
    if isinstance(material, MultiPolygon):
        return max(material.geoms, key=lambda polygon: float(polygon.area))
    raise TypeError(f"Unsupported material geometry for CUTTING rebuild: {type(material)!r}")


def _vec2_points_from_polygon_exterior(polygon):
    from .sheetmetal_geometry import Vec2

    coords = list(polygon.exterior.coords)
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    return tuple(Vec2(float(x), float(y)) for x, y in coords)


def _scene_with_replaced_primary_cutting(scene, material):
    from .sheetmetal_drawing import DrawingScene, PolylinePrimitive

    exterior = _polygon_for_exterior(material)
    replacement = PolylinePrimitive(
        points=_vec2_points_from_polygon_exterior(exterior),
        layer="CUTTING",
        closed=True,
    )

    out = DrawingScene()
    replaced = False
    for primitive in getattr(scene, "primitives", ()):
        is_primary_cutting = (
            not replaced
            and isinstance(primitive, PolylinePrimitive)
            and str(primitive.layer).upper() == "CUTTING"
            and primitive.closed
        )
        if is_primary_cutting:
            out.add(replacement)
            replaced = True
        else:
            out.add(primitive)
    if not replaced:
        out.add(replacement)
    return out


def apply_endcap_relief_candidate(endcap_render_data, candidate: ReliefCandidate | None):
    if candidate is None:
        return endcap_render_data

    material = endcap_render_data.material.difference(candidate.cut_polygon_2d)
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty:
        raise ValueError("EndCap relief removed all material")

    scene = _scene_with_replaced_primary_cutting(endcap_render_data.scene, material)
    return replace(endcap_render_data, scene=scene, material=material)


def solve_boxbody_endcap_relief(
    *,
    box_body_render_data,
    endcap_render_data,
    ownership: AssemblyOwnershipPolicy | None = None,
    clearance: float = 0.0,
) -> EndCapReliefSolution:
    policy = ownership or default_boxbody_endcap_ownership()
    collision = detect_planar_collision(
        box_body_material=box_body_render_data.material,
        endcap_material=endcap_render_data.material,
    )
    if collision is None:
        return EndCapReliefSolution(
            original_collision=None,
            candidate=None,
            solved_render_data=endcap_render_data,
            verified=True,
        )

    candidate = project_collision_to_endcap_relief(
        collision,
        policy,
        clearance=clearance,
    )
    if candidate is None:
        return EndCapReliefSolution(
            original_collision=collision,
            candidate=None,
            solved_render_data=endcap_render_data,
            verified=False,
        )

    solved = apply_endcap_relief_candidate(endcap_render_data, candidate)
    remaining = detect_planar_collision(
        box_body_material=box_body_render_data.material,
        endcap_material=solved.material,
    )
    return EndCapReliefSolution(
        original_collision=collision,
        candidate=candidate,
        solved_render_data=solved,
        verified=remaining is None,
    )


@dataclass(frozen=True)
class FlatInterferenceProjection:
    """World-space sheet crossings mapped back to authoritative flat coordinates."""

    segments_2d: tuple
    points_2d: tuple
    pair_count: int = 0
    # Optional diagnostic evidence. Kept after the legacy positional fields so
    # existing constructors ``FlatInterferenceProjection(seg, pts, count)``
    # remain binary/source compatible.
    segments_world: tuple = ()

    @property
    def has_interference(self) -> bool:
        return bool(self.segments_2d)


def _triangle_pair_crossing_segment(target_tri, source_tri, *, tolerance=1e-7):
    """Return the longest non-coplanar triangle/triangle crossing segment."""
    from .assembly_geometry import _segment_triangle_intersection

    pair_points = []
    for a, b in ((target_tri[0], target_tri[1]), (target_tri[1], target_tri[2]), (target_tri[2], target_tri[0])):
        hit = _segment_triangle_intersection(a, b, source_tri, tolerance=tolerance)
        if hit is not None:
            pair_points.append(hit)
    for a, b in ((source_tri[0], source_tri[1]), (source_tri[1], source_tri[2]), (source_tri[2], source_tri[0])):
        hit = _segment_triangle_intersection(a, b, target_tri, tolerance=tolerance)
        if hit is not None:
            pair_points.append(hit)
    unique = []
    seen = set()
    for point in pair_points:
        key = tuple(round(float(v), 8) for v in point)
        if key not in seen:
            seen.add(key)
            unique.append(tuple(float(v) for v in point))
    if len(unique) < 2:
        return None
    best = None
    best_d2 = -1.0
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            a, b = unique[i], unique[j]
            d2 = sum((a[k] - b[k]) ** 2 for k in range(3))
            if d2 > best_d2:
                best_d2 = d2
                best = (a, b)
    if best is None or best_d2 <= tolerance * tolerance:
        return None
    return best


def _barycentric_world_to_flat(point, world_triangle, flat_triangle, *, tolerance=1e-10):
    a, b, c = world_triangle
    p = point
    v0 = tuple(float(b[i]) - float(a[i]) for i in range(3))
    v1 = tuple(float(c[i]) - float(a[i]) for i in range(3))
    v2 = tuple(float(p[i]) - float(a[i]) for i in range(3))
    d00 = sum(v0[i] * v0[i] for i in range(3))
    d01 = sum(v0[i] * v1[i] for i in range(3))
    d11 = sum(v1[i] * v1[i] for i in range(3))
    d20 = sum(v2[i] * v0[i] for i in range(3))
    d21 = sum(v2[i] * v1[i] for i in range(3))
    denom = d00 * d11 - d01 * d01
    if abs(denom) <= tolerance:
        raise ValueError("degenerate mapped target triangle")
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    u = alpha * float(flat_triangle[0][0]) + beta * float(flat_triangle[1][0]) + gamma * float(flat_triangle[2][0])
    v = alpha * float(flat_triangle[0][1]) + beta * float(flat_triangle[1][1]) + gamma * float(flat_triangle[2][1])
    return (u, v)


def backproject_world_interference_to_endcap_flat(
    source_triangles,
    mapped_target_skin_triangles,
    *,
    tolerance=1e-6,
) -> FlatInterferenceProjection:
    """Map physical world-space crossings back to EndCap/Tail flat coordinates.

    ``mapped_target_skin_triangles`` retains the original flat UV for every
    physical skin triangle.  Triangle crossing endpoints are mapped with
    barycentric coordinates, which is exact for the current sharp-bend,
    piecewise-affine Fold Profile model.
    """
    import numpy as np

    source = tuple(tuple(tuple(map(float, p)) for p in tri) for tri in (source_triangles or ()))
    targets = tuple(mapped_target_skin_triangles or ())
    if not source or not targets:
        return FlatInterferenceProjection((), (), 0)
    src = np.asarray(source, dtype=float)
    src_min = src.min(axis=1)
    src_max = src.max(axis=1)
    segments = []
    segment_keys = set()
    world_segments = []
    world_segment_keys = set()
    points = []
    point_keys = set()
    pair_count = 0

    def record_point(point):
        key = tuple(round(float(v), 6) for v in point)
        if key not in point_keys:
            point_keys.add(key)
            points.append(tuple(float(v) for v in point))

    for mapped in targets:
        target_tri = tuple(tuple(map(float, p)) for p in mapped.world)
        arr = np.asarray(target_tri, dtype=float)
        tmin = arr.min(axis=0) - float(tolerance)
        tmax = arr.max(axis=0) + float(tolerance)
        mask = np.all(src_max + tolerance >= tmin, axis=1) & np.all(src_min - tolerance <= tmax, axis=1)
        for idx in np.nonzero(mask)[0]:
            crossing = _triangle_pair_crossing_segment(
                target_tri, source[int(idx)], tolerance=tolerance
            )
            if crossing is None:
                continue
            a2 = _barycentric_world_to_flat(crossing[0], target_tri, mapped.flat)
            b2 = _barycentric_world_to_flat(crossing[1], target_tri, mapped.flat)
            d2 = (a2[0] - b2[0]) ** 2 + (a2[1] - b2[1]) ** 2
            if d2 <= tolerance * tolerance:
                continue
            pair_count += 1
            key = tuple(sorted((
                tuple(round(float(v), 6) for v in a2),
                tuple(round(float(v), 6) for v in b2),
            )))
            if key not in segment_keys:
                segment_keys.add(key)
                segments.append((a2, b2))
            wseg = (
                tuple(float(v) for v in crossing[0]),
                tuple(float(v) for v in crossing[1]),
            )
            wkey = tuple(sorted(tuple(round(float(v), 6) for v in point) for point in wseg))
            if wkey not in world_segment_keys:
                world_segment_keys.add(wkey)
                world_segments.append(wseg)
            record_point(a2)
            record_point(b2)
    return FlatInterferenceProjection(
        tuple(segments), tuple(points), pair_count, tuple(world_segments)
    )


# The barycentric implementation is generic; keep the legacy EndCap name as a
# compatibility alias while Solver v2 uses the neutral API.
backproject_world_interference_to_flat = backproject_world_interference_to_endcap_flat


@dataclass(frozen=True)
class JointReliefProjection:
    """Joint-local penetration projected onto the flat pattern of the relief owner.

    ``relief_part``/``preserve_part`` keep canonical AssemblyJoint ownership.
    Multi-piece adapters may additionally select physical geometry keys without
    rewriting the mechanical graph (for example ``box_body:left_side``).
    """

    joint_id: str
    preserve_part: str
    relief_part: str
    projection: FlatInterferenceProjection
    illegal_penetration: bool
    has_contact: bool
    evidence: object | None = None
    relief_geometry_key: str | None = None
    source_geometry_key: str | None = None


def project_joint_interference_to_relief_owner(
    joint,
    *,
    world_triangles_by_part,
    mapped_skin_triangles_by_part,
    flat_material_by_part,
    tolerance=1e-6,
    relief_geometry_key=None,
    source_geometry_key=None,
) -> JointReliefProjection:
    """Backproject a Joint crossing onto whichever part owns the relief.

    The ownership is semantic, not geometric guesswork.  For WRAP this means
    the wrapper (subject) is preserved and crossings are projected onto the
    wrapped target's mapped skin.  INSERT performs the inverse ownership: the
    inserting subject owns relief.
    """
    ownership = joint_relief_ownership(joint)
    relief = str(ownership.relief_part)
    preserve = str(ownership.preserve_part)
    relief_geometry = str(relief_geometry_key or relief)
    mapped = tuple((mapped_skin_triangles_by_part or {}).get(relief_geometry, ()) or ())
    material = (flat_material_by_part or {}).get(relief_geometry)
    if not mapped or material is None:
        missing = []
        if not mapped:
            missing.append(f"mapped_skin:{relief_geometry}")
        if material is None:
            missing.append(f"flat_material:{relief_geometry}")
        raise ValueError("missing relief-owner geometry: " + ", ".join(missing))

    # The collision source is the opposite Joint endpoint.  Ownership may pick
    # either subject or target as relief owner, but a two-part Joint always
    # leaves exactly one counterpart whose world surface crosses it.
    if relief == str(joint.subject_part):
        source_part = str(joint.target_part)
    elif relief == str(joint.target_part):
        source_part = str(joint.subject_part)
    else:
        raise ValueError(f"relief owner {relief!r} is not a Joint endpoint")
    source_geometry = str(source_geometry_key or source_part)
    source = tuple((world_triangles_by_part or {}).get(source_geometry, ()) or ())
    if not source:
        raise ValueError(f"missing collision-source world geometry: {source_geometry}")

    projection = backproject_world_interference_to_flat(
        source, mapped, tolerance=float(tolerance)
    )
    classified = classify_joint_interference(
        joint, projection=projection, flat_material=material, tolerance=float(tolerance)
    )
    return JointReliefProjection(
        joint_id=str(joint.joint_id),
        preserve_part=preserve,
        relief_part=relief,
        projection=projection,
        illegal_penetration=bool(classified.illegal_penetration),
        has_contact=bool(classified.has_contact),
        evidence={
            "source_part": source_part,
            "relief_part": relief,
            "source_geometry_key": source_geometry,
            "relief_geometry_key": relief_geometry,
            "pair_count": int(projection.pair_count),
            "ownership_reason": ownership.reason,
        },
        relief_geometry_key=relief_geometry,
        source_geometry_key=source_geometry,
    )


@dataclass(frozen=True)
class JointDiscoveryCandidate:
    joint_id: str
    preserve_part: str
    relief_part: str
    status: str
    projection: JointReliefProjection
    cut_polygon_2d: object | None = None
    corner_relief: object | None = None
    evidence: object | None = None
    relief_geometry_key: str | None = None
    source_geometry_key: str | None = None


def _joint_relief_corner_name(joint, relief_part: str) -> str | None:
    if str(relief_part) == str(joint.subject_part):
        region = str(joint.subject_region or "")
    elif str(relief_part) == str(joint.target_part):
        region = str(joint.target_region or "")
    else:
        return None
    normalized = region.strip().lower().replace("-", "_")
    for name in ("bottom_left", "bottom_right", "top_left", "top_right"):
        if normalized == name:
            return name
    return None


def discover_joint_relief_candidate(
    joint,
    *,
    world_triangles_by_part,
    mapped_skin_triangles_by_part,
    flat_material_by_part,
    topology_levels: int | None,
    relief_component=None,
    clearance: float = 0.0,
    tolerance: float = 1e-6,
    relief_geometry_key=None,
    source_geometry_key=None,
    corner_name_override=None,
) -> JointDiscoveryCandidate:
    """Create a manufacturing-shaped candidate from physical Joint evidence.

    This function deliberately refuses to invent a corner from a generic
    ``rear_mating``/``mating_zone`` label.  Discovery may only fit a cut when
    the relief owner is tied to one physical corner and a caller supplies the
    allowed relief component/topology.  Otherwise diagnostics retain the raw
    projection and the solver reports ``UNFITTED_REGION``.
    """
    projected = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world_triangles_by_part,
        mapped_skin_triangles_by_part=mapped_skin_triangles_by_part,
        flat_material_by_part=flat_material_by_part,
        tolerance=tolerance,
        relief_geometry_key=relief_geometry_key,
        source_geometry_key=source_geometry_key,
    )
    if not projected.illegal_penetration:
        return JointDiscoveryCandidate(
            joint_id=projected.joint_id, preserve_part=projected.preserve_part,
            relief_part=projected.relief_part, status="NO_ILLEGAL_PENETRATION",
            projection=projected, evidence={"reason": "LEGAL_CONTACT_OR_CLEAR"},
            relief_geometry_key=projected.relief_geometry_key,
            source_geometry_key=projected.source_geometry_key,
        )
    corner_name = str(corner_name_override or "").strip().lower() or _joint_relief_corner_name(joint, projected.relief_part)
    if corner_name is None or relief_component is None:
        return JointDiscoveryCandidate(
            joint_id=projected.joint_id, preserve_part=projected.preserve_part,
            relief_part=projected.relief_part, status="UNFITTED_REGION",
            projection=projected, evidence={
                "reason": "RELIEF_OWNER_REGION_NOT_A_STABLE_CORNER" if corner_name is None else "RELIEF_COMPONENT_REQUIRED",
                "topology_levels": None if topology_levels is None else int(topology_levels),
            },
            relief_geometry_key=projected.relief_geometry_key,
            source_geometry_key=projected.source_geometry_key,
        )
    geometry_key = str(projected.relief_geometry_key or projected.relief_part)
    material = (flat_material_by_part or {}).get(geometry_key)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError(f"missing relief-owner material: {projected.relief_part}")
    if topology_levels is None:
        fitted = derive_corner_relief_from_flat_interference(
            relief_component=relief_component,
            segments_2d=tuple(getattr(projected.projection, "segments_2d", ()) or ()),
            blank_bounds=tuple(map(float, material.bounds)), corner_name=corner_name,
            clearance=float(clearance), tolerance=float(tolerance),
        )
    else:
        fitted = fit_joint_projection_to_corner_topology(
            projection=projected.projection, relief_component=relief_component,
            blank_bounds=tuple(map(float, material.bounds)), corner_name=corner_name,
            topology_levels=int(topology_levels), clearance=float(clearance), tolerance=float(tolerance),
        )
    if fitted is None:
        return JointDiscoveryCandidate(
            joint_id=projected.joint_id, preserve_part=projected.preserve_part,
            relief_part=projected.relief_part, status="FIT_FAILED", projection=projected,
            evidence={"reason": "NO_STABLE_TOPOLOGY_FIT", "corner_name": corner_name},
            relief_geometry_key=projected.relief_geometry_key,
            source_geometry_key=projected.source_geometry_key,
        )
    measurement = getattr(fitted, "measurement", None)
    actual_levels = 2 if (getattr(measurement, "secondary_u", None) is not None and getattr(measurement, "secondary_depth", None) is not None) else 1
    return JointDiscoveryCandidate(
        joint_id=projected.joint_id, preserve_part=projected.preserve_part,
        relief_part=projected.relief_part, status="CANDIDATE", projection=projected,
        cut_polygon_2d=fitted.cut_polygon_2d, corner_relief=fitted,
        evidence={
            "corner_name": corner_name, "topology_levels": actual_levels,
            "pair_count": int(projected.projection.pair_count),
            "source": "PHYSICAL_BACKPROJECTION_NOT_BBOX",
        },
        relief_geometry_key=projected.relief_geometry_key,
        source_geometry_key=projected.source_geometry_key,
    )


@dataclass(frozen=True)
class JointCandidateVerification:
    joint_id: str
    relief_part: str
    verified: bool
    solved_material: object
    residual: JointReliefProjection
    evidence: object | None = None


def verify_joint_candidate_replay(
    joint,
    candidate: JointDiscoveryCandidate,
    *,
    world_triangles_by_part,
    flat_material_by_part,
    rebuild_mapped_skins,
    tolerance: float = 1e-6,
) -> JointCandidateVerification:
    """Replay one discovery candidate and verify residual penetration is zero.

    ``rebuild_mapped_skins(part, material)`` is the geometry adapter boundary:
    Solver v2 owns the relief decision, while Family/part geometry owns how a
    solved flat material becomes a world-space mapped skin.
    """
    if str(getattr(candidate, "status", "")) != "CANDIDATE" or candidate.cut_polygon_2d is None:
        raise ValueError("joint candidate is not replayable")
    relief = str(candidate.relief_part)
    relief_geometry = str(getattr(candidate, "relief_geometry_key", None) or relief)
    source_geometry = str(getattr(candidate, "source_geometry_key", None) or "") or None
    original = (flat_material_by_part or {}).get(relief_geometry)
    if original is None or getattr(original, "is_empty", True):
        raise ValueError(f"missing original relief material: {relief_geometry}")
    solved = original.difference(candidate.cut_polygon_2d)
    if getattr(solved, "is_empty", True):
        raise ValueError("candidate removed all relief-owner material")
    mapped = tuple(rebuild_mapped_skins(relief_geometry, solved) or ())
    if not mapped:
        raise ValueError("rebuild_mapped_skins returned no geometry")
    residual = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=dict(world_triangles_by_part or {}),
        mapped_skin_triangles_by_part={relief_geometry: mapped},
        flat_material_by_part={relief_geometry: solved},
        tolerance=tolerance,
        relief_geometry_key=relief_geometry,
        source_geometry_key=source_geometry,
    )
    return JointCandidateVerification(
        joint_id=str(joint.joint_id), relief_part=relief,
        verified=not bool(residual.illegal_penetration), solved_material=solved, residual=residual,
        evidence={
            "pre_pair_count": int(candidate.projection.projection.pair_count),
            "post_pair_count": int(residual.projection.pair_count),
            "policy": "REPLAY_AND_ZERO_ILLEGAL_PENETRATION",
        },
    )


@dataclass(frozen=True)
class CornerReliefMeasurement:
    corner_name: str
    primary_u: float
    primary_v: float
    secondary_u: float | None = None
    secondary_depth: float | None = None
    clearance_a: float = 0.0


@dataclass(frozen=True)
class BackprojectedCornerRelief:
    corner_name: str
    cut_polygon_2d: object
    measurement: CornerReliefMeasurement


def _canonical_corner_geometry(geometry, blank_bounds, corner_name):
    from shapely.affinity import affine_transform

    minx, miny, maxx, maxy = map(float, blank_bounds)
    name = str(corner_name)
    if name == "bottom_left":
        matrix = [1.0, 0.0, 0.0, 1.0, -minx, -miny]
    elif name == "bottom_right":
        matrix = [-1.0, 0.0, 0.0, 1.0, maxx, -miny]
    elif name == "top_left":
        matrix = [1.0, 0.0, 0.0, -1.0, -minx, maxy]
    elif name == "top_right":
        matrix = [-1.0, 0.0, 0.0, -1.0, maxx, maxy]
    else:
        raise ValueError(f"unknown physical corner: {corner_name!r}")
    return affine_transform(geometry, matrix)


def _measure_canonical_corner_cut(cut_polygon, corner_name, blank_bounds, clearance):
    from shapely.geometry import LineString

    canonical = _canonical_corner_geometry(cut_polygon, blank_bounds, corner_name)
    if canonical.is_empty:
        raise ValueError("empty corner cut")
    if getattr(canonical, "geom_type", "") == "MultiPolygon":
        canonical = max(canonical.geoms, key=lambda geom: float(geom.area))
    min_u, min_v, max_u, max_v = map(float, canonical.bounds)
    tol = 1e-6
    # A physical corner cut must remain connected to canonical u=v=0.
    if min_u > tol or min_v > tol:
        raise ValueError("corner cut does not touch the physical blank corner")

    v_values = {0.0, max_v}
    for x, y in canonical.exterior.coords:
        if -tol <= float(y) <= max_v + tol:
            v_values.add(max(0.0, min(max_v, float(y))))
    levels = sorted(v_values)
    bands = []
    for lo, hi in zip(levels, levels[1:]):
        if hi - lo <= tol:
            continue
        sample_v = (lo + hi) / 2.0
        line = LineString([(-1.0, sample_v), (max_u + 1.0, sample_v)])
        section = canonical.intersection(line)
        if section.is_empty:
            continue
        geoms = [section] if getattr(section, "geom_type", "") == "LineString" else [
            g for g in getattr(section, "geoms", ()) if getattr(g, "geom_type", "") == "LineString"
        ]
        widths = []
        for geom in geoms:
            coords = list(geom.coords)
            if not coords:
                continue
            xs = [float(p[0]) for p in coords]
            if min(xs) <= tol:
                widths.append(max(xs))
        if widths:
            bands.append((float(lo), float(hi), max(widths)))
    if not bands:
        return CornerReliefMeasurement(
            corner_name=str(corner_name),
            primary_u=max_u,
            primary_v=max_v,
            clearance_a=float(clearance),
        )

    primary_width = bands[0][2]
    primary_v = bands[0][1]
    index = 1
    while index < len(bands) and abs(bands[index][2] - primary_width) <= tol:
        primary_v = bands[index][1]
        index += 1
    secondary_u = None
    secondary_depth = None
    if index < len(bands):
        secondary_u = max(band[2] for band in bands[index:])
        secondary_depth = max_v - primary_v
        if secondary_depth <= tol or secondary_u <= tol:
            secondary_u = None
            secondary_depth = None
    return CornerReliefMeasurement(
        corner_name=str(corner_name),
        primary_u=float(primary_width),
        primary_v=float(primary_v),
        secondary_u=None if secondary_u is None else float(secondary_u),
        secondary_depth=None if secondary_depth is None else float(secondary_depth),
        clearance_a=float(clearance),
    )


def _physical_corner_geometry(geometry, blank_bounds, corner_name):
    from shapely.affinity import affine_transform

    minx, miny, maxx, maxy = map(float, blank_bounds)
    name = str(corner_name)
    if name == "bottom_left":
        matrix = [1.0, 0.0, 0.0, 1.0, minx, miny]
    elif name == "bottom_right":
        matrix = [-1.0, 0.0, 0.0, 1.0, maxx, miny]
    elif name == "top_left":
        matrix = [1.0, 0.0, 0.0, -1.0, minx, maxy]
    elif name == "top_right":
        matrix = [-1.0, 0.0, 0.0, -1.0, maxx, maxy]
    else:
        raise ValueError(f"unknown physical corner: {corner_name!r}")
    return affine_transform(geometry, matrix)


def derive_corner_relief_from_flat_interference(
    *,
    relief_component,
    segments_2d,
    blank_bounds,
    corner_name,
    clearance=0.0,
    tolerance=1e-6,
) -> BackprojectedCornerRelief | None:
    """Build a corner cut from physical collision depth inside each topology band.

    The legacy fixed-relief component is used only as the *topological search
    domain* (one-level vs two-level corner bands).  Width/depth inside each band
    comes from backprojected 3D physical crossings.  This avoids both under-cutting
    the deeper sheet skin and inventing extra levels from triangulation vertices.
    """
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union

    if relief_component is None or getattr(relief_component, "is_empty", True):
        return None
    canonical_component = _canonical_corner_geometry(
        relief_component, blank_bounds, corner_name
    )
    if getattr(canonical_component, "geom_type", "") == "MultiPolygon":
        canonical_component = unary_union(canonical_component)
    _cu0, _cv0, component_max_u, component_max_v = map(float, canonical_component.bounds)

    # Physical corner topology is orthogonal.  Horizontal exterior vertices are
    # the only legitimate level boundaries; collision triangulation points must
    # never create new manufacturing levels.
    levels = {0.0, component_max_v}
    polygons = _polygon_parts(canonical_component)
    for poly in polygons:
        coords = list(poly.exterior.coords)
        for i in range(len(coords) - 1):
            x1, y1 = map(float, coords[i])
            x2, y2 = map(float, coords[i + 1])
            if abs(y1 - y2) <= tolerance:
                levels.add(max(0.0, min(component_max_v, (y1 + y2) / 2.0)))
    levels = sorted(levels)
    bands = [(lo, hi) for lo, hi in zip(levels, levels[1:]) if hi - lo > tolerance]
    if not bands:
        bands = [(0.0, component_max_v)]

    canonical_lines = []
    for segment in tuple(segments_2d or ()):
        if len(segment) < 2:
            continue
        line = LineString(segment[:2]).intersection(relief_component)
        if line.is_empty:
            continue
        canonical_lines.append(_canonical_corner_geometry(line, blank_bounds, corner_name))
    if not canonical_lines:
        return None

    required = []
    for band_index, (lo, hi) in enumerate(bands):
        # A crossing that terminates exactly on a topology boundary belongs to
        # the lower band.  Do not let it inflate the narrower upper level.
        band_lo = lo + (tolerance * 10.0 if band_index > 0 else -tolerance)
        band_window = box(-tolerance, band_lo, component_max_u + tolerance, hi + tolerance)
        band_region = canonical_component.intersection(band_window)
        max_u = 0.0
        max_v = lo
        hit = False
        for line in canonical_lines:
            clipped = line.intersection(band_region)
            if clipped.is_empty:
                continue
            geoms = [clipped] if getattr(clipped, "geom_type", "") == "LineString" else [
                g for g in getattr(clipped, "geoms", ())
                if getattr(g, "geom_type", "") == "LineString"
            ]
            for geom in geoms:
                for x, y in geom.coords:
                    hit = True
                    max_u = max(max_u, float(x))
                    max_v = max(max_v, float(y))
        required.append([lo, hi, max_u, max_v, hit])

    occupied = [i for i, item in enumerate(required) if item[4] and item[2] > tolerance]
    if not occupied:
        return None
    highest = max(occupied)
    # A higher-level collision requires a connected material removal path to the
    # blank corner. Propagate its width downward while preserving wider lower hits.
    carry_width = 0.0
    for i in range(highest, -1, -1):
        carry_width = max(carry_width, float(required[i][2]))
        required[i][2] = carry_width

    rectangles = []
    for i, (lo, hi, width, hit_max_v, _hit) in enumerate(required[:highest + 1]):
        if width <= tolerance:
            continue
        cut_hi = hi if i < highest else min(hi, max(lo, hit_max_v))
        if cut_hi - lo <= tolerance:
            continue
        rectangles.append(box(0.0, lo, width, cut_hi))
    if not rectangles:
        return None
    canonical_cut = unary_union(rectangles).intersection(canonical_component)
    cut = _physical_corner_geometry(canonical_cut, blank_bounds, corner_name)

    minx, miny, maxx, maxy = map(float, blank_bounds)
    a = max(0.0, float(clearance or 0.0))
    if a > 0.0:
        cut = cut.buffer(a, join_style=2)
    cut = cut.intersection(box(minx, miny, maxx, maxy))
    if not cut.is_valid:
        cut = cut.buffer(0)
    if cut.is_empty or float(cut.area) <= tolerance:
        return None
    measurement = _measure_canonical_corner_cut(
        cut, str(corner_name), blank_bounds, a
    )
    return BackprojectedCornerRelief(
        corner_name=str(corner_name),
        cut_polygon_2d=cut,
        measurement=measurement,
    )



def fit_joint_projection_to_corner_topology(
    *, projection, relief_component, blank_bounds, corner_name, topology_levels,
    clearance=0.0, tolerance=1e-6,
):
    """Fit physical backprojection to the requested manufacturing stage count.

    Geometry evidence may never invent a second stage for a one-stage contract,
    nor collapse a required two-stage rule into a one-stage cut.
    """
    fitted = derive_corner_relief_from_flat_interference(
        relief_component=relief_component,
        segments_2d=tuple(getattr(projection, "segments_2d", ()) or ()),
        blank_bounds=blank_bounds,
        corner_name=corner_name,
        clearance=clearance,
        tolerance=tolerance,
    )
    if fitted is None:
        return None
    m = fitted.measurement
    actual = 2 if (m.secondary_u is not None and m.secondary_depth is not None) else 1
    expected = int(topology_levels)
    if actual != expected:
        raise ValueError(f"topology fit mismatch: got {actual}, expected {expected}")
    return fitted


def projection_has_material_penetration(
    projection: FlatInterferenceProjection | None,
    material,
    *,
    tolerance: float = 1e-5,
) -> bool:
    """Return True only when a projected crossing lies inside remaining material.

    A=0 is allowed to finish exactly on the new CUTTING boundary.  Those
    boundary-only contacts can still appear as 3D surface intersection lines,
    but they do not represent remaining sheet area penetrating the retained
    part.  Clearance A > 0 expands the cut afterwards and naturally removes
    even this line contact.
    """
    from shapely.geometry import Point

    if (
        projection is None
        or not projection.has_interference
        or material is None
        or getattr(material, "is_empty", True)
    ):
        return False
    tol = max(0.0, float(tolerance or 0.0))
    interior = material.buffer(-tol) if tol > 0.0 else material
    # If the entire retained region disappears under the inward tolerance, it
    # is a numerical/manufacturing sub-tolerance sliver, not material that can
    # physically penetrate another sheet.  Never resurrect the original sliver.
    if getattr(interior, "is_empty", True):
        return False
    for segment in tuple(projection.segments_2d or ()):
        if len(segment) < 2:
            continue
        a, b = segment[0], segment[1]
        midpoint = Point(
            (float(a[0]) + float(b[0])) / 2.0,
            (float(a[1]) + float(b[1])) / 2.0,
        )
        if interior.contains(midpoint):
            return True
    return False



@dataclass(frozen=True)
class JointLocalCollisionResult:
    joint_id: str
    relation: str
    has_contact: bool
    illegal_penetration: bool
    preserve_part: str
    relief_part: str
    projection: object | None = None
    evidence: object | None = None


def classify_joint_interference(
    joint,
    *,
    projection,
    flat_material,
    tolerance=1e-6,
) -> JointLocalCollisionResult:
    """Classify one joint-local projection without confusing legal contact with penetration."""
    ownership = joint_relief_ownership(joint)
    has_contact = bool(getattr(projection, "has_interference", False))
    illegal = projection_has_material_penetration(projection, flat_material, tolerance=tolerance)
    return JointLocalCollisionResult(
        joint_id=str(joint.joint_id),
        relation=str(getattr(joint.relation, "value", joint.relation)),
        has_contact=has_contact,
        illegal_penetration=bool(illegal),
        preserve_part=ownership.preserve_part,
        relief_part=ownership.relief_part,
        projection=projection,
        evidence={
            "pair_count": int(getattr(projection, "pair_count", 0) or 0),
            "policy": getattr(getattr(joint, "semantics", None), "legal_contact_mode", ""),
        },
    )


def verify_joint_zero_penetration(joint, *, projection, flat_material, tolerance=1e-6) -> JointLocalCollisionResult:
    return classify_joint_interference(
        joint, projection=projection, flat_material=flat_material, tolerance=tolerance
    )


def _projection_within_material_boundary_band(
    projection: FlatInterferenceProjection | None, material, *, tolerance: float
) -> bool:
    """True when every projected crossing midpoint is only a boundary-band contact.

    Used after topology normalization: a fold/refold triangulation can place a
    physical skin a few microns inside the retained polygon even when the
    semantic mid-surface is clear.  Never use this alone to forgive a crossing;
    callers must also confirm the mid-surface has no material penetration.
    """
    from shapely.geometry import Point

    if (
        projection is None
        or not projection.has_interference
        or material is None
        or getattr(material, "is_empty", True)
    ):
        return False
    tol = max(0.0, float(tolerance or 0.0))
    if tol <= 0.0:
        return False
    boundary = material.boundary
    saw_segment = False
    for segment in tuple(projection.segments_2d or ()):
        if len(segment) < 2:
            continue
        saw_segment = True
        a, b = segment[0], segment[1]
        midpoint = Point(
            (float(a[0]) + float(b[0])) / 2.0,
            (float(a[1]) + float(b[1])) / 2.0,
        )
        if float(midpoint.distance(boundary)) > tol:
            return False
    return saw_segment


@dataclass(frozen=True)
class AssemblyBackprojectedReliefSolution:
    cut_polygon_2d: object | None
    corner_reliefs: tuple[BackprojectedCornerRelief, ...]
    projections: tuple[FlatInterferenceProjection, ...]
    solved_render_data: object
    verified: bool
    residual_projection: FlatInterferenceProjection | None = None
    trust_level: str = "PROVISIONAL_3D"
    rule_id: str | None = None
    rule_revision: int | None = None
    joint_signature: tuple[dict, ...] = ()
    shadow_validation: object | None = None


def _polygon_parts(geometry):
    if geometry is None or getattr(geometry, "is_empty", True):
        return []
    if getattr(geometry, "geom_type", "") == "Polygon":
        return [geometry]
    return [
        geom for geom in getattr(geometry, "geoms", ())
        if getattr(geom, "geom_type", "") == "Polygon" and float(geom.area) > 1e-9
    ]


def _corner_name_for_component(component, blank_bounds, *, tolerance=1e-6):
    from shapely.geometry import Point

    minx, miny, maxx, maxy = map(float, blank_bounds)
    corners = (
        ("bottom_left", (minx, miny)),
        ("bottom_right", (maxx, miny)),
        ("top_left", (minx, maxy)),
        ("top_right", (maxx, maxy)),
    )
    for name, point in corners:
        if component.buffer(tolerance).covers(Point(point)):
            return name
    return None


def measure_material_corner_reliefs(material, *, blank_bounds=None, clearance=0.0, tolerance=1e-6):
    """Measure actual corner material removed from one authoritative sheet polygon.

    The renderer/UI must not reconstruct CornerType semantics.  This helper
    measures the *resolved material* itself: interior holes are ignored and only
    missing material connected to a physical blank corner is reported.
    """
    from shapely.geometry import Point, box
    from shapely.ops import unary_union

    if material is None or getattr(material, "is_empty", True):
        return tuple()
    bounds = tuple(map(float, blank_bounds or material.bounds))
    minx, miny, maxx, maxy = bounds
    if maxx - minx <= tolerance or maxy - miny <= tolerance:
        return tuple()
    blank = box(minx, miny, maxx, maxy)
    missing = blank.difference(material)
    if missing.is_empty:
        return tuple()
    parts = _polygon_parts(missing)
    corners = (
        ("bottom_left", (minx, miny)),
        ("bottom_right", (maxx, miny)),
        ("top_left", (minx, maxy)),
        ("top_right", (maxx, maxy)),
    )
    measured = []
    for name, coords in corners:
        point = Point(coords)
        connected = [
            part for part in parts
            if part.buffer(tolerance).covers(point)
        ]
        if not connected:
            continue
        cut = unary_union(connected)
        try:
            item = _measure_canonical_corner_cut(cut, name, bounds, clearance)
        except ValueError:
            continue
        if item.primary_u <= tolerance or item.primary_v <= tolerance:
            continue
        measured.append(item)
    return tuple(measured)


def apply_verified_endcap_relief_material(original_material, cut_polygons, *, tolerance=1e-6):
    """Replay verified dynamic EndCap relief without resurrecting unrelated corners.

    ``cut_polygons`` are the world-verified 2D corner cuts.  The probe solver may
    restore the whole rectangular blank to discover collisions, but production
    replay must add back legacy fixed-relief material only at corners that have a
    verified replacement cut.  2D, 3D and DXF all call this same helper.
    """
    from shapely.ops import unary_union
    from .assembly_geometry import (
        restore_unrelieved_endcap_material, restored_endcap_relief_delta,
    )

    cuts = [
        geom for geom in tuple(cut_polygons or ())
        if geom is not None and not getattr(geom, "is_empty", True)
        and float(getattr(geom, "area", 0.0)) > float(tolerance)
    ]
    if original_material is None or getattr(original_material, "is_empty", True) or not cuts:
        return original_material

    restored = restore_unrelieved_endcap_material(original_material)
    delta = restored_endcap_relief_delta(original_material)
    if restored is None or getattr(restored, "is_empty", True):
        return original_material
    blank_bounds = tuple(map(float, restored.bounds))

    solved_corners = set()
    for cut in cuts:
        for part in _polygon_parts(cut):
            name = _corner_name_for_component(part, blank_bounds, tolerance=tolerance)
            if name is not None:
                solved_corners.add(name)

    corner_deltas = []
    for component in _polygon_parts(delta):
        name = _corner_name_for_component(component, blank_bounds, tolerance=tolerance)
        if name in solved_corners:
            corner_deltas.append(component)

    restored_for_solution = original_material
    if corner_deltas:
        restored_for_solution = unary_union([original_material, *corner_deltas])
    solved = restored_for_solution.difference(unary_union(cuts))
    if not solved.is_valid:
        solved = solved.buffer(0)
    return solved


def _render_data_rebuilt_from_material(endcap_render_data, material):
    scene = _scene_with_replaced_primary_cutting(endcap_render_data.scene, material)
    return replace(endcap_render_data, scene=scene, material=material)


def _build_box_body_world_solid(
    box_body_render_data,
    box_body_x_profile,
    finished_dimensions,
    sheet_thickness,
):
    from .assembly_geometry import (
        folded_mesh_from_polygon,
        place_assembly_triangles,
        thicken_triangle_surface,
    )

    pieces = tuple(getattr(box_body_render_data, "pieces", ()) or ())
    if pieces:
        from .assembly_geometry import place_box_body_structure_points
        total_w = max(float(getattr(piece, "formed_w_end", 0.0)) for piece in pieces)
        structure_local = []
        for piece in pieces:
            data = piece.render_data
            _minx, miny, _maxx, maxy = map(float, data.material.bounds)
            body_y_profile = ({"len": max(0.0, maxy - miny), "core": True},)
            piece_profile = tuple(getattr(piece, "fold_profile", ()) or ())
            piece_local = folded_mesh_from_polygon(
                data.material, piece_profile, body_y_profile,
                fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
            )
            flat_points = [point for tri in piece_local for point in tri]
            placed_points = place_box_body_structure_points(
                flat_points, piece, total_w=total_w, thickness=sheet_thickness,
                x_profile=piece_profile,
            )
            structure_local.extend(
                tuple(placed_points[i:i + 3]) for i in range(0, len(placed_points), 3)
            )
        world_surface = place_assembly_triangles(
            tuple(structure_local), "box_body", finished_dimensions, (0.0, 0.0, 0.0)
        )
        return world_surface, thicken_triangle_surface(world_surface, sheet_thickness)

    _minx, miny, _maxx, maxy = map(float, box_body_render_data.material.bounds)
    body_y_profile = ({"len": max(0.0, maxy - miny), "core": True},)
    local = folded_mesh_from_polygon(
        box_body_render_data.material,
        box_body_x_profile,
        body_y_profile,
        fold_guides=tuple(getattr(box_body_render_data, "fold_guides", ()) or ()),
    )
    world_surface = place_assembly_triangles(
        local, "box_body", finished_dimensions, (0.0, 0.0, 0.0)
    )
    return world_surface, thicken_triangle_surface(world_surface, sheet_thickness)


def _folded_profile_is_mirror_symmetric(profile, *, tolerance=1e-6):
    """Return True only when the folded X cross-section is mirror-symmetric."""
    from .assembly_geometry import _profile_geometry

    _boundaries, folded = _profile_geometry(profile)
    points = tuple((float(u), float(z)) for u, z in folded)
    tol = max(0.0, float(tolerance or 0.0))
    for left, right in zip(points, reversed(points)):
        if abs(left[0] + right[0]) > tol or abs(left[1] - right[1]) > tol:
            return False
    return True


def _profile_flat_positions_for_folded_u(profile, target_u, *, tolerance=1e-7):
    """Invert horizontal folded-profile runs back to authoritative flat positions.

    A Box Body flange tip and an EndCap core run share the same folded U axis.
    Mapping that structural contact line back through the EndCap profile gives the
    exact manufacturing cut boundary.  Vertical folded runs are intentionally
    ignored because one U value would map to an interval instead of one cut line.
    """
    from .assembly_geometry import _profile_geometry

    boundaries, folded = _profile_geometry(profile)
    target = float(target_u)
    positions = []
    tol = max(0.0, float(tolerance or 0.0))
    for index in range(len(boundaries) - 1):
        u0 = float(folded[index][0])
        u1 = float(folded[index + 1][0])
        du = u1 - u0
        if abs(du) <= tol:
            continue
        lo, hi = sorted((u0, u1))
        if target < lo - tol or target > hi + tol:
            continue
        ratio = (target - u0) / du
        if ratio < -tol or ratio > 1.0 + tol:
            continue
        flat0 = float(boundaries[index])
        flat1 = float(boundaries[index + 1])
        positions.append(flat0 + (flat1 - flat0) * ratio)
    return tuple(positions)


def _single_stage_structural_contact_width(
    *,
    raw_cut,
    corner_name,
    blank_bounds,
    box_body_x_profile,
    endcap_x_profile,
    sheet_thickness,
    tolerance=1e-6,
):
    """Return an exact folded-profile contact width when skin crossings overshoot it.

    True-thickness surface intersection produces two nearby skin crossings around a
    legitimate mating/contact line.  For a one-stage INSERT corner, the physical cut
    boundary is the structural Box Body profile line, not the outer T/2 skin.  Only
    snap when the raw 3D result is within one half thickness of that exact line.
    Multi-stage INSERT_OVERLAY geometry is deliberately excluded.
    """
    from .assembly_geometry import _profile_geometry

    measurement = _measure_canonical_corner_cut(raw_cut, corner_name, blank_bounds, 0.0)
    if measurement.secondary_u is not None or measurement.secondary_depth is not None:
        return None

    raw_width = float(measurement.primary_u)
    if raw_width <= tolerance:
        return None
    minx, _miny, maxx, _maxy = map(float, blank_bounds)
    is_left = str(corner_name).endswith("left")
    half_t = max(0.0, float(sheet_thickness or 0.0)) / 2.0
    snap_window = max(0.02, half_t + 0.02)

    _body_boundaries, body_folded = _profile_geometry(box_body_x_profile)
    candidates = []
    for target_u, _target_z in body_folded:
        for flat_x in _profile_flat_positions_for_folded_u(endcap_x_profile, target_u):
            width = float(flat_x) - minx if is_left else maxx - float(flat_x)
            if width <= tolerance or width > raw_width + tolerance:
                continue
            delta = raw_width - width
            if delta <= snap_window + tolerance:
                candidates.append((delta, width))
    if not candidates:
        return None
    _delta, width = min(candidates, key=lambda item: (item[0], -item[1]))
    return float(width)


def _snap_single_stage_cut_to_structural_contact(
    raw_cut, corner_name, blank_bounds, *, box_body_x_profile, endcap_x_profile, sheet_thickness
):
    from shapely.geometry import box

    width = _single_stage_structural_contact_width(
        raw_cut=raw_cut,
        corner_name=corner_name,
        blank_bounds=blank_bounds,
        box_body_x_profile=box_body_x_profile,
        endcap_x_profile=endcap_x_profile,
        sheet_thickness=sheet_thickness,
    )
    if width is None:
        return raw_cut, False
    measurement = _measure_canonical_corner_cut(raw_cut, corner_name, blank_bounds, 0.0)
    canonical = box(0.0, 0.0, width, float(measurement.primary_v))
    return _physical_corner_geometry(canonical, blank_bounds, corner_name), True


def _project_probe_mid_surface(
    *,
    probe_material,
    box_body_world_surface,
    box_body_world_solid,
    endcap_reference_local,
    endcap_x_profile,
    endcap_y_profile,
    endcap_fold_guides,
    endcap_placement,
    sheet_thickness,
    preserve_core_origin=False,
):
    """Backproject the semantic EndCap mid-surface for contact-only verification.

    This is not used to derive relief.  It is only a confirmation path after a
    single-stage cut has been snapped to an exact structural mating line: if the
    mid-surface is clear, residual +/-T/2 skin crossings are contact/tessellation
    artifacts rather than retained-material penetration.
    """
    from .assembly_geometry import (
        MappedSkinTriangle,
        folded_mesh_with_flat_uv_from_polygon,
        place_endcap_against_box_body,
    )

    if probe_material is None or getattr(probe_material, "is_empty", True):
        return FlatInterferenceProjection((), (), 0)
    mapped = folded_mesh_with_flat_uv_from_polygon(
        probe_material,
        endcap_x_profile,
        endcap_y_profile,
        fold_guides=tuple(endcap_fold_guides or ()),
    )
    world = place_endcap_against_box_body(
        tuple(item.local for item in mapped),
        endcap_placement,
        box_body_world_surface,
        sheet_thickness=sheet_thickness,
        reference_triangles=endcap_reference_local,
        preserve_core_origin=preserve_core_origin,
    )
    mids = tuple(
        MappedSkinTriangle(flat=item.flat, world=tri, side=0)
        for item, tri in zip(mapped, world)
    )
    return backproject_world_interference_to_endcap_flat(box_body_world_solid, mids)


def _project_probe_material(
    *,
    probe_material,
    box_body_world_surface,
    box_body_world_solid,
    endcap_reference_local,
    endcap_x_profile,
    endcap_y_profile,
    endcap_fold_guides,
    endcap_placement,
    sheet_thickness,
    preserve_core_origin=False,
):
    from .assembly_geometry import (
        endcap_world_skin_with_flat_uv,
        folded_mesh_with_flat_uv_from_polygon,
    )

    if probe_material is None or getattr(probe_material, "is_empty", True):
        return FlatInterferenceProjection((), (), 0)
    mapped = folded_mesh_with_flat_uv_from_polygon(
        probe_material,
        endcap_x_profile,
        endcap_y_profile,
        fold_guides=tuple(endcap_fold_guides or ()),
    )
    skins = endcap_world_skin_with_flat_uv(
        mapped,
        endcap_placement,
        box_body_world_surface,
        sheet_thickness=sheet_thickness,
        reference_triangles=endcap_reference_local,
        preserve_core_origin=preserve_core_origin,
    )
    return backproject_world_interference_to_endcap_flat(
        box_body_world_solid, skins
    )


def _normalize_corner_cut_to_component_topology(
    raw_cut, relief_component, corner_name, blank_bounds, *, tolerance=1e-6, snap_tolerance=1e-3
):
    """Collapse iterative/numerical cut evidence back to the approved corner topology."""
    from shapely.geometry import box
    from shapely.ops import unary_union

    canonical_component = _canonical_corner_geometry(
        relief_component, blank_bounds, corner_name
    )
    canonical_cut = _canonical_corner_geometry(raw_cut, blank_bounds, corner_name)
    canonical_cut = canonical_cut.intersection(canonical_component)
    if canonical_cut.is_empty:
        return raw_cut

    _min_u, _min_v, component_max_u, component_max_v = map(
        float, canonical_component.bounds
    )
    levels = {0.0, component_max_v}
    for poly in _polygon_parts(canonical_component):
        coords = list(poly.exterior.coords)
        for i in range(len(coords) - 1):
            x1, y1 = map(float, coords[i])
            x2, y2 = map(float, coords[i + 1])
            if abs(y1 - y2) <= tolerance:
                levels.add(max(0.0, min(component_max_v, (y1 + y2) / 2.0)))
    levels = sorted(levels)
    bands = [(lo, hi) for lo, hi in zip(levels, levels[1:]) if hi - lo > tolerance]
    if not bands:
        bands = [(0.0, component_max_v)]

    required = []
    for band_index, (lo, hi) in enumerate(bands):
        # Shared horizontal boundaries belong to the lower topology band.
        # Otherwise a wide lower cut edge can inflate the narrower upper stage.
        band_lo = lo + (tolerance * 10.0 if band_index > 0 else -tolerance)
        region = canonical_cut.intersection(
            box(-tolerance, band_lo, component_max_u + tolerance, hi + tolerance)
        )
        if region.is_empty:
            required.append([lo, hi, 0.0, lo, False])
            continue
        _rminx, _rminy, rmaxx, rmaxy = map(float, region.bounds)
        max_u = max(0.0, min(component_max_u, rmaxx))
        max_v = max(lo, min(hi, rmaxy))
        if hi - max_v <= max(float(snap_tolerance), tolerance):
            max_v = hi
        required.append([lo, hi, max_u, max_v, max_u > tolerance])

    occupied = [i for i, item in enumerate(required) if item[4]]
    if not occupied:
        return raw_cut
    highest = max(occupied)
    carry_width = 0.0
    for i in range(highest, -1, -1):
        carry_width = max(carry_width, float(required[i][2]))
        required[i][2] = carry_width

    rectangles = []
    for i, (lo, hi, width, hit_max_v, _hit) in enumerate(required[:highest + 1]):
        if width <= tolerance:
            continue
        cut_hi = hi if i < highest else hit_max_v
        if cut_hi - lo <= tolerance:
            continue
        rectangles.append(box(0.0, lo, width, cut_hi))
    if not rectangles:
        return raw_cut
    canonical = unary_union(rectangles).intersection(canonical_component)
    return _physical_corner_geometry(canonical, blank_bounds, corner_name)


def _expand_orthogonal_corner_cut_with_clearance(
    raw_cut, corner_name, blank_bounds, clearance
):
    """Expand a verified orthogonal corner cut by clearance A without buffer noise.

    Collision depth comes from 3D backprojection.  Clearance is a separate
    manufacturing policy applied along the two unfolded sheet axes, so preserve
    the solved step depths exactly and expand only the inward U/V reach.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union

    a = max(0.0, float(clearance or 0.0))
    if a <= 0.0:
        return raw_cut
    measurement = _measure_canonical_corner_cut(
        raw_cut, corner_name, blank_bounds, 0.0
    )
    primary_u = float(measurement.primary_u) + a
    primary_v = float(measurement.primary_v) + a
    rectangles = [box(0.0, 0.0, primary_u, primary_v)]
    if measurement.secondary_u is not None and measurement.secondary_depth is not None:
        secondary_u = float(measurement.secondary_u) + a
        secondary_depth = float(measurement.secondary_depth)
        rectangles.append(
            box(0.0, primary_v, secondary_u, primary_v + secondary_depth)
        )
    canonical = unary_union(rectangles)
    physical = _physical_corner_geometry(canonical, blank_bounds, corner_name)
    minx, miny, maxx, maxy = map(float, blank_bounds)
    return physical.intersection(box(minx, miny, maxx, maxy))


def solve_world_backprojected_endcap_relief(
    *,
    box_body_render_data,
    endcap_render_data,
    box_body_x_profile,
    endcap_x_profile,
    endcap_y_profile,
    finished_dimensions,
    endcap_placement="top",
    sheet_thickness=0.0,
    clearance=0.0,
    max_iterations=8,
    assembly_intent=None,
    cabinet_family="ANY",
    allow_3d_fallback=True,
    assembly_joint=None,
    assembly_graph=None,
    endcap_part=None,
    certified_result_override=None,
) -> AssemblyBackprojectedReliefSolution:
    """Replace fixed relief with a converged, world-verified 3D-derived cut."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    from .assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon,
        restore_unrelieved_endcap_material,
        restored_endcap_relief_delta,
    )

    t = max(0.0, float(sheet_thickness or 0.0))
    # The receiving cabinet's asymmetric EndCap fold profile uses the core
    # datum as the authoritative assembly-depth origin. Existing vault/generic
    # solver contracts retain historical envelope centering until migrated and
    # certified independently, so this opt-in must stay family-scoped.
    family_key = str(cabinet_family or "").strip().upper()
    preserve_endcap_core_origin = family_key in {"受電箱", "RECEIVING"}
    restored = restore_unrelieved_endcap_material(endcap_render_data.material)
    delta = restored_endcap_relief_delta(endcap_render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return AssemblyBackprojectedReliefSolution(None, (), (), endcap_render_data, False, None)

    body_world_surface, body_world_solid = _build_box_body_world_solid(
        box_body_render_data, box_body_x_profile, finished_dimensions, t
    )
    full_mapped = folded_mesh_with_flat_uv_from_polygon(
        restored, endcap_x_profile, endcap_y_profile,
        fold_guides=tuple(getattr(endcap_render_data, "fold_guides", ()) or ()),
    )
    full_reference_local = tuple(mapped.local for mapped in full_mapped)
    blank_bounds = tuple(map(float, restored.bounds))
    minx, miny, maxx, maxy = blank_bounds
    components = []
    for component in _polygon_parts(delta):
        name = _corner_name_for_component(component, blank_bounds)
        if name is not None:
            components.append((name, component))

    # Certified formulas have priority over 3D discovery.  Once a resolved
    # AssemblyJoint graph exists it is the assembly source of truth; the legacy
    # high-level assembly_intent mirror is ignored for rule selection.
    if assembly_graph is not None or assembly_intent is not None or certified_result_override is not None:
        from .certified_relief_registry import (
            CertifiedReliefStatus,
            lookup_certified_endcap_relief,
            lookup_certified_endcap_relief_from_graph,
        )
        certified = certified_result_override
        if certified is None and assembly_graph is not None:
            part_key = str(endcap_part or ("tail" if str(endcap_placement).lower() == "bottom" else "head"))
            certified = lookup_certified_endcap_relief_from_graph(
                graph=assembly_graph,
                endcap_part=part_key,
                endcap_render_data=endcap_render_data,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                sheet_thickness=t,
                cabinet_family=cabinet_family,
            )
        elif certified is None and assembly_intent is not None:
            signature_relations = None
            if assembly_joint is not None:
                # Legacy compatibility only: one explicit Joint augments the
                # high-level mirror when no resolved graph is available.
                signature_relations = (
                    str(getattr(assembly_intent, "value", assembly_intent)),
                    str(getattr(getattr(assembly_joint, "relation", None), "value", getattr(assembly_joint, "relation", ""))),
                )
            certified = lookup_certified_endcap_relief(
                assembly_intent=assembly_intent,
                endcap_render_data=endcap_render_data,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                sheet_thickness=t,
                cabinet_family=cabinet_family,
                joint_signature_relations=signature_relations,
            )
        if certified is not None:
            certified_corner_names = {
                str(getattr(relief, "corner_name", "") or "")
                for relief in tuple(getattr(certified, "corner_reliefs", ()) or ())
            }
            certified_components = tuple(
                (name, component) for name, component in components
                if not certified_corner_names or str(name) in certified_corner_names
            )
            certified_projections = []
            for _corner_name, component in certified_components:
                probe = restored.intersection(component)
                certified_projections.append(_project_probe_material(
                    probe_material=probe,
                    box_body_world_surface=body_world_surface,
                    box_body_world_solid=body_world_solid,
                    endcap_reference_local=full_reference_local,
                    endcap_x_profile=endcap_x_profile,
                    endcap_y_profile=endcap_y_profile,
                    endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                    endcap_placement=endcap_placement,
                    sheet_thickness=t,
                    preserve_core_origin=preserve_endcap_core_origin,
                ))

            final_cuts = tuple(certified.cut_polygons or ())
            cut_polygon = unary_union(final_cuts) if final_cuts else None
            solved_material = apply_verified_endcap_relief_material(
                endcap_render_data.material, final_cuts
            )
            if solved_material.is_empty:
                return AssemblyBackprojectedReliefSolution(
                    cut_polygon, tuple(certified.corner_reliefs), tuple(certified_projections),
                    endcap_render_data, False, FlatInterferenceProjection((), (), 0),
                    trust_level=CertifiedReliefStatus.ENGINE_CONFLICT.value,
                    rule_id=certified.rule_id,
                    rule_revision=certified.rule_revision,
                    joint_signature=tuple(dict(item) for item in tuple(certified.rule.joint_signature or ())),
                    shadow_validation={
                        "reason": "certified rule removed all material",
                        "geometry_inputs": list(getattr(certified.rule, "geometry_inputs", ()) or ()),
                        "geometry_evidence": dict(getattr(certified, "geometry_evidence", {}) or {}),
                    },
                )
            solved_render = _render_data_rebuilt_from_material(endcap_render_data, solved_material)

            verify_segments = []
            verify_points = []
            verify_pairs = 0
            has_material_penetration = False
            verification_tolerance = 1e-5
            for _corner_name, component in certified_components:
                probe = solved_render.material.intersection(component)
                projection = _project_probe_material(
                    probe_material=probe,
                    box_body_world_surface=body_world_surface,
                    box_body_world_solid=body_world_solid,
                    endcap_reference_local=full_reference_local,
                    endcap_x_profile=endcap_x_profile,
                    endcap_y_profile=endcap_y_profile,
                    endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                    endcap_placement=endcap_placement,
                    sheet_thickness=t,
                    preserve_core_origin=preserve_endcap_core_origin,
                )
                penetrates = projection_has_material_penetration(
                    projection, probe, tolerance=verification_tolerance
                )
                if penetrates:
                    mid_projection = _project_probe_mid_surface(
                        probe_material=probe,
                        box_body_world_surface=body_world_surface,
                        box_body_world_solid=body_world_solid,
                        endcap_reference_local=full_reference_local,
                        endcap_x_profile=endcap_x_profile,
                        endcap_y_profile=endcap_y_profile,
                        endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                        endcap_placement=endcap_placement,
                        sheet_thickness=t,
                    )
                    mid_clear = not projection_has_material_penetration(
                        mid_projection, probe, tolerance=verification_tolerance
                    )
                    if mid_clear:
                        # Certified structural-contact rules intentionally end
                        # exactly at a mating line.  Physical +/-T/2 skins can
                        # still intersect as surface contact, but the certified
                        # answer remains authoritative when the semantic
                        # mid-surface is clear.
                        penetrates = False
                    elif _projection_within_material_boundary_band(
                        projection, probe, tolerance=max(0.02, t * 0.01 if t > 0.0 else 0.02)
                    ):
                        penetrates = False
                verify_segments.extend(projection.segments_2d)
                verify_points.extend(projection.points_2d)
                verify_pairs += projection.pair_count
                if penetrates:
                    has_material_penetration = True
            final_residual = FlatInterferenceProjection(
                tuple(verify_segments), tuple(verify_points), verify_pairs
            )
            verified = not has_material_penetration
            trust = (
                certified.trust_level.value if verified
                else CertifiedReliefStatus.ENGINE_CONFLICT.value
            )
            return AssemblyBackprojectedReliefSolution(
                cut_polygon_2d=cut_polygon,
                corner_reliefs=tuple(certified.corner_reliefs),
                projections=tuple(certified_projections),
                solved_render_data=solved_render,
                verified=verified,
                residual_projection=final_residual,
                trust_level=trust,
                rule_id=certified.rule_id,
                rule_revision=certified.rule_revision,
                joint_signature=tuple(dict(item) for item in tuple(certified.rule.joint_signature or ())),
                shadow_validation={
                    "policy": certified.rule.solver_shadow_policy,
                    "verified": bool(verified),
                    "residual_pair_count": int(final_residual.pair_count),
                    "geometry_inputs": list(getattr(certified.rule, "geometry_inputs", ()) or ()),
                    "geometry_evidence": dict(getattr(certified, "geometry_evidence", {}) or {}),
                },
            )

    if assembly_joint is not None:
        from .assembly_joint import AssemblyJointRelation
        relation = getattr(assembly_joint, "relation", None)
        try:
            relation = relation if isinstance(relation, AssemblyJointRelation) else AssemblyJointRelation(str(relation))
        except Exception:
            relation = None
        if relation is AssemblyJointRelation.WRAP:
            ownership = joint_relief_ownership(assembly_joint)
            # Current EndCap fallback can only remove EndCap material.  For WRAP
            # the outer subject must be preserved and the wrapped target owns
            # relief. Refuse an unsafe subject cut until the generalized target
            # flat-mapper path handles this Joint.
            return AssemblyBackprojectedReliefSolution(
                cut_polygon_2d=None, corner_reliefs=(), projections=(),
                solved_render_data=endcap_render_data, verified=False,
                residual_projection=FlatInterferenceProjection((), (), 0),
                trust_level="FAILED", rule_id=None, rule_revision=None,
                shadow_validation={
                    "reason": "WRAP_RELIEF_OWNER_IS_TARGET",
                    "preserve_part": ownership.preserve_part,
                    "relief_part": ownership.relief_part,
                    "joint_id": str(assembly_joint.joint_id),
                },
            )

    if not bool(allow_3d_fallback):
        return AssemblyBackprojectedReliefSolution(
            cut_polygon_2d=None,
            corner_reliefs=(),
            projections=(),
            solved_render_data=endcap_render_data,
            verified=False,
            residual_projection=FlatInterferenceProjection((), (), 0),
            trust_level="FAILED",
            rule_id=None,
            rule_revision=None,
            shadow_validation={"reason": "NO_CERTIFIED_RULE_AND_3D_FALLBACK_DISABLED"},
        )

    raw_cuts = {}
    all_projections = []
    current_material = restored
    residual_projection = FlatInterferenceProjection((), (), 0)

    for _iteration in range(max(1, int(max_iterations))):
        changed = False
        residual_segments = []
        residual_points = []
        residual_pairs = 0
        for corner_name, component in components:
            probe = current_material.intersection(component)
            projection = _project_probe_material(
                probe_material=probe,
                box_body_world_surface=body_world_surface,
                box_body_world_solid=body_world_solid,
                endcap_reference_local=full_reference_local,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                endcap_placement=endcap_placement,
                sheet_thickness=t,
            )
            all_projections.append(projection)
            # Solve with a stricter interior tolerance than final refold
            # verification.  Otherwise a few-micron crossing can be accepted too
            # early, then topology/replay leaves a visible retained boundary
            # crossing (自訂(10) Tail).
            if not projection_has_material_penetration(
                projection, probe, tolerance=1e-6
            ):
                continue
            residual_segments.extend(projection.segments_2d)
            residual_points.extend(projection.points_2d)
            residual_pairs += projection.pair_count
            result = derive_corner_relief_from_flat_interference(
                relief_component=component,
                segments_2d=projection.segments_2d,
                blank_bounds=blank_bounds,
                corner_name=corner_name,
                clearance=0.0,
            )
            if result is None:
                continue
            previous = raw_cuts.get(corner_name)
            combined = result.cut_polygon_2d if previous is None else unary_union([previous, result.cut_polygon_2d])
            if previous is None or float(combined.area) > float(previous.area) + 1e-7:
                raw_cuts[corner_name] = combined
                changed = True
        residual_projection = FlatInterferenceProjection(
            tuple(residual_segments), tuple(residual_points), residual_pairs
        )
        if not residual_projection.has_interference:
            break
        if not changed:
            break
        raw_union = unary_union(list(raw_cuts.values())) if raw_cuts else None
        current_material = restored if raw_union is None else restored.difference(raw_union)
        if not current_material.is_valid:
            current_material = current_material.buffer(0)

    # Numerical triangle intersections can leave mirror-equivalent corner cuts
    # a few microns apart.  When the canonical cut shapes are already within a
    # tight manufacturing tolerance, harmonize them by taking the shared union.
    # This removes triangulation noise without forcing genuinely asymmetric
    # geometry to become symmetric.
    mirror_pairs = (("bottom_left", "bottom_right"), ("top_left", "top_right"))
    mirror_tolerance = max(0.01, min(0.05, t * 0.01 if t > 0.0 else 0.01))
    x_geometry_is_symmetric = (
        _folded_profile_is_mirror_symmetric(box_body_x_profile, tolerance=1e-6)
        and _folded_profile_is_mirror_symmetric(endcap_x_profile, tolerance=1e-6)
    )
    component_lookup = {name: component for name, component in components}
    for left_name, right_name in mirror_pairs:
        left_cut = raw_cuts.get(left_name)
        right_cut = raw_cuts.get(right_name)
        if left_cut is None or right_cut is None:
            continue
        left_canonical = _canonical_corner_geometry(left_cut, blank_bounds, left_name)
        right_canonical = _canonical_corner_geometry(right_cut, blank_bounds, right_name)

        force_structural_mirror = False
        if x_geometry_is_symmetric:
            left_component = component_lookup.get(left_name)
            right_component = component_lookup.get(right_name)
            if left_component is not None and right_component is not None:
                left_component_canonical = _canonical_corner_geometry(
                    left_component, blank_bounds, left_name
                )
                right_component_canonical = _canonical_corner_geometry(
                    right_component, blank_bounds, right_name
                )
                force_structural_mirror = (
                    float(left_component_canonical.hausdorff_distance(
                        right_component_canonical
                    )) <= 1e-6
                )

        if (
            not force_structural_mirror
            and float(left_canonical.hausdorff_distance(right_canonical)) > mirror_tolerance
        ):
            continue
        # Symmetric physical geometry must have symmetric collision evidence.
        # Union is conservative: if triangulation misses one mirrored crossing,
        # retain the evidence seen on the opposite, physically identical side.
        common = unary_union([left_canonical, right_canonical])
        raw_cuts[left_name] = _physical_corner_geometry(common, blank_bounds, left_name)
        raw_cuts[right_name] = _physical_corner_geometry(common, blank_bounds, right_name)

    # Apply clearance A once, after the physical collision envelope has converged.
    a = max(0.0, float(clearance or 0.0))
    blank = box(minx, miny, maxx, maxy)
    corner_reliefs = []
    final_cuts = []
    structural_contact_snaps = set()
    topology_normalized_corners = set()
    component_by_name = {name: component for name, component in components}
    topology_snap_tolerance = max(0.01, t * 0.005 if t > 0.0 else 0.01)
    # Dynamic 3D solving owns the size, but the existing corner component owns
    # the legal manufacturing topology (single-stage vs two-stage).  This rule
    # also applies to flat-X OVERLAY parts: skipping normalization there lets
    # triangle-skin intersection noise invent a tiny second stage.
    for corner_name, raw_cut in raw_cuts.items():
        component = component_by_name.get(corner_name)
        if component is not None:
            raw_cut = _normalize_corner_cut_to_component_topology(
                raw_cut, component, corner_name, blank_bounds,
                snap_tolerance=topology_snap_tolerance,
            )
            topology_normalized_corners.add(corner_name)
            raw_cut, contact_snapped = _snap_single_stage_cut_to_structural_contact(
                raw_cut,
                corner_name,
                blank_bounds,
                box_body_x_profile=box_body_x_profile,
                endcap_x_profile=endcap_x_profile,
                sheet_thickness=t,
            )
            if contact_snapped:
                structural_contact_snaps.add(corner_name)
        final_cut = _expand_orthogonal_corner_cut_with_clearance(
            raw_cut, corner_name, blank_bounds, a
        ) if a > 0.0 else raw_cut
        if not final_cut.is_valid:
            final_cut = final_cut.buffer(0)
        measurement = _measure_canonical_corner_cut(
            final_cut, corner_name, blank_bounds, a
        )
        corner_reliefs.append(BackprojectedCornerRelief(
            corner_name=corner_name, cut_polygon_2d=final_cut, measurement=measurement
        ))
        final_cuts.append(final_cut)

    cut_polygon = unary_union(final_cuts) if final_cuts else None

    # Production replay uses the exact same corner-scoped helper as
    # Manufacturing API.  The probe may restore the whole blank, but only
    # corners with verified replacement cuts are restored into final material.
    solved_material = apply_verified_endcap_relief_material(
        endcap_render_data.material, final_cuts
    )
    if solved_material.is_empty:
        return AssemblyBackprojectedReliefSolution(
            cut_polygon, tuple(corner_reliefs), tuple(all_projections),
            endcap_render_data, False, residual_projection
        )
    solved_render = _render_data_rebuilt_from_material(endcap_render_data, solved_material)

    # Fresh verification after clearance: every remaining piece in each legacy
    # corner domain must be free of non-coplanar physical crossings.
    verify_segments = []
    verify_points = []
    verify_pairs = 0
    has_material_penetration = False
    # Final refold verification works on independently triangulated physical
    # skins. Coincident cut/mating edges can therefore land a few nanometres
    # inside retained material. Treat only this numerical boundary band as
    # contact; the iterative solver itself still uses the stricter default.
    verification_tolerance = 1e-5
    for _corner_name, component in components:
        probe = solved_render.material.intersection(component)
        projection = _project_probe_material(
            probe_material=probe,
            box_body_world_surface=body_world_surface,
            box_body_world_solid=body_world_solid,
            endcap_reference_local=full_reference_local,
            endcap_x_profile=endcap_x_profile,
            endcap_y_profile=endcap_y_profile,
            endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
            endcap_placement=endcap_placement,
            sheet_thickness=t,
        )
        penetrates = projection_has_material_penetration(
            projection, probe, tolerance=verification_tolerance
        )
        if penetrates and (
            _corner_name in structural_contact_snaps
            or _corner_name in topology_normalized_corners
        ):
            mid_projection = _project_probe_mid_surface(
                probe_material=probe,
                box_body_world_surface=body_world_surface,
                box_body_world_solid=body_world_solid,
                endcap_reference_local=full_reference_local,
                endcap_x_profile=endcap_x_profile,
                endcap_y_profile=endcap_y_profile,
                endcap_fold_guides=getattr(endcap_render_data, "fold_guides", ()),
                endcap_placement=endcap_placement,
                sheet_thickness=t,
            )
            mid_clear = not projection_has_material_penetration(
                mid_projection, probe, tolerance=verification_tolerance
            )
            if _corner_name in structural_contact_snaps and mid_clear:
                # Exact structural contact is legal.  Keep physical skins as the
                # primary evidence, but reject their T/2 contact-band crossing when
                # the semantic mid-surface confirms no retained-material penetration.
                penetrates = False
            elif (
                _corner_name in topology_normalized_corners
                and mid_clear
                and _projection_within_material_boundary_band(
                    projection, probe, tolerance=topology_snap_tolerance
                )
            ):
                # Topology normalization may replace a micron-scale triangle-skin
                # stair step with the approved single/two-stage manufacturing edge.
                # Forgive only a boundary-band crossing when the semantic mid-surface
                # is also clear; deeper retained-material penetration still fails.
                penetrates = False
        verify_segments.extend(projection.segments_2d)
        verify_points.extend(projection.points_2d)
        verify_pairs += projection.pair_count
        if penetrates:
            has_material_penetration = True
    final_residual = FlatInterferenceProjection(
        tuple(verify_segments), tuple(verify_points), verify_pairs
    )
    return AssemblyBackprojectedReliefSolution(
        cut_polygon_2d=cut_polygon,
        corner_reliefs=tuple(sorted(corner_reliefs, key=lambda item: item.corner_name)),
        projections=tuple(all_projections),
        solved_render_data=solved_render,
        verified=not has_material_penetration,
        residual_projection=final_residual,
    )
