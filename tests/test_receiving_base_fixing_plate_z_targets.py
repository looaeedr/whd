# -*- coding: utf-8 -*-
"""#1503 source-derived real installed ear target, never fabricated large-ear BEND."""
from copy import deepcopy
import pytest
from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_base_fixing_plate_z_targets import (
    resolve_receiving_fixing_plate_installation_targets,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def test_source_ear_pair_world_x_hole_y_and_true_base_skin_z_contact():
    snap=_assembled()
    ears=resolve_receiving_fixing_plate_installation_targets(snap)
    assert len(ears)==2
    left,right=ears
    assert [x.part_id for x in ears]==[
        "base_plate:fixing_plate:left","base_plate:fixing_plate:right"
    ]
    assert (left.welded_side_inside_world_x_mm,
            right.welded_side_inside_world_x_mm)==pytest.approx((-398.,398.))
    assert (left.fixing_hole_world_x_mm,
            right.fixing_hole_world_x_mm)==pytest.approx((-335.,335.))
    assert left.fixing_hole_world_y_mm==pytest.approx((180.,320.))
    assert right.fixing_hole_world_y_mm==pytest.approx((180.,320.))
    assert [row.selected_source_slot_indexes for row in ears]==[(1,2),(1,2)]
    for e in ears:
        assert e.fixing_plate_contact_skin_world_z_mm==pytest.approx(e.base_back_skin_world_z_mm)
        assert e.fixing_plate_contact_skin_world_z_mm-e.fixing_plate_back_skin_world_z_mm==pytest.approx(3)
        assert not e.source_bend_verified
        assert not e.formed_weld_contact_verified
        assert not e.side_plate_marking_export_approved
        assert not e.manufacturing_ready


def test_operator_nfb_y_moves_both_welded_ears_with_base_not_separately():
    snap=_assembled()
    original=resolve_receiving_fixing_plate_installation_targets(snap)
    snap["receiving_inner_door_layer_heights_mm"]=[330,830]
    adjusted=resolve_receiving_fixing_plate_installation_targets(snap)
    assert adjusted[0].fixing_hole_world_y_mm==pytest.approx((400.,540.))
    for old,new in zip(original,adjusted):
        assert new.fixing_plate_contact_skin_world_z_mm==pytest.approx(old.fixing_plate_contact_skin_world_z_mm)
        assert tuple(y2-y1 for y1,y2 in zip(old.fixing_hole_world_y_mm,new.fixing_hole_world_y_mm))==pytest.approx((220,220))


def test_verified_nfb_hole_x_moves_only_machining_not_fixed_welded_ear_pair():
    snap=_assembled()
    ears=resolve_receiving_fixing_plate_installation_targets(snap)
    for hole,x in zip(snap["nfb_config"]["holes"],(-130.,70.)):
        hole.update(manual_x_state="CONFIRMED",manual_x_mm=x,
                    datum_revision="source-proven",datum_snapshot={"w":800,"t":2})
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    p=resolve_assembly_placement(snap,"base_plate")
    assert p.world_offset[0]==pytest.approx(0)
    new=resolve_receiving_fixing_plate_installation_targets(snap)
    assert [row.fixing_hole_world_x_mm for row in new]==[-335.,335.]
    assert new==ears


def test_unsubmitted_and_wrong_source_pattern_never_emit_synthetic_weld_marks():
    snap=_assembled()
    snap["nfb_config_submitted"]=False
    assert resolve_receiving_fixing_plate_installation_targets(snap)==()


def test_true_ear_z_moves_with_inner_door_offset_and_nfb_depth():
    before=resolve_receiving_fixing_plate_installation_targets(_assembled(offset=80))
    after=resolve_receiving_fixing_plate_installation_targets(_assembled(offset=95))
    for a,b in zip(before,after):
        assert a.fixing_plate_contact_skin_world_z_mm-b.fixing_plate_contact_skin_world_z_mm == pytest.approx(15)
        assert a.fixing_hole_world_x_mm==b.fixing_hole_world_x_mm
    original=resolve_receiving_fixing_plate_installation_targets(_assembled(shallow="125_90X155_72.dxf"))
    changed=resolve_receiving_fixing_plate_installation_targets(_assembled(shallow="100_75X130_68.dxf"))
    assert changed[0].base_back_skin_world_z_mm==pytest.approx(original[0].base_back_skin_world_z_mm)
