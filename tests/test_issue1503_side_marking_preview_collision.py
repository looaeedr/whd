# -*- coding: utf-8 -*-
"""#1503: source-safe preview of provisional left/right side EAR MARKING."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.manufacturing_render_data import FoldGuide
from ae_engine.receiving_fixed_plate_side_contact import (
    resolve_receiving_ear_side_contact_surfaces,
)
from ae_engine.receiving_fixed_plate_side_mark_preview import (
    build_receiving_ear_side_marking_previews,
)
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from tests.test_issue1503_real_side_uv_backprojection import _project
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _receipts(factory):
    return tuple(_project(c) for c in resolve_receiving_ear_side_contact_surfaces(factory()))


def _owners():
    return {
        side: SimpleNamespace(material=box(0., 0., 1500., 1500.),
                              fold_guides=(), scene=DrawingScene())
        for side in ("box_body:left_side", "box_body:right_side")
    }


@pytest.mark.parametrize("factory,expected", ((_assembled, 8), (_two_tier, 16)))
def test_true_ear_source_receipts_make_separate_side_preview_without_mutation(factory, expected):
    rows = _receipts(factory)
    owners = _owners()
    owners["box_body:left_side"].scene.add_line((10, 10), (20, 10), layer="DATUM")
    staged = build_receiving_ear_side_marking_previews(rows, owners)
    assert set(staged) == set(owners)
    assert sum(p.layer == "MARKING" for scene in staged.values()
               for p in scene.primitives) == expected
    assert len(owners["box_body:left_side"].scene.primitives) == 1
    assert len(owners["box_body:right_side"].scene.primitives) == 0
    assert any(p.layer == "DATUM" for p in staged["box_body:left_side"].primitives)
    assert all(isinstance(p, LinePrimitive) for scene in staged.values()
               for p in scene.primitives)


@pytest.mark.parametrize("layer", ("CUTTING", "BLIND_HOLE", "MARKING"))
def test_original_side_source_hole_and_marking_conflicts_block_preview(layer):
    rows = _receipts(_assembled)
    owners = _owners()
    first = rows[0]
    x, y = first.side_source_flat_boundary[0]
    owners[first.side_piece_id].scene.add_circle((x + 40, y + 10), 3, layer=layer)
    with pytest.raises(ValueError, match="EAR_MARK_PREVIEW_EXISTING_"+layer+"_CONFLICT"):
        build_receiving_ear_side_marking_previews(rows, owners)


def test_original_cutting_edge_and_bend_are_rejected_on_true_patch():
    rows = _receipts(_assembled)
    owners = _owners()
    row = rows[0]
    patch = row.side_source_flat_boundary
    x = (patch[0][0] + patch[1][0]) / 2.
    owners[row.side_piece_id].scene.add_line(
        (x, 0), (x, 1500), layer="CUTTING",
    )
    with pytest.raises(ValueError, match="EXISTING_CUTTING_CONFLICT"):
        build_receiving_ear_side_marking_previews(rows, owners)
    owners = _owners()
    owners[row.side_piece_id].fold_guides = (FoldGuide("x", x, 0, 1500),)
    with pytest.raises(ValueError, match="BEND_CONFLICT"):
        build_receiving_ear_side_marking_previews(rows, owners)


def test_side_sheet_final_material_cutout_blocks_staged_marks():
    rows = _receipts(_assembled)
    owners = _owners()
    row = rows[0]
    a = row.side_source_flat_boundary
    x, y = (a[0][0] + a[1][0]) / 2, (a[0][1] + a[3][1]) / 2
    owners[row.side_piece_id].material = box(0, 0, 1500, 1500).difference(
        box(x - 5, y - 5, x + 5, y + 5)
    )
    with pytest.raises(ValueError, match="FINAL_MATERIAL_CONFLICT"):
        build_receiving_ear_side_marking_previews(rows, owners)


def test_multi_tier_same_side_weld_footprints_cannot_overlap():
    rows = list(_receipts(_two_tier))
    rows[2] = replace(rows[2],
        side_source_flat_boundary=rows[0].side_source_flat_boundary,
        marking_segments=rows[0].marking_segments)
    with pytest.raises(ValueError, match="TIER_COLLISION"):
        build_receiving_ear_side_marking_previews(tuple(rows), _owners())


def test_receipts_cannot_approve_manufacturing_or_borrow_missing_right_side():
    rows = list(_receipts(_assembled))
    with pytest.raises(ValueError, match="UNVERIFIED_RECEIPT"):
        build_receiving_ear_side_marking_previews(
            tuple([replace(rows[0], manufacturing_ready=True), rows[1]]),
            _owners(),
        )
    with pytest.raises(ValueError, match="SIDE_SOURCE_MISSING"):
        build_receiving_ear_side_marking_previews(
            tuple(rows), {"box_body:left_side": _owners()["box_body:left_side"]},
        )
