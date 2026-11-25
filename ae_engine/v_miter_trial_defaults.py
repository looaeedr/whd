# -*- coding: utf-8 -*-
"""#3317 explicit Engine-owned *unverified* starting values for V-miter CHECK.

These are generic trial assumptions, NOT measured bend tooling, a calibrated
neutral axis, a certified relief, or permission to export CNC toolpaths.
The operator's real PartSpec thickness and authored second fold angle stay
authoritative.  Passing independently measured overrides to the existing
solver must remain possible; no Engine manufacturing route calls this helper.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .sheetmetal_geometry_core import GeometryError
from .v_miter_corner_source import VMiterReliefMode, _finite


DEFAULT_V_MITER_TRIAL_INNER_R_T = 1.0
DEFAULT_V_MITER_TRIAL_NEUTRAL_K = 0.33
DEFAULT_V_MITER_TRIAL_ROUND_R_T = 1.0
DEFAULT_V_MITER_TRIAL_HOLE_DIAMETER_T = 2.0


@dataclass(frozen=True)
class VMiterTrialParameterDefaults:
    """Engine-derived candidate inputs; every value is uncertified."""

    thickness_mm: float
    second_fold_angle_deg: float
    relief_mode: VMiterReliefMode
    relief_t_factor: float
    relief_dimension_mm: float
    first_inner_radius_mm: float
    second_inner_radius_mm: float
    first_bend_allowance_mm: float
    second_bend_allowance_mm: float
    neutral_axis_k: float = DEFAULT_V_MITER_TRIAL_NEUTRAL_K
    assumption_source: str = "ENGINE_GENERIC_TRIAL_DEFAULT_NOT_SHOP_MEASUREMENT"
    manufacturing_status: str = "V_MITER_R_BA_TRIAL_DEFAULTS_UNCERTIFIED"

    def as_trial_inputs(self) -> dict[str, float]:
        """Optional R/BA + relief arguments for existing CHECK solver only.

        The solver still needs real source BENDs, flange heights and an
        explicitly bounded max_permitted_edge_trim_mm.  It may reject these
        values for a given source; never treat defaults as a pass result.
        """
        return {
            "relief_t_factor": self.relief_t_factor,
            "first_inner_radius_mm": self.first_inner_radius_mm,
            "second_inner_radius_mm": self.second_inner_radius_mm,
            "first_bend_allowance_mm": self.first_bend_allowance_mm,
            "second_bend_allowance_mm": self.second_bend_allowance_mm,
        }


def project_v_miter_trial_parameter_defaults(
    *, thickness_mm: float, second_fold_angle_deg: float,
    relief_mode: VMiterReliefMode | str = VMiterReliefMode.ROUND_R,
) -> VMiterTrialParameterDefaults:
    """Resolve conservative *trial assumptions*, never machining rules.

    The first V fold is fixed 90 degrees.  The other angle must be read
    from the actual Fold source; callers must never invent its value.
    BA = bend_angle_radians * (inside_R + K * T) in this trial model.
    """
    t = _finite(thickness_mm, "thickness_mm", positive=True)
    second_angle = _finite(second_fold_angle_deg, "second_fold_angle_deg")
    if not 0 < second_angle < 180:
        raise GeometryError("second_fold_angle_deg must be between 0 and 180")
    try:
        mode = VMiterReliefMode(relief_mode)
    except (ValueError, TypeError) as exc:
        raise GeometryError("V-miter trial relief mode must be ROUND_R or RELIEF_HOLE") from exc
    factor = (
        DEFAULT_V_MITER_TRIAL_ROUND_R_T if mode is VMiterReliefMode.ROUND_R
        else DEFAULT_V_MITER_TRIAL_HOLE_DIAMETER_T
    )
    r = t * DEFAULT_V_MITER_TRIAL_INNER_R_T
    neutral_radius = r + DEFAULT_V_MITER_TRIAL_NEUTRAL_K * t
    first_ba = math.pi / 2 * neutral_radius
    second_ba = math.radians(second_angle) * neutral_radius
    if not all(math.isfinite(v) and v > 0 for v in (r, neutral_radius, first_ba, second_ba, factor * t)):
        raise GeometryError("V-miter trial defaults exceed finite geometry limits")
    return VMiterTrialParameterDefaults(
        thickness_mm=t, second_fold_angle_deg=second_angle,
        relief_mode=mode, relief_t_factor=factor,
        relief_dimension_mm=t * factor,
        first_inner_radius_mm=r, second_inner_radius_mm=r,
        first_bend_allowance_mm=first_ba,
        second_bend_allowance_mm=second_ba,
    )
