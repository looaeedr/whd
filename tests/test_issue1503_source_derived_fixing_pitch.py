# -*- coding: utf-8 -*-
"""#1503 non-W800 SOURCE-backed fixing-hole pitch, independent of cabinet T.

All expected values below follow real 固定片.dxf T2/BEND23: the hole centre
is 84 - 23 + 2 = 63 mm from the actual cabinet SIDE inside skin.
No bend compensation; no whole-cabinet / PAD / weld-workmanship certification.
"""
import pytest

from ae_engine.receiving_weld_ear_policy import (
    receiving_source_fixing_pitch_x_mm,
    resolve_receiving_large_weld_ear_fit,
)
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_base_fixing_plate_mating import (
    resolve_base_fixing_pair_xy_mating,
)


@pytest.mark.parametrize("width,side_t,pitch,inside_x", (
    (800., 2., 670., 398.),
    (750., 2., 620., 373.),
    (900., 2., 770., 448.),
    (800., 3., 668., 397.),
))
@pytest.mark.parametrize("pattern,y_pitch,pair", (
    ("LEFT_FLAT_SIDE", 210., (0, 3)),
    ("RIGHT_FLAT_SIDE", 210., (0, 3)),
    ("CENTER_DOUBLE_SIDE_FOLD", 140., (1, 2)),
))
def test_source_plate_pitches_follow_actual_box_inside_skins(
    width, side_t, pitch, inside_x, pattern, y_pitch, pair,
):
    # Cabinet T and fixed-plate T are independent. This is an XY contact
    # source proof, not a claim that T3 center-fold Base Plate can manufacture.
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=width, box_side_thickness_mm=side_t,
    ) == pytest.approx(pitch)
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=width, box_side_thickness_mm=side_t,
        fixing_hole_pitch_x_mm=pitch, fixing_hole_pitch_y_mm=y_pitch,
    )
    assert fit.fixing_center_from_inside_skin_mm == pytest.approx(63.)
    assert fit.ear_thickness_mm == pytest.approx(2.)
    assert fit.nominal_fold_from_weld_edge_mm == pytest.approx(23.)
    assert fit.slot_pair_indexes == pair

    snapshot = {
        "model": "受電箱", "w": width, "t": side_t,
        "receiving_base_plate": {"pattern": pattern},
    }
    previews = receiving_base_fixing_plate_previews(
        snapshot, available_parts=("base_plate",),
    )
    assert len(previews) == 2
    assert all(p.stock_thickness_mm == 2. and
               p.nominal_fold_from_weld_edge_mm == 23. for p in previews)
    left, right = resolve_base_fixing_pair_xy_mating(snapshot)
    assert (left.inside_skin_world_x_mm, right.inside_skin_world_x_mm) == pytest.approx(
        (-inside_x, inside_x)
    )
    assert (left.selected_fixing_world_x_mm,
            right.selected_fixing_world_x_mm) == pytest.approx(
        (-pitch/2., pitch/2.)
    )
    assert all(row.nominal_fold_from_weld_edge_mm == 23.
               and row.factory_bend_compensation_mm == 0.
               and not row.manufacturing_approved for row in (left, right))


@pytest.mark.parametrize("width,side_t", ((120., 2.), (800., 0.), (float("nan"), 2.)))
def test_no_physical_source_overlap_rejects_invalid_cabinet(width, side_t):
    with pytest.raises(ValueError):
        receiving_source_fixing_pitch_x_mm(
            box_outer_width_mm=width, box_side_thickness_mm=side_t,
        )


def test_stale_670_pitch_does_not_silently_mate_different_cabinet():
    with pytest.raises(ValueError, match="source-folded EAR/side-skin"):
        resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=750., box_side_thickness_mm=2.,
            fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=140.,
        )
