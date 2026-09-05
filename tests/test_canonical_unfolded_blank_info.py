# -*- coding: utf-8 -*-
from shapely.geometry import box

from ae_engine.manufacturing_api import (
    BoxBodyPieceRenderData,
    BoxBodyStructureRenderData,
    PartRenderData,
    measure_unfolded_blanks,
)


def _render(x0, y0, x1, y1):
    return PartRenderData(scene=object(), material=box(x0, y0, x1, y1))


def test_single_sheet_blank_is_measured_from_final_material_not_fold_profile():
    render = _render(-5, -7, 123, 45)
    blanks = measure_unfolded_blanks(render, part_key="head")

    assert len(blanks) == 1
    blank = blanks[0]
    assert blank.part_key == "head"
    assert blank.width == 128.0
    assert blank.height == 52.0
    assert blank.area == 128.0 * 52.0
    assert blank.bounds == (-5.0, -7.0, 123.0, 45.0)


def test_multi_piece_box_body_returns_one_blank_per_physical_sheet_not_preview_envelope():
    pieces = (
        BoxBodyPieceRenderData("left_side", "left_side", 0, 100, (), _render(0, 0, 365, 596)),
        BoxBodyPieceRenderData("back", "back", 100, 700, (), _render(-20, 5, 779, 601)),
        BoxBodyPieceRenderData("right_side", "right_side", 700, 800, (), _render(0, 0, 365, 596)),
    )
    # Deliberately absurd preview envelope: this must never be reported as one blank.
    preview = _render(0, 0, 9999, 9999)
    render = BoxBodyStructureRenderData("THREE_PIECE_SIDE_BACK_SPLIT", pieces, preview)

    blanks = measure_unfolded_blanks(render, part_key="box_body")

    assert [b.part_key for b in blanks] == [
        "box_body:left_side", "box_body:back", "box_body:right_side"
    ]
    assert [(b.width, b.height) for b in blanks] == [
        (365.0, 596.0), (799.0, 596.0), (365.0, 596.0)
    ]
    assert all(b.width < 9999 for b in blanks)


def test_blank_area_reflects_final_relief_even_when_outer_blank_size_is_unchanged():
    full = PartRenderData(scene=object(), material=box(0, 0, 100, 50))
    cut = PartRenderData(scene=object(), material=box(0, 0, 100, 50).difference(box(90, 40, 100, 50)))

    a = measure_unfolded_blanks(full, part_key="head")[0]
    b = measure_unfolded_blanks(cut, part_key="tail")[0]

    assert (a.width, a.height) == (b.width, b.height) == (100.0, 50.0)
    assert a.area == 5000.0
    assert b.area == 4900.0
