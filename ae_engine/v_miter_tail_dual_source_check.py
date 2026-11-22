# -*- coding: utf-8 -*-
"""#3317: one source Tail blank, two side-opening V's, same-source folded 3D.

Model CHECK only. All geometry originates from one EndCap PartSpec/FinalScene
and the existing Factory's original (pre-corner) sheet and BEND stations.
No Door trim, no CNC export, no factory tolerance, no X publication.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .assembly_geometry import (
    detect_world_mesh_surface_interference,
    detect_world_mesh_enclosed_volume_witness,
)
from .assembly_geometry_primitives import thicken_triangle_surface
from .contracts import EndCapPartSpec
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


_TOL = 1e-6


@dataclass(frozen=True)
class TailDualVFaceResult:
    corner: str
    side_folded_solid: tuple
    bottom_folded_solid: tuple
    side_cut_faces: tuple
    bottom_cut_faces: tuple
    model_interference_pairs: int
    model_interference_segments: tuple
    model_volume_status: str
    side_cut_failure: str | None
    bottom_cut_failure: str | None
    seam_continuity: object | None
    seam_failure: str | None
    actual_formed_reach_mm: float
    distal_ideal_shortfall_mm: float
    # Direct true 3D cut-face stations, not whole-solid nearest distance.
    sampled_seam_gap_stations_mm: tuple = ()
    interference_z_range_mm: tuple | None = None
    actual_joint_axis_xyz: tuple = ()
    native_uncut_fold_endpoint_jump_max_mm: float | None = None
    native_uncut_fold_endpoint_status: str = "UNCHECKED"
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
    corners: tuple[TailDualVFaceResult, TailDualVFaceResult]
    geometry_status: str = "TAIL_DOUBLE_V_CHECK_ONLY_UNVERIFIED"


def project_tail_dual_v_same_source_check(
    spec: EndCapPartSpec, render: PartRenderData,
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
    # The opt-in transition is bounded by the REAL untouched source
    # outer edges x=0/422 and the two REAL lower BEND endpoints x=16/406.
    # Its start/end angle is 0/90 degrees, so no 3D tear can appear
    # across the same uncut stock while the center guide stays 90.
    tip_continuity = (("y", float(bottom_y), minx, maxx),)
    folded_domains = {
        "left": corrected.intersection(box(
            minx, left_guide.span_start, xl, left_guide.span_end,
        )),
        "right": corrected.intersection(box(
            xr, right_guide.span_start, maxx, right_guide.span_end,
        )),
        "bottom": corrected.intersection(box(
            bottom_start, miny, bottom_end, bottom_y,
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
        offsets = _measured_cylindrical_half_t_offsets(
            flat, skin, apex=origin, outside=outside,
            angle_rad=math.pi / 2, allowance=q.first_bend_allowance_mm,
            thickness=q.thickness_mm,
        )
        solid = tuple(thicken_triangle_surface(
            skin, q.thickness_mm, smooth_vertex_normals=True,
            physical_vertex_offsets=offsets,
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
        collision = detect_world_mesh_surface_interference(
            models[side][2], models["bottom"][2],
        )
        if collision.pair_count:
            volume_status = "SURFACE_INTERFERENCE"
        else:
            witness = detect_world_mesh_enclosed_volume_witness(
                models[side][2], models["bottom"][2],
            )
            volume_status = (
                "ENCLOSED_VOLUME_INTERFERENCE" if witness.strictly_inside_points
                else "NO_DETECTED_VOLUME_WITNESS" if witness.meshes_closed
                else "VOLUME_UNRESOLVED"
            )
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
            try:
                seam = project_v_miter_true_cut_face_continuity_trial(
                    side_faces, bottom_faces,
                    formed_seam_start=physical_seam_start,
                    formed_seam_end=physical_seam_end,
                )
            except GeometryError as exc:
                seam_error = str(exc)
        else:
            seam_error = "V_MITER_TAIL_DUAL_SOURCE_CUT_FACE_MISSING"
        endpoint_records = dict(boundary_jumps)[corner]
        endpoint_jump_max = max(gap for _y, gap in endpoint_records)
        endpoint_status = (
            "UNCUT_SHEET_FOLD_MAPPING_DISCONTINUITY"
            if endpoint_jump_max > 1e-3
            else "NO_DETECTED_NATIVE_SPAN_DISCONTINUITY"
        )
        sampled_stations = ()
        if side_faces and bottom_faces:
            fractions = (0.25, 0.50, 0.75, 0.95)
            sampled = project_v_miter_true_t_seam_section_gap_trial(
                side_faces, bottom_faces,
                formed_seam_start=physical_seam_start,
                formed_seam_end=physical_seam_end,
                station_fractions=fractions,
            )
            sampled_stations = tuple(
                (float(frac * contact_reach), section.status,
                 section.measured_gap_mm)
                for frac, section in zip(fractions, sampled.sections)
            )
        interference_z = tuple(
            float(point[2])
            for segment in collision.intersection_segments
            for point in segment
        )
        reports.append(TailDualVFaceResult(
            corner=corner,
            side_folded_solid=models[side][2],
            bottom_folded_solid=models["bottom"][2],
            side_cut_faces=side_faces, bottom_cut_faces=bottom_faces,
            model_interference_pairs=collision.pair_count,
            model_interference_segments=collision.intersection_segments,
            model_volume_status=volume_status,
            side_cut_failure=side_error, bottom_cut_failure=bottom_error,
            seam_continuity=seam, seam_failure=seam_error,
            actual_formed_reach_mm=contact_reach,
            distal_ideal_shortfall_mm=max(0.0, min(row[4], row[5])-contact_reach),
            sampled_seam_gap_stations_mm=sampled_stations,
            interference_z_range_mm=(
                (min(interference_z), max(interference_z))
                if interference_z else None
            ),
            actual_joint_axis_xyz=(physical_seam_start, physical_seam_end),
            native_uncut_fold_endpoint_jump_max_mm=float(endpoint_jump_max),
            native_uncut_fold_endpoint_status=endpoint_status,
            topology_contact_failure=topo_failure,
            topological_clearance_lower_bound_mm=None,
            contact_gap_floor_at_straight_start_mm=None,
            contact_gap_floor_at_straight_end_mm=None,
            asymmetry_best_case_far_gap_floor_mm=None,
            model_status=(
                "MODEL_PASS" if (
                    endpoint_status == "NO_DETECTED_NATIVE_SPAN_DISCONTINUITY"
                ) and topo_failure is None
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
        corners=(reports[0], reports[1]),
    )
