# -*- coding: utf-8 -*-
"""#3317 true-thickness, source-material V-miter *collision shadow*.

Use the real, source-verified remaining V-miter relief polygon and the two
physical BEND rays to extract the two actual flange footprints. Rotate those
footprints to the same 3D coordinates as the existing ideal mating witness,
then call WHD's existing true-thickness solid and noncoplanar interference
engine. This detects real T-thick overlap that zero-thickness seam mathematics
cannot see.

IMPORTANT: This is only a local *sharp-bend* mesh shadow; the actual inside
bend R, neutral-axis compensation, cut-edge bevel, kerf and the complete
sheet/assembly are NOT solved. Even no detected surface crossings is NOT
certification to emit CUTTING or offer a fifth manufacturing CornerType.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Polygon
from shapely.ops import triangulate

from .assembly_geometry import detect_world_mesh_surface_interference
from .assembly_geometry_primitives import thicken_triangle_surface
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError
from .v_miter_bounded_contact import diagnose_v_miter_bounded_bend_reach
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_ideal_mating import (
    Vec3, _UNIT_Z, _add, _dot, _outside_normal,
    _outward_bend_axis, _scale,
)
from .v_miter_relief_trial import (
    VMiterReliefMatingTrial, project_v_miter_relief_mating_trial,
)

_EPS = 1e-7
_MAX_TRIANGLES_PER_FLANGE = 10000


@dataclass(frozen=True)
class VMiterTrueThicknessCollisionShadow:
    """Real T-thick sharp-fold mesh vs mesh, strictly diagnostic."""

    mating: VMiterReliefMatingTrial
    first_flange_flat_area_mm2: float
    second_flange_flat_area_mm2: float
    first_formed_skin_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    second_formed_skin_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    first_thick_solid_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    second_thick_solid_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    surface_interference_pair_count: int
    surface_intersection_segments: tuple
    # A zero result can still hide coplanar overlap or inner-R interference.
    geometry_model: str = "V_MITER_SOURCE_FINITE_T_SHARP_FOLD_MESH_SHADOW"
    manufacturing_status: str = "V_MITER_TRUE_T_COLLISION_UNCERTIFIED"

    @property
    def has_detected_surface_interference(self) -> bool:
        return self.surface_interference_pair_count > 0


def _flange_footprint(
    remaining: Polygon,
    origin,
    axis: Vec3,
    outside: Vec3,
    *,
    source_span: float,
    source_flange_height: float,
) -> Polygon:
    """Intersect *actual* remaining source stock with finite bend-side panel."""
    def flat(axial: float, outward: float) -> tuple[float, float]:
        return (
            origin.x + axis[0] * axial + outside[0] * outward,
            origin.y + axis[1] * axial + outside[1] * outward,
        )

    domain = Polygon((
        flat(0.0, 0.0),
        flat(source_span, 0.0),
        flat(source_span, source_flange_height),
        flat(0.0, source_flange_height),
    ))
    if not domain.is_valid or domain.area <= _EPS:
        raise GeometryError("V-miter true-T source flange domain is degenerate")
    actual = remaining.intersection(domain)
    if (actual.geom_type != "Polygon" or actual.is_empty
            or not actual.is_valid or actual.interiors or actual.area <= _EPS):
        raise GeometryError("V-miter true-T source material has no single valid flange region")
    return actual


def _source_triangulation(patch: Polygon) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Triangulate actual polygon; no silently dropped source material.

    Existing WHD's folded mesh also clips Delaunay triangles to material.
    Here additionally check exact 2D area balance, because a collision
    verdict on a *partially missing* flange would be falsely reassuring.
    """
    faces = []
    area = 0.0
    for proposal in triangulate(patch):
        inside = proposal.intersection(patch)
        if inside.is_empty:
            continue
        parts = (inside,) if inside.geom_type == "Polygon" else tuple(
            item for item in getattr(inside, "geoms", ())
            if item.geom_type == "Polygon"
        )
        for part in parts:
            if part.area <= _EPS:
                continue
            if part.interiors:
                raise GeometryError("V-miter true-T triangulation cannot drop inner material boundaries")
            for triangle in triangulate(part):
                if triangle.area <= _EPS or not part.covers(triangle):
                    continue
                pts = tuple((float(x), float(y)) for x, y in triangle.exterior.coords[:3])
                if len(pts) != 3:
                    raise GeometryError("V-miter true-T triangulation has invalid vertices")
                orientation = (
                    (pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1])
                    - (pts[1][1] - pts[0][1]) * (pts[2][0] - pts[0][0])
                )
                if orientation < 0:
                    pts = (pts[0], pts[2], pts[1])
                faces.append(pts)
                area += triangle.area
                if len(faces) > _MAX_TRIANGLES_PER_FLANGE:
                    raise GeometryError("V-miter true-T source mesh exceeds safe triangle budget")
    if not faces or abs(area - patch.area) > max(1e-5, patch.area * 1e-7):
        raise GeometryError("V-miter true-T flange triangulation does not cover source material")
    return tuple(faces)


