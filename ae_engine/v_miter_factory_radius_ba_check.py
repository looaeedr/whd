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

from shapely.geometry import Polygon

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
from .sheetmetal_geometry_core import GeometryError
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
)
from .v_miter_factory_relief_check import (
    VMiterFactoryBottomReliefCheck,
    project_v_miter_factory_bottom_relief_default_check,
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
) -> VMiterFactoryRadiusBADefaultCheck:
    """Run actual R/BA curved finite-T CHECK on Factory-proven post-V stock.

    The V-side CUTTING endpoint is the *real* Factory source perimeter
    intersection, not the shorter ideal formed seam endpoint. If present,
    the Factory R/Ø relief is independently revalidated and its exact
    remaining outline becomes the ONLY source for both physical mesh sets.
    V-edge trimming is not invented or permitted as factory machining.
    """
    if (not isinstance(part_spec, (DoorPartSpec, EndCapPartSpec))
            or not isinstance(defaults, (VMiterTrialParameterDefaults,
                                         VMiterFactoryMeasuredInputs))
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or not isinstance(ideal, VMiterIdealMatingCandidate)
            or not isinstance(factory_fold, VMiterFactoryPrecutFoldCheck)):
        raise GeometryError("V_MITER_FACTORY_R_BA_TYPED_SOURCE_REQUIRED")
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
    apex = ideal.source.bend_intersection
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

    all_skins, all_solids, all_sharp_solids = [], [], []
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
        relief_application_status=relief_status,
        manufacturing_status=(
            "V_MITER_FACTORY_R_BA_MEASURED_INPUT_UNCERTIFIED"
            if isinstance(defaults, VMiterFactoryMeasuredInputs)
            else "V_MITER_FACTORY_R_BA_DEFAULT_UNCERTIFIED"
        ),
    )
