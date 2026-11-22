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
from .manufacturing_render_data import PartRenderData
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
    # A physical impossibility is a model FAIL, not an invitation to trim
    # an arbitrary Door edge or call geometric diagnostics "passed".
    topology_contact_failure: str | None = None
    topological_clearance_lower_bound_mm: float | None = None
    contact_gap_floor_at_straight_start_mm: float | None = None
    contact_gap_floor_at_straight_end_mm: float | None = None
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
    # A real 3D sidefold contains the same post-V source stock as the
    # bottom flap, including its original free outer tabs beyond BEND ends.
    # Split only at PHYSICAL BEND stations, never a guessed flank clip.
    xl, xr, bottom_y = left[0].x, right[0].x, left[0].y
    folded_domains = {
        "left": corrected.intersection(box(minx, bottom_y, xl, maxy)),
        "right": corrected.intersection(box(xr, bottom_y, maxx, maxy)),
        "bottom": corrected.intersection(box(minx, miny, maxx, bottom_y)),
    }
    if (any(p.geom_type != "Polygon" or p.is_empty or
            not p.is_valid or p.interiors or p.area <= _TOL
            for p in folded_domains.values())
            or any(
                folded_domains[a].intersection(folded_domains[b]).area > _TOL
                for a, b in (("left", "right"), ("left", "bottom"), ("right", "bottom"))
            )):
        raise GeometryError("V_MITER_TAIL_DUAL_FLANGE_PARTITION_INVALID")
    # The rest of this SAME source sheet is left flat: only its lower
    # two corner folds are in scope. Do not omit its unchanged top/center
    # material from the user's 3D projection.
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
        # For BOTH rays to exit their same outer SIDE with a 90-degree
        # included V, the ray on the side-fold portion extends from the
        # apex toward Y>=apex.Y. But the folded bottom flange's true
        # planar T-surface occupies Y <= apex.Y - R at this 90-degree
        # bend (its mid-plane is Y=apex.Y-(R+T/2)). There is thus at
        # least an R-sized positive separation even for a zero-slope ray;
        # a nonzero upper V slope makes it strictly worse with height.
        # No angle split or "Door trim" can satisfy the full-seam contact
        # while preserving this side-opening topology and both BEND axes.
        topological_floor = q.first_inner_radius_mm
        side_upper_hit = row[2]
        side_mouth_horizontal_reach = abs(side_upper_hit.x - row[0].x)
        side_mouth_vertical_rise = side_upper_hit.y - row[0].y
        if side_mouth_horizontal_reach <= _TOL:
            raise GeometryError("V_MITER_TAIL_DUAL_UPPER_MOUTH_HAS_NO_HORIZONTAL_REACH")
        upper_ray_slope = side_mouth_vertical_rise / side_mouth_horizontal_reach
        # In the straight 90-degree region, the FLAT transverse distance
        # is u=BA+(Z-(R+T/2)). On this same source-cut leg Y=apexY+
        # upper_ray_slope*u, while the bottom solid can reach no farther
        # than Y=apexY-R. Their signed separation is therefore at least
        # R + slope*u, independent of the near-face nearest-point sample.
        # This is a physically sourced *lower bound*, not a kerf/tolerance.
        def source_contact_gap_floor(z):
            u = q.first_bend_allowance_mm + (z - mid_radius)
            return q.first_inner_radius_mm + upper_ray_slope * u
        floor_start = source_contact_gap_floor(straight_start)
        floor_end = source_contact_gap_floor(contact_reach)
        physical_no_solution = (
            side_upper_hit.y >= row[0].y - _TOL
            and n_bottom[1] < -1.0 + _TOL
            and abs(q.first_inner_radius_mm - q.second_inner_radius_mm)
            <= _TOL
            and upper_ray_slope > _TOL
            and floor_start > _TOL
            and floor_end > _TOL
        )
        topo_failure = (
            "V_MITER_SIDE_OPENING_90_BENDS_NO_CONTACT: "
            "upper V-cut belongs to SIDE flange at Y>=BEND_Y, "
            "but folded BOTTOM flange's physical T surface is "
            "at Y<=BEND_Y-R. Cannot close its entire seam "
            "without changing the specified cut topology or BEND."
            if physical_no_solution else None
        )
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
            topology_contact_failure=topo_failure,
            topological_clearance_lower_bound_mm=(
                topological_floor if physical_no_solution else None
            ),
            contact_gap_floor_at_straight_start_mm=(
                floor_start if physical_no_solution else None
            ),
            contact_gap_floor_at_straight_end_mm=(
                floor_end if physical_no_solution else None
            ),
            model_status=(
                "MODEL_PASS" if topo_failure is None
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
        corners=(reports[0], reports[1]),
    )
