# -*- coding: utf-8 -*-
"""Receiving 800-mm cabinet: large side-weld ear / bottom-plate hole contract.

Factory positioning policy only. This shop does NOT use bend
compensation; no K-factor, bend deduction or bend allowance is a release gate.
Actual new fixed-plate BEND comes from uploaded 固定片.dxf 2026-10-18; prior 受電耳朵.dxf policy is superseded. Base Plate source remains independent.
(2026-10-09); see docs/manufacturing/receiving-large-weld-ear.md.

The 670-mm assembled cross-cabinet fixing pitch belongs to BOTH plate
variants. The long ear has two alternative longitudinal hole pitches:
210 mm (outer pair) and 140 mm (inner pair), not two different ears.
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
    if any(not isfinite(float(v)) for v in values):
        raise ValueError("Receiving weld-ear dimensions must be finite")
    box_w, side_t, pitch_x, pitch_y, edge_to_hole, ear_t = map(float, values)
    if side_t <= 0 or ear_t <= 0 or edge_to_hole <= 0:
        raise ValueError("Receiving weld-ear sheet thicknesses and edge reference must be positive")
    if abs(side_t - 2.0) > DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving large-ear geometry is certified only for side-wall T=2")
    if abs(box_w - RECEIVING_REFERENCE_BOX_OUTER_WIDTH_MM) > DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving large-ear geometry is certified only for nominal box W=800")
    if abs(pitch_x - RECEIVING_ASSEMBLED_FIXING_PITCH_X_MM) > DIMENSION_TOLERANCE_MM:
        raise ValueError("Receiving large-ear plate must have ASSEMBLED fixing pitch X=670")
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
    # Source rule: y_BEND = 21 + EAR material thickness. Its formed
    # hole-to-side-skin relation retains the sheet T without factory
    # compensation: 84 - (21 + 2) + 2 = 63 mm.
    nominal_fold = edge_to_hole - from_inside + ear_t
    if abs(nominal_fold - (21.0 + ear_t)) > DIMENSION_TOLERANCE_MM:
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
