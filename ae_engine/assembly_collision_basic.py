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
from . import collision_backprojection as _collision_backprojection
from . import divider_relief_solver as _divider_relief_solver
from . import endcap_world_relief_solver as _endcap_world_relief_solver

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
    return _collision_backprojection.detect_planar_collision(
        box_body_material=box_body_material,
        endcap_material=endcap_material,
        collision_region_factory=CollisionRegion,
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
    return _collision_backprojection.project_collision_to_endcap_relief(
        collision,
        policy,
        endcap_role=AssemblyRole.ENDCAP,
        cut_action=OwnershipAction.CUT,
        relief_candidate_factory=ReliefCandidate,
        clearance=clearance,
        min_area=min_area,
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


def _vec2_points_from_ring(ring):
    from .sheetmetal_geometry import Vec2

    coords = list(ring.coords)
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    return tuple(Vec2(float(x), float(y)) for x, y in coords)


def _iter_line_geometries(geom):
    from shapely.geometry import LineString, MultiLineString, GeometryCollection

    if geom is None or getattr(geom, "is_empty", True):
        return
    if isinstance(geom, LineString):
        if float(geom.length) > 1e-6:
            yield geom
    elif isinstance(geom, (MultiLineString, GeometryCollection)):
        for part in geom.geoms:
            yield from _iter_line_geometries(part)


def _scene_with_replaced_primary_cutting(scene, material):
    from shapely.geometry import LineString, Polygon
    from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
    from .sheetmetal_geometry import Vec2

    exterior = _polygon_for_exterior(material)
    replacement = PolylinePrimitive(
        points=_vec2_points_from_polygon_exterior(exterior),
        layer="CUTTING",
        closed=True,
    )

    primitives = tuple(getattr(scene, "primitives", ()) or ())
    has_segmented_cutting = any(
        str(getattr(p, "layer", "")).upper() == "CUTTING"
        and (
            isinstance(p, LinePrimitive)
            or (isinstance(p, PolylinePrimitive) and not p.closed)
        )
        for p in primitives
    )
    closed_cutting_polys = []
    for index, primitive in enumerate(primitives):
        if (
            isinstance(primitive, PolylinePrimitive)
            and str(primitive.layer).upper() == "CUTTING"
            and primitive.closed
            and len(primitive.points) >= 3
        ):
            try:
                poly = Polygon([(p.x, p.y) for p in primitive.points])
                if not poly.is_valid:
                    poly = poly.buffer(0)
            except Exception:
                poly = None
            closed_cutting_polys.append((index, poly))

    primary_index = None
    if closed_cutting_polys:
        best_index, best_poly = max(
            closed_cutting_polys,
            key=lambda item: float(item[1].area) if item[1] is not None and not item[1].is_empty else -1.0,
        )
        if best_poly is not None and not best_poly.is_empty:
            if not has_segmented_cutting or float(best_poly.area) > float(exterior.area) * 0.5:
                primary_index = best_index

    existing_hole_polys = [
        poly
        for index, poly in closed_cutting_polys
        if index != primary_index and poly is not None and not poly.is_empty
    ]

    new_interior_Loops = []
    for ring in getattr(exterior, "interiors", ()):
        ring_pts = _vec2_points_from_ring(ring)
        if len(ring_pts) < 3:
            continue
        try:
            ring_poly = Polygon([(p.x, p.y) for p in ring_pts])
        except Exception:
            ring_poly = None
        already_present = False
        if ring_poly is not None and not ring_poly.is_empty:
            for existing in existing_hole_polys:
                if existing is not None and not existing.is_empty and ring_poly.symmetric_difference(existing).area <= 1e-4:
                    already_present = True
                    break
        if not already_present:
            new_interior_Loops.append(
                PolylinePrimitive(points=ring_pts, layer="CUTTING", closed=True)
            )

    out = DrawingScene()
    replaced = False
    for index, primitive in enumerate(primitives):
        is_primary_cutting = (
            index == primary_index
            if primary_index is not None
            else (
                str(getattr(primitive, "layer", "")).upper() == "CUTTING"
                and (
                    isinstance(primitive, LinePrimitive)
                    or (isinstance(primitive, PolylinePrimitive) and not primitive.closed)
                )
            )
        )
        if is_primary_cutting:
            if not replaced:
                out.add(replacement)
                for hole_loop in new_interior_Loops:
                    out.add(hole_loop)
                replaced = True
        elif isinstance(primitive, LinePrimitive) and str(primitive.layer).upper() == "BEND":
            raw_line = LineString([(float(primitive.p1.x), float(primitive.p1.y)), (float(primitive.p2.x), float(primitive.p2.y))])
            clipped = material.intersection(raw_line)
            for seg in _iter_line_geometries(clipped):
                coords = list(seg.coords)
                if len(coords) >= 2:
                    out.add(
                        LinePrimitive(
                            p1=Vec2(float(coords[0][0]), float(coords[0][1])),
                            p2=Vec2(float(coords[-1][0]), float(coords[-1][1])),
                            layer=primitive.layer,
                            color=primitive.color,
                        )
                    )
        else:
            out.add(primitive)
    if not replaced:
        out.add(replacement)
        for hole_loop in new_interior_Loops:
            out.add(hole_loop)
    return out


def apply_endcap_relief_candidate(endcap_render_data, candidate: ReliefCandidate | None):
    if candidate is None:
        return endcap_render_data

    material = endcap_render_data.material.difference(candidate.cut_polygon_2d)
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty:
        raise ValueError("EndCap relief removed all material")

    from .manufacturing_render_data import fold_guides_from_final_scene
    scene = _scene_with_replaced_primary_cutting(endcap_render_data.scene, material)
    recomputed_guides = fold_guides_from_final_scene(scene)
    fold_guides = recomputed_guides if recomputed_guides else tuple(getattr(endcap_render_data, "fold_guides", ()) or ())
    return replace(endcap_render_data, scene=scene, material=material, fold_guides=fold_guides)


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
