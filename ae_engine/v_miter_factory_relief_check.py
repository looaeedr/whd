# -*- coding: utf-8 -*-
"""#3317 source-backed Factory V bottom R / circular relief CHECK.

Use the *real perimeter hits* from a separately validated Factory mother,
not the shorter ideal formed contact endpoints. Reuse the existing V-tip
fillet formula; hole geometry is a true source-contained circle. This is
one detached, closed *trial* profile with no certified cutting layers.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Point, Polygon

from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_ideal_mating import VMiterIdealMatingCandidate
from .v_miter_material_trial import VMiterSourceBoundSharpCheck
from .v_miter_factory_fold_check import (
    VMiterFactoryPrecutFoldCheck, project_v_miter_factory_precut_fold_check,
)
from .v_miter_factory_mother_check import VMiterFactoryMotherReplacementCheck
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_relief_trial import _rounded_v_notch_polygon
from .v_miter_trial_defaults import (
    VMiterTrialParameterDefaults, project_v_miter_trial_parameter_defaults,
)
from .v_miter_factory_measurements import (
    VMiterFactoryMeasuredInputs, require_v_miter_factory_measurement_source,
)


@dataclass(frozen=True)
class VMiterFactoryBottomReliefCheck:
    """Source-clipped one-sheet ROUND_R or RELIEF_HOLE, never CNC CUTTING."""

    relief_mode: VMiterReliefMode
    relief_t_factor: float
    relief_dimension_mm: float
    relief_radius_mm: float
    flat_leg_tip_cutback_mm: float
    source_original_area_mm2: float
    original_sharp_remaining_area_mm2: float
    corrected_remaining_area_mm2: float
    corrected_removed_area_mm2: float
    corrected_remaining_outline: tuple[Vec2, ...]
    corrected_removed_outline: tuple[Vec2, ...]
    geometry_model: str = "FACTORY_SOURCE_V_R_OR_HOLE_SINGLE_SHEET_TRIAL"
    manufacturing_status: str = "V_MITER_FACTORY_RELIEF_UNCERTIFIED"


def project_v_miter_factory_bottom_relief_default_check(
    part_spec: DoorPartSpec | EndCapPartSpec,
    render_data: PartRenderData,
    corner_key: str,
    ideal: VMiterIdealMatingCandidate,
    source_check: VMiterSourceBoundSharpCheck,
    factory_fold: VMiterFactoryPrecutFoldCheck,
    first_real_bend: LinePrimitive,
    second_real_bend: LinePrimitive,
    defaults: VMiterTrialParameterDefaults | VMiterFactoryMeasuredInputs,
    factory_mother: VMiterFactoryMotherReplacementCheck | None = None,
) -> VMiterFactoryBottomReliefCheck:
    """Replace the *source-qualified* sharp V tip with supplied R or hole.

    The original 4-type FinalScene cannot be replaced with a guessed
    rectangle; reprove the complete original Factory mother and both
    physical source BENDs. This does not apply relief to folded 3D, remove
    interference, compute a machining fillet/kerf, or authorize export.
    """
    if (not isinstance(part_spec, (DoorPartSpec, EndCapPartSpec))
            or not isinstance(ideal, VMiterIdealMatingCandidate)
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or not isinstance(factory_fold, VMiterFactoryPrecutFoldCheck)
            or not isinstance(defaults, (VMiterTrialParameterDefaults,
                                         VMiterFactoryMeasuredInputs))):
        raise GeometryError("V_MITER_FACTORY_RELIEF_TYPED_SOURCE_REQUIRED")
    if isinstance(defaults, VMiterFactoryMeasuredInputs):
        require_v_miter_factory_measurement_source(
            defaults, part_spec, corner_key, ideal,
        )
    else:
        expected_defaults = project_v_miter_trial_parameter_defaults(
            thickness_mm=part_spec.thickness,
            second_fold_angle_deg=ideal.source.second_fold_angle_deg,
            relief_mode=ideal.source.relief_mode,
        )
        if defaults != expected_defaults:
            raise GeometryError("V_MITER_FACTORY_RELIEF_DEFAULTS_SOURCE_CHANGED")
    validated_fold = project_v_miter_factory_precut_fold_check(
        part_spec, render_data, corner_key, source_check,
        first_real_bend, second_real_bend, factory_mother,
    )
    if factory_fold != validated_fold:
        raise GeometryError("V_MITER_FACTORY_RELIEF_FOLD_SOURCE_CHANGED")

    original_sharp = Polygon(
        (p.x, p.y) for p in source_check.remaining_outline
    )
    sharp_removed = Polygon(
        (p.x, p.y) for p in source_check.removed_corner_outline
    )
    original_mother = original_sharp.union(sharp_removed)
    if (original_mother.geom_type != "Polygon" or original_mother.is_empty
            or not original_mother.is_valid or original_mother.interiors
            or abs(original_mother.area - source_check.source_material_area_mm2) > 1e-6
            or original_sharp.intersection(sharp_removed).area > 1e-6):
        raise GeometryError("V_MITER_FACTORY_RELIEF_MOTHER_STOCK_INVALID")

    apex = ideal.source.bend_intersection
    first = source_check.first_perimeter_hit
    second = source_check.second_perimeter_hit
    arc = tuple(
        (point.x, point.y)
        for point in source_check.removed_corner_outline[1:-1]
    )
    if (not arc or math.hypot(
        source_check.removed_corner_outline[0].x - apex.x,
        source_check.removed_corner_outline[0].y - apex.y,
    ) > 1e-6):
        raise GeometryError("V_MITER_FACTORY_RELIEF_SOURCE_APEX_NOT_PROVEN")

    mode = defaults.relief_mode
    radius = (
        defaults.relief_dimension_mm if mode is VMiterReliefMode.ROUND_R
        else 0.5 * defaults.relief_dimension_mm
    )
    if mode is VMiterReliefMode.ROUND_R:
        removed, cutback = _rounded_v_notch_polygon(
            apex, first, second, arc, radius,
        )
        if removed.difference(sharp_removed.buffer(1e-7)).area > 1e-6:
            raise GeometryError("V_MITER_FACTORY_RELIEF_ROUND_R_OUTSIDE_SOURCE_V")
    elif mode is VMiterReliefMode.RELIEF_HOLE:
        circle = Point(apex.x, apex.y).buffer(radius, resolution=48)
        if not circle.difference(original_mother.buffer(1e-7)).is_empty:
            raise GeometryError("V_MITER_FACTORY_RELIEF_HOLE_OFF_SOURCE_STOCK")
        removed = sharp_removed.union(circle)
        cutback = radius
    else:
        raise GeometryError("V_MITER_FACTORY_RELIEF_MODE_UNSUPPORTED")

    if (removed.geom_type != "Polygon" or removed.is_empty
            or not removed.is_valid or removed.interiors
            or removed.area <= 1e-7
            or not removed.difference(original_mother.buffer(1e-7)).is_empty):
        raise GeometryError("V_MITER_FACTORY_RELIEF_REMOVAL_TOPOLOGY_INVALID")
    remaining = original_mother.difference(removed)
    if (remaining.geom_type != "Polygon" or remaining.is_empty
            or not remaining.is_valid or remaining.interiors
            or remaining.area <= 1e-7):
        raise GeometryError("V_MITER_FACTORY_RELIEF_BREAKS_ONE_SHEET")
    if (not remaining.difference(original_mother.buffer(1e-7)).is_empty
            or abs(original_mother.area - removed.area - remaining.area) > 1e-5):
        raise GeometryError("V_MITER_FACTORY_RELIEF_AREA_OR_SOURCE_MISMATCH")
    return VMiterFactoryBottomReliefCheck(
        relief_mode=mode,
        relief_t_factor=defaults.relief_t_factor,
        relief_dimension_mm=defaults.relief_dimension_mm,
        relief_radius_mm=radius,
        flat_leg_tip_cutback_mm=cutback,
        source_original_area_mm2=original_mother.area,
        original_sharp_remaining_area_mm2=original_sharp.area,
        corrected_remaining_area_mm2=remaining.area,
        corrected_removed_area_mm2=removed.area,
        corrected_remaining_outline=tuple(
            Vec2(float(x), float(y)) for x, y in remaining.exterior.coords
        ),
        corrected_removed_outline=tuple(
            Vec2(float(x), float(y)) for x, y in removed.exterior.coords
        ),
    )
