# -*- coding: utf-8 -*-
"""#1502 canonical unfolded UV -> assembled 3D middle-plate witness."""
from dataclasses import replace
from math import isfinite

import pytest

from ae_engine.receiving_nfb_middle_3d_witness import (
    WITNESS_ONLY, witness_middle_plate_uv_on_folded_assembly,
)
from ae_engine.receiving_nfb_middle_plate_projection import (
    shadow_nfb_middle_plate_color150,
)
from tests.test_issue1502_nfb_middle_plate_physical_shadow import _plan


def test_real_W800_divider_middle_preview_3d_world_matches_saved_X_and_y_plane(tmp_path):
    snap,divider,baseline,options=_plan(tmp_path)
    shadow=shadow_nfb_middle_plate_color150(snap,divider,baseline,**options)
    witness=witness_middle_plate_uv_on_folded_assembly(
        snap,divider,baseline,uv_xy=shadow.uv_center_xy,
        expected_world_x_mm=shadow.world_x_mm,
    )
    assert witness.status==WITNESS_ONLY
    assert not witness.manufacturing_ready
    assert witness.part_id==divider.stable_id
    assert witness.world_xyz[0]==pytest.approx(0.,abs=1e-5)
    assert witness.world_xyz[1]==pytest.approx(-300.,abs=1e-5)
    assert all(isfinite(value) for value in witness.world_xyz)
    assert witness.world_xyz==pytest.approx(
        shadow.render_data.metadata["nfb_middle_assembled_world_xyz"]
    )
    assert shadow.render_data.metadata["nfb_middle_3d_witness_status"]==WITNESS_ONLY
    assert shadow.render_data.metadata["nfb_mfg2_manufacturing_ready"] is False


def test_3d_world_X_tracks_only_existing_NFB_verified_hole_position(tmp_path):
    snap,divider,baseline,options=_plan(tmp_path)
    first=shadow_nfb_middle_plate_color150(snap,divider,baseline,**options)
    original=options["verified_inner_door"]
    updated=replace(original,verified_hole_locations=(
        (options["physical_hole_id"],120.,1,0,0),
    ))
    moved=shadow_nfb_middle_plate_color150(
        snap,divider,baseline,**(options|{"verified_inner_door":updated}),
    )
    original_world=first.render_data.metadata["nfb_middle_assembled_world_xyz"]
    moved_world=moved.render_data.metadata["nfb_middle_assembled_world_xyz"]
    assert moved_world[0]-original_world[0]==pytest.approx(120.)
    assert moved_world[1]==pytest.approx(original_world[1])
    assert moved_world[2]==pytest.approx(original_world[2])


def test_3d_depth_mapping_is_physical_but_not_engineering_depth_approval(tmp_path):
    snap,divider,baseline,options=_plan(tmp_path)
    datum=options["physical_datum"]
    centered=shadow_nfb_middle_plate_color150(snap,divider,baseline,**options)
    shifted=shadow_nfb_middle_plate_color150(
        snap,divider,baseline,
        **(options|{
            "physical_datum":replace(
                datum,core_depth_uv_x_mm=datum.core_depth_uv_x_mm+12.
            )
        }),
    )
    w0=centered.render_data.metadata["nfb_middle_assembled_world_xyz"]
    w1=shifted.render_data.metadata["nfb_middle_assembled_world_xyz"]
    assert w0[0]==pytest.approx(w1[0])
    assert w0[1]==pytest.approx(w1[1])
    assert abs(w1[2]-w0[2])==pytest.approx(12.,abs=1e-4)
    assert centered.status==shifted.status
    assert not centered.manufacturing_ready and not shifted.manufacturing_ready


def test_3d_witness_refuses_wrong_world_x_and_off_material_uv(tmp_path):
    snap,divider,baseline,options=_plan(tmp_path)
    s=shadow_nfb_middle_plate_color150(snap,divider,baseline,**options)
    with pytest.raises(ValueError,match="assembled X"):
        witness_middle_plate_uv_on_folded_assembly(
            snap,divider,baseline,uv_xy=s.uv_center_xy,
            expected_world_x_mm=300.,
        )
    with pytest.raises(ValueError,match="not inside actual baseline material"):
        witness_middle_plate_uv_on_folded_assembly(
            snap,divider,baseline,uv_xy=(-100.,398.),
            expected_world_x_mm=0.,
        )
