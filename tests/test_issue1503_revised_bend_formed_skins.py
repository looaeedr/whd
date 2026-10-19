# -*- coding: utf-8 -*-
"""The revised fixed-plate BEND was supplied: build and test its formed 3D."""
from copy import deepcopy

import pytest

from ae_engine.receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from ae_engine.receiving_base_fixing_plate_geometry import (
    SOURCE_DXF_SHA256, build_fixing_plate_source_render_data,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


@pytest.mark.parametrize("factory", (_assembled, _two_tier))
def test_actual_t2_source_bend23_forms_one_or_two_tiers_with_real_side_wall_axes(factory):
    snapshot = factory()
    two = factory is _two_tier
    owners = [
        f"base_plate:fixing_plate:nfb_layer:{tier}:{side}"
        if two else f"base_plate:fixing_plate:{side}"
        for tier in range(2 if two else 1)
        for side in ("left", "right")
    ]
    result = [
        build_receiving_formed_fixing_plate_skins(snapshot, owner)
        for owner in owners
    ]
    assert len({r.part_id for r in result}) == len(owners)
    assert len(result) == (4 if two else 2)
    assert [r.side_wall_inside_world_x_mm for r in result] == (
        [-398., 398., -398., 398.] if two else [-398., 398.]
    )
    assert [r.source_to_cabinet_hole_x_mm for r in result] == (
        [-335., 335., -335., 335.] if two else [-335., 335.]
    )
    assert [r.fold_station_world_x_mm for r in result] == (
        [-397., 397., -397., 397.] if two else [-397., 397.]
    )
    assert all(
        r.source_bend_y_mm == 23.0 and
        r.actual_mid_surface_hinge_y_mm == 22.0 and
        r.side_wall_skin_contact_x_verified and
        r.source_sheet_t_mm == 2.0 and
        r.signed_source_fold_degrees == 90.0 and
        r.source_bend_verified and
        r.actual_signed_forming_constructed and
        not r.weld_contact_verified and
        not r.manufacturing_ready and
        r.mapped_world_middle and r.mapped_world_skins
        for r in result
    )
    for row in result:
        source = build_fixing_plate_source_render_data(
            row.part_id, snapshot=snapshot,
        )
        assert source.metadata["source_dxf_sha256"] == SOURCE_DXF_SHA256
        assert source.metadata["source_bend_verified"] is True
        # All UV source faces must survive the 3D mapping, including the
        # original four CUTTING slots (do not replace by filled rectangles).
        assert len(row.mapped_world_skins) == 2*len(row.mapped_world_middle)
        uv = [corner for face in row.mapped_world_middle for corner in face.flat]
        assert min(pt[0] for pt in uv) == pytest.approx(0.0, abs=0.02)
        assert max(pt[0] for pt in uv) == pytest.approx(256.0, abs=0.02)
        assert min(pt[1] for pt in uv) == pytest.approx(0.0, abs=0.02)
        assert max(pt[1] for pt in uv) == pytest.approx(105.0, abs=0.02)
        mid_z = [p[2] for face in row.mapped_world_middle for p in face.local]
        assert min(mid_z) == pytest.approx(row.parent_base_back_skin_world_z_mm-23.)
        assert max(mid_z) == pytest.approx(row.parent_base_back_skin_world_z_mm-1.)
        # The vertical fold's physical 2mm skin touches the side-wall
        # inside skin exactly; the original source y=23 BEND stays intact.
        flange_skin_x = [
            pt[0] for tri in row.mapped_world_skins
            for uv, pt in zip(tri.flat, tri.world)
            if uv[1] < 21.99
        ]
        assert flange_skin_x
        assert row.side_wall_inside_world_x_mm == pytest.approx(
            min(flange_skin_x) if row.side == "left" else max(flange_skin_x),
            abs=1e-6,
        )


def test_real_source_flange_points_back_from_base_not_through_perforated_face():
    snapshot = _assembled()
    row = build_receiving_formed_fixing_plate_skins(
        snapshot, "base_plate:fixing_plate:left",
    )
    # The physically supplied y=23 BEND divides original weld leg from the
    # perforated face; +90 creates a rear/negative-Z leg.
    leg = [world_pt for face in row.mapped_world_middle
           for uv,world_pt in zip(face.flat, face.local)
           if uv[1] <= 0.05]
    face = [world_pt for item in row.mapped_world_middle
            for uv,world_pt in zip(item.flat,item.local)
            if uv[1] >= 83.95]
    assert leg and face
    assert max(pt[2] for pt in leg) < min(pt[2] for pt in face)-20
    assert row.fold_station_world_x_mm > row.side_wall_inside_world_x_mm
    # The source's finished X hole datum is 84 - (21+2) + 2 = 63.
    assert row.source_to_cabinet_hole_x_mm - row.side_wall_inside_world_x_mm == 63.


def test_other_bay_or_unknown_source_must_not_get_formed_source_mesh():
    snapshot = _two_tier()
    snapshot["_receiving_runtime_selection"]["bay_id"] = "invalid-bay"
    with pytest.raises(ValueError, match="OWNER_OR_Z_UNVERIFIED"):
        build_receiving_formed_fixing_plate_skins(
            snapshot, "base_plate:fixing_plate:nfb_layer:0:left",
        )
    snapshot = _assembled()
    with pytest.raises(ValueError, match="OWNER_OR_Z_UNVERIFIED"):
        build_receiving_formed_fixing_plate_skins(
            snapshot, "base_plate:fixing_plate:nfb_layer:7:right",
        )
    unsubmitted = deepcopy(snapshot)
    unsubmitted["nfb_config_submitted"] = False
    with pytest.raises(ValueError, match="REQUIRES_SUBMITTED"):
        build_receiving_formed_fixing_plate_skins(
            unsubmitted, "base_plate:fixing_plate:left",
        )
