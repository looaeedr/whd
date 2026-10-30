# -*- coding: utf-8 -*-
"""#1502: exact Receiving CENTER CUTTING+BENDING measured from original DXF.

Fixture measured from operator-uploaded 受電箱底板(5).dxf
SHA256 cccf060cf6ff704b717dff0edd01d522c559cbf4ca98f5113ad84c9f4160d29b.
The real drawing has W772, H240, twenty CUTTING contour vertices, and
four vertical BENDING lines 40/73/699/732 with 170 mm spans.
These are independent source coordinates, not copied from current algorithm.
"""
import pytest
from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_CENTER,
    build_receiving_base_plate_result,
)

SOURCE_CUTTING = (
    (79, 240), (693, 240), (698, 235), (698, 205),
    (767, 205), (772, 200), (772, 40), (767, 35),
    (698, 35), (698, 5), (693, 0), (79, 0),
    (74, 5), (74, 35), (5, 35), (0, 40),
    (0, 200), (5, 205), (74, 205), (74, 235),
)


def _result(pair=(107, 72)):
    return build_receiving_base_plate_result(
        w=800, h=350, t=2,
        shrink_top=55, shrink_bottom=55,
        shrink_left=85, shrink_right=85,
        bend=20, pattern=RECEIVING_BASE_PATTERN_CENTER,
        nfb_depth_pair_mm=pair,
    )


def test_source_cutting_20_vertices_and_chamfer_are_not_old_twelve_vertex_rectangle():
    result = _result()
    assert (result.width, result.height) == (772, 240)
    assert len(result.outline) == 20
    assert tuple((round(v.x, 5), round(v.y, 5)) for v in result.outline) == SOURCE_CUTTING


def test_source_four_vertical_bends_are_separated_by_true_33_not_false_31():
    result = _result()
    vertical = {bend.name: bend for bend in result.bends if "_left_" in bend.name or "_right_" in bend.name}
    assert {
        name: (bend.p1.x, bend.p1.y, bend.p2.x, bend.p2.y)
        for name, bend in vertical.items()
    } == {
        "receiving_left_40": (40, 35, 40, 205),
        "receiving_left_33": (73, 35, 73, 205),
        "receiving_right_33": (699, 35, 699, 205),
        "receiving_right_40": (732, 35, 732, 205),
    }


def test_center_source_upper_lower_bends_are_35_material_not_flat_side_20():
    result = _result()
    horizontal = [b for b in result.bends if b.p1.y == b.p2.y]
    assert len(horizontal) == 2
    assert {b.p1.y for b in horizontal} == {35, 205}
    assert {b.p2.y for b in horizontal} == {35, 205}
    # The operator sees 37 outside at T2, equal to the X second return:
    # X 33+2T, Y 35+T.
    assert 35 + 2 == 33 + 2*2 == 37


def test_other_depth_pair_preserves_actual_cutting_and_bend_construction():
    result = _result((105, 75))  # delta30, second28, total width762
    assert result.width == 762
    contour = [(v.x, v.y) for v in result.outline]
    assert len(contour) == 20
    assert (69, 5) in contour      # shoulder = first40 + return28 + T2/2
    assert (762 - 69, 205) in contour
    bends = {b.name: b for b in result.bends}
    assert bends["receiving_left_33"].p1.x == 68
    assert bends["receiving_right_33"].p1.x == 762 - 68
    assert bends["receiving_bottom_20"].p1.y == 30
    assert bends["receiving_top_20"].p1.y == 210
