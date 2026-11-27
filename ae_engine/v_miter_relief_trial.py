# -*- coding: utf-8 -*-
"""#3317 V-miter tip relief shape experiments on canonical source material.

ROUND_R rounds the sharp removed V tip with a tangent circular arc.  A
RELIEF_HOLE unions a true circular drill-shaped relief centered at the V
intersection.  Both modify the *actual source-backed removed polygon* from
v_miter_material_trial, never a guessed stock rectangle.

Every dimension is an EXPLICIT positive multiple of source thickness T.
There is no certified default R/T or diameter/T; these read-only candidate
outlines do not prove developed bend allowance, finite-radius fold/solid
collision, kerf or factory acceptance and MUST NOT become CUTTING geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode, _finite
from .v_miter_material_trial import (
    VMiterMaterialOutlineTrial, _single_source_material,
    build_v_miter_trial_check_scene, project_v_miter_source_material_trial,
)

_AREA_TOL = 1e-6


@dataclass(frozen=True)
class VMiterReliefTrial:
    """A material-checked relief candidate, never a machine CUTTING result."""

    source_trial: VMiterMaterialOutlineTrial
    relief_mode: VMiterReliefMode
    relief_t_factor: float
    relief_dimension_mm: float  # R for ROUND_R; diameter for RELIEF_HOLE
    relief_radius_mm: float
    flat_leg_tip_cutback_mm: float  # tangent distance for R, circle radius for hole
    removed_material_area_mm2: float
    remaining_material_area_mm2: float
    trial_remaining_outline: tuple[Vec2, ...]
    cut_geometry_model: str = "IDEAL_SHARP_V_WITH_EXPLICIT_T_RELIEF_TRIAL"
    manufacturing_status: str = "V_MITER_RELIEF_CUTTING_UNCERTIFIED"


def _unit_vector_from(apex: Vec2, tip: Vec2) -> tuple[float, float, float]:
    dx, dy = tip.x - apex.x, tip.y - apex.y
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= _AREA_TOL:
        raise GeometryError("V-miter relief needs two positive V leg lengths")
    return dx / length, dy / length, length


def _rounded_v_notch_polygon(
    apex: Vec2, first: Vec2, second: Vec2,
    outer_arc: tuple[tuple[float, float], ...],
    radius: float,
) -> tuple[Polygon, float]:
    """One R-tangent notch formula shared by ideal and offset trial rays.

    The two rays may meet at a *virtual* apex after a one-sided V line
    offset. Their circular fillet retains exactly the supplied R; no
    separate approximate radius formula belongs in the R/BA solver.
    The caller must source-validate its perimeter arc and whole sheet.
    """
    if not math.isfinite(radius) or radius <= 0:
        raise GeometryError("V-miter rounded trial radius must be finite and positive")
    ux, uy, first_len = _unit_vector_from(apex, first)
    vx, vy, second_len = _unit_vector_from(apex, second)
    dot = max(-1.0, min(1.0, ux * vx + uy * vy))
    interior = math.acos(dot)
    if not 1e-5 < interior < math.pi - 1e-5:
        raise GeometryError("V-miter relief tip has invalid included angle")
    tangent_length = radius / math.tan(interior / 2.0)
    if (not math.isfinite(tangent_length) or
            tangent_length >= min(first_len, second_len) - _AREA_TOL):
        raise GeometryError("V-miter rounded tip exceeds a V cut leg")

    bisector_x, bisector_y = ux + vx, uy + vy
    bisector_length = math.hypot(bisector_x, bisector_y)
    if bisector_length <= _AREA_TOL:
        raise GeometryError("V-miter relief cannot resolve a circular bisector")
    center_distance = radius / math.sin(interior / 2)
    cx = apex.x + bisector_x / bisector_length * center_distance
    cy = apex.y + bisector_y / bisector_length * center_distance
    p_first = (apex.x + ux * tangent_length, apex.y + uy * tangent_length)
    p_second = (apex.x + vx * tangent_length, apex.y + vy * tangent_length)

    # The CHECK mesh is a polygonal approximation of the requested exact
    # circular radius; this is NOT a CNC G02/G03 machining instruction.
    start = math.atan2(p_second[1] - cy, p_second[0] - cx)
    stop = math.atan2(p_first[1] - cy, p_first[0] - cx)
    sweep = (stop - start + math.pi) % (2 * math.pi) - math.pi
    steps = max(32, math.ceil(abs(sweep) * radius / 0.25))
    if steps > 4096:
        raise GeometryError("V-miter round relief preview exceeds resolution limit")
    arc = [
        (cx + radius * math.cos(start + sweep * i / steps),
         cy + radius * math.sin(start + sweep * i / steps))
        for i in range(1, steps + 1)
    ]
    if len(outer_arc) < 2:
        raise GeometryError("V-miter tip relief needs a source outside arc")
    return Polygon((p_first, *outer_arc, p_second, *arc)), tangent_length


def _round_v_tip(
    source: VMiterMaterialOutlineTrial,
    radius: float,
) -> tuple[Polygon, float]:
    """Preserve the original source-backed, rounded sharp-notch semantics."""
    apex = source.ideal.source.bend_intersection
    first = source.ideal.first_flat_miter_ray[1]
    second = source.ideal.second_flat_miter_ray[1]
    outer_arc = tuple(
        (p.x, p.y) for p in source.removed_corner_outline[1:-1]
    )
    rounded, tangent_length = _rounded_v_notch_polygon(
        apex, first, second, outer_arc, radius,
    )
    sharp = Polygon((p.x, p.y) for p in source.removed_corner_outline)
    if rounded.difference(sharp).area > _AREA_TOL:
        raise GeometryError("V-miter rounded tip extends beyond original V wedge")
    return rounded, tangent_length



def project_v_miter_relief_trial(
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
) -> VMiterReliefTrial:
    """Apply explicit R/T or diameter/T to one validated CUTTING source.

    No numeric multiplier is assumed, and NONE of these choices certifies a
    new CornerType for CNC manufacture.  Categorical intent is checked using
    the SAME source qualifier as the trial, before touching any geometry.
    """
    source = project_v_miter_source_material_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    qualified = source.ideal.source
    if qualified.relief_t_factor is None:
        raise GeometryError("V-miter R/T or diameter/T requires an explicit trial factor")
    factor = qualified.relief_t_factor
    dimension = qualified.thickness_mm * factor
    if not math.isfinite(dimension) or dimension <= 0:
        raise GeometryError("V-miter trial relief dimension must be finite and positive")
    mode = qualified.relief_mode
    radius = dimension if mode is VMiterReliefMode.ROUND_R else dimension / 2
    material = _single_source_material(scene)
    sharp = Polygon((p.x, p.y) for p in source.removed_corner_outline)
    if mode is VMiterReliefMode.ROUND_R:
        removed, cutback = _round_v_tip(source, radius)
    elif mode is VMiterReliefMode.RELIEF_HOLE:
        apex = qualified.bend_intersection
        circle = Point(apex.x, apex.y).buffer(radius, resolution=48)
        if circle.difference(material).area > _AREA_TOL:
            raise GeometryError("V-miter relief hole exceeds source material boundary")
        removed = sharp.union(circle)
        cutback = radius
    else:
        raise GeometryError("V-miter unknown relief selection")

    if (removed.geom_type != "Polygon" or removed.is_empty or
            not removed.is_valid or removed.interiors or
            removed.area <= _AREA_TOL or
            removed.difference(material).area > _AREA_TOL):
        raise GeometryError("V-miter relief candidate is not a valid source material cut")
    remaining = material.difference(removed)
    if (remaining.geom_type != "Polygon" or remaining.is_empty or
            not remaining.is_valid or remaining.interiors or
            remaining.area <= _AREA_TOL):
        raise GeometryError("V-miter relief breaks the single sheet outline")
    if abs(material.area - removed.area - remaining.area) > max(
        1e-5, material.area * 1e-9,
    ):
        raise GeometryError("V-miter relief source material area does not balance")
    return VMiterReliefTrial(
        source_trial=source,
        relief_mode=mode,
        relief_t_factor=factor,
        relief_dimension_mm=dimension,
        relief_radius_mm=radius,
        flat_leg_tip_cutback_mm=cutback,
        removed_material_area_mm2=removed.area,
        remaining_material_area_mm2=remaining.area,
        trial_remaining_outline=tuple(
            Vec2(float(x), float(y)) for x, y in remaining.exterior.coords
        ),
    )


@dataclass(frozen=True)
class VMiterReverseCreaseAsymmetricCutTrial:
    """Real stock-removal alternative for a negative-axial 60° fold; CHECK ONLY.

    The outer-perimeter arc retract is an EXPLICIT candidate source input.
    It is NOT a shop allowance, not a resolved 3D seam and not permission
    to cut, bend or mark. The original ideal seam/cut-face mating becomes
    invalid after moving this V leg and MUST be re-solved independently.
    """

    original_relief: VMiterReliefTrial
    second_leg_outer_perimeter_retract_mm: float
    second_leg_relocated_tip: Vec2
    candidate_remaining_outline: tuple[Vec2, ...]
    candidate_removed_area_mm2: float
    candidate_remaining_area_mm2: float
    first_original_stock_covers_extension: bool
    first_real_bend_continuation_covers: bool
    first_remaining_interior_covers_extension: bool
    first_remaining_interior_crease_length_mm: float
    geometry_model: str = "V_MITER_60_DEG_SOURCE_OUTER_PERIMETER_ASYMMETRIC_LEG_CHECK"
    manufacturing_status: str = "V_MITER_REVERSE_CREASE_CUT_UNCERTIFIED"


def project_v_miter_reverse_crease_asymmetric_cut_trial(
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
) -> VMiterReverseCreaseAsymmetricCutTrial:
    """Move the SECOND V tip along REAL original exterior stock, not a GUI ray.

    For a 60° formed second fold the analytical second V leg can coincide
    with the physical first BEND continuation after cutting. Retraction of
    that OUTER tip toward the first V leg can retain a strip of genuine
    original stock under the full missing crease. This only constructs and
    checks one alternate physical CUTTING *hypothesis*, not a corrected
    formed seam, thickness-safe R/BA/bevel or certified factory relief.

    No inferred stock: both leg tips and the complete shortened outer arc
    come from the verified source CUTTING perimeter and the Engine's
    original ideal V geometry. The original R or drill diameter remains the
    operator's explicit T multiple. Any candidate causing invalid stock,
    crossing a source edge, or splitting the original sheet is rejected.
    """
    from .v_miter_bounded_contact import diagnose_v_miter_original_stock_crease_extension

    p = dict(thickness_mm=thickness_mm,
             first_flange_height_mm=first_flange_height_mm,
             second_flange_height_mm=second_flange_height_mm,
             second_fold_angle_deg=second_fold_angle_deg,
             relief_mode=relief_mode, relief_t_factor=relief_t_factor)
    original = project_v_miter_relief_trial(
        scene, v_edge_bend, second_bend, **p,
    )
    reach = diagnose_v_miter_original_stock_crease_extension(
        scene, v_edge_bend, second_bend, **p,
    )
    if not (0 < original.source_trial.ideal.source.second_fold_angle_deg < 90
            and reach.first_missing_bend_extension is not None
            and reach.bounded.first_axial_seam_reach_mm < -_AREA_TOL
            and reach.second_missing_bend_extension is None):
        raise GeometryError(
            "V-miter asymmetric reverse crease cut requires a negative first BEND 60-degree-type reach"
        )
    amount = _finite(
        second_leg_outer_perimeter_retract_mm,
        "second_leg_outer_perimeter_retract_mm", positive=True,
    )
    stock = _single_source_material(scene)
    sharp = original.source_trial
    apex = sharp.ideal.source.bend_intersection
    first_tip = sharp.ideal.first_flat_miter_ray[1]
    outer = tuple((p.x, p.y) for p in sharp.removed_corner_outline[1:-1])
    perimeter_arc = LineString(outer)
    if (not perimeter_arc.is_simple or not math.isfinite(perimeter_arc.length)
            or amount >= perimeter_arc.length - _AREA_TOL):
        raise GeometryError("V-miter asymmetric leg retract exceeds original source exterior arc")
    shortened = substring(perimeter_arc, 0.0, perimeter_arc.length - amount)
    coords = tuple((float(x), float(y)) for x, y in shortened.coords)
    if len(coords) < 2:
        raise GeometryError("V-miter asymmetric leg has no physical exterior arc")
    tip = Vec2(*coords[-1])
    if Point(*coords[-1]).distance(stock.boundary) > _AREA_TOL:
        raise GeometryError("V-miter asymmetric second tip is not on original CUTTING")

    if original.relief_mode is VMiterReliefMode.ROUND_R:
        removed, _ = _rounded_v_notch_polygon(
            apex, first_tip, tip, coords, original.relief_radius_mm,
        )
    else:
        hole = Point(apex.x, apex.y).buffer(
            original.relief_radius_mm, resolution=48,
        )
        removed = Polygon(((apex.x, apex.y), *coords)).union(hole)
    if (removed.is_empty or removed.geom_type != "Polygon"
            or not removed.is_valid or removed.interiors
            or removed.area <= _AREA_TOL
            or removed.difference(stock).area > _AREA_TOL):
        raise GeometryError("V-miter asymmetric leg has no valid source-stock removal")
    remaining = stock.difference(removed)
    if (remaining.is_empty or remaining.geom_type != "Polygon"
            or not remaining.is_valid or remaining.interiors
            or remaining.area <= _AREA_TOL
            or abs(stock.area - removed.area - remaining.area) >
            max(1e-5, stock.area * 1e-9)):
        raise GeometryError("V-miter asymmetric leg breaks one-piece source stock")

    a, b = reach.first_missing_bend_extension
    missing = LineString(((a.x, a.y), (b.x, b.y)))
    extras = tuple(
        LineString(((item.p1.x, item.p1.y), (item.p2.x, item.p2.y)))
        for item in scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
        and item is not v_edge_bend and item is not second_bend
    )
    # Exact collinear source ownership; crossing, offset or interrupted
    # BENDs cannot collectively create a virtual missing fold interval.
    true_bend = bool(
        extras and missing.difference(unary_union(extras)).is_empty
    )
    near_boundary = remaining.boundary.buffer(_AREA_TOL * .1)
    interior = float(
        missing.intersection(remaining).difference(near_boundary).length
    )
    # Do not confuse an intentional tip-hole cutback with true material
    # covering the full crease. Report the partial material separately.
    full_interior = bool(
        remaining.covers(missing)
        and remaining.contains(missing.interpolate(0.5, normalized=True))
        and missing.intersection(near_boundary).length == 0
    )
    return VMiterReverseCreaseAsymmetricCutTrial(
        original_relief=original,
        second_leg_outer_perimeter_retract_mm=amount,
        second_leg_relocated_tip=tip,
        candidate_remaining_outline=tuple(
            Vec2(float(x), float(y)) for x, y in remaining.exterior.coords
        ),
        candidate_removed_area_mm2=float(removed.area),
        candidate_remaining_area_mm2=float(remaining.area),
        first_original_stock_covers_extension=bool(
            reach.first_original_stock_covers_extension
        ),
        first_real_bend_continuation_covers=true_bend,
        first_remaining_interior_covers_extension=full_interior,
        first_remaining_interior_crease_length_mm=interior,
    )


def build_v_miter_reverse_crease_asymmetric_check_scene(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    **kwargs,
) -> DrawingScene:
    """CHECK-only, never CNC CUTTING/BEND/MARKING for a changed 60° V ray."""
    trial = project_v_miter_reverse_crease_asymmetric_cut_trial(
        scene, v_edge_bend, second_bend, **kwargs,
    )
    source = _single_source_material(scene)
    out = DrawingScene()
    out.add(PolylinePrimitive(
        points=tuple(Vec2(float(x), float(y)) for x, y in source.exterior.coords),
        layer="DATUM", closed=True, color=6,
        semantic_id="v_miter_reverse_original_stock_only",
    ))
    out.add(PolylinePrimitive(
        points=trial.candidate_remaining_outline,
        layer="CHECK", closed=True, color=2,
        semantic_id="v_miter_reverse_asymmetric_cut_uncertified_only",
    ))
    for bend in (v_edge_bend, second_bend):
        out.add(LinePrimitive(p1=bend.p1, p2=bend.p2,
                              layer="DATUM", color=6))
    return out


def build_v_miter_relief_trial_check_scene(
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
) -> DrawingScene:
    """One CHECK-only 2D/DXF view; no CUTTING, BEND or MARKING entities."""
    parameters = dict(
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    preview = build_v_miter_trial_check_scene(
        scene, v_edge_bend, second_bend, **parameters,
    )
    relief = project_v_miter_relief_trial(
        scene, v_edge_bend, second_bend, **parameters,
    )
    result = DrawingScene(list(preview.primitives))
    if (len(result.primitives) != 4 or
            not isinstance(result.primitives[1], PolylinePrimitive) or
            result.primitives[1].layer != "CHECK"):
        raise GeometryError("V-miter CHECK source preview topology is unexpected")
    result.primitives[1] = PolylinePrimitive(
        points=relief.trial_remaining_outline,
        layer="CHECK", closed=True, color=2,
        semantic_id="v_miter_explicit_relief_trial_uncertified",
    )
    return result



@dataclass(frozen=True)
class VMiterReliefMatingTrial:
    """2D rounded/hole tip and its *ideal* formed shared-contact subsegment.

    Since an ideal sharp fold is an isometry, the V-leg cutback measured on
    each flat ray maps to exactly that distance along the shared 3D seam.
    The first cutback length is OPEN RELIEF, not a bonded contact or a
    tolerance-corrected real sheet-metal solid.
    """

    relief: VMiterReliefTrial
    first_flat_contact_start: Vec2
    second_flat_contact_start: Vec2
    formed_contact_start: tuple[float, float, float]
    formed_contact_end: tuple[float, float, float]
    formed_open_relief_length_mm: float
    formed_contact_length_mm: float
    geometry_model: str = "IDEAL_SHARP_FOLD_RELIEF_AWARE_2D_3D_PARITY"
    manufacturing_status: str = "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED"


def project_v_miter_relief_mating_trial(
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
) -> VMiterReliefMatingTrial:
    """Reconcile actual source-backed 2D tip relief with one 3D ideal seam.

    No duplicate corner R, hole, angle or flange compensation formula: all
    tip dimensions come from project_v_miter_relief_trial, and all formed
    geometry comes from the existing ideal shared-plane intersection.
    """
    relief = project_v_miter_relief_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    ideal = relief.source_trial.ideal
    origin = ideal.source.bend_intersection
    full_length = ideal.formed_contact_length_mm
    cutback = relief.flat_leg_tip_cutback_mm
    if not (math.isfinite(full_length) and math.isfinite(cutback)
            and 0 < cutback < full_length - _AREA_TOL):
        raise GeometryError("V-miter relief leaves no usable formed shared edge")

    first_tip = ideal.first_flat_miter_ray[1]
    second_tip = ideal.second_flat_miter_ray[1]
    # The old ideal 3D and flat 2D sources MUST be isometric. Fail closed if
    # they ever drift or were assembled from unrelated sources.
    for tip in (first_tip, second_tip):
        flat_length = math.hypot(tip.x - origin.x, tip.y - origin.y)
        if abs(flat_length - full_length) > max(
            _AREA_TOL, full_length * 1e-8
        ):
            raise GeometryError("V-miter unfolded rays disagree with formed seam length")

    fraction = cutback / full_length

    def flat_start(tip: Vec2) -> Vec2:
        return Vec2(
            origin.x + (tip.x - origin.x) * fraction,
            origin.y + (tip.y - origin.y) * fraction,
        )

    start_3d = tuple(
        ideal.formed_seam_start[i] + (
            ideal.formed_seam_end[i] - ideal.formed_seam_start[i]
        ) * fraction
        for i in range(3)
    )
    return VMiterReliefMatingTrial(
        relief=relief,
        first_flat_contact_start=flat_start(first_tip),
        second_flat_contact_start=flat_start(second_tip),
        formed_contact_start=start_3d,
        formed_contact_end=ideal.formed_seam_end,
        formed_open_relief_length_mm=cutback,
        formed_contact_length_mm=full_length - cutback,
    )
