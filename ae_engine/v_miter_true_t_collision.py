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
    VMiterReverseCreaseAsymmetricCutTrial,
    project_v_miter_reverse_crease_asymmetric_cut_trial,
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
        # A crease coinciding with a new CUTTING edge is not interior
        # stock.  At a genuinely drawn far OUTER endpoint, though, a
        # 1e-7mm GEOS boundary neighborhood necessarily intersects the
        # BEND by ~1e-7mm despite all its positive-length interior being
        # foldable. Allow at most numerical end-cap contact at BOTH
        # segment endpoints, not a positive-length boundary coincidence.
        # This bound is *only* numerical resolution, never a factory kerf,
        # gap, R/BA or physical bend-width allowance.
        near_cut_length = float(
            addition.intersection(remaining.boundary.buffer(_EPS)).length
        )
        if not math.isfinite(near_cut_length) or near_cut_length > 2 * _EPS + 1e-9:
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


@dataclass(frozen=True)
class VMiterReverseCreaseTrueTTrial:
    """Real 60° source flange COMPONENTS and zero-R formed T skin; CHECK only.

    This deliberately has NO formed mating seam, gap, bevel, calibrated
    inside R, BA or factory-accepted contact result: moving the second
    V cut leg invalidates the old ideal formed seam. Even zero detected
    crossings does NOT authorize a fifth type, a real bend or a DXF.
    """

    cut: VMiterReverseCreaseAsymmetricCutTrial
    first_reverse_source_end_axial_mm: float
    first_bend_source_component_count: int
    first_component_flat_areas_mm2: tuple[float, ...]
    first_component_real_bend_attachment_mm: tuple[float, ...]
    first_flange_flat_area_mm2: float
    second_flange_flat_area_mm2: float
    first_full_height_source_span_mm: float
    second_full_height_source_span_mm: float
    first_formed_skin_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    second_formed_skin_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    first_thick_solid_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    second_thick_solid_triangles: tuple[tuple[Vec3, Vec3, Vec3], ...]
    surface_interference_pair_count: int
    surface_intersection_segments: tuple
    geometry_model: str = "REAL_SOURCE_60_DEG_TWO_COMPONENT_SHARP_FOLD_TRUE_T_CHECK"
    manufacturing_status: str = "V_MITER_REVERSE_CREASE_TRUE_T_UNCERTIFIED"


