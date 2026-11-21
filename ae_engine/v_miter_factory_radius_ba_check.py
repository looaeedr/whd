# -*- coding: utf-8 -*-
"""#3317 source-qualified Factory V geometry -> real default R/BA/T CHECK.

An Engine-only bridge to the existing cylindrical bend solver. The pre-corner
Factory source, real BEND identities and post-V T mesh must be reverified
before the trial. Generic R/K is not a measured press-brake setting and no
production CUTTING/BEND/MARKING is published.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Polygon

from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_ideal_mating import VMiterIdealMatingCandidate
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck, project_v_miter_source_material_trial,
)
from .v_miter_factory_fold_check import VMiterFactoryPrecutFoldCheck
from .v_miter_factory_mother_check import VMiterFactoryMotherReplacementCheck
from .v_miter_factory_true_t_check import (
    project_v_miter_factory_post_v_true_t_check, _formed_perimeter_edges,
)
from .v_miter_radius_ba_interface_trial import (
    VMiterRadiusBAFullSheetCheck, project_v_miter_radius_ba_full_sheet_check,
)
from .v_miter_trial_defaults import (
    VMiterTrialParameterDefaults, project_v_miter_trial_parameter_defaults,
)


@dataclass(frozen=True)
class VMiterFactoryRadiusBADefaultCheck:
    """Source-backed R/BA/T curved sheet CHECK, not machining permission."""

    full_sheet: VMiterRadiusBAFullSheetCheck
    trim_search_cap_mm: float
    first_formed_perimeter_edges: tuple
    second_formed_perimeter_edges: tuple
    geometry_model: str = "FACTORY_PROVEN_SOURCE_DEFAULT_R_BA_CURVED_T_CHECK"
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
    defaults: VMiterTrialParameterDefaults,
    factory_mother: VMiterFactoryMotherReplacementCheck | None = None,
) -> VMiterFactoryRadiusBADefaultCheck:
    """Solve default cylindrical R/BA against the verified physical mother.

    Uses a temporary source scene only. A trial-only 6T/half-first-flange
    search cap is *not* a permissible factory machining trim. The original
    FinalScene and all public manufactured layers are unchanged.
    """
    if (not isinstance(part_spec, (DoorPartSpec, EndCapPartSpec))
            or not isinstance(defaults, VMiterTrialParameterDefaults)
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or not isinstance(ideal, VMiterIdealMatingCandidate)
            or not isinstance(factory_fold, VMiterFactoryPrecutFoldCheck)):
        raise GeometryError("V_MITER_FACTORY_R_BA_TYPED_SOURCE_REQUIRED")
    if defaults != project_v_miter_trial_parameter_defaults(
        thickness_mm=part_spec.thickness,
        second_fold_angle_deg=ideal.source.second_fold_angle_deg,
        relief_mode=ideal.source.relief_mode,
    ) or defaults.thickness_mm != ideal.source.thickness_mm:
        raise GeometryError("V_MITER_FACTORY_R_BA_DEFAULTS_SOURCE_CHANGED")

    # Re-prove the actual source BEND objects, independent Factory axes,
    # surviving material, and real post-V T geometry; not a GUI-borrowed
    # rectangle or unproven virtual fold.
    project_v_miter_factory_post_v_true_t_check(
        part_spec, render_data, corner_key, ideal, source_check,
        factory_fold, first_real_bend, second_real_bend,
        first_station_bend, second_station_bend, factory_mother,
    )
    remaining = Polygon((p.x, p.y) for p in source_check.remaining_outline)
    removed = Polygon((p.x, p.y) for p in source_check.removed_corner_outline)
    restored = remaining.union(removed)
    if (restored.geom_type != "Polygon" or restored.is_empty
            or not restored.is_valid or restored.interiors
            or abs(restored.area - source_check.source_material_area_mm2) > 1e-6
            or remaining.intersection(removed).area > 1e-6):
        raise GeometryError("V_MITER_FACTORY_R_BA_RESTORED_STOCK_INVALID")

    # Stage only a private solver source from the proven mother and the
    # already-verified Factory station axes. The staged CUTTING/BEND must
    # never be forwarded to a manufacturing or DXF exporter.
    first = LinePrimitive(first_station_bend.p1, first_station_bend.p2, "BEND")
    second = LinePrimitive(second_station_bend.p1, second_station_bend.p2, "BEND")
    staged = DrawingScene([
        PolylinePrimitive(
            tuple(Vec2(float(x), float(y)) for x, y in restored.exterior.coords),
            "CUTTING", closed=True,
        ), first, second,
    ])
    params = {
        "thickness_mm": defaults.thickness_mm,
        "first_flange_height_mm": ideal.source.first_flange_height_mm,
        "second_flange_height_mm": ideal.source.second_flange_height_mm,
        "second_fold_angle_deg": defaults.second_fold_angle_deg,
        "relief_mode": defaults.relief_mode,
    }
    # Critical parity check: a legitimate curved trial must begin with the
    # EXACT original V cut from the independently qualified Factory stock.
    sharp = project_v_miter_source_material_trial(
        staged, first, second,
        relief_t_factor=defaults.relief_t_factor, **params,
    )
    proposed = Polygon((p.x, p.y) for p in sharp.trial_remaining_outline)
    if proposed.symmetric_difference(remaining).area > 1e-6:
        raise GeometryError("V_MITER_FACTORY_R_BA_IDEAL_SHARP_STOCK_MISMATCH")

    cap = min(6.0 * defaults.thickness_mm,
              0.5 * ideal.source.first_flange_height_mm)
    if not math.isfinite(cap) or cap <= 0:
        raise GeometryError("V_MITER_FACTORY_R_BA_INVALID_TRIAL_TRIM_CAP")
    result = project_v_miter_radius_ba_full_sheet_check(
        staged, first, second,
        max_permitted_edge_trim_mm=cap,
        **params, **defaults.as_trial_inputs(),
    )
    corrected = Polygon((p.x, p.y) for p in result.corrected_check_outline)
    if (corrected.geom_type != "Polygon" or corrected.is_empty
            or not corrected.is_valid or corrected.interiors
            or not corrected.difference(restored.buffer(1e-7)).is_empty):
        raise GeometryError("V_MITER_FACTORY_R_BA_CORRECTION_INVENTS_SOURCE_STOCK")
    return VMiterFactoryRadiusBADefaultCheck(
        full_sheet=result,
        trim_search_cap_mm=cap,
        first_formed_perimeter_edges=_formed_perimeter_edges(
            result.trial.first_formed_skin_triangles,
        ),
        second_formed_perimeter_edges=_formed_perimeter_edges(
            result.trial.second_formed_skin_triangles,
        ),
    )
