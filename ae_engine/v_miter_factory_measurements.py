# -*- coding: utf-8 -*-
"""#3317 explicitly supplied physical V-miter bend/relief dimensions.

This is a typed *input* to the existing Factory 2D/3D source solvers, not
evidence of shop measurement or a manufacturing/CUTTING release token.
No neutral-axis K, bend allowance, R/T or relief hole dimension is guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import DoorPartSpec, EndCapPartSpec
from .sheetmetal_geometry_core import GeometryError
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_ideal_mating import VMiterIdealMatingCandidate

_CORNERS = frozenset(("top_left", "top_right", "bottom_left", "bottom_right"))


def _positive_number(value: object, field: str) -> float:
    if type(value) not in (int, float):
        raise GeometryError(f"V_MITER_FACTORY_MEASUREMENT_{field}_INVALID")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise GeometryError(f"V_MITER_FACTORY_MEASUREMENT_{field}_INVALID")
    return number


@dataclass(frozen=True)
class VMiterFactoryMeasuredInputs:
    """Declared shop measurements, still independently UNVERIFIED by Engine.

    'measurement_reference' identifies an external actual sheet / bend sample;
    a string alone does NOT prove the data was measured or calibrated.
    This can never authorize production DXF by itself.
    """

    part_key: str
    corner_key: str
    thickness_mm: float
    second_fold_angle_deg: float
    relief_mode: VMiterReliefMode
    relief_dimension_mm: float
    first_inner_radius_mm: float
    second_inner_radius_mm: float
    first_bend_allowance_mm: float
    second_bend_allowance_mm: float
    measurement_reference: str
    manufacturing_status: str = "V_MITER_FACTORY_MEASURED_INPUT_UNCERTIFIED"

    def __post_init__(self):
        if type(self.part_key) is not str or self.part_key not in ("door", "head", "tail"):
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_PART_INVALID")
        if type(self.corner_key) is not str or self.corner_key not in _CORNERS:
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_CORNER_INVALID")
        if type(self.relief_mode) is not VMiterReliefMode:
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_RELIEF_MODE_INVALID")
        if (type(self.measurement_reference) is not str
                or not self.measurement_reference.strip()):
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_REFERENCE_REQUIRED")
        if self.manufacturing_status != "V_MITER_FACTORY_MEASURED_INPUT_UNCERTIFIED":
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_STATUS_INVALID")
        t = _positive_number(self.thickness_mm, "THICKNESS")
        angle = _positive_number(self.second_fold_angle_deg, "ANGLE")
        if angle >= 180:
            raise GeometryError("V_MITER_FACTORY_MEASUREMENT_ANGLE_INVALID")
        _positive_number(self.relief_dimension_mm, "RELIEF")
        for name, radians in (("first", math.pi / 2), ("second", math.radians(angle))):
            radius = _positive_number(getattr(self, name + "_inner_radius_mm"),
                                      name.upper() + "_R")
            ba = _positive_number(getattr(self, name + "_bend_allowance_mm"),
                                  name.upper() + "_BA")
            # A physical cylindrical neutral axis must lie through T.
            # This verifies consistency only, never invents the machine K.
            k = (ba / radians - radius) / t
            if not math.isfinite(k) or k < -1e-8 or k > 1 + 1e-8:
                raise GeometryError(
                    "V_MITER_FACTORY_MEASUREMENT_R_BA_INCONSISTENT"
                )

    @property
    def relief_t_factor(self) -> float:
        return self.relief_dimension_mm / self.thickness_mm


def require_v_miter_factory_measurement_source(
    measured: VMiterFactoryMeasuredInputs,
    part_spec: DoorPartSpec | EndCapPartSpec,
    corner_key: str,
    ideal: VMiterIdealMatingCandidate,
) -> None:
    """Bind declared dimensions to the *current* real PartSpec/Fold identity."""
    if not isinstance(measured, VMiterFactoryMeasuredInputs):
        raise GeometryError("V_MITER_FACTORY_MEASUREMENT_TYPED_SOURCE_REQUIRED")
    # Re-run on the current object, not an untrusted object-like mapping.
    measured.__post_init__()
    if isinstance(part_spec, DoorPartSpec):
        part = "door"
    elif isinstance(part_spec, EndCapPartSpec):
        part = "tail" if part_spec.is_tail else "head"
    else:
        raise GeometryError("V_MITER_FACTORY_MEASUREMENT_PART_SOURCE_INVALID")
    if (measured.part_key != part or measured.corner_key != corner_key
            or measured.thickness_mm != part_spec.thickness
            or measured.thickness_mm != ideal.source.thickness_mm
            or abs(measured.second_fold_angle_deg -
                   ideal.source.second_fold_angle_deg) > 1e-8
            or measured.relief_mode is not ideal.source.relief_mode):
        raise GeometryError("V_MITER_FACTORY_MEASUREMENT_SOURCE_CHANGED")
