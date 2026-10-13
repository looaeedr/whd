# -*- coding: utf-8 -*-
"""DXF-backed receiving large-ear physical mounting dimensions.

Independent acceptance numbers were measured from the ORIGINAL user drawing
受電耳朵.dxf and plate drawing 受電箱底板.dxf; these are not computed by the
policy under test. The source-file fingerprints are in the manufacturing spec.
"""
from __future__ import annotations

import pytest

from ae_engine.receiving_weld_ear_policy import resolve_receiving_large_weld_ear_fit


@pytest.mark.parametrize(
    "row_pitch,expected_slot_pair",
    [(210.0, (0, 3)), (140.0, (1, 2))],
)
def test_big_receiving_weld_ear_mates_either_bottom_plate(row_pitch, expected_slot_pair):
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800.0,
        box_side_thickness_mm=2.0,
        fixing_hole_pitch_x_mm=670.0,
        fixing_hole_pitch_y_mm=row_pitch,
    )
    # Independent DXF facts: 670 assembled transverse fixing centers,
    # single large ear longitudinal slot positions 0/35/175/210 and 86 mm
    # from the nominated welding edge to the slot center. Ear stock is T3.
    assert fit.fixing_center_from_outer_side_mm == pytest.approx(65.0)
    assert fit.fixing_center_from_inside_skin_mm == pytest.approx(63.0)
    assert fit.ear_weld_edge_to_hole_center_mm == pytest.approx(86.0)
    assert fit.nominal_fold_from_weld_edge_mm == pytest.approx(23.0)
    assert fit.ear_thickness_mm == pytest.approx(3.0)
    assert fit.slot_pair_indexes == expected_slot_pair


def test_ear_65_mm_is_outside_datum_not_bend_or_inside_skin_dimension():
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800.0, box_side_thickness_mm=2.0,
        fixing_hole_pitch_x_mm=670.0, fixing_hole_pitch_y_mm=210.0,
    )
    assert fit.fixing_center_from_outer_side_mm - fit.fixing_center_from_inside_skin_mm == 2
    assert fit.nominal_fold_from_weld_edge_mm != 65
    assert fit.nominal_fold_from_weld_edge_mm != 63
    assert fit.nominal_fold_from_weld_edge_mm + fit.fixing_center_from_inside_skin_mm == 86


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"box_outer_width_mm": 750.0}, "W=800"),
        ({"box_side_thickness_mm": -2.0}, "positive"),
        ({"box_side_thickness_mm": 3.0}, "T=2"),
        ({"fixing_hole_pitch_x_mm": 732.0}, "ASSEMBLED.*670"),
        ({"fixing_hole_pitch_y_mm": 200.0}, "210 or 140"),
        ({"ear_thickness_mm": 2.0}, "T=3"),
        ({"ear_weld_edge_to_hole_center_mm": 85.0}, "86"),
    ],
)
def test_weld_ear_unverified_dimensions_fail_closed(kwargs, reason):
    source = {
        "box_outer_width_mm": 800.0,
        "box_side_thickness_mm": 2.0,
        "fixing_hole_pitch_x_mm": 670.0,
        "fixing_hole_pitch_y_mm": 140.0,
    }
    source.update(kwargs)
    with pytest.raises(ValueError, match=reason):
        resolve_receiving_large_weld_ear_fit(**source)


def test_bottom_fixing_plate_part_identity_and_original_2d_source():
    from ae_engine.receiving_base_fixing_plate import (
        receiving_base_fixing_plate_previews, MANUFACTURING_STATUS,
    )
    snapshot = {"model": "受電箱", "w": 800, "t": 2,
                "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"}}
    parts = receiving_base_fixing_plate_previews(
        snapshot, available_parts=("box_body", "base_plate"),
    )
    assert [p.part_id for p in parts] == [
        "base_plate:fixing_plate:left", "base_plate:fixing_plate:right",
    ]
    assert [p.display_name for p in parts] == [
        "底板固定片（左）", "底板固定片（右）",
    ]
    for part in parts:
        assert part.parent_part_id == "base_plate"
        assert part.stock_thickness_mm == 3
        assert part.nominal_source_outline_mm == (256, 105)
        assert part.nominal_source_slot_centers_mm == (
            (23, 86), (58, 86), (198, 86), (233, 86),
        )
        assert part.source_slot_size_mm == (25, 11)
        assert part.source_top_corner_radius_mm == 5
        assert part.nominal_fold_from_weld_edge_mm == 23
        assert part.applicable_slot_pair_indexes == (0, 3)
        assert part.manufacturing_status == MANUFACTURING_STATUS
        assert part.manufacturing_ready is False
    # Same physical fixing plate, only an alternative hole pair for center base.
    center = receiving_base_fixing_plate_previews(
        {**snapshot, "receiving_base_plate": {"pattern": "CENTER_DOUBLE_SIDE_FOLD"}},
        available_parts=("box_body", "base_plate"),
    )
    assert [p.part_id for p in center] == [p.part_id for p in parts]
    assert all(p.applicable_slot_pair_indexes == (1, 2) for p in center)


@pytest.mark.parametrize("snapshot,available", [
    ({"model": "金庫型", "w": 800, "t": 2}, ("base_plate",)),
    ({"model": "受電箱", "w": 750, "t": 2}, ("base_plate",)),
    ({"model": "受電箱", "w": 800, "t": 3}, ("base_plate",)),
    ({"model": "受電箱", "w": 800, "t": 2}, ("box_body",)),
])
def test_bottom_fixing_plate_not_invented_for_other_families_or_unknown_geometry(
    snapshot, available,
):
    from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
    assert receiving_base_fixing_plate_previews(snapshot, available_parts=available) == ()
