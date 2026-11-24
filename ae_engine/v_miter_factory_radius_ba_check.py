# -*- coding: utf-8 -*-
"""#3317 actual Factory V-source curved R/BA/T CHECK with generic defaults.

The older R/BA *trimming* solver requires the ideal finite contact ray to
end on the CUTTING perimeter. Real Factory V-miter uses an independently
extended, source-clipped V edge instead: substituting the ideal ray for the
real stock exit is physically invalid. This module therefore computes
only honest curved R/BA/T surface/interference diagnostics from the
verified Factory post-V stock, without making up a corrected CUTTING or
using a shop-unapproved relief/trim dimension. Where an independently
source-proven R/hole trial is supplied, the same 2D corrected material
feeds both the zero-R and curved R/BA finite-T shadow. No manufacture.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Polygon

from .assembly_geometry import (
    detect_world_mesh_surface_interference,
    detect_world_mesh_enclosed_volume_witness,
    diagnose_world_mesh_triangle_edge_incidence,
    diagnose_world_mesh_self_intersections,
)
from .assembly_geometry_primitives import thicken_triangle_surface
from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_ideal_mating import (
    VMiterIdealMatingCandidate, _outward_bend_axis, _outside_normal,
    _UNIT_Z, _add, _scale,
)
from .v_miter_material_trial import VMiterSourceBoundSharpCheck
from .v_miter_factory_fold_check import VMiterFactoryPrecutFoldCheck
from .v_miter_factory_mother_check import VMiterFactoryMotherReplacementCheck
from .v_miter_factory_true_t_check import (
    project_v_miter_factory_post_v_true_t_check, _source_flange_parts,
    _formed_perimeter_edges, _formed_skin,
)
from .v_miter_radius_ba_interface_trial import (
    _formed_curved_skin, _measured_cylindrical_half_t_offsets,
    _trim_one_v_edge, _checked_full_source_from_trim,
)
from .v_miter_factory_relief_check import (
    VMiterFactoryBottomReliefCheck,
    project_v_miter_factory_bottom_relief_default_check,
)
from .v_miter_source_cut_face_trial import (
    VMiterSourceCutFaceTrial, trace_v_miter_source_true_t_cut_faces,
)
from .v_miter_cut_face_continuity_trial import (
    VMiterCutFaceContinuityTrial, project_v_miter_true_cut_face_continuity_trial,
)
from .v_miter_trial_defaults import (
    VMiterTrialParameterDefaults, project_v_miter_trial_parameter_defaults,
)
from .v_miter_factory_measurements import (
    VMiterFactoryMeasuredInputs, require_v_miter_factory_measurement_source,
)


@dataclass(frozen=True)
class VMiterFactoryRadiusBADefaultCheck:
    """Physical post-V source curved-T shadow. No manufacturing contour."""

    first_inner_radius_mm: float
    second_inner_radius_mm: float
    first_bend_allowance_mm: float
    second_bend_allowance_mm: float
    first_formed_perimeter_edges: tuple
    second_formed_perimeter_edges: tuple
    first_curved_skin_triangles: tuple
    second_curved_skin_triangles: tuple
    first_thick_solid_triangles: tuple
    second_thick_solid_triangles: tuple
    sharp_t_surface_interference_pairs: int
    curved_t_surface_interference_pairs: int
    curved_t_volume_status: str
    # The exact same 2D source contour used by every formed physical mesh.
    formed_source_outline: tuple
    # The physically attainable formed seam is shorter than the zero-R
    # ideal where BA consumes more flat stock than the neutral R/T offset.
    # It is a DISTAL reach delta, never a root relief.
    physical_formed_seam_reach_mm: float = 0.0
    distal_ideal_seam_shortfall_mm: float = 0.0
    first_edge_trim_mm: float = 0.0
    additional_source_removed_area_mm2: float = 0.0
    first_source_tagged_cut_faces: VMiterSourceCutFaceTrial | None = None
    second_source_tagged_cut_faces: VMiterSourceCutFaceTrial | None = None
    first_cut_face_failure: str | None = None
    second_cut_face_failure: str | None = None
    source_cut_face_continuity: VMiterCutFaceContinuityTrial | None = None
    source_cut_face_continuity_failure: str | None = None
    relief_application_status: str = "FACTORY_R_BA_RELIEF_NOT_YET_APPLIED"
    trim_application_status: str = "FACTORY_R_BA_V_EDGE_TRIM_NOT_YET_SOLVED"
    geometry_model: str = "FACTORY_PROVEN_POST_V_R_BA_CYLINDRICAL_T_CHECK"
    manufacturing_status: str = "V_MITER_FACTORY_R_BA_DEFAULT_UNCERTIFIED"


def project_v_miter_factory_radius_ba_default_check(
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
    defaults: VMiterTrialParameterDefaults | VMiterFactoryMeasuredInputs,
    factory_mother: VMiterFactoryMotherReplacementCheck | None = None,
    *,
    relief_check: VMiterFactoryBottomReliefCheck | None = None,
    first_edge_trim_mm: float = 0.0,
) -> VMiterFactoryRadiusBADefaultCheck:
    """Run actual R/BA curved finite-T CHECK on Factory-proven post-V stock.

    The V-side CUTTING endpoint is the *real* Factory source perimeter
    intersection, not the shorter ideal formed seam endpoint. If present,
    the Factory R/Ø relief is independently revalidated and its exact
    remaining outline becomes the ONLY source for both physical mesh sets.
    An explicitly supplied first-edge trim is applied to this same Factory
    source in both 2D and R/BA/T 3D. This remains CHECK-only and can never
    authorize an uncertified production CUTTING path.
    """
    if (not isinstance(part_spec, (DoorPartSpec, EndCapPartSpec))
            or not isinstance(defaults, (VMiterTrialParameterDefaults,
                                         VMiterFactoryMeasuredInputs))
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or not isinstance(ideal, VMiterIdealMatingCandidate)
            or not isinstance(factory_fold, VMiterFactoryPrecutFoldCheck)):
        raise GeometryError("V_MITER_FACTORY_R_BA_TYPED_SOURCE_REQUIRED")
    if (type(first_edge_trim_mm) not in (int, float)
            or not math.isfinite(first_edge_trim_mm)
            or first_edge_trim_mm < 0):
        raise GeometryError("V_MITER_FACTORY_FIRST_EDGE_TRIM_INVALID")
    if first_edge_trim_mm and not isinstance(defaults, VMiterFactoryMeasuredInputs):
        raise GeometryError("V_MITER_FACTORY_TRIM_MEASURED_SOURCE_REQUIRED")
    if first_edge_trim_mm and relief_check is None:
        raise GeometryError("V_MITER_FACTORY_TRIM_RELIEF_SOURCE_REQUIRED")
    if isinstance(defaults, VMiterFactoryMeasuredInputs):
        require_v_miter_factory_measurement_source(
            defaults, part_spec, corner_key, ideal,
        )
    elif defaults != project_v_miter_trial_parameter_defaults(
        thickness_mm=part_spec.thickness,
        second_fold_angle_deg=ideal.source.second_fold_angle_deg,
        relief_mode=ideal.source.relief_mode,
    ) or defaults.thickness_mm != ideal.source.thickness_mm:
        raise GeometryError("V_MITER_FACTORY_R_BA_DEFAULTS_SOURCE_CHANGED")
    sharp_t = project_v_miter_factory_post_v_true_t_check(
        part_spec, render_data, corner_key, ideal, source_check,
        factory_fold, first_real_bend, second_real_bend,
        first_station_bend, second_station_bend, factory_mother,
    )
    if relief_check is not None:
        if not isinstance(relief_check, VMiterFactoryBottomReliefCheck):
            raise GeometryError("V_MITER_FACTORY_R_BA_RELIEF_TYPES_INVALID")
        proven_relief = project_v_miter_factory_bottom_relief_default_check(
            part_spec, render_data, corner_key, ideal, source_check,
            factory_fold, first_real_bend, second_real_bend,
            defaults, factory_mother,
        )
        if proven_relief != relief_check:
            raise GeometryError("V_MITER_FACTORY_R_BA_RELIEF_SOURCE_CHANGED")
        selected_outline = proven_relief.corrected_remaining_outline
        relief_status = "FACTORY_R_BA_SOURCE_RELIEF_APPLIED_UNCERTIFIED"
    else:
        selected_outline = source_check.remaining_outline
        relief_status = "FACTORY_R_BA_RELIEF_NOT_YET_APPLIED"
    remaining = Polygon((p.x, p.y) for p in selected_outline)
    if (remaining.geom_type != "Polygon" or remaining.is_empty
            or not remaining.is_valid or remaining.interiors):
        raise GeometryError("V_MITER_FACTORY_R_BA_POST_V_STOCK_INVALID")
    # This original pre-V Factory mother, not the shorter ideal contact
    # ray or the C01/C04 already-cut FinalScene, is the only legitimate
    # provenance datum for newly created V-side CUTTING faces.
    source_mother = Polygon(
        (p.x, p.y) for p in source_check.remaining_outline
    ).union(Polygon(
        (p.x, p.y) for p in source_check.removed_corner_outline
    ))
    if (source_mother.geom_type != "Polygon" or source_mother.is_empty
            or not source_mother.is_valid or source_mother.interiors
            or abs(source_mother.area - source_check.source_material_area_mm2) > 1e-6):
        raise GeometryError("V_MITER_FACTORY_R_BA_CUT_FACE_MOTHER_INVALID")
    if not remaining.difference(source_mother.buffer(1e-7)).is_empty:
        raise GeometryError("V_MITER_FACTORY_R_BA_CUT_FACE_INVENTS_STOCK")
    apex = ideal.source.bend_intersection
    # Only the original *actual source-perimeter* V leg directions are
    # permitted as inclined seam faces. Any R/Ø root face must not provide
    # false "mating" coverage in the physical continuous gap solver.
    actual_v_legs = (
        LineString(((apex.x, apex.y),
                    (source_check.first_perimeter_hit.x,
                     source_check.first_perimeter_hit.y))),
        LineString(((apex.x, apex.y),
                    (source_check.second_perimeter_hit.x,
                     source_check.second_perimeter_hit.y))),
    )
    e1 = _outward_bend_axis(first_station_bend, apex)
    e2 = _outward_bend_axis(second_station_bend, apex)
    n1 = _outside_normal(e1, e2)
    n2 = _outside_normal(e2, e1)
    source = ideal.source
    domains = (
        (e1, n1, factory_fold.first_proposed_segments,
         source.first_flange_height_mm,
         ideal.first_flat_miter_ray[1], "FIRST",
         math.pi / 2, defaults.first_inner_radius_mm,
         defaults.first_bend_allowance_mm),
        (e2, n2, factory_fold.second_proposed_segments,
         source.second_flange_height_mm,
         ideal.second_flat_miter_ray[1], "SECOND",
         math.radians(defaults.second_fold_angle_deg),
         defaults.second_inner_radius_mm,
         defaults.second_bend_allowance_mm),
    )

    # #3317: same original Factory mother, same physical first/second BEND
    # and same already-source-verified R/HOLE remain mandatory. A declared
    # trim amount is *not* guessed by the engine, and no old ideal finite-tip
    # path can silently replace the real perimeter V ray. Apply only material
    # removal from the first flange, then re-use the resulting whole sheet
    # for BOTH 2D output and all formed T/R/BA mesh/sidewall calculations.
    removed_trim_area = 0.0
    if first_edge_trim_mm:
        def real_flange_piece(domain):
            axis, normal, folds, height, tip, name = domain[:6]
            tip_axial = ((tip.x - apex.x) * axis[0]
                         + (tip.y - apex.y) * axis[1])
            parts, _, _, _ = _source_flange_parts(
                remaining, apex, axis, normal, folds, height,
                tip_axial, name,
            )
            if len(parts) != 1:
                raise GeometryError(
                    "V_MITER_FACTORY_TRIM_MULTIPLE_FLANGE_COMPONENTS"
                )
            return parts[0]

        first_source = real_flange_piece(domains[0])
        unchanged_second = real_flange_piece(domains[1])
        first_corrected, first_trimmed_v_leg = _trim_one_v_edge(
            first_source, apex, source_check.first_perimeter_hit,
            float(first_edge_trim_mm),
            relief_open_length_mm=relief_check.flat_leg_tip_cutback_mm,
            return_source_mating_leg=True,
        )
        corrected_sheet, removal = _checked_full_source_from_trim(
            remaining, first_source, first_corrected, unchanged_second,
        )
        if removal.area <= 1e-8:
            raise GeometryError("V_MITER_FACTORY_FIRST_EDGE_TRIM_REMOVES_NO_STOCK")
        # The physical weld-side first V leg is now the actual source trim
        # line, NOT the original sharp ray. Prove it is an actual portion of
        # this corrected whole sheet's CUTTING boundary before admitting it
        # to the independently source-tagged true-T cut-face tracer.
        if corrected_sheet.boundary.intersection(
            first_trimmed_v_leg.buffer(1e-6),
        ).length <= 1e-6:
            raise GeometryError(
                "V_MITER_FACTORY_TRIMMED_SOURCE_LEG_NOT_ON_NEW_CUTTING"
            )
        actual_v_legs = (first_trimmed_v_leg, actual_v_legs[1])
        # This one-sheet CHECK source supersedes the original R/HOLE stock.
        # The original source and unaffected second flange stay untouched.
        remaining = corrected_sheet
        selected_outline = tuple(
            Vec2(float(x), float(y)) for x, y in remaining.exterior.coords
        )
        removed_trim_area = float(removal.area)

    all_skins, all_solids, all_sharp_solids = [], [], []
    tagged_faces, cut_face_failures = [], []
    for axis, normal, folds, height, tip, name, angle, radius, allowance in domains:
        tip_axial = (
            (tip.x - apex.x) * axis[0] +
            (tip.y - apex.y) * axis[1]
        )
        parts, low, high, _ = _source_flange_parts(
            remaining, apex, axis, normal, folds, height, tip_axial, name,
        )
        formed, paired_flat = [], []
        sharp_formed = []
        bent_outward = (
            _UNIT_Z if name == "FIRST"
            else _add(_scale(normal, math.cos(angle)),
                      _scale(_UNIT_Z, math.sin(angle)))
        )
        for part in parts:
            sharp_formed.extend(_formed_skin(
                part, apex, axis, normal, bent_outward,
            ))
            skin, flat = _formed_curved_skin(
                part, apex, axis, normal,
                angle_rad=angle, inner_r=radius, allowance=allowance,
                thickness=defaults.thickness_mm, axial_span=high,
                axial_min_mm=min(0.0, low),
                flange_height=height, return_flat_pairs=True,
            )
            formed.extend(skin)
            paired_flat.extend(flat)
        skin = tuple(formed)
        offsets = _measured_cylindrical_half_t_offsets(
            tuple(paired_flat), skin, apex=apex, outside=normal,
            angle_rad=angle, allowance=allowance,
            thickness=defaults.thickness_mm,
        )
        solid = tuple(thicken_triangle_surface(
            skin, defaults.thickness_mm, smooth_vertex_normals=True,
            physical_vertex_offsets=offsets,
        ))
        topo = diagnose_world_mesh_triangle_edge_incidence(solid)
        if (not topo.edges_manifold_closed or
                not diagnose_world_mesh_self_intersections(
                    solid,
                ).permits_strict_volume_sampling):
            raise GeometryError(
                f"V_MITER_FACTORY_R_BA_{name}_VOLUME_TOPOLOGY_UNPROVEN"
            )
        sharp_solid = tuple(thicken_triangle_surface(
            tuple(sharp_formed), defaults.thickness_mm,
        ))
        if not sharp_solid:
            raise GeometryError(
                f"V_MITER_FACTORY_R_BA_{name}_SHARP_SOURCE_MISSING"
            )
        # Trace real V-cut walls through precisely the SAME paired flat
        # triangles, cylindrically formed skin, measured radial T/2 offsets,
        # and physical solid. Proving only their new source CUTTING edges
        # avoids mistaking an unrelated clip plane or bottom hole for contact.
        try:
            cut_faces = trace_v_miter_source_true_t_cut_faces(
                source_mother, remaining, tuple(paired_flat), skin, solid,
                thickness_mm=defaults.thickness_mm,
                physical_vertex_offsets=offsets,
                physical_v_cut_leg_lines=actual_v_legs,
            )
            if not cut_faces.has_source_tagged_cut_faces:
                raise GeometryError(
                    f"V_MITER_FACTORY_R_BA_{name}_NO_SOURCE_V_LEG_SIDEWALL"
                )
        except GeometryError as exc:
            cut_faces = None
            cut_failure = str(exc)
        else:
            cut_failure = None
        tagged_faces.append(cut_faces)
        cut_face_failures.append(cut_failure)
        all_sharp_solids.append(sharp_solid)
        all_skins.append(skin)
        all_solids.append(solid)

    # Crucial: both reported R=0 and R/BA collision counts use exactly
    # the same *source* one-sheet profile (including R or relief hole).
    zero_r_collision = detect_world_mesh_surface_interference(
        all_sharp_solids[0], all_sharp_solids[1],
    )
    collision = detect_world_mesh_surface_interference(
        all_solids[0], all_solids[1],
    )
    volume_status = "V_MITER_FACTORY_R_BA_SURFACE_INTERFERENCE_PRESENT_UNCERTIFIED"
    if not collision.pair_count:
        witness = detect_world_mesh_enclosed_volume_witness(
            all_solids[0], all_solids[1],
        )
        if witness.strictly_inside_points:
            volume_status = "V_MITER_FACTORY_R_BA_ENCLOSED_VOLUME_INTERFERENCE_UNCERTIFIED"
        elif witness.meshes_closed:
            volume_status = "V_MITER_FACTORY_R_BA_NO_DETECTED_VOLUME_WITNESS_UNCERTIFIED"
        else:
            volume_status = "V_MITER_FACTORY_R_BA_VOLUME_UNKNOWN_UNCERTIFIED"

    # Enumerate the full physical formed-seam line as exact vertex-to-vertex
    # projection intervals. No whole-solid nearest-distance or a few hand-
    # chosen samples may claim a continuous seam or shop gap tolerance.
    continuity = None
    continuity_failure = None
    physical_seam_reach = ideal.formed_contact_length_mm
    # Two 90-degree folds: the paired cylindrical neutral surfaces finish
    # their respective arc at Z=R+T/2. Every additional flat millimeter
    # after BA adds exactly one millimeter of formed Z. The old ideal
    # Z=flat flange height incorrectly counted the resulting FAR END
    # (BA-(R+T/2)) shortfall as absent cut-face stock.
    # Other second angles keep their existing independently qualified
    # ideal station until a non-90 inverse contact model exists.
    if abs(float(defaults.second_fold_angle_deg) - 90.0) <= 1e-8:
        mid_r1 = defaults.first_inner_radius_mm + defaults.thickness_mm / 2.0
        mid_r2 = defaults.second_inner_radius_mm + defaults.thickness_mm / 2.0
        physical_seam_reach = min(
            source.first_flange_height_mm - defaults.first_bend_allowance_mm + mid_r1,
            source.second_flange_height_mm - defaults.second_bend_allowance_mm + mid_r2,
            ideal.formed_contact_length_mm,
        )
        if physical_seam_reach <= 0:
            raise GeometryError("V_MITER_FACTORY_PHYSICAL_FOLDED_REACH_NONPOSITIVE")
    source_seam_start = ideal.formed_seam_start
    ratio = physical_seam_reach / ideal.formed_contact_length_mm
    source_seam_end = tuple(
        source_seam_start[i] + ratio * (
            ideal.formed_seam_end[i] - source_seam_start[i]
        ) for i in range(3)
    )
    distal_shortfall = max(0.0, ideal.formed_contact_length_mm - physical_seam_reach)
    if any(item is None for item in tagged_faces):
        continuity_failure = (
            "V_MITER_FACTORY_R_BA_SOURCE_V_LEG_SIDEWALL_INCOMPLETE: "
            + "; ".join(x for x in cut_face_failures if x)
        )
    else:
        try:
            continuity = project_v_miter_true_cut_face_continuity_trial(
                tagged_faces[0].true_cut_face_triangles,
                tagged_faces[1].true_cut_face_triangles,
                formed_seam_start=source_seam_start,
                formed_seam_end=source_seam_end,
            )
        except GeometryError as exc:
            continuity_failure = str(exc)
    return VMiterFactoryRadiusBADefaultCheck(
        first_inner_radius_mm=defaults.first_inner_radius_mm,
        second_inner_radius_mm=defaults.second_inner_radius_mm,
        first_bend_allowance_mm=defaults.first_bend_allowance_mm,
        second_bend_allowance_mm=defaults.second_bend_allowance_mm,
        first_formed_perimeter_edges=_formed_perimeter_edges(all_skins[0]),
        second_formed_perimeter_edges=_formed_perimeter_edges(all_skins[1]),
        first_curved_skin_triangles=all_skins[0],
        second_curved_skin_triangles=all_skins[1],
        first_thick_solid_triangles=all_solids[0],
        second_thick_solid_triangles=all_solids[1],
        sharp_t_surface_interference_pairs=zero_r_collision.pair_count,
        curved_t_surface_interference_pairs=collision.pair_count,
        curved_t_volume_status=volume_status,
        formed_source_outline=tuple(selected_outline),
        physical_formed_seam_reach_mm=physical_seam_reach,
        distal_ideal_seam_shortfall_mm=distal_shortfall,
        first_edge_trim_mm=float(first_edge_trim_mm),
        additional_source_removed_area_mm2=removed_trim_area,
        first_source_tagged_cut_faces=tagged_faces[0],
        second_source_tagged_cut_faces=tagged_faces[1],
        first_cut_face_failure=cut_face_failures[0],
        second_cut_face_failure=cut_face_failures[1],
        source_cut_face_continuity=continuity,
        source_cut_face_continuity_failure=continuity_failure,
        relief_application_status=relief_status,
        trim_application_status=(
            "FACTORY_R_BA_SOURCE_FIRST_EDGE_TRIM_APPLIED_UNCERTIFIED"
            if first_edge_trim_mm else
            "FACTORY_R_BA_V_EDGE_TRIM_NOT_YET_SOLVED"
        ),
        manufacturing_status=(
            "V_MITER_FACTORY_R_BA_MEASURED_INPUT_UNCERTIFIED"
            if isinstance(defaults, VMiterFactoryMeasuredInputs)
            else "V_MITER_FACTORY_R_BA_DEFAULT_UNCERTIFIED"
        ),
    )
