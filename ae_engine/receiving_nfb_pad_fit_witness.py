# -*- coding: utf-8 -*-
"""Independent quantitative PAD-to-actual-Base T2 seating witness (#1503).

Derived from FULL folded world triangle bounds and current source sheet
thickness, not an approval boolean or a paper DXF location. Failing a
seat/depth test is evidence against release, not a reason to skip inspection.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite


@dataclass(frozen=True)
class PadBaseSeatingWitness:
    physical_id: str
    base_front_z_mm: float
    base_back_z_mm: float
    tab_tip_world_z_mm: float
    tab_insertion_mm: float
    full_thickness_required_mm: float
    tab_back_skin_shortfall_mm: float
    regular_leg_front_gap_mm: float
    all_four_real_cut_squares_verified: bool
    full_thickness_seated: bool
    actual_volume_collision_verified: bool = False
    manufacturing_ready: bool = False


def inspect_pad_base_seating(skin, pad_draft) -> PadBaseSeatingWitness:
    """Inspect geometry after cut-square ownership and rotated tab fit passed.

    The original T2 CAD geometry can currently reach only 1 mm into the
    2-mm base (sharp neutral sheet model). Report that failed interface
    honestly. Never reverse-engineer a fake extra 1 mm by shifting the whole
    spacer and losing its source-defined NFB mounting Z.
    """
    from .assembly_geometry_primitives import triangle_bounds
    from .receiving_nfb_pad_generator import read_pad_tooling_rule
    if (skin.part_id != pad_draft.part_id
            or skin.parent_base_id != pad_draft.parent_base_id
            or skin.owner_hole_id != pad_draft.owner_hole_id
            or skin.manufacturing_ready or pad_draft.manufacturing_ready
            or not skin.four_tab_mesh_mating_verified):
        raise ValueError("PAD_FIT_REAL_OWNER_AND_FOUR_CUTS_REQUIRED")
    p=pad_draft.pattern
    t=float(p.plate_thickness_mm)
    base=float(skin.base_front_world_z_mm)
    bounds=triangle_bounds(skin.world_triangles)
    if bounds is None or not isfinite(t) or t <= 0 or not isfinite(base):
        raise ValueError("PAD_FIT_ACTUAL_Z_SOURCE_MISSING")
    low,high=map(float,bounds[2])
    if (not isfinite(low) or not isfinite(high)
            or not isclose(high,base+float(p.rise_mm),
                           rel_tol=0,abs_tol=1e-4)):
        raise ValueError("PAD_FIT_SELECTED_NFB_UPPER_SKIN_DRIFT")
    rule=read_pad_tooling_rule()
    if rule.revision!=p.tooling_revision:
        raise ValueError("PAD_FIT_TOOLING_SOURCE_CHANGED")
    insertion=max(0.,base-low)
    shortfall=max(0.,t-insertion)
    # On the source blank the four tabs extend down exactly
    # tab_projection_mm beyond the regular long-leg end.
    regular_gap=low+rule.tab_projection_mm-base
    seated=(isclose(shortfall,0.,rel_tol=0,abs_tol=1e-4)
            and isclose(regular_gap,0.,rel_tol=0,abs_tol=1e-4))
    return PadBaseSeatingWitness(
        physical_id=pad_draft.part_id,
        base_front_z_mm=base,base_back_z_mm=base-t,
        tab_tip_world_z_mm=low,
        tab_insertion_mm=insertion,
        full_thickness_required_mm=t,
        tab_back_skin_shortfall_mm=shortfall,
        regular_leg_front_gap_mm=regular_gap,
        all_four_real_cut_squares_verified=True,
        full_thickness_seated=seated,
        actual_volume_collision_verified=False,
        manufacturing_ready=False,
    )


def require_manufacturable_pad_base_interface(witness: PadBaseSeatingWitness) -> None:
    """Hard physical gate before any formal manufacturing authorization."""
    if not isinstance(witness,PadBaseSeatingWitness):
        raise TypeError("PAD_MFG_SOURCE_FIT_WITNESS_REQUIRED")
    if not witness.all_four_real_cut_squares_verified:
        raise ValueError("PAD_MFG_FOUR_REAL_BASE_CUTS_REQUIRED")
    if not witness.full_thickness_seated:
        raise ValueError(
            "PAD_MFG_FULL_BASE_SEAT_NOT_VERIFIED:"
            f" tab_shortfall_mm={witness.tab_back_skin_shortfall_mm:.6f};"
            f" regular_leg_gap_mm={witness.regular_leg_front_gap_mm:.6f}"
        )
    if not witness.actual_volume_collision_verified:
        raise ValueError("PAD_MFG_TRUE_SOLID_COLLISION_NOT_VERIFIED")
    # Separate production drawing/CHECK-Q release remains independently
    # guarded even if true-skin seating and real volume checks pass.
    if not witness.manufacturing_ready:
        raise ValueError("PAD_MFG_PART_AND_PAIRED_BASE_CHECK_Q_NOT_APPROVED")
