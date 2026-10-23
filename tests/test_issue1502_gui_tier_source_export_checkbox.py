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


def test_original_main_gui_old_presence_mirror_does_not_hide_two_live_bases():
    from types import SimpleNamespace
    from gui_modules.project.export_actions import _selected_export_flags
    class Toggle:
        def __init__(self,value):
            self.value=value
        def get(self):
            return self.value
    real_workspace=SimpleNamespace(available_parts=(
        "box_body","inner_door:upper:panel",
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1",
    ))
    designer=SimpleNamespace(
        _phase6_input_snapshot={
            "model":"受電箱","nfb_config_submitted":True,
        },
        designer_workspace=real_workspace,
    )
    host=SimpleNamespace(
        fold_designer_app=designer,
        export_z_var=Toggle(True),export_head_var=Toggle(False),
        export_tail_var=Toggle(False),export_door_var=Toggle(True),
        export_base_plate_var=Toggle(True),export_ib_var=Toggle(False),
        export_ib_door_var=Toggle(False),
        _phase6_logical_part_present=logical_part_present,
    )
    flags=_selected_export_flags(host,{"box_body"},False)
    assert flags["base_plate"] is True
    assert flags["door"] is True
    assert flags["box_body"] is True
