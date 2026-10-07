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
