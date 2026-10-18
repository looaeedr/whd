# -*- coding: utf-8 -*-
"""Physical bent T2 EAR -> true cabinet inside-wall contact, NOT UV MARKING."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine.receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from ae_engine.receiving_fixed_plate_side_contact import (
    derive_receiving_ear_side_contact_from_formed_skin,
    resolve_receiving_ear_side_contact_surfaces,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


@pytest.mark.parametrize("factory,count", ((_assembled, 2), (_two_tier, 4)))
def test_actual_folded_ear_contact_skin_is_real_box_side_not_fake_marking(factory, count):
    rows = resolve_receiving_ear_side_contact_surfaces(factory())
    assert len(rows) == count
    assert [r.side_piece_id for r in rows] == [
        "box_body:left_side", "box_body:right_side",
    ]*(count//2)
    assert [r.side_inside_skin_world_x_mm for r in rows] == [
        -398., 398.,
    ]*(count//2)
    assert len({r.ear_part_id for r in rows}) == count
    assert all(r.contact_length_world_y_mm == pytest.approx(256., abs=0.02)
               for r in rows)
    assert all(r.contact_height_world_z_mm == pytest.approx(22., abs=0.02)
               for r in rows)
    assert all(not r.side_flat_uv_backprojection_verified
               and not r.weld_contact_verified
               and not r.manufacturing_ready for r in rows)
    for row in rows:
        assert len(row.world_surface_boundary) == 4
        assert all(p[0] == pytest.approx(row.side_inside_skin_world_x_mm)
                   for p in row.world_surface_boundary)
        assert row.world_surface_boundary[0][1] < row.world_surface_boundary[1][1]
        assert row.world_surface_boundary[0][2] < row.world_surface_boundary[3][2]
    if count == 4:
        assert [r.nfb_layer_index for r in rows] == [0, 0, 1, 1]
        assert len({r.world_surface_boundary[0][2] for r in rows}) == 2


def test_one_tier_source_rechecks_real_panel_uv_not_unapproved_marks():
    snapshot = _assembled()
    row = build_receiving_formed_fixing_plate_skins(
        snapshot, "base_plate:fixing_plate:left",
    )
    quad = derive_receiving_ear_side_contact_from_formed_skin(row)
    assert quad.ear_part_id == row.part_id
    assert quad.base_part_id == row.base_part_id
    assert quad.world_surface_boundary[0][2] == pytest.approx(
        row.parent_base_back_skin_world_z_mm-23.,
    )
    assert quad.world_surface_boundary[3][2] == pytest.approx(
        row.parent_base_back_skin_world_z_mm-1.,
    )


def test_fake_forming_or_forged_mfg_readiness_not_accepted_as_contact():
    row = build_receiving_formed_fixing_plate_skins(
        _assembled(), "base_plate:fixing_plate:left",
    )
    for replacement in (
        replace(row, manufacturing_ready=True),
        replace(row, weld_contact_verified=True),
        replace(row, source_bend_verified=False),
        replace(row, side_wall_skin_contact_x_verified=False),
        replace(row, mapped_world_skins=()),
    ):
        with pytest.raises(ValueError, match="EAR_SIDE_CONTACT"):
            derive_receiving_ear_side_contact_from_formed_skin(replacement)


def test_other_bay_owners_do_not_borrow_contact_weld_surface():
    snap = _two_tier()
    stale = deepcopy(snap)
    stale["_receiving_runtime_selection"]["bay_id"] = "wrong-bay"
    with pytest.raises(ValueError):
        resolve_receiving_ear_side_contact_surfaces(stale)
