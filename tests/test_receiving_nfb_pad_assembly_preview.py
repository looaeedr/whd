# -*- coding: utf-8 -*-
"""PAD shared 3D engine must show tabs inside the real T2 base sheet."""
from types import SimpleNamespace
import pytest
from ae_engine.receiving_nfb_pad_generator import (
    read_pad_tooling_rule,generate_nfb_pad_patterns,
)
from ae_engine.receiving_nfb_pad_assembly_preview import (
    pad_physical_preview_world_mesh,
)
from ae_engine.assembly_geometry_primitives import triangle_bounds


def _s(name,w,h,d,px,py,diam):
    return SimpleNamespace(brand="士林",model=name,width_mm=w,height_mm=h,
        depth_mm=d,screw_pitch_mm=(px,py),screw_diameter_mm=diam,
        screw_offset_x_mm=0.,screw_offset_y_mm=0.)


def test_two_real_folded_legs_align_tab_tips_to_real_base_skin():
    small=_s("100HN-s",75,130,68,25,111,3.2)
    big=_s("3P400SN",140,257,107,44,194,5.1)
    pattern,=generate_nfb_pad_patterns([small,big],plate_thickness_mm=2,
                                       tooling=read_pad_tooling_rule())
    base_z=-150.
    skin=pad_physical_preview_world_mesh(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:pad:1",
        world_x=147.,world_y=260.,base_front_world_z_mm=base_z,
    )
    assert skin
    bounds=triangle_bounds(skin)
    assert bounds[0][0] < 147 < bounds[0][1]
    assert bounds[1][0] < 260 < bounds[1][1]
    assert bounds[2][0] <= base_z - 1.+1e-4
    assert bounds[2][1] >= base_z + pattern.rise_mm - 1.-1e-4


def test_different_sheet_T_does_not_falsely_claim_verified_2mm_tab_engagement():
    s=_s("small",75,130,68,25,111,3.2)
    b=_s("deep",140,257,107,44,194,5.1)
    p,=generate_nfb_pad_patterns([s,b],plate_thickness_mm=3,
                                 tooling=read_pad_tooling_rule())
    with pytest.raises(ValueError,match="TAB"):
        pad_physical_preview_world_mesh(
            p,parent_base_id="base_plate",owner_hole_id="nfb:pad:2",
            world_x=0.,world_y=0.,base_front_world_z_mm=-100.,
        )
