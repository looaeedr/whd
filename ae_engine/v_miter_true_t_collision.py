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

from shapely.geometry import LineString, Polygon
from shapely.ops import triangulate, unary_union

from .assembly_geometry import detect_world_mesh_surface_interference
from .assembly_geometry_primitives import thicken_triangle_surface
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError
from .v_miter_bounded_contact import (
    diagnose_v_miter_bounded_bend_reach,
    diagnose_v_miter_physical_crease_after_relief,
)
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
    first_full_height_source_span_mm: float
    second_full_height_source_span_mm: float
    first_mesh_source_bend_span_mm: float
    second_mesh_source_bend_span_mm: float
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
) -> tuple[Polygon, float]:
    """Clip actual source stock and verify it reaches the declared flange height."""
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
    if actual.geom_type == "GeometryCollection":
        # A correctly retargeted ROUND_R notch can meet a BEND domain only
        # along a ZERO-AREA line beyond its one physical material polygon.
        # Shapely then returns Polygon + LineString; rejecting the entire
        # source loses a real, connected flange. Extract only the unique
        # positive-area polygon, with exact area parity. Never discard
        # separate positive-area islands or use buffer/convex-hull repair.
        material_parts = tuple(
            part for part in actual.geoms
            if part.geom_type == "Polygon" and part.area > _EPS
        )
        if (len(material_parts) == 1 and
                abs(material_parts[0].area - actual.area) <=
                max(1e-7, actual.area * 1e-9)):
            actual = material_parts[0]
    if (actual.geom_type != "Polygon" or actual.is_empty
            or not actual.is_valid or actual.interiors or actual.area <= _EPS):
        raise GeometryError("V-miter true-T source material has no single valid flange region")
    # The requested height is a source material requirement, not a domain
    # to which missing stock may be silently added. Check at least a real
    # nonzero physical span reaches that height along the original BEND.
    # This deliberately does NOT assert full-height material exists across
    # the entire flange: local reliefs/trims can shorten some portions.
    full_height_boundary = LineString((
        flat(0.0, source_flange_height),
        flat(source_span, source_flange_height),
    ))
    available_span = float(actual.intersection(full_height_boundary).length)
    if not math.isfinite(available_span) or available_span <= _EPS:
        raise GeometryError(
            "V-miter true-T source flange missing requested full height"
        )
    return actual, available_span


def _verified_contiguous_positive_mesh_span(
    scene: DrawingScene,
    bend: LinePrimitive,
    other_bend: LinePrimitive,
    origin,
    axis: Vec3,
    remaining: Polygon,
    *,
    original_span: float,
    required_reach: float,
) -> float:
    """Use only a complete, continuous ORIGINAL BEND + surviving stock span.

    The mathematical seam is not necessarily the outer edge where the
    requested full flange height occurs. A mesh cropped merely at the
    seam would delete genuine outboard flange material and can fail the
    original _flange_footprint full-height evidence. Select the farthest
    *actually drawn* collinear BEND endpoint that is connected all the
    way to the original BEND, and whose full added interval survives the
    same original source's V/R/hole cut. Never invent an extension limit.
    """
    if required_reach <= original_span + _EPS:
        return original_span
    def axial(point) -> float:
        return _dot((point.x - origin.x, point.y - origin.y, 0.0), axis)

    physical_bends = (
        item for item in scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
        and item is not other_bend
    )
    lines = tuple(
        LineString(((item.p1.x, item.p1.y), (item.p2.x, item.p2.y)))
        for item in physical_bends
    )
    source_lines = unary_union(lines)
    endpoints = sorted({
        axial(point)
        for item in scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
        and item is not bend and item is not other_bend
        for point in (item.p1, item.p2)
        if math.isfinite(axial(point)) and axial(point) > required_reach + _EPS
    }, reverse=True)
    for end in endpoints:
        far_point = (origin.x + axis[0] * end,
                     origin.y + axis[1] * end)
        whole_crease = LineString(((origin.x, origin.y), far_point))
        if not whole_crease.difference(source_lines).is_empty:
            continue
        addition = LineString((
            (origin.x + axis[0] * original_span,
             origin.y + axis[1] * original_span),
            far_point,
        ))
        if not remaining.covers(addition):
            continue
        if not remaining.contains(addition.interpolate(0.5, normalized=True)):
            continue
        # A crease coinciding with a newly cut edge is not interior stock.
        # 1e-7mm is the pre-existing numerical GEOS boundary tolerance,
        # NOT a manufacturing allowance.
        if addition.intersection(remaining.boundary.buffer(_EPS)).length > 0:
            continue
        return end
    raise GeometryError(
        "V-miter true-T shadow needs independent source material extension evidence"
    )


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