def diagnose_v_miter_reverse_crease_true_t_trial(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    *,
    thickness_mm: float,
    first_flange_height_mm: float,
    second_flange_height_mm: float,
    second_fold_angle_deg: float,
    relief_mode: VMiterReliefMode | str,
    relief_t_factor: float | None,
    second_leg_outer_perimeter_retract_mm: float,
) -> VMiterReverseCreaseTrueTTrial:
    """Form BOTH actual disconnected first-flange pieces of a 60° V trial.

    The source-backed asymmetric relief can leave a SECOND triangular
    reverse-crease lip. Treating the clipped first flange as a single
    Polygon silently throws away that real positive-area stock. Convex
    hull or union repair would INVENT sheet over the V slot. Instead:
      * require original collinear real BENDs over the reverse reach,
      * take a physically drawn far reverse endpoint still inside stock,
      * clip the actual alternate CUTTING by finite first/second fold
        domains, never the old ideal mate's original V sector,
      * preserve EVERY positive-area connected source component and
        prove each is attached over a real length of that actual BEND,
      * independently bend/triangulate every source patch and thicken the
        EXACT collected 3D skins using the existing Engine owners.

    NO old seam gap/clearance claim: changing the V cut changes the
    actual mate and needs a newly measured R/BA and finite-T cut-face
    solution. This API cannot generate production CUTTING/BEND/MARKING.
    """
    from .v_miter_material_trial import _single_source_material

    params = dict(
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    candidate = project_v_miter_reverse_crease_asymmetric_cut_trial(
        scene, v_edge_bend, second_bend,
        second_leg_outer_perimeter_retract_mm=second_leg_outer_perimeter_retract_mm,
        **params,
    )
    if not (candidate.first_original_stock_covers_extension
            and candidate.first_real_bend_continuation_covers
            and candidate.first_remaining_interior_crease_length_mm > _EPS):
        raise GeometryError(
            "V-miter reverse true-T requires real continuous BEND and post-cut fold material"
        )
    bounded = diagnose_v_miter_bounded_bend_reach(
        scene, v_edge_bend, second_bend, **params,
    )
    q = candidate.original_relief.source_trial.ideal.source
    apex = q.bend_intersection
    e1 = _outward_bend_axis(v_edge_bend, apex)
    e2 = _outward_bend_axis(second_bend, apex)
    n1, n2 = _outside_normal(e1, e2), _outside_normal(e2, e1)
    remaining = Polygon(
        ((p.x, p.y) for p in candidate.candidate_remaining_outline)
    )
    if (remaining.geom_type != "Polygon" or not remaining.is_valid
            or remaining.interiors or remaining.area <= _EPS):
        raise GeometryError("V-miter reverse true-T has no valid source CUTTING")

    def axial(point) -> float:
        return _dot((point.x - apex.x, point.y - apex.y, 0.0), e1)

    # Proven original-first BEND + extra original BEND parts ONLY. The
    # second BEND line and virtual V/check/mark lines cannot bridge gaps.
    physical_lines = tuple(
        LineString(((b.p1.x, b.p1.y), (b.p2.x, b.p2.y)))
        for b in scene.primitives
        if isinstance(b, LinePrimitive) and b.layer == "BEND"
        and b is not second_bend
    )
    source_fold = unary_union(physical_lines)
    original_stock = _single_source_material(scene)
    potential_ends = sorted({
        axial(point)
        for item in scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
        and item is not v_edge_bend and item is not second_bend
        for point in (item.p1, item.p2)
        if math.isfinite(axial(point))
        and axial(point) < bounded.first_axial_seam_reach_mm + _EPS
    })
    negative_end = None
    for end in potential_ends:
        endpoint = (
            apex.x + e1[0] * end,
            apex.y + e1[1] * end,
        )
        demanded = LineString(((apex.x, apex.y), endpoint))
        # The physical line may have a relief hole at the apex. Source
        # BEND ownership remains continuous even if the metal is not.
        if (demanded.difference(source_fold).is_empty
                and original_stock.covers(demanded)
                and original_stock.contains(demanded.interpolate(.5, normalized=True))
                and demanded.intersection(remaining).difference(
                    remaining.boundary.buffer(_EPS)
                ).length > _EPS):
            negative_end = float(end)
            break
    if negative_end is None:
        raise GeometryError(
            "V-miter reverse true-T has no stock-backed real negative-axis BEND endpoint"
        )

    def flat(axial_mm, outward_mm, axis, outside):
        return (
            apex.x + axis[0] * axial_mm + outside[0] * outward_mm,
            apex.y + axis[1] * axial_mm + outside[1] * outward_mm,
        )

    # This physical first fold contains TWO independent material lobes
    # after the asymmetric V relief. Both must be kept, even when the
    # second is a small lip without the full declared flange height.
    domain = Polygon((
        flat(negative_end, 0, e1, n1),
        flat(bounded.first_bend_span_mm, 0, e1, n1),
        flat(bounded.first_bend_span_mm, q.first_flange_height_mm, e1, n1),
        flat(negative_end, q.first_flange_height_mm, e1, n1),
    ))
    clipped = remaining.intersection(domain)
    if clipped.is_empty or not math.isfinite(clipped.area):
        raise GeometryError("V-miter reverse true-T has no first-flange material")
    parts = (
        (clipped,) if clipped.geom_type == "Polygon" else
        tuple(g for g in getattr(clipped, "geoms", ()) if g.geom_type == "Polygon")
    )
    if (not parts or len(parts) > 16
            or any(not part.is_valid or part.interiors or part.area <= _EPS
                   for part in parts)
            or abs(sum(p.area for p in parts) - clipped.area) >
            max(1e-7, clipped.area * 1e-9)):
        raise GeometryError(
            "V-miter reverse true-T cannot account for every real first-flange component"
        )
    original_far = (
        apex.x + e1[0] * bounded.first_bend_span_mm,
        apex.y + e1[1] * bounded.first_bend_span_mm,
    )
    reverse_far = (
        apex.x + e1[0] * negative_end,
        apex.y + e1[1] * negative_end,
    )
    real_crease = LineString((original_far, reverse_far))
    attachments = tuple(float(
        part.boundary.intersection(real_crease).length
    ) for part in parts)
    if any(not math.isfinite(n) or n <= _EPS for n in attachments):
        raise GeometryError(
            "V-miter reverse true-T first material component is not attached to real BEND"
        )
    first_full_height = LineString((
        flat(negative_end, q.first_flange_height_mm, e1, n1),
        flat(bounded.first_bend_span_mm, q.first_flange_height_mm, e1, n1),
    ))
    available_first_height = sum(
        float(part.intersection(first_full_height).length) for part in parts
    )
    if available_first_height <= _EPS:
        raise GeometryError(
            "V-miter reverse true-T first flange missing requested full height"
        )
    second, second_full_height = _flange_footprint(
        remaining, apex, e2, n2,
        source_span=bounded.second_bend_span_mm,
        source_flange_height=q.second_flange_height_mm,
    )
    if sum(p.intersection(second).area for p in parts) > _EPS:
        raise GeometryError(
            "V-miter reverse true-T cannot assign the same original stock to two folds"
        )

    theta = math.radians(q.second_fold_angle_deg)
    b2 = _add(_scale(n2, math.cos(theta)), _scale(_UNIT_Z, math.sin(theta)))
    # Keep both disconnected source surfaces separately. The existing
    # Engine triangulator checks 2D area parity before each 3D fold.
    first_skin = tuple(
        tri for part in parts
        for tri in _formed_skin(part, apex, e1, n1, _UNIT_Z)
    )
    second_skin = _formed_skin(second, apex, e2, n2, b2)
    if (not first_skin or not second_skin
            or len(first_skin) > _MAX_TRIANGLES_PER_FLANGE):
        raise GeometryError("V-miter reverse true-T has invalid folded source triangles")
    solid1 = tuple(thicken_triangle_surface(first_skin, q.thickness_mm))
    solid2 = tuple(thicken_triangle_surface(second_skin, q.thickness_mm))
    if not solid1 or not solid2:
        raise GeometryError("V-miter reverse true-T created empty thick solid")
    crossing = detect_world_mesh_surface_interference(solid1, solid2)
    return VMiterReverseCreaseTrueTTrial(
        cut=candidate,
        first_reverse_source_end_axial_mm=negative_end,
        first_bend_source_component_count=len(parts),
        first_component_flat_areas_mm2=tuple(float(p.area) for p in parts),
        first_component_real_bend_attachment_mm=attachments,
        first_flange_flat_area_mm2=float(sum(p.area for p in parts)),
        second_flange_flat_area_mm2=float(second.area),
        first_full_height_source_span_mm=float(available_first_height),
        second_full_height_source_span_mm=float(second_full_height),
        first_formed_skin_triangles=first_skin,
        second_formed_skin_triangles=second_skin,
        first_thick_solid_triangles=solid1,
        second_thick_solid_triangles=solid2,
        surface_interference_pair_count=crossing.pair_count,
        surface_intersection_segments=crossing.intersection_segments,
    )
