# -*- coding: utf-8 -*-
"""#3317 true T-mesh CHECK from ONE verified Factory post-V material source.

A C01/C04 FinalScene has clipped its BEND before the proposed fifth V
corner.  A zero-radius solid mesh must use the independently rebuilt,
post-V Factory Fold (§#3379), NOT assume clipped old BEND extends into the
replaced corner. Rebuild and validate exact source identity before allowing
a 3D shadow. Even zero surface crossings is not a factory mating proof:
actual inside R/BA, kerf, hole/fillet, bevel, springback and contact gap
remain unknown. This module never emits manufacturing CUTTING/BEND/MARKING.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Polygon

from .assembly_geometry import detect_world_mesh_surface_interference
from .assembly_geometry_primitives import thicken_triangle_surface
from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError
from .v_miter_factory_fold_check import (
    VMiterFactoryPrecutFoldCheck,
    project_v_miter_factory_precut_fold_check,
)
from .v_miter_factory_mother_check import VMiterFactoryMotherReplacementCheck
from .v_miter_ideal_mating import (
    VMiterIdealMatingCandidate, _UNIT_Z, _add, _dot, _outward_bend_axis,
    _outside_normal, _scale, project_ideal_v_miter_mating_candidate,
)
from .v_miter_material_trial import VMiterSourceBoundSharpCheck
from .v_miter_source_cut_face_trial import (
    VMiterSourceCutFaceTrial, trace_v_miter_source_true_t_cut_faces,
)
from .v_miter_true_t_collision import _formed_skin, _source_triangulation

_EPS = 1e-7
_MAX_COMPONENTS = 16


@dataclass(frozen=True)
class VMiterFactoryPostVTrueTCheck:
    """Zero-R actual-T mesh shadow: exact Factory Fold + remaining V stock."""

    thickness_mm: float
    first_source_flange_area_mm2: float
    second_source_flange_area_mm2: float
    first_source_component_count: int
    second_source_component_count: int
    first_source_fold_min_axial_mm: float
    second_source_fold_min_axial_mm: float
    first_source_fold_max_axial_mm: float
    second_source_fold_max_axial_mm: float
    first_formed_skin_triangles: tuple
    second_formed_skin_triangles: tuple
    first_formed_perimeter_edges: tuple
    second_formed_perimeter_edges: tuple
    first_thick_solid_triangles: tuple
    second_thick_solid_triangles: tuple
    surface_interference_pair_count: int
    surface_intersection_segments: tuple
    first_source_tagged_cut_faces: VMiterSourceCutFaceTrial | None = None
    second_source_tagged_cut_faces: VMiterSourceCutFaceTrial | None = None
    first_cut_face_failure: str | None = None
    second_cut_face_failure: str | None = None
    geometry_model: str = "FACTORY_POST_V_SHARP_FOLD_TRUE_T_MESH_CHECK"
    manufacturing_status: str = "V_MITER_FACTORY_POST_V_TRUE_T_UNCERTIFIED"


def _source_flange_parts(
    remaining: Polygon,
    apex,
    axis,
    outward,
    source_fold: tuple[LinePrimitive, ...],
    height: float,
    tip_axial: float,
    name: str,
):
    """Clip full Factory-proven pre-corner crease to real post-V stock.

    No clipping to an invented 60-degree reverse endpoint. Every existing
    connected material component is triangulated; missing or detached source
    components fail closed rather than projecting a fake 3D flange.
    """
    axial = lambda point: (
        (point.x - apex.x) * axis[0] +
        (point.y - apex.y) * axis[1]
    )
    xs = tuple(
        axial(point)
        for segment in source_fold for point in (segment.p1, segment.p2)
    )
    if not xs or not all(math.isfinite(x) for x in xs):
        raise GeometryError(f"V_MITER_FACTORY_T_{name}_FOLD_SPAN_INVALID")
    low, high = min(xs), max(xs)
    if (high - low <= _EPS or high <= _EPS or
            tip_axial < low - _EPS or tip_axial > high + _EPS):
        raise GeometryError(
            f"V_MITER_FACTORY_T_{name}_MISSING_REAL_V_FOLD_REACH"
        )

    def flat(longitudinal, transverse):
        return (
            apex.x + axis[0] * longitudinal + outward[0] * transverse,
            apex.y + axis[1] * longitudinal + outward[1] * transverse,
        )

    domain = Polygon((
        flat(low, 0), flat(high, 0),
        flat(high, height), flat(low, height),
    ))
    if not domain.is_valid or domain.area <= _EPS:
        raise GeometryError(f"V_MITER_FACTORY_T_{name}_DOMAIN_INVALID")
    actual = remaining.intersection(domain)
    parts = (
        (actual,) if actual.geom_type == "Polygon" else
        tuple(p for p in getattr(actual, "geoms", ())
              if p.geom_type == "Polygon" and p.area > _EPS)
    )
    if (
        not parts or len(parts) > _MAX_COMPONENTS
        or any(p.is_empty or not p.is_valid or p.interiors
               or p.area <= _EPS for p in parts)
        or abs(sum(p.area for p in parts) - actual.area) >
            max(1e-6, actual.area * 1e-9)
    ):
        raise GeometryError(f"V_MITER_FACTORY_T_{name}_SOURCE_PARTS_INCOMPLETE")
    real_fold = tuple(
        LineString(((s.p1.x, s.p1.y), (s.p2.x, s.p2.y)))
        for s in source_fold
    )
    # A clipped 2D part must attach to a positive-length *Factory sourced*
    # Fold, not merely touch a guessed construction line at a point.
    for part in parts:
        if max(
            (part.boundary.intersection(line).length for line in real_fold),
            default=0.0,
        ) <= _EPS:
            raise GeometryError(
                f"V_MITER_FACTORY_T_{name}_FLANGE_NOT_ATTACHED_TO_SOURCE_FOLD"
            )
    return parts, low, high


def _formed_perimeter_edges(triangles):
    """Only physical formed skin boundary edges, for a read-only 3D canvas."""
    counts = {}
    oriented = {}
    for tri in triangles:
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            key = tuple(sorted((
                tuple(round(float(c), 7) for c in a),
                tuple(round(float(c), 7) for c in b),
            )))
            counts[key] = counts.get(key, 0) + 1
            oriented[key] = (a, b)
    edges = tuple(oriented[k] for k, n in counts.items() if n == 1)
    if not edges or len(edges) > 10000 or any(
        len(a) != 3 or len(b) != 3 or
        not all(math.isfinite(x) for x in (*a, *b))
        for a, b in edges
    ):
        raise GeometryError("V_MITER_FACTORY_T_FORMED_SKIN_BOUNDARY_INVALID")
    return edges


def project_v_miter_factory_post_v_true_t_check(
    part_spec: DoorPartSpec | EndCapPartSpec,
    render_data: PartRenderData,
    corner_key: str,
    ideal: VMiterIdealMatingCandidate,
    source_check: VMiterSourceBoundSharpCheck,
    factory_fold: VMiterFactoryPrecutFoldCheck,
    first_real_bend: LinePrimitive,
    second_real_bend: LinePrimitive,
    first_station_bend: LinePrimitive,
    second_station_bend: LinePrimitive,
    factory_mother: VMiterFactoryMotherReplacementCheck | None = None,
) -> VMiterFactoryPostVTrueTCheck:
    """Make an Engine finite-T formed source mesh, then diagnose crossings.

    This is physically traceable ZERO-R sharp-bend CHECK geometry, not a
    measured R/BA model or certified interference-free manufactured sheet.
    The restored Factory mother and proposed Fold are strictly reverified.
    """
    if (not isinstance(ideal, VMiterIdealMatingCandidate)
            or not isinstance(factory_fold, VMiterFactoryPrecutFoldCheck)
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or not isinstance(render_data, PartRenderData)):
        raise GeometryError("V_MITER_FACTORY_T_SOURCE_TYPES_INVALID")
    t = part_spec.thickness
    if (type(t) not in (float, int) or not math.isfinite(t)
            or t <= 0 or abs(t - ideal.source.thickness_mm) > _EPS):
        raise GeometryError("V_MITER_FACTORY_T_ACTUAL_THICKNESS_MISMATCH")

    # Independent exact-source requalification, not trusting a forged
    # dataclass carrying plausible-looking candidate Fold linework.
    expected_fold = project_v_miter_factory_precut_fold_check(
        part_spec, render_data, corner_key, source_check,
        first_real_bend, second_real_bend, factory_mother,
    )
    if expected_fold != factory_fold:
        raise GeometryError("V_MITER_FACTORY_T_FOLD_PROVENANCE_MISMATCH")
    expected_ideal = project_ideal_v_miter_mating_candidate(
        DrawingScene([first_station_bend, second_station_bend]),
        first_station_bend, second_station_bend,
        thickness_mm=t,
        first_flange_height_mm=ideal.source.first_flange_height_mm,
        second_flange_height_mm=ideal.source.second_flange_height_mm,
        second_fold_angle_deg=ideal.source.second_fold_angle_deg,
        relief_mode=ideal.source.relief_mode,
        relief_t_factor=ideal.source.relief_t_factor,
    )
    if expected_ideal != ideal:
        raise GeometryError("V_MITER_FACTORY_T_IDEAL_SOURCE_MISMATCH")
    apex = ideal.source.bend_intersection
    e1 = _outward_bend_axis(first_station_bend, apex)
    e2 = _outward_bend_axis(second_station_bend, apex)
    for name, station, actual in (
        ("FIRST", first_station_bend, first_real_bend),
        ("SECOND", second_station_bend, second_real_bend),
    ):
        a = LineString(((station.p1.x, station.p1.y),
                        (station.p2.x, station.p2.y)))
        b = LineString(((actual.p1.x, actual.p1.y),
                        (actual.p2.x, actual.p2.y)))
        if b.distance(a) > _EPS or b.intersection(a).length <= _EPS:
            raise GeometryError(f"V_MITER_FACTORY_T_{name}_STATION_NOT_REAL_FOLD")

    remaining = Polygon(
        ((p.x, p.y) for p in source_check.remaining_outline)
    )
    removed = Polygon(
        ((p.x, p.y) for p in source_check.removed_corner_outline)
    )
    restored = remaining.union(removed)
    if (any(p.geom_type != "Polygon" or p.is_empty or
            not p.is_valid or p.interiors or p.area <= _EPS
            for p in (remaining, removed)) or
            restored.geom_type != "Polygon" or not restored.is_valid or
            abs(restored.area - source_check.source_material_area_mm2) > 1e-6 or
            remaining.intersection(removed).area > 1e-6):
        raise GeometryError("V_MITER_FACTORY_T_SOURCE_STOCK_INVALID")

    n1, n2 = _outside_normal(e1, e2), _outside_normal(e2, e1)
    def axial(flat_tip, axis):
        return ((flat_tip.x - apex.x) * axis[0]
                + (flat_tip.y - apex.y) * axis[1])

    first_parts, low1, hi1 = _source_flange_parts(
        remaining, apex, e1, n1, factory_fold.first_proposed_segments,
        ideal.source.first_flange_height_mm,
        axial(ideal.first_flat_miter_ray[1], e1),
        "FIRST",
    )
    second_parts, low2, hi2 = _source_flange_parts(
        remaining, apex, e2, n2, factory_fold.second_proposed_segments,
        ideal.source.second_flange_height_mm,
        axial(ideal.second_flat_miter_ray[1], e2),
        "SECOND",
    )
    if sum(
        p.intersection(q).area for p in first_parts for q in second_parts
    ) > _EPS:
        raise GeometryError("V_MITER_FACTORY_T_OVERLAPPING_FLANGE_SOURCE")

    theta = math.radians(ideal.source.second_fold_angle_deg)
    bent_second = _add(_scale(n2, math.cos(theta)),
                       _scale(_UNIT_Z, math.sin(theta)))
    flat1 = tuple(tri for p in first_parts for tri in _source_triangulation(p))
    flat2 = tuple(tri for p in second_parts for tri in _source_triangulation(p))
    skin1 = tuple(tri for p in first_parts for tri in
                  _formed_skin(p, apex, e1, n1, _UNIT_Z))
    skin2 = tuple(tri for p in second_parts for tri in
                  _formed_skin(p, apex, e2, n2, bent_second))
    if not skin1 or not skin2 or len(flat1) != len(skin1) or len(flat2) != len(skin2):
        raise GeometryError("V_MITER_FACTORY_T_2D_3D_TRIANGLE_PAIR_MISMATCH")
    solid1 = tuple(thicken_triangle_surface(skin1, t))
    solid2 = tuple(thicken_triangle_surface(skin2, t))
    if not solid1 or not solid2:
        raise GeometryError("V_MITER_FACTORY_T_MISSING_PHYSICAL_SOLID")
    collisions = detect_world_mesh_surface_interference(solid1, solid2)

    def cut_faces(flat, formed, solid):
        try:
            return (
                trace_v_miter_source_true_t_cut_faces(
                    restored, remaining, flat, formed, solid,
                    thickness_mm=t,
                ), None
            )
        except GeometryError as exc:
            # Missing cut-face lineage is not a zero gap or an approved
            # bevel. Surface interference still remains useful CHECK data.
            return None, str(exc)

    first_faces, first_failure = cut_faces(flat1, skin1, solid1)
    second_faces, second_failure = cut_faces(flat2, skin2, solid2)

    return VMiterFactoryPostVTrueTCheck(
        thickness_mm=t,
        first_source_flange_area_mm2=sum(p.area for p in first_parts),
        second_source_flange_area_mm2=sum(p.area for p in second_parts),
        first_source_component_count=len(first_parts),
        second_source_component_count=len(second_parts),
        first_source_fold_min_axial_mm=low1,
        second_source_fold_min_axial_mm=low2,
        first_source_fold_max_axial_mm=hi1,
        second_source_fold_max_axial_mm=hi2,
        first_formed_skin_triangles=skin1,
        second_formed_skin_triangles=skin2,
        first_formed_perimeter_edges=_formed_perimeter_edges(skin1),
        second_formed_perimeter_edges=_formed_perimeter_edges(skin2),
        first_thick_solid_triangles=solid1,
        second_thick_solid_triangles=solid2,
        surface_interference_pair_count=collisions.pair_count,
        surface_intersection_segments=collisions.intersection_segments,
        first_source_tagged_cut_faces=first_faces,
        second_source_tagged_cut_faces=second_faces,
        first_cut_face_failure=first_failure,
        second_cut_face_failure=second_failure,
    )