def _verified_v_miter_source_bend_mesh_spans(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    bounded,
    remaining: Polygon,
    params: dict,
) -> tuple[float, float]:
    """One true physical source owner shared by sharp-T and measured R/BA.

    The original BEND lengths are unchanged unless the ideal seam needs a
    POSITIVE axial extension and the actual original CUTTING, a continuous
    additional BEND, and post-relief material *all* prove it. Only actual
    drawn far endpoints can bound the mesh, never projected mathematical
    seam positions. Negative axial overreach (60°) is a distinct fold
    topology and remains unsupported. This cannot certify manufacturing.
    """
    first_span = bounded.first_bend_span_mm
    second_span = bounded.second_bend_span_mm
    if not bounded.needs_independent_material_extension_evidence:
        return first_span, second_span
    reaches = (
        bounded.first_axial_seam_reach_mm,
        bounded.second_axial_seam_reach_mm,
    )
    if any(axial < -_EPS for axial in reaches):
        raise GeometryError(
            "V-miter source fold needs independent source material extension evidence"
        )
    physical = diagnose_v_miter_physical_crease_after_relief(
        scene, v_edge_bend, second_bend, **params,
    )
    stock = physical.original_stock
    proofs = (
        (stock.first_original_stock_covers_extension,
         physical.first_original_bend_continuation_covers,
         physical.first_remaining_material_interior_covers),
        (stock.second_original_stock_covers_extension,
         physical.second_original_bend_continuation_covers,
         physical.second_remaining_material_interior_covers),
    )
    apex = bounded.ideal.source.bend_intersection
    axis1 = _outward_bend_axis(v_edge_bend, apex)
    axis2 = _outward_bend_axis(second_bend, apex)
    spans = []
    for bend, other, axis, original, needed, evidence in (
        (v_edge_bend, second_bend, axis1, first_span, reaches[0], proofs[0]),
        (second_bend, v_edge_bend, axis2, second_span, reaches[1], proofs[1]),
    ):
        if needed <= original + _EPS:
            spans.append(original)
            continue
        if not all(value is True for value in evidence):
            raise GeometryError(
                "V-miter source fold needs independent source material extension evidence"
            )
        spans.append(_verified_contiguous_positive_mesh_span(
            scene, bend, other, apex, axis, remaining,
            original_span=original, required_reach=needed,
        ))
    return tuple(spans)


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
    first_mesh_span, second_mesh_span = _verified_v_miter_source_bend_mesh_spans(
        scene, v_edge_bend, second_bend, bounded, remaining, params,
    )
    first_patch, first_full_height_span = _flange_footprint(
        remaining, apex, e1, n1,
        source_span=first_mesh_span,
        source_flange_height=q.first_flange_height_mm,
    )
    second_patch, second_full_height_span = _flange_footprint(
        remaining, apex, e2, n2,
        source_span=second_mesh_span,
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
        first_full_height_source_span_mm=first_full_height_span,
        second_full_height_source_span_mm=second_full_height_span,
        first_mesh_source_bend_span_mm=first_mesh_span,
        second_mesh_source_bend_span_mm=second_mesh_span,
        first_formed_skin_triangles=skin1,
        second_formed_skin_triangles=skin2,
        first_thick_solid_triangles=solid1,
        second_thick_solid_triangles=solid2,
        surface_interference_pair_count=interference.pair_count,
        surface_intersection_segments=interference.intersection_segments,
    )
