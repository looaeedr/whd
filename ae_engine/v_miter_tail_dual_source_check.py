# -*- coding: utf-8 -*-
"""#3317: one source Tail blank, two side-opening V's, same-source folded 3D.

Model CHECK only. All geometry originates from one EndCap PartSpec/FinalScene
and the existing Factory's original (pre-corner) sheet and BEND stations.
No Door trim, no CNC export, no factory tolerance, no X publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
import math

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .assembly_geometry import (
    detect_world_mesh_surface_interference,
    detect_world_mesh_enclosed_volume_witness,
)
from .assembly_geometry_primitives import thicken_triangle_surface
from .contracts import EndCapPartSpec, PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .manufacturing_render_data import (
    PartRenderData, fold_guides_from_final_scene,
)
from .assembly_geometry_folded_mesh import (
    folded_mesh_from_polygon, _profile_map_with_guides,
)
from .final_scene_fold_source import fold_ownership_exemptions, scene_fold_boundaries
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive,
)
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_factory_mother_check import (
    _factory_original_shape, _selected_original_corner_component,
)
from .v_miter_material_trial import _single_source_material
from .v_miter_true_t_collision import _source_triangulation
from .v_miter_operator_gui_check import (
    _physical_corner_bends, _endcap_existing_fold_angle_sources,
    _profile_angle_at_bend,
)
from .v_miter_ideal_mating import (
    _outward_bend_axis, _outside_normal,
)
from .v_miter_radius_ba_interface_trial import (
    _formed_curved_skin, _measured_cylindrical_half_t_offsets,
)
from .v_miter_trial_defaults import project_v_miter_trial_parameter_defaults
from .v_miter_source_cut_face_trial import trace_v_miter_source_true_t_cut_faces
from .v_miter_cut_face_continuity_trial import (
    project_v_miter_true_cut_face_continuity_trial,
)
from .v_miter_seam_gap_trial import (
    project_v_miter_true_t_seam_section_gap_trial,
)
from .v_miter_tail_sequential_fold_check import (
    project_tail_same_sheet_sequential_fold_check,
    project_tail_same_sheet_staged_source_point,
)
from .v_miter_tail_alternative_mating_check import (
    project_tail_existing_bottom_broad_face_candidate,
)
from .v_miter_tail_user_image_source import (
    TailIllustratedSideV90Flat,
    project_tail_illustrated_side_v90_flat,
)


_TOL = 1e-6


def _inverse_straight_90_fold_contact(
    point_xy: tuple[float, float], z_mm: float, *,
    apex: Vec2, axis: tuple, outside: tuple,
    bend_allowance_mm: float, mid_radius_mm: float,
) -> Vec2:
    """Backproject a real straight 90-degree R/BA skin station to flat UV.

    Inverts the exact straight branch of _formed_curved_skin, never the
    zero-R ideal or a whole-width fabricated BEND. Only CHECK geometry;
    the curved root and T-thick cut-face contact remain independent tests.
    """
    if not (mid_radius_mm <= z_mm + _TOL
            and bend_allowance_mm > 0 and mid_radius_mm > 0):
        raise GeometryError("V_MITER_TAIL_INVERSE_NOT_ON_STRAIGHT_RBA_SKIN")
    axial = (
        (point_xy[0] - apex.x - mid_radius_mm * outside[0]) * axis[0]
        + (point_xy[1] - apex.y - mid_radius_mm * outside[1]) * axis[1]
    )
    flat_u = bend_allowance_mm + z_mm - mid_radius_mm
    if not all(math.isfinite(v) for v in (axial, flat_u)):
        raise GeometryError("V_MITER_TAIL_INVERSE_NONFINITE")
    return Vec2(
        apex.x + axis[0] * axial + outside[0] * flat_u,
        apex.y + axis[1] * axial + outside[1] * flat_u,
    )


def _apex_ray_side_exit_least_squares(
    apex: Vec2, projected: tuple[Vec2, ...], side_x: float,
) -> tuple[float, float]:
    """Infer an unconstrained straight V ray, pinned at the actual BEND apex.

    Returns the fitted intersection y at the ORIGINAL outside side edge and
    the maximum flat residual (mm). Neither result grants CUTTING status.
    A negative or wrong-side exit is an explicit incompatibility witness,
    not a reason to silently move the original apex or outer perimeter.
    """
    dx = tuple(p.x - apex.x for p in projected)
    denominator = sum(v * v for v in dx)
    if denominator <= _TOL * _TOL:
        raise GeometryError("V_MITER_TAIL_INVERSE_RAY_NOT_DETERMINED")
    slope = sum(x * (p.y - apex.y) for x, p in zip(dx, projected)) / denominator
    side_hit_y = apex.y + slope * (side_x - apex.x)
    max_residual = max(
        abs((p.y - apex.y) - slope * x) / math.sqrt(1.0 + slope * slope)
        for x, p in zip(dx, projected)
    )
    return float(side_hit_y), float(max_residual)


def _root_intersection_topology(segments, numerical_tol_mm: float):
    """Classify geometric *location*, not triangle-pair count as penetration.

    Coincident tessellation faces often yield several primitive pairs from
    ONE physical root edge. A line-only witness is not volumetric overlap.
    Conversely, non-collinearity is unresolved, not certified penetration.
    """
    points = tuple(
        tuple(float(x) for x in p)
        for segment in segments for p in segment
    )
    if not points:
        return "NO_ROOT_SURFACE_INTERSECTION"
    if any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in points):
        raise GeometryError("V_MITER_TAIL_NONFINITE_ROOT_INTERSECTION")
    a,b=max(((v,w) for i,v in enumerate(points) for w in points[i+1:]),
            key=lambda pair: math.dist(*pair))
    span=math.dist(a,b)
    if span <= numerical_tol_mm:
        return "ROOT_POINT_CONTACT_CANDIDATE_NOT_PENETRATION"
    direction=tuple((b[i]-a[i])/span for i in range(3))
    max_off_axis=0.0
    for p in points:
        delta=tuple(p[i]-a[i] for i in range(3))
        projection=sum(delta[i]*direction[i] for i in range(3))
        off=math.sqrt(max(0.0,sum(delta[i]**2 for i in range(3))-projection**2))
        max_off_axis=max(max_off_axis,off)
    if max_off_axis <= max(numerical_tol_mm*20.0, 1e-7):
        return "COLLINEAR_SHARED_ROOT_EDGE_CANDIDATE_NOT_PENETRATION"
    return "ROOT_SURFACE_INTERSECTION_NOT_YET_CLASSIFIED_AS_PENETRATION"


@dataclass(frozen=True)
class TailDualVFaceResult:
    corner: str
    first_bend_axis: str
    second_bend_axis: str
    side_folded_solid: tuple
    bottom_folded_solid: tuple
    side_cut_faces: tuple
    bottom_cut_faces: tuple
    model_interference_pairs: int
    model_interference_segments: tuple
    root_intersection_topology: str
    model_volume_status: str
    # Two actual stages from ONE source-meshed sheet, not renamed static
    # flange meshes. Each track: source UV, after first, after second.
    sequential_source_cut_edge_tracks: tuple
    sequential_first_side_cut_faces: tuple
    sequential_first_bottom_cut_faces: tuple
    sequential_second_side_cut_faces: tuple
    sequential_second_bottom_cut_faces: tuple
    sequential_final_seam_sections: tuple
    sequential_final_full_seam_continuity: object | None
    alternative_existing_stock_contact_trial: object
    # Actual one-source inverse rechecked against present/removed CUTTING:
    # (z, side_uv, side_retained, side_formed_xyz, side_residual_mm,
    #     bottom_uv, bottom_retained, bottom_formed_xyz, bottom_residual_mm).
    sequential_inverse_actual_source_trace_mm: tuple
    sequential_root_process_status: str
    # Physical Y-direction separation floor under the actual *disjoint*
    # finite-R/BA straight patches. Not an industrial tolerance or a
    # proof that every alternative single-blank fold sequence is impossible.
    straight_section_y_domain_witness_mm: tuple
    side_cut_failure: str | None
    bottom_cut_failure: str | None
    seam_continuity: object | None
    seam_failure: str | None
    actual_formed_reach_mm: float
    distal_ideal_shortfall_mm: float
    # Direct true 3D cut-face stations, not whole-solid nearest distance.
    sampled_seam_gap_stations_mm: tuple = ()
    # Formed true-T cut-face witnesses, not nearest whole-flange skins:
    # (fraction, gap, side cut XYZ, bottom cut XYZ, status).
    sampled_cut_face_nearest_xyz: tuple = ()
    # Source CUTTING proof for the two actually mating candidate faces:
    # side uses upper V leg, bottom uses lower V leg.
    source_cut_leg_owner_lengths_mm: tuple = ()
    # Actual finite-R/BA 90-degree contact inverses: z, side UV, bottom UV,
    # each distance from its current SOURCE V leg and unrepresented side BEND.
    inverse_straight_contact_flat_trace_mm: tuple = ()
    # Unconstrained straight-ray side-edge intersections, not accepted cuts:
    # (side_ray_y, side_ray_max_residual, bottom_ray_y, bottom_ray_max_residual).
    inverse_unconstrained_outer_hits_mm: tuple = ()
    inverse_source_fit_status: str = "NOT_EVALUATED"
    # z, side_in_original_mother, side_in_own_folded_patch,
    # bottom_in_original_mother, bottom_in_own_folded_patch.
    # This is a HYPOTHETICAL R/BA plane-intersection inverse, not
    # proof that true finite-T cut walls already mate there.
    inverse_flat_source_coverage_mm: tuple = ()
    # Hypothetical same-neutral-seam R/BA arc inverse (not a sequential
    # whole-blank cut). A non-apex intersection means its two source
    # legs cannot be used as one simple V opening without further work.
    inverse_root_arc_source_traces_xy: tuple = ()
    inverse_root_nonapex_crossings_xy: tuple = ()
    inverse_root_candidate_status: str = "NOT_EVALUATED"
    interference_z_range_mm: tuple | None = None
    actual_joint_axis_xyz: tuple = ()
    native_uncut_fold_endpoint_jump_max_mm: float | None = None
    native_uncut_fold_endpoint_status: str = "UNCHECKED"
    native_side_tip_endpoint_jump_max_mm: float | None = None
    native_side_tip_endpoint_status: str = "UNCHECKED"
    # A physical impossibility is a model FAIL, not an invitation to trim
    # an arbitrary Door edge or call geometric diagnostics "passed".
    topology_contact_failure: str | None = None
    topological_clearance_lower_bound_mm: float | None = None
    contact_gap_floor_at_straight_start_mm: float | None = None
    contact_gap_floor_at_straight_end_mm: float | None = None
    # For ANY asymmetric 90-degree included V whose two legs still exit
    # this very same side, the best possible distant contact has a
    # strictly positive lower bound without changing the original BEND.
    asymmetry_best_case_far_gap_floor_mm: float | None = None
    # An incomplete or touching 3D result is NOT declared physically fitting.
    model_status: str = "MODEL_NOT_VERIFIED"


@dataclass(frozen=True)
class TailDualVSourceCheck:
    original_factory_scene: DrawingScene
    operator_first_bend_axes: tuple
    flat_check_scene: DrawingScene
    original_outline: tuple[Vec2, ...]
    corrected_outline: tuple[Vec2, ...]
    left_apex: Vec2
    right_apex: Vec2
    left_outer_v_hits: tuple[Vec2, Vec2]
    right_outer_v_hits: tuple[Vec2, Vec2]
    side_flange_left_mm: float
    side_flange_right_mm: float
    bottom_flange_mm: float
    original_other_primitives: tuple
    side_left_solid: tuple
    side_right_solid: tuple
    bottom_solid: tuple
    remaining_flat_solid: tuple
    native_original_fold_path_mesh: tuple
    bottom_bend_span_x_mm: tuple
    side_bend_span_y_mm: tuple
    retained_out_of_span_corner_area_mm2: tuple
    out_of_bottom_span_corner_contours_xy: tuple
    restored_stock_ownership_mm2: tuple
    # Displacement of two arbitrarily close points on the SAME uncut
    # material either side of finite bottom BEND endpoint in native 3D.
    native_bottom_span_boundary_jump_samples_mm: tuple
    native_side_span_boundary_jump_samples_mm: tuple
    corners: tuple[TailDualVFaceResult, TailDualVFaceResult]
    sequential_same_sheet_stage_models: tuple
    geometry_status: str = "TAIL_DOUBLE_V_CHECK_ONLY_UNVERIFIED"


def project_tail_dual_v_same_source_check(
    spec: EndCapPartSpec, render: PartRenderData, *,
    first_bend_axes: Mapping[str, str] | None = None,
    illustrated_v90_source: TailIllustratedSideV90Flat | None = None,
) -> TailDualVSourceCheck:
    """Construct a two-90-degree V CHECK with both openings on side edges.

    The 90-degree included angle and each 15mm side span produce two
    symmetric +/-45-degree rays for this nominated test candidate only.
    Actual R/BA/T contact may require a DIFFERENT, source-proven cut, and
    that candidate remains NOT VERIFIED until folded faces truly pass.
    """
    if (not isinstance(spec, EndCapPartSpec) or not spec.is_tail
            or not isinstance(render, PartRenderData)
            or not isinstance(render.scene, DrawingScene)):
        raise GeometryError("V_MITER_TAIL_DUAL_TYPED_FACTORY_SOURCE_REQUIRED")
    # Same contract as the existing GUI live-corner CHECK. The two
    # physical 90-degree BENDs do NOT imply a preferred fold order.
    # Pass the operator's saved X/Y choice for EACH corner, not an
    # inferred default or the order of a Python dictionary.
    if (not isinstance(first_bend_axes, Mapping)
            or set(first_bend_axes) != {"bottom_left","bottom_right"}
            or any(type(v) is not str or v not in ("x","y")
                   for v in first_bend_axes.values())):
        raise GeometryError("V_MITER_TAIL_OPERATOR_FIRST_PHYSICAL_BEND_REQUIRED")
    # The previous unconfirmed candidate is still rejected by default.
    # The user has NOW supplied a corrected illustrated, symmetrical 90°
    # side V for this exact Vault example. Only the source-checked,
    # exactly matching physical image candidate can reopen this 3D trial.
    # Flat confirmation is NOT a folded-contact certification.
    if illustrated_v90_source is None:
        raise GeometryError(
            "V_MITER_TAIL_OLD_SYMMETRIC_45_DEG_NOT_USER_CONFIRMED_"
            "EXPLICIT_ILLUSTRATED_2D_SOURCE_REQUIRED"
        )
    if (not isinstance(illustrated_v90_source,TailIllustratedSideV90Flat)
            or illustrated_v90_source.source_spec!=spec
            or illustrated_v90_source.original_scene!=render.scene
            or illustrated_v90_source.manufacturing_approved):
        raise GeometryError("V_MITER_TAIL_ILLUSTRATED_2D_SOURCE_MISMATCH")
    authenticated=project_tail_illustrated_side_v90_flat(spec,render)
    if (illustrated_v90_source.result_material.symmetric_difference(
            authenticated.result_material
        ).area > _TOL):
        raise GeometryError("V_MITER_TAIL_ILLUSTRATION_NOT_MATCHING_CUTTING")
    from .v_miter_operator_gui_check import _endcap_existing_fold_angle_sources
    original = _single_source_material(render.scene)
    factory, width, height, original_bends = _factory_original_shape(spec)
    if factory.symmetric_difference(original).area > _TOL:
        raise GeometryError("V_MITER_TAIL_DUAL_FACTORY_ORIGINAL_DIFFERS")
    minx, miny, maxx, maxy = map(float, original.bounds)
    old_corner = {
        key: _selected_original_corner_component(
            original, box(0, 0, width, height), key,
        ) for key in ("bottom_left", "bottom_right")
    }
    restored = original.union(unary_union(tuple(old_corner.values())))
    if (restored.geom_type != "Polygon" or not restored.is_valid
            or restored.interiors or restored.is_empty):
        raise GeometryError("V_MITER_TAIL_DUAL_ORIGINAL_MOTHER_NOT_ONE_PIECE")

    x_profile, y_profile = _endcap_existing_fold_angle_sources(spec, "tail")
    corner_data = {}
    for name in ("bottom_left", "bottom_right"):
        x_bend, y_bend, x_height, y_height, _, _, real_x, real_y = (
            _physical_corner_bends(render.scene, original, name)
        )
        apex = x_bend.p1
        if math.hypot(apex.x - y_bend.p1.x, apex.y - y_bend.p1.y) > _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_REAL_BENDS_NOT_COINCIDENT")
        if (abs(abs(_profile_angle_at_bend(x_profile, apex.x, minx)) - 90) > 1e-8
                or abs(abs(_profile_angle_at_bend(y_profile, apex.y, miny)) - 90) > 1e-8):
            raise GeometryError("V_MITER_TAIL_DUAL_ONLY_BOTH_90_DEG_SUPPORTED")
        side_x = minx if name.endswith("left") else maxx
        dx = abs(apex.x - side_x)
        if dx <= _TOL or y_height <= dx + _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_SIDE_OPENING_NO_VALID_STOCK")
        # For this 90/90 candidate two +/-45-degree rays on the SAME
        # original outer side; not the old different-edge zero-R rays.
        low = Vec2(side_x, apex.y - dx)
        high = Vec2(side_x, apex.y + dx)
        for point in (low, high):
            if (Point(point.x, point.y).distance(restored.boundary) > _TOL
                    or not restored.covers(Point(point.x, point.y))):
                raise GeometryError("V_MITER_TAIL_DUAL_OPENING_NOT_ON_ACTUAL_SIDE")
        wedge = Polygon(((apex.x, apex.y), (low.x, low.y), (high.x, high.y)))
        if (wedge.geom_type != "Polygon" or not wedge.is_valid
                or wedge.area <= _TOL
                or wedge.difference(restored).area > _TOL):
            raise GeometryError("V_MITER_TAIL_DUAL_INVALID_SOURCE_V_WEDGE")
        a = (low.x - apex.x, low.y - apex.y)
        b = (high.x - apex.x, high.y - apex.y)
        if abs(a[0] * b[0] + a[1] * b[1]) > _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_V_NOT_90_DEG")
        corner_data[name] = (
            apex, low, high, wedge, float(x_height), float(y_height),
            x_bend, y_bend, real_x, real_y,
        )
    if abs(corner_data["bottom_left"][0].y -
           corner_data["bottom_right"][0].y) > _TOL:
        raise GeometryError("V_MITER_TAIL_DUAL_BOTTOM_BEND_MISALIGNED")
    if not corner_data["bottom_left"][3].disjoint(corner_data["bottom_right"][3]):
        raise GeometryError("V_MITER_TAIL_DUAL_VS_CROSS_EACH_OTHER")

    corrected = restored.difference(unary_union((
        corner_data["bottom_left"][3], corner_data["bottom_right"][3],
    )))
    if corrected.symmetric_difference(
        illustrated_v90_source.result_material
    ).area > _TOL:
        raise GeometryError("V_MITER_TAIL_MAPPED_V_NOT_USER_ILLUSTRATION")
    if (corrected.geom_type != "Polygon" or corrected.is_empty
            or not corrected.is_valid or corrected.interiors
            or corrected.difference(restored).area > _TOL
            or abs(restored.area - corrected.area -
                   sum(row[3].area for row in corner_data.values())) > _TOL):
        raise GeometryError("V_MITER_TAIL_DUAL_SOURCE_NOT_ONE_VALID_SHEET")
    # The only permissible changes are the two exact original corner
    # rectangles; all hole and upper-chain geometry retain source identity.
    left, right = corner_data["bottom_left"], corner_data["bottom_right"]
    # The exact modified footprint is the verified original Factory
    # two cut components UNION the two newly Engine-derived V wedges.
    # Original corner reliefs may cross the nominal BEND station by
    # their source-defined clearance, e.g. 0.5mm: a guessed box must not
    # incorrectly flag that real component as an unrelated contour.
    allowed = unary_union((
        old_corner["bottom_left"], old_corner["bottom_right"],
        left[3], right[3],
    ))
    if original.symmetric_difference(corrected).difference(
        allowed.buffer(_TOL)
    ).area > _TOL:
        raise GeometryError("V_MITER_TAIL_DUAL_UNRELATED_FACTORY_SHAPE_CHANGED")

    original_outer = [
        primitive for primitive in render.scene.primitives
        if (isinstance(primitive, PolylinePrimitive)
            and primitive.layer == "CUTTING" and primitive.closed
            and abs(Polygon([(p.x, p.y) for p in primitive.points])
                    .symmetric_difference(original).area) <= _TOL)
    ]
    if len(original_outer) != 1:
        raise GeometryError("V_MITER_TAIL_DUAL_OUTER_CUTTING_IDENTITY_AMBIGUOUS")
    all_original_other = tuple(
        primitive for primitive in render.scene.primitives
        if primitive is not original_outer[0]
    )
    flat_scene = DrawingScene([
        PolylinePrimitive(
            tuple(Vec2(float(x), float(y)) for x, y in corrected.exterior.coords),
            "CHECK", closed=True, semantic_id="tail_both_v_same_source_check_only",
        ),
        *all_original_other,
    ])
    # The original WHD 3D owner uses *finite* FinalScene BEND guides:
    # a physical Y bend at (16..406, 48) does not fold the V-restored
    # stock at x<16 or x>406. Likewise X folds only act within their
    # own physical Y spans, not across blank corner stock.
    # Never replace a finite BEND with a bbox-wide guessed hinge.
    xl, xr, bottom_y = left[0].x, right[0].x, left[0].y
    guides = fold_guides_from_final_scene(render.scene)
    if tuple(render.fold_guides or ()) and tuple(render.fold_guides) != guides:
        raise GeometryError("V_MITER_TAIL_DUAL_RENDER_BEND_GUIDES_DIFFER")
    def one_guide(axis, station):
        matches = tuple(
            g for g in guides
            if g.axis == axis and abs(g.position - station) <= _TOL
        )
        if len(matches) != 1:
            raise GeometryError("V_MITER_TAIL_DUAL_BEND_SPAN_NOT_UNIQUE")
        return matches[0]
    left_guide = one_guide("x", xl)
    right_guide = one_guide("x", xr)
    bottom_guide = one_guide("y", bottom_y)
    bottom_start, bottom_end = bottom_guide.span_start, bottom_guide.span_end
    if not (minx < bottom_start < xl + 2.0
            and xr - 2.0 < bottom_end < maxx
            and bottom_start < bottom_end):
        raise GeometryError("V_MITER_TAIL_DUAL_BEND_SPAN_OUTSIDE_REAL_SOURCE")
    if (abs(bottom_start - min(left[9].p1.x, left[9].p2.x)) > _TOL
            or abs(bottom_end - max(left[9].p1.x, left[9].p2.x)) > _TOL
            or abs(bottom_start - min(right[9].p1.x, right[9].p2.x)) > _TOL
            or abs(bottom_end - max(right[9].p1.x, right[9].p2.x)) > _TOL):
        raise GeometryError("V_MITER_TAIL_DUAL_SOURCE_BEND_ENDPOINTS_CHANGED")
    # The source V removes its opening to the LEFT/RIGHT outer edge.
    # Its *upper* leg leaves a real material tongue between Y=48 and the
    # side BEND's first drawn point Y=49. On each side check that a 2D
    # cross-tip witness is genuinely retained stock, not a guessed BEND.
    # If the tongue were cut away, no continuation may be introduced.
    side_tips = ()
    for corner_key, guide, sx in (
        ("bottom_left", left_guide, xl),
        ("bottom_right", right_guide, xr),
    ):
        if not (bottom_y < guide.span_start < guide.span_end):
            raise GeometryError("V_MITER_TAIL_SIDE_BEND_TIP_SOURCE_INVALID")
        tongue_span = float(guide.span_start - bottom_y)
        if tongue_span <= _TOL:
            raise GeometryError("V_MITER_TAIL_SIDE_TIP_HAS_NO_SOURCE_EXTENSION")
        test_y = float((bottom_y + guide.span_start) / 2.0)
        test_x = float(sx + (tongue_span / 4.0 if corner_key.endswith("right")
                              else -tongue_span / 4.0))
        if not all(corrected.covers(Point(x, y)) for x, y in (
            (test_x, test_y), (test_x, guide.span_start - 1e-4),
            (test_x, guide.span_start + 1e-4),
        )):
            raise GeometryError("V_MITER_TAIL_SIDE_TIP_NOT_SOURCE_CONNECTED")
        side_tips += (("x", float(sx), float(bottom_y),
                       float(guide.span_end)),)
    # Continue ONLY connected corner stock. Never extend physical BEND
    # segments or carry the side return through the lower Y<48 flange.
    # The X tips extend *one* lower end only; their upper end remains exact.
    tip_continuity = (("y", float(bottom_y), minx, maxx), *side_tips)
    folded_domains = {
        "left": corrected.intersection(box(
            minx, bottom_y, xl, left_guide.span_end,
        )),
        "right": corrected.intersection(box(
            xr, bottom_y, maxx, right_guide.span_end,
        )),
        # Full connected stock including both wedge-side bottom cut legs.
        # Only x=16..406 has a full 90-degree fold; the two continuous
        # attached tips are warped by the source-anchored fold transition.
        "bottom": corrected.intersection(box(
            minx, miny, maxx, bottom_y,
        )),
    }
    # Preserve the user's source geometry in the existing WHD sharp 3D
    # owner. This provides one directly comparable whole-blank 3D, which
    # applies the same span-specific guide masks as standard WHD preview.
    xb, yb = scene_fold_boundaries(render.scene, corrected)
    native_fold_mesh = folded_mesh_from_polygon(
        corrected, x_profile, y_profile,
        fold_guides=guides,
        fold_exemptions=fold_ownership_exemptions(corrected, xb, yb),
        fold_tip_continuity=tip_continuity,
    )
    if not native_fold_mesh:
        raise GeometryError("V_MITER_TAIL_DUAL_NATIVE_FOLD_MESH_EMPTY")

    # The triangles are only a display tessellation. Independently
    # verify whether their finite-guide mapping is continuous across
    # material that has NOT been cut at the end of the bottom BEND.
    # A jump is a geometric tear in the preview, NOT a V-cut-face gap.
    sampling_delta = 1e-4
    scan_heights = (0.10, 0.25, 0.50, 0.75, 0.90)
    boundary_jumps = []
    for which, station in (("bottom_left", bottom_start),
                           ("bottom_right", bottom_end)):
        records = []
        for fraction in scan_heights:
            y = miny + (bottom_y - miny) * fraction
            before, after = (station - sampling_delta, y), (
                station + sampling_delta, y,
            )
            if not all(corrected.covers(Point(*p)) for p in (before, after)):
                continue
            pts3d = []
            for x, y2 in (before, after):
                ux, zx = _profile_map_with_guides(
                    x, y2, x_profile, axis="x", fold_guides=guides,
                    fold_tip_continuity=tip_continuity,
                )
                uy, zy = _profile_map_with_guides(
                    y2, x, y_profile, axis="y", fold_guides=guides,
                    fold_tip_continuity=tip_continuity,
                )
                pts3d.append((ux, uy, zx + zy))
            dx = math.dist(pts3d[0], pts3d[1])
            records.append((float(y), float(dx)))
        if not records:
            raise GeometryError(
                "V_MITER_TAIL_DUAL_NATIVE_BEND_END_CONTINUITY_UNRESOLVED"
            )
        boundary_jumps.append((which, tuple(records)))

    # Independently check the original side-BEND lower tips. The tiny
    # connected source tongue must not jump from "flat" to "folded" at
    # the uncut Y=49 boundary. This checks same-sheet geometry, not seam fit.
    side_boundary_jumps = []
    for which, guide, sx in (
        ("bottom_left", left_guide, xl),
        ("bottom_right", right_guide, xr),
    ):
        span = float(guide.span_start - bottom_y)
        points = []
        for frac in (0.10, 0.25, 0.50, 0.75):
            x = float(sx + (span*frac if which.endswith("right")
                            else -span*frac))
            a = (x, float(guide.span_start - sampling_delta))
            b = (x, float(guide.span_start + sampling_delta))
            if not all(corrected.covers(Point(*p)) for p in (a,b)):
                continue
            def formed_xy(source):
                xx, yy = source
                ux, zx = _profile_map_with_guides(
                    xx, yy, x_profile, axis="x", fold_guides=guides,
                    fold_tip_continuity=tip_continuity,
                )
                uy, zy = _profile_map_with_guides(
                    yy, xx, y_profile, axis="y", fold_guides=guides,
                    fold_tip_continuity=tip_continuity,
                )
                return (ux, uy, zx+zy)
            points.append((x, float(math.dist(formed_xy(a), formed_xy(b)))))
        if len(points) < 3:
            raise GeometryError("V_MITER_TAIL_SIDE_TIP_CONTINUITY_UNRESOLVED")
        side_boundary_jumps.append((which, tuple(points)))

    # Ownership of the *restored* original corner stock is computed from
    # the existing fold spans, NOT from the V's visual 2D appearance.
    # The region outside BOTH side and bottom BEND coverage stays under
    # WHD's normal 3D no-fold (or other-guide) mapping. Do not count it
    # as a physical lower return merely because it is below Y=48.
    added_stock = corrected.difference(original)
    restored_stock_ownership = []
    for which, limit in (("bottom_left", bottom_start),
                          ("bottom_right", bottom_end)):
        if which == "bottom_left":
            local = added_stock.intersection(
                box(minx, miny, limit, maxy)
            )
        else:
            local = added_stock.intersection(
                box(limit, miny, maxx, maxy)
            )
        side_name = "left" if which == "bottom_left" else "right"
        bottom_owned = float(local.intersection(folded_domains["bottom"]).area)
        side_owned = float(local.intersection(folded_domains[side_name]).area)
        not_lower_fold = float(local.area) - bottom_owned - side_owned
        if min(bottom_owned, side_owned, not_lower_fold) < -_TOL:
            raise GeometryError(
                "V_MITER_TAIL_DUAL_RESTORED_STOCK_OWNERSHIP_OVERLAP"
            )
        restored_stock_ownership.append((
            which, float(local.area), side_owned,
            bottom_owned, max(0.0, not_lower_fold),
        ))
    corner_material_regions = (
        corrected.intersection(box(minx,miny,bottom_start,bottom_y)),
        corrected.intersection(box(bottom_end,miny,maxx,bottom_y)),
    )
    if any(
        p.geom_type != "Polygon" or not p.is_valid or p.is_empty
        or p.interiors for p in corner_material_regions
    ):
        raise GeometryError("V_MITER_TAIL_DUAL_OUT_OF_SPAN_CORNER_NOT_ONE_PIECE")
    if (any(p.geom_type != "Polygon" or p.is_empty or
            not p.is_valid or p.interiors or p.area <= _TOL
            for p in folded_domains.values())
            or any(
                folded_domains[a].intersection(folded_domains[b]).area > _TOL
                for a, b in (("left", "right"), ("left", "bottom"), ("right", "bottom"))
            )):
        raise GeometryError("V_MITER_TAIL_DUAL_FLANGE_PARTITION_INVALID")
    # R/BA focused lower-fold domains leave all out-of-span material in
    # a distinct remainder; the FULL real WHD 3D above independently
    # folds that remainder wherever OTHER FinalScene BEND guides apply.
    unchanged_flat = corrected.difference(unary_union(tuple(folded_domains.values())))
    flat_regions = (
        (unchanged_flat,) if unchanged_flat.geom_type == "Polygon"
        else tuple(p for p in getattr(unchanged_flat, "geoms", ())
                   if p.geom_type == "Polygon" and p.area > _TOL)
    )
    if (not flat_regions or any(not p.is_valid or p.interiors
                                for p in flat_regions)
            or abs(sum(p.area for p in flat_regions) +
                   sum(p.area for p in folded_domains.values()) -
                   corrected.area) > _TOL):
        raise GeometryError("V_MITER_TAIL_DUAL_FULL_SHEET_3D_PARTITION_INCOMPLETE")
    unformed_skin = tuple(
        tuple((float(x), float(y), 0.0) for x, y in triangle)
        for piece in flat_regions for triangle in _source_triangulation(piece)
    )
    unchanged_solid = tuple(thicken_triangle_surface(
        unformed_skin, spec.thickness,
    ))
    if not unchanged_solid:
        raise GeometryError("V_MITER_TAIL_DUAL_UNCHANGED_FLAT_BODY_MISSING")
    q = project_v_miter_trial_parameter_defaults(
        thickness_mm=spec.thickness,
        second_fold_angle_deg=90.0, relief_mode="ROUND_R",
    )
    # Never substitute three independently static flange previews for
    # the operator's two-stage process. Each trial transports the ONE
    # exact restored-and-V-cut Factory blank and its source UV triangles
    # through the physical first bend, THEN the second in its moved frame.
    # Distinct per-corner first-axis choices get separately labeled whole-
    # sheet CHECK shadows; no implicit order is assigned to the other corner.
    sequential_models = {
        axis: project_tail_same_sheet_sequential_fold_check(
            restored, corrected,
            left_apex=left[0], right_apex=right[0],
            left_v_hits=(left[1],left[2]),
            right_v_hits=(right[1],right[2]),
            guides=guides, first_axis=axis,
            thickness_mm=q.thickness_mm,
            inner_r_mm=q.first_inner_radius_mm,
            bend_allowance_mm=q.first_bend_allowance_mm,
        )
        for axis in ("x","y") if axis in first_bend_axes.values()
    }
    def form(patch, origin, axis, outside, reach, label, axial_min):
        if q.first_bend_allowance_mm >= reach - _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_RBA_CONSUMES_FLANGE")
        # The same Engine neutral axis and radial T/2 mesh as normal Factory
        # R/BA checking, on a PHYSICAL source polygon (not a viewed drawing).
        bounds = tuple(
            (x - origin.x) * axis[0] + (y - origin.y) * axis[1]
            for x, y in patch.exterior.coords
        )
        skin, flat = _formed_curved_skin(
            patch, origin, axis, outside,
            angle_rad=math.pi / 2, inner_r=q.first_inner_radius_mm,
            allowance=q.first_bend_allowance_mm,
            thickness=q.thickness_mm, axial_span=max(bounds) + 0.1,
            axial_min_mm=min(axial_min, min(bounds), 0.0),
            flange_height=reach, return_flat_pairs=True,
        )
        # Same R/BA/T owner for center and physically connected outer
        # corner. The free source cut legs are rigid extensions of the
        # bottom lip, not a guessed 0-to-90 local bending angle. In
        # particular the lower source V wall MUST keep its full height.
        offsets = _measured_cylindrical_half_t_offsets(
            flat, skin, apex=origin, outside=outside,
            angle_rad=math.pi / 2, allowance=q.first_bend_allowance_mm,
            thickness=q.thickness_mm,
        )
        solid = tuple(thicken_triangle_surface(
            skin, q.thickness_mm, smooth_vertex_normals=True,
            physical_vertex_offsets=offsets,
            tolerance=float(
                PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
            ),
        ))
        if not solid:
            raise GeometryError("V_MITER_TAIL_DUAL_"+label+"_SOLID_EMPTY")
        return flat, skin, solid, offsets

    # Both side BEND axes rise along their ORIGINAL physical Y stations;
    # bottom bends along the original horizontal X axis. Its recovered
    # corner tabs at the two ends MUST also fold, not disappear from 3D.
    e_left = _outward_bend_axis(left[6], left[0])
    e_right = _outward_bend_axis(right[6], right[0])
    e_bottom = _outward_bend_axis(left[7], left[0])
    n_left = _outside_normal(e_left, e_bottom)
    n_right = _outside_normal(e_right, _outward_bend_axis(right[7], right[0]))
    n_bottom = _outside_normal(e_bottom, e_left)
    models = {
        "left": form(folded_domains["left"], left[0], e_left, n_left,
                     left[4], "LEFT", 0.0),
        "right": form(folded_domains["right"], right[0], e_right, n_right,
                      right[4], "RIGHT", 0.0),
        "bottom": form(folded_domains["bottom"], left[0], e_bottom, n_bottom,
                       left[5], "BOTTOM", minx - left[0].x),
    }
    V_lines = {
        name: (LineString(((row[0].x, row[0].y), (row[1].x, row[1].y))),
               LineString(((row[0].x, row[0].y), (row[2].x, row[2].y))))
        for name, row in corner_data.items()
    }
    # Identify source V-cut T-solid walls from the EXACT same full
    # post-V source polygon and meshes; exclude root relief and unrelated
    # flange-boundary clips from the contact evidence.
    def face_for(model, local_legs):
        flat, skin, solid, offsets = model
        tagged = trace_v_miter_source_true_t_cut_faces(
            restored, corrected, flat, skin, solid,
            thickness_mm=spec.thickness,
            physical_vertex_offsets=offsets,
            physical_v_cut_leg_lines=local_legs,
        )
        if not tagged.has_source_tagged_cut_faces:
            raise GeometryError("V_MITER_TAIL_DUAL_NO_ACTUAL_V_CUT_SIDEWALL")
        return tagged.true_cut_face_triangles

    reports = []
    for corner, side in (("bottom_left", "left"), ("bottom_right", "right")):
        row = corner_data[corner]
        first_axis = first_bend_axes[corner]
        second_axis = "y" if first_axis == "x" else "x"
        sequential = sequential_models[first_axis]
        source_tracks = tuple(track for track in
                              sequential.source_cut_edge_tracks
                              if track[0] == corner)
        seq_face_row = next(item for item in
                            sequential.true_t_cut_faces_by_corner
                            if item[0] == corner)
        (_,seq_first_side,seq_first_bottom,
         seq_final_side,seq_final_bottom) = seq_face_row
        first_mesh = models[side] if first_axis == "x" else models["bottom"]
        second_mesh = models["bottom"] if first_axis == "x" else models[side]
        collision = detect_world_mesh_surface_interference(
            first_mesh[2], second_mesh[2],
        )
        root_contact = _root_intersection_topology(
            collision.intersection_segments,
            float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance),
        )
        # Triangle intersection pairs alone cannot certify *volume*
        # penetration. Check actual interior witnesses independently.
        witness = detect_world_mesh_enclosed_volume_witness(
            first_mesh[2], second_mesh[2],
        )
        volume_status = (
            "ENCLOSED_VOLUME_INTERFERENCE" if witness.strictly_inside_points
            else "NO_DETECTED_VOLUME_WITNESS" if witness.meshes_closed
            else "VOLUME_UNRESOLVED"
        )
        # A source CUTTING wedge has TWO distinct legs. The edge in the
        # y>48 side lip is the UPPER (outward-to-high-Y) V cut, while the
        # y<48 bottom lip owns its LOWER (outward-to-low-Y) cut. Qualify
        # these against actual material-domain boundaries before any
        # 3D nearest-face query; a flange clipping wall is not a V face.
        low_leg, high_leg = V_lines[corner]
        actual_side_boundary = folded_domains[side].boundary.buffer(_TOL)
        actual_bottom_boundary = folded_domains["bottom"].boundary.buffer(_TOL)
        cut_ownership = (
            float(high_leg.intersection(actual_side_boundary).length),
            float(low_leg.intersection(actual_side_boundary).length),
            float(low_leg.intersection(actual_bottom_boundary).length),
            float(high_leg.intersection(actual_bottom_boundary).length),
        )
        if (min(cut_ownership[0], cut_ownership[2]) < _TOL
                or max(cut_ownership[1], cut_ownership[3]) > 10*_TOL):
            raise GeometryError("V_MITER_TAIL_TRUE_CUT_FACE_SOURCE_OWNER_AMBIGUOUS")
        side_faces, bottom_faces = (), ()
        side_error = bottom_error = None
        for side_name, mesh in ((side, models[side]), ("bottom", models["bottom"])):
            try:
                faces = face_for(mesh, V_lines[corner])
            except GeometryError as exc:
                faces = ()
                if side_name == "bottom":
                    bottom_error = str(exc)
                else:
                    side_error = str(exc)
            if side_name == "bottom":
                bottom_faces = faces
            else:
                side_faces = faces
        # Actual formed reach of a 90-degree neutral-axis return; do not
        # count its far-end BA-vs-mid-R contraction as root relief.
        side_formed = row[4] - q.first_bend_allowance_mm + (
            q.first_inner_radius_mm + q.thickness_mm / 2.0
        )
        bottom_formed = row[5] - q.first_bend_allowance_mm + (
            q.first_inner_radius_mm + q.thickness_mm / 2.0
        )
        contact_reach = min(side_formed, bottom_formed)
        # A finite-R 90-degree fold has a STRAIGHT planar surface shifted
        # outward by the mid-surface radius R+T/2. The source apex (X,Y)
        # used in the sharp ideal was NOT the 3D intersection line. For
        # each corner use the actual SIDE and BOTTOM planar fold normals.
        # Sample only above the ends of the cylindrical bend arcs; root
        # contact/relief must be checked separately, never hidden here.
        mid_radius = q.first_inner_radius_mm + q.thickness_mm / 2.0
        joined_x = row[0].x + mid_radius * (
            (n_left if side == "left" else n_right)[0] + n_bottom[0]
        )
        joined_y = row[0].y + mid_radius * (
            (n_left if side == "left" else n_right)[1] + n_bottom[1]
        )
        # Source-owned side lip has y>=48, and its side X-fold does
        # not change Y. The bottom Y-fold straight T-skin occupies
        # y=joined_y +/- T/2. This *physical Y projection* witnesses a
        # strictly positive gap even if the two V source rays are moved
        # arbitrarily inside their existing patches. It says nothing
        # about a different, yet-to-be-proven shared-root sheet map.
        side_axis = e_left if side == "left" else e_right
        side_normal = n_left if side == "left" else n_right
        if (abs(side_axis[0])>_TOL or abs(side_normal[1])>_TOL
                or abs(e_bottom[1])>_TOL or abs(n_bottom[0])>_TOL
                or n_bottom[1]>=-_TOL):
            raise GeometryError("V_MITER_TAIL_STRAIGHT_DOMAIN_AXES_NOT_ORTHOGONAL")
        side_min_y = float(folded_domains[side].bounds[1])
        bottom_max_y = float(joined_y+q.thickness_mm/2.0)
        y_domain_floor = max(0.0, side_min_y-bottom_max_y)
        # (side material min-Y, bottom outer physical-T Y,
        # physical Y floor, hypothetical seam Y)
        straight_y_witness = (
            side_min_y, bottom_max_y, float(y_domain_floor), joined_y,
        )
        straight_start = min(contact_reach, mid_radius)
        if contact_reach <= mid_radius + _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_NO_STRAIGHT_FORMED_SEAM")
        physical_seam_start = (joined_x, joined_y, straight_start)
        physical_seam_end = (joined_x, joined_y, contact_reach)
        # IMPORTANT: only triangles inside the *actual* finite BEND
        # domains are folded. Retained source stock outside (16..406)
        # never receives this bottom Y fold. The earlier bbox-wide model
        # and its 6.6875mm impossibility certificate were invalid.
        # Do not infer geometric impossibility from that stale proof.
        # The old whole-width-bottom-fold 6.6875-mm certificate must NOT
        # be evaluated for finite-guide geometry: it assigned restored
        # stock outside the real BEND to a bottom flange that does not
        # exist. Keep only measured/certified geometry evidence below.
        topo_failure = None
        seam = None
        seam_error = None
        if side_faces and bottom_faces:
            # The physical first fold is explicitly selected, even for
            # 90/90. The independent flange skins are source-disjoint:
            # this can measure straight-wall contact in either order, but
            # cannot prove the shared curved root's ordered deformation.
            first_faces = side_faces if first_axis == "x" else bottom_faces
            second_faces = bottom_faces if first_axis == "x" else side_faces
            try:
                seam = project_v_miter_true_cut_face_continuity_trial(
                    first_faces, second_faces,
                    formed_seam_start=physical_seam_start,
                    formed_seam_end=physical_seam_end,
                )
            except GeometryError as exc:
                seam_error = str(exc)
        else:
            seam_error = "V_MITER_TAIL_DUAL_SOURCE_CUT_FACE_MISSING"
        endpoint_records = dict(boundary_jumps)[corner]
        endpoint_jump_max = max(gap for _y, gap in endpoint_records)
        side_tip_records = dict(side_boundary_jumps)[corner]
        side_tip_jump_max = max(gap for _x, gap in side_tip_records)
        side_tip_status = (
            "UNCUT_SIDE_TIP_FOLD_MAPPING_DISCONTINUITY"
            if side_tip_jump_max > 1e-3
            else "NO_DETECTED_SIDE_TIP_DISCONTINUITY"
        )
        endpoint_status = (
            "UNCUT_SHEET_FOLD_MAPPING_DISCONTINUITY"
            if endpoint_jump_max > 1e-3
            else "NO_DETECTED_NATIVE_SPAN_DISCONTINUITY"
        )
        # Invert the *formed* straight contact line through the same actual
        # R/BA map used to form both physical skins. A same-side-opening V
        # is allowed only if these two inverse curves can each be supported
        # by its own actual connected stock and unmodified BEND spans.
        inverse_stations = tuple(
            mid_radius + fraction * (contact_reach - mid_radius)
            for fraction in (0.25, 0.50, 0.75, 0.95)
        )
        side_outside = n_left if side == "left" else n_right
        side_inverse = tuple(_inverse_straight_90_fold_contact(
            (joined_x, joined_y), z, apex=row[0],
            axis=e_left if side == "left" else e_right,
            outside=side_outside,
            bend_allowance_mm=q.first_bend_allowance_mm,
            mid_radius_mm=mid_radius,
        ) for z in inverse_stations)
        bottom_inverse = tuple(_inverse_straight_90_fold_contact(
            (joined_x, joined_y), z, apex=row[0], axis=e_bottom,
            outside=n_bottom, bend_allowance_mm=q.first_bend_allowance_mm,
            mid_radius_mm=mid_radius,
        ) for z in inverse_stations)
        outer_x = minx if side == "left" else maxx
        upper_ray = LineString(((row[0].x, row[0].y),
                                (row[2].x, row[2].y)))
        lower_ray = LineString(((row[0].x, row[0].y),
                                (row[1].x, row[1].y)))
        real_side_guide = left_guide if side == "left" else right_guide
        inverse_trace = tuple((
            float(z), (float(s.x), float(s.y)),
            (float(b.x), float(b.y)),
            float(Point(s.x, s.y).distance(upper_ray)),
            float(Point(b.x, b.y).distance(lower_ray)),
            float(max(real_side_guide.span_start - s.y,
                      s.y - real_side_guide.span_end, 0.0)),
        ) for z, s, b in zip(inverse_stations, side_inverse, bottom_inverse))
        side_fit = _apex_ray_side_exit_least_squares(
            row[0], side_inverse, outer_x,
        )
        bottom_fit = _apex_ray_side_exit_least_squares(
            row[0], bottom_inverse, outer_x,
        )
        # Invert the curved *root* branch of the SAME finite R/BA
        # neutral-axis equations, rather than extrapolating the straight
        # z>=R+T/2 inverse down through the physical bend. This is an
        # inverse HYPOTHESIS; a true single-blank sequential root still
        # needs physical ownership proof before any cutting is permitted.
        neutral_r=q.first_bend_allowance_mm/(math.pi/2.0)
        root_phi=tuple(math.pi*i/(2.0*64) for i in range(65))
        source_side_root=tuple((
            float(row[0].x+side_outside[0]*neutral_r*phi),
            float(row[0].y+n_bottom[1]*mid_radius*math.sin(phi)),
        ) for phi in root_phi)
        source_bottom_root=tuple((
            float(row[0].x+side_outside[0]*mid_radius*math.sin(phi)),
            float(row[0].y+n_bottom[1]*neutral_r*phi),
        ) for phi in root_phi)
        if not all(restored.covers(Point(*point)) for point in (
            *source_side_root,*source_bottom_root
        )):
            raise GeometryError("V_MITER_TAIL_INVERSE_ROOT_LEAVES_ORIGINAL_MOTHER")
        root_cross_geometry=LineString(source_side_root).intersection(
            LineString(source_bottom_root)
        )
        root_cross_candidates = (
            (root_cross_geometry,)
            if root_cross_geometry.geom_type == "Point"
            else tuple(getattr(root_cross_geometry,"geoms",()))
        )
        root_crossings=tuple(
            (float(pt.x),float(pt.y))
            for pt in root_cross_candidates
            if pt.geom_type == "Point"
            and pt.distance(Point(row[0].x,row[0].y)) > 100*_TOL
        )
        root_inverse_status=(
            "ROOT_NEUTRAL_INVERSE_CURVES_CROSS_OUTSIDE_APEX_CHECK_ONLY"
            if root_crossings else
            "ROOT_NEUTRAL_INVERSE_WITHOUT_NONAPEX_CROSSING_CHECK_ONLY"
        )
        # The old analytic inverse assumes separate straight RBA planes.
        # Verify it on the CURRENT single-blank staged physical map, and
        # refuse any UV in stock removed by the real current V CUTTING.
        # This is not a redesigned cut line or an automatic source repair.
        seq_actual_inverse=[]
        for z,sv,bv in zip(inverse_stations,side_inverse,bottom_inverse):
            target=(float(joined_x),float(joined_y),float(z))
            source_s=(float(sv.x),float(sv.y))
            source_b=(float(bv.x),float(bv.y))
            s_present=bool(corrected.covers(Point(*source_s)))
            b_present=bool(corrected.covers(Point(*source_b)))
            def reproject(uv,present):
                if not present:
                    return None,None
                _,formed,_,_=project_tail_same_sheet_staged_source_point(
                    sequential,uv,
                )
                return tuple(float(q) for q in formed),float(
                    math.dist(formed,target)
                )
            s3,s_err=reproject(source_s,s_present)
            b3,b_err=reproject(source_b,b_present)
            seq_actual_inverse.append((
                float(z),source_s,s_present,s3,s_err,
                source_b,b_present,b3,b_err,
            ))
        inverse_coverage = tuple((
            float(z),
            bool(restored.covers(Point(s.x, s.y))),
            bool(folded_domains[side].covers(Point(s.x, s.y))),
            bool(restored.covers(Point(b.x, b.y))),
            bool(folded_domains["bottom"].covers(Point(b.x, b.y))),
        ) for z,s,b in zip(inverse_stations,side_inverse,bottom_inverse))
        # The projected V rays must have a *real* upper and lower exterior
        # exit and lie on both inverse straight seams; the physical side
        # flange cannot silently extend below its source BEND start.
        inverse_fit_status = (
            "INVERSE_SOURCE_RAYS_COMPATIBLE"
            if side_fit[0] > row[0].y + _TOL
            and bottom_fit[0] < row[0].y - _TOL
            and max(side_fit[1], bottom_fit[1]) <= _TOL
            and all(max(record[3:]) <= _TOL for record in inverse_trace)
            else "INVERSE_SOURCE_RAYS_NOT_COMPATIBLE"
        )
        sampled_stations = ()
        cut_face_witnesses = ()
        if side_faces and bottom_faces:
            fractions = (0.25, 0.50, 0.75, 0.95)
            sampled = project_v_miter_true_t_seam_section_gap_trial(
                first_faces, second_faces,
                formed_seam_start=physical_seam_start,
                formed_seam_end=physical_seam_end,
                station_fractions=fractions,
            )
            # The historical 'frac * contact_reach' field was WRONG:
            # this section begins above the finite-R arc at z=mid_radius.
            # Persist the actual 3D z of each trial section.
            sampled_stations = tuple(
                (float(physical_seam_start[2] +
                       frac * (physical_seam_end[2]-physical_seam_start[2])),
                 section.status, section.measured_gap_mm)
                for frac, section in zip(fractions, sampled.sections)
            )
            cut_face_witnesses = tuple(
                (float(frac), section.measured_gap_mm,
                 (section.nearest_first_xyz if first_axis == "x"
                  else section.nearest_second_xyz),
                 (section.nearest_second_xyz if first_axis == "x"
                  else section.nearest_first_xyz),
                 section.status)
                for frac, section in zip(fractions, sampled.sections)
            )
        # This is the NEW one-blank sequential T-wall evidence.
        # It is measured independently of the earlier three-patch shadow.
        # Its first-stage cut walls are present even before the second
        # fold; final walls come from the SAME source triangle IDs.
        seq_full_seam = project_v_miter_true_cut_face_continuity_trial(
            seq_final_side if first_axis=="x" else seq_final_bottom,
            seq_final_bottom if first_axis=="x" else seq_final_side,
            formed_seam_start=physical_seam_start,
            formed_seam_end=physical_seam_end,
        )
        # DIFFERENT physical pair from the old V-edge/V-edge trial:
        # the actual SIDE upper V CUTTING wall versus the original
        # BOTTOM material's +T broad outer skin. Source UV remains bottom-
        # owned, never reassigned to side; this is a candidate lap contact,
        # not an approved V miter or a change of CUTTING.
        alternative = project_tail_existing_bottom_broad_face_candidate(
            sequential,corner=corner,apex=row[0],
            current_V_hits=(row[1],row[2]),
            formed_seam_start=physical_seam_start,
            formed_seam_end=physical_seam_end,
        )
        seq_sample = project_v_miter_true_t_seam_section_gap_trial(
            seq_final_side if first_axis=="x" else seq_final_bottom,
            seq_final_bottom if first_axis=="x" else seq_final_side,
            formed_seam_start=physical_seam_start,
            formed_seam_end=physical_seam_end,
            station_fractions=(.25,.50,.75,.95),
        )
        seq_sections=tuple((
            float(section.section_origin_xyz[2]),
            section.status,section.measured_gap_mm,
            (section.nearest_first_xyz if first_axis=="x"
             else section.nearest_second_xyz),
            (section.nearest_second_xyz if first_axis=="x"
             else section.nearest_first_xyz),
        ) for section in seq_sample.sections)
        interference_z = tuple(
            float(point[2])
            for segment in collision.intersection_segments
            for point in segment
        )
        reports.append(TailDualVFaceResult(
            corner=corner, first_bend_axis=first_axis,
            second_bend_axis=second_axis,
            side_folded_solid=models[side][2],
            bottom_folded_solid=models["bottom"][2],
            side_cut_faces=side_faces, bottom_cut_faces=bottom_faces,
            model_interference_pairs=collision.pair_count,
            model_interference_segments=collision.intersection_segments,
            root_intersection_topology=root_contact,
            model_volume_status=volume_status,
            sequential_source_cut_edge_tracks=source_tracks,
            sequential_first_side_cut_faces=seq_first_side,
            sequential_first_bottom_cut_faces=seq_first_bottom,
            sequential_second_side_cut_faces=seq_final_side,
            sequential_second_bottom_cut_faces=seq_final_bottom,
            sequential_final_seam_sections=seq_sections,
            sequential_final_full_seam_continuity=seq_full_seam,
            alternative_existing_stock_contact_trial=alternative,
            sequential_inverse_actual_source_trace_mm=tuple(seq_actual_inverse),
            sequential_root_process_status=sequential.root_process_status,
            straight_section_y_domain_witness_mm=straight_y_witness,
            side_cut_failure=side_error, bottom_cut_failure=bottom_error,
            seam_continuity=seam, seam_failure=seam_error,
            actual_formed_reach_mm=contact_reach,
            distal_ideal_shortfall_mm=max(0.0, min(row[4], row[5])-contact_reach),
            sampled_seam_gap_stations_mm=sampled_stations,
            sampled_cut_face_nearest_xyz=cut_face_witnesses,
            source_cut_leg_owner_lengths_mm=cut_ownership,
            inverse_straight_contact_flat_trace_mm=inverse_trace,
            inverse_unconstrained_outer_hits_mm=(*side_fit, *bottom_fit),
            inverse_source_fit_status=inverse_fit_status,
            inverse_flat_source_coverage_mm=inverse_coverage,
            inverse_root_arc_source_traces_xy=(
                source_side_root,source_bottom_root,
            ),
            inverse_root_nonapex_crossings_xy=root_crossings,
            inverse_root_candidate_status=root_inverse_status,
            interference_z_range_mm=(
                (min(interference_z), max(interference_z))
                if interference_z else None
            ),
            actual_joint_axis_xyz=(physical_seam_start, physical_seam_end),
            native_uncut_fold_endpoint_jump_max_mm=float(endpoint_jump_max),
            native_uncut_fold_endpoint_status=endpoint_status,
            native_side_tip_endpoint_jump_max_mm=float(side_tip_jump_max),
            native_side_tip_endpoint_status=side_tip_status,
            topology_contact_failure=topo_failure,
            topological_clearance_lower_bound_mm=None,
            contact_gap_floor_at_straight_start_mm=None,
            contact_gap_floor_at_straight_end_mm=None,
            asymmetry_best_case_far_gap_floor_mm=None,
            model_status=(
                "MODEL_PASS" if (
                    endpoint_status == "NO_DETECTED_NATIVE_SPAN_DISCONTINUITY"
                    and side_tip_status == "NO_DETECTED_SIDE_TIP_DISCONTINUITY"
                ) and topo_failure is None
                and y_domain_floor <= _TOL
                and sequential.root_process_status == "PHYSICALLY_VERIFIED"
                and seq_full_seam is not None
                and seq_full_seam.max_gap_upper_bound_mm is not None
                and seq_full_seam.max_gap_upper_bound_mm <= _TOL
                and not seq_full_seam.missing_face_interval_count
                and not collision.pair_count
                and volume_status == "NO_DETECTED_VOLUME_WITNESS"
                and seam is not None and not seam.missing_face_interval_count
                and not seam.numerically_unresolved_vertex_event_count
                and seam.max_gap_upper_bound_mm is not None
                and seam.max_gap_upper_bound_mm <= _TOL
                else "MODEL_NOT_VERIFIED"
            ),
        ))
    return TailDualVSourceCheck(
        original_factory_scene=render.scene,
        operator_first_bend_axes=tuple(
            (corner, first_bend_axes[corner]) for corner in (
                "bottom_left","bottom_right"
            )
        ),
        flat_check_scene=flat_scene,
        original_outline=tuple(Vec2(float(x), float(y))
                               for x, y in original.exterior.coords),
        corrected_outline=tuple(Vec2(float(x), float(y))
                                for x, y in corrected.exterior.coords),
        left_apex=left[0], right_apex=right[0],
        left_outer_v_hits=(left[1], left[2]),
        right_outer_v_hits=(right[1], right[2]),
        side_flange_left_mm=left[4], side_flange_right_mm=right[4],
        bottom_flange_mm=left[5],
        original_other_primitives=all_original_other,
        side_left_solid=models["left"][2], side_right_solid=models["right"][2],
        bottom_solid=models["bottom"][2],
        remaining_flat_solid=unchanged_solid,
        native_original_fold_path_mesh=native_fold_mesh,
        bottom_bend_span_x_mm=(float(bottom_start), float(bottom_end)),
        side_bend_span_y_mm=(
            (float(left_guide.span_start),float(left_guide.span_end)),
            (float(right_guide.span_start),float(right_guide.span_end)),
        ),
        retained_out_of_span_corner_area_mm2=(
            float(corrected.intersection(
                box(minx,miny,bottom_start,bottom_y)
            ).area),
            float(corrected.intersection(
                box(bottom_end,miny,maxx,bottom_y)
            ).area),
        ),
        out_of_bottom_span_corner_contours_xy=tuple(
            tuple(Vec2(float(x),float(y)) for x,y in region.exterior.coords)
            for region in corner_material_regions
        ),
        restored_stock_ownership_mm2=tuple(restored_stock_ownership),
        native_bottom_span_boundary_jump_samples_mm=tuple(boundary_jumps),
        native_side_span_boundary_jump_samples_mm=tuple(side_boundary_jumps),
        corners=(reports[0], reports[1]),
        sequential_same_sheet_stage_models=tuple(
            (axis,sequential_models[axis]) for axis in ("x","y")
            if axis in sequential_models
        ),
    )