def _formed_skin(
    patch: Polygon,
    origin,
    axis: Vec3,
    outside: Vec3,
    bent_outward: Vec3,
) -> tuple[tuple[Vec3, Vec3, Vec3], ...]:
    """Apply one and only one Engine sharp-fold isometry to source triangles."""
    result = []
    for triangle in _source_triangulation(patch):
        formed = []
        for x, y in triangle:
            delta = (x - origin.x, y - origin.y, 0.0)
            parallel = _dot(delta, axis)
            transverse = _dot(delta, outside)
            point = _add(
                (origin.x, origin.y, 0.0),
                _add(_scale(axis, parallel), _scale(bent_outward, transverse)),
            )
            if not all(math.isfinite(v) for v in point):
                raise GeometryError("V-miter true-T folded triangle is non-finite")
            formed.append(point)
        result.append(tuple(formed))
    return tuple(result)


def diagnose_v_miter_true_thickness_collision(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    *,
    thickness_mm: float,
    first_flange_height_mm: float,
    second_flange_height_mm: float,
    second_fold_angle_deg: float,
    relief_mode: VMiterReliefMode | str,
    relief_t_factor: float | None = None,
) -> VMiterTrueThicknessCollisionShadow:
    """Rebuild real cut material -> 2 flange skins -> finite-T solid collision.

    A mathematical seam beyond either physical BEND endpoint requires
    additional material/ownership evidence; this shadow cannot invent it.
    Neither a collision hit nor a zero-hit result authorizes manufacturing.
    """
    params = dict(
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    mating = project_v_miter_relief_mating_trial(
        scene, v_edge_bend, second_bend, **params,
    )
    bounded = diagnose_v_miter_bounded_bend_reach(
        scene, v_edge_bend, second_bend, **params,
    )
    if bounded.needs_independent_material_extension_evidence:
        raise GeometryError(
            "V-miter true-T shadow needs independent source material extension evidence"
        )

    q = mating.relief.source_trial.ideal.source
    apex = q.bend_intersection
    e1 = _outward_bend_axis(v_edge_bend, apex)
    e2 = _outward_bend_axis(second_bend, apex)
    n1, n2 = _outside_normal(e1, e2), _outside_normal(e2, e1)
    theta = math.radians(q.second_fold_angle_deg)
    b1 = _UNIT_Z
    b2 = _add(_scale(n2, math.cos(theta)), _scale(_UNIT_Z, math.sin(theta)))

    remaining = Polygon((
        (p.x, p.y) for p in mating.relief.trial_remaining_outline
    ))
    if remaining.is_empty or not remaining.is_valid or remaining.area <= _EPS:
        raise GeometryError("V-miter true-T source remaining material is invalid")
    first_patch = _flange_footprint(
        remaining, apex, e1, n1,
        source_span=bounded.first_bend_span_mm,
        source_flange_height=q.first_flange_height_mm,
    )
    second_patch = _flange_footprint(
        remaining, apex, e2, n2,
        source_span=bounded.second_bend_span_mm,
        source_flange_height=q.second_flange_height_mm,
    )
    if first_patch.intersection(second_patch).area > _EPS:
        raise GeometryError("V-miter true-T two flat flange patches overlap")

    skin1 = _formed_skin(first_patch, apex, e1, n1, b1)
    skin2 = _formed_skin(second_patch, apex, e2, n2, b2)
    solid1 = tuple(thicken_triangle_surface(skin1, q.thickness_mm))
    solid2 = tuple(thicken_triangle_surface(skin2, q.thickness_mm))
    if not solid1 or not solid2:
        raise GeometryError("V-miter true-T thickening produced empty solid")
    interference = detect_world_mesh_surface_interference(solid1, solid2)
    return VMiterTrueThicknessCollisionShadow(
        mating=mating,
        first_flange_flat_area_mm2=first_patch.area,
        second_flange_flat_area_mm2=second_patch.area,
        first_formed_skin_triangles=skin1,
        second_formed_skin_triangles=skin2,
        first_thick_solid_triangles=solid1,
        second_thick_solid_triangles=solid2,
        surface_interference_pair_count=interference.pair_count,
        surface_intersection_segments=interference.intersection_segments,
    )
