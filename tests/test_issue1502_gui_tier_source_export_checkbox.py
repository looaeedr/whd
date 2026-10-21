# -*- coding: utf-8 -*-
"""#1502: real physical two-tier identities must reach the ORIGINAL GUI DXF checks."""
from gui_modules.parts.panels.common import logical_part_present
from gui_modules.project.export_actions import _resolved_export_intention_key


def test_two_real_tier_bases_make_original_gui_base_checkbox_actionable():
    two=("box_body","inner_door:upper:panel",
         "base_plate:nfb_layer:0","base_plate:nfb_layer:1")
    assert logical_part_present(two,"base_plate")
    assert logical_part_present(two,"door")
    assert [_resolved_export_intention_key(s) for s in two[2:]]==[
        "base_plate","base_plate",
    ]


def test_one_inner_door_without_outer_door_is_still_real_door_export():
    assert logical_part_present(("inner_door:upper:panel",),"door")
    assert not logical_part_present(("base_plate:fixing_plate:nfb_layer:0:left",),"base_plate")
    assert not logical_part_present(("box_body",),"door")


def test_legacy_cabinet_selection_stays_compatible():
    assert logical_part_present(("base_plate",),"base_plate")
    assert logical_part_present(("base_plate_c1_r1",),"base_plate")
    assert logical_part_present(("door_c1_r1",),"door")
    assert not logical_part_present((),"base_plate")
