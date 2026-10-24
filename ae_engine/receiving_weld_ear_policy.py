# -*- coding: utf-8 -*-
"""Receiving source-derived large fixing-plate / bottom-plate hole contract.

Factory positioning policy only. This shop does NOT use bend
compensation; no K-factor, bend deduction or bend allowance is a release gate.
Actual new fixed-plate BEND comes from uploaded 固定片.dxf 2026-10-18; prior 受電耳朵.dxf policy is superseded. Base Plate source remains independent.
(2026-10-09); see docs/manufacturing/receiving-large-weld-ear.md.

W800/T2 has an assembled 670-mm fixing pitch, derived from the source
T2/BEND23 fixing plate which places the slot centre 63 mm inside the side
skin. Other cabinet widths must rederive that transverse pitch from their
actual inside side-wall skin. Longitudinal pitches are 210/140.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

RECEIVING_REFERENCE_BOX_OUTER_WIDTH_MM = 800.0
RECEIVING_ASSEMBLED_FIXING_PITCH_X_MM = 670.0
RECEIVING_BASE_PLATE_FIXING_PITCH_Y_MM = (210.0, 140.0)
LARGE_EAR_SLOT_CENTERS_FROM_FIRST_MM = (0.0, 35.0, 175.0, 210.0)
LARGE_EAR_EDGE_TO_HOLE_CENTER_MM = 84.0
LARGE_EAR_MATERIAL_THICKNESS_MM = 2.0
LARGE_EAR_SOURCE_BEND_MM = 23.0
DIMENSION_TOLERANCE_MM = 1e-6


@dataclass(frozen=True)
class ReceivingLargeWeldEarFit:
    box_outer_width_mm: float
    box_side_thickness_mm: float
    fixing_hole_pitch_x_mm: float
    fixing_hole_pitch_y_mm: float
    ear_thickness_mm: float
    fixing_center_from_outer_side_mm: float
    fixing_center_from_inside_skin_mm: float
    ear_weld_edge_to_hole_center_mm: float
    nominal_fold_from_weld_edge_mm: float
    slot_pair_indexes: tuple[int, int]


def receiving_source_fixing_pitch_x_mm(
    *, box_outer_width_mm: float, box_side_thickness_mm: float,
) -> float:
    """Installed LEFT/RIGHT fixing-hole pitch from the real T2 source.

    This computes only the transverse source-mating datum. The full
    manufacturing geometry must still prove true contact and hole geometry.
    For W800/T2: inside side skins at +/-398, source slot centre 63 from
    each inside skin, so X = +/-335 and pitch = 670. No bend compensation.
    """
    if isinstance(box_outer_width_mm, bool) or isinstance(box_side_thickness_mm, bool):
        raise ValueError("Receiving cabinet width and side thickness must not be boolean")
    try:
        w, side_t = float(box_outer_width_mm), float(box_side_thickness_mm)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Receiving cabinet width and side thickness must be finite and positive") from exc
    if not all(isfinite(v) for v in (w, side_t)) or side_t <= 0:
        raise ValueError("Receiving cabinet width and side thickness must be finite and positive")
    # From current 固定片.dxf: Y-hole 84, source BEND23, EAR T2.
    # The fixed plate's thickness is independent of the cabinet side's T.
    inside_offset = (
        LARGE_EAR_EDGE_TO_HOLE_CENTER_MM - LARGE_EAR_SOURCE_BEND_MM
        + LARGE_EAR_MATERIAL_THICKNESS_MM
    )
    pitch = (w - 2.0 * side_t) - 2.0 * inside_offset
    if pitch <= DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving cabinet too narrow for source fixed plate")
    return float(pitch)


def resolve_receiving_large_weld_ear_fit(
    *, box_outer_width_mm: float, box_side_thickness_mm: float,
    fixing_hole_pitch_x_mm: float, fixing_hole_pitch_y_mm: float,
    ear_weld_edge_to_hole_center_mm: float = LARGE_EAR_EDGE_TO_HOLE_CENTER_MM,
    ear_thickness_mm: float = LARGE_EAR_MATERIAL_THICKNESS_MM,
) -> ReceivingLargeWeldEarFit:
    """Resolve the nominal fold reference relative to the side-wall INSIDE skin.

    For 800/T2, assembled fixing X pitch 670:
      center from outer box side = (800 - 670)/2 = 65
      center from inside side-wall skin = 65 - 2 = 63
      new 固定片.dxf hole center from bottom weld edge = 84
      real source BEND line = 21 + ear T = 21 + 2 = 23
      formed hole center from INSIDE weld skin = 84 - 23 + 2 = 63.

    All distances above are physical finished-position datums. 23 mm is explicitly PRESENT on the current source BEND layer. It is
    neither a bend allowance nor a K-factor or a guessed press-brake setting.
    Actual factory process uses no bend compensation. Do not require an
    inside-radius/K-factor/bend-allowance signoff to calculate this fit.
    The source BEND is verified at y=23 for the T2 file. Signed folding
    direction, real welding contact face and Z still need independent checks.
    """
    values = (
        box_outer_width_mm, box_side_thickness_mm,
        fixing_hole_pitch_x_mm, fixing_hole_pitch_y_mm,
        ear_weld_edge_to_hole_center_mm, ear_thickness_mm,
    )
    if any(isinstance(v, bool) for v in values):
        raise ValueError("Receiving weld-ear dimensions must be finite")
    try:
        physical = tuple(float(v) for v in values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Receiving weld-ear dimensions must be finite") from exc
    if not all(isfinite(v) for v in physical):
        raise ValueError("Receiving weld-ear dimensions must be finite")
    box_w, side_t, pitch_x, pitch_y, edge_to_hole, ear_t = physical
    if side_t <= 0 or ear_t <= 0 or edge_to_hole <= 0:
        raise ValueError("Receiving weld-ear sheet thicknesses and edge reference must be positive")
    expected_pitch = receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=box_w, box_side_thickness_mm=side_t,
    )
    if abs(pitch_x - expected_pitch) > DIMENSION_TOLERANCE_MM:
        raise ValueError(
            "Receiving fixing pitch must match source-folded EAR/side-skin "
            f"contact: expected X={expected_pitch:g}, got {pitch_x:g}"
        )
    if abs(ear_t - LARGE_EAR_MATERIAL_THICKNESS_MM) > DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving revised fixed-plate drawing is T=2")
    if abs(edge_to_hole - LARGE_EAR_EDGE_TO_HOLE_CENTER_MM) > DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving revised fixed-plate source hole center must be 84 mm")
    if abs(pitch_y - 210.0) <= DIMENSION_TOLERANCE_MM:
        pair = (0, 3)
    elif abs(pitch_y - 140.0) <= DIMENSION_TOLERANCE_MM:
        pair = (1, 2)
    else:
        raise ValueError("Receiving large ear fits only the 210 or 140 mm fixing-hole rows")
    if abs(
        LARGE_EAR_SLOT_CENTERS_FROM_FIRST_MM[pair[1]]
        - LARGE_EAR_SLOT_CENTERS_FROM_FIRST_MM[pair[0]] - pitch_y
    ) > DIMENSION_TOLERANCE_MM:
        raise ValueError("large-ear selected slot pair does not match the physical pitch")

    from_outer = (box_w - pitch_x) / 2.0
    from_inside = from_outer - side_t
    # Current source BEND23 makes the EAR hole 63 mm from the side inside
    # skin, regardless of cabinet W/side T. Do not bend-compensate or
    # confuse cabinet thickness with the fixed-plate material thickness.
    nominal_fold = edge_to_hole - from_inside + ear_t
    if abs(nominal_fold - LARGE_EAR_SOURCE_BEND_MM) > DIMENSION_TOLERANCE_MM:
        raise ValueError("REVISED_EAR_SOURCE_BEND_RULE_MISMATCH")
    if from_inside <= 0 or nominal_fold <= 0 or nominal_fold >= edge_to_hole:
        raise ValueError("Receiving ear cannot mate the selected cabinet inside-side face")
    return ReceivingLargeWeldEarFit(
        box_outer_width_mm=box_w,
        box_side_thickness_mm=side_t,
        fixing_hole_pitch_x_mm=pitch_x,
        fixing_hole_pitch_y_mm=pitch_y,
        ear_thickness_mm=ear_t,
        fixing_center_from_outer_side_mm=from_outer,
        fixing_center_from_inside_skin_mm=from_inside,
        ear_weld_edge_to_hole_center_mm=edge_to_hole,
        nominal_fold_from_weld_edge_mm=nominal_fold,
        slot_pair_indexes=pair,
    )
