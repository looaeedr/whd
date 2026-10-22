# -*- coding: utf-8 -*-
"""PAD FinalScene must retain all four tabs, two physical BENDs and 4 CSV screws."""
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon
from ae_engine.receiving_nfb_pad_generator import (
    read_pad_tooling_rule,generate_nfb_pad_patterns,
)
from ae_engine.receiving_nfb_pad_part import build_nfb_pad_draft_part
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive


def _s(brand,model,w,h,depth,px,py,dia):
    return SimpleNamespace(brand=brand,model=model,width_mm=w,height_mm=h,
        depth_mm=depth,screw_pitch_mm=(px,py),screw_diameter_mm=dia,
        screw_offset_x_mm=0.,screw_offset_y_mm=0.)


def test_full_100hn_pad_is_real_wHD_part_and_retains_four_tabs():
    rule=read_pad_tooling_rule()
    small=_s("士林","100HN-s",75,130,68,25,111,3.2)
    big=_s("士林","3P400SN",140,257,107,44,194,5.1)
    p,=generate_nfb_pad_patterns([small,big],plate_thickness_mm=2,tooling=rule)
    part=build_nfb_pad_draft_part(
        p,parent_base_id="base_plate",owner_hole_id="nfb:upper:tier:0:unit:0")
    assert part.render_data.unfolded_topology.width==pytest.approx(149)
    assert part.pattern.blank_width_mm==pytest.approx(145)
    assert part.render_data.unfolded_topology.height==pytest.approx(130)
    assert tuple(g.position for g in part.render_data.fold_guides)==(39,110)
    assert [s["len"] for s in part.x_profile]==pytest.approx((39,71,39))
    assert [s["angle"] for s in part.x_profile[:2]]==[90.,90.]
    assert len([x for x in part.render_data.scene.primitives
                if isinstance(x,CirclePrimitive) and x.layer=="CUTTING"])==4
    assert len([x for x in part.render_data.scene.primitives
                if isinstance(x,LinePrimitive) and x.layer=="BEND"])==2
    assert len([x for x in part.render_data.scene.primitives
                if isinstance(x,PolylinePrimitive) and x.layer=="CUTTING"])==1
    assert part.render_data.material.area>0
    assert part.render_data.metadata["manufacturing_ready"] is False
    assert part.render_data.metadata["assembly_mating_verified"] is False


def test_common_part_is_not_brand_specific():
    rule=read_pad_tooling_rule()
    shallow=_s("東元","unrelated",90,155,72,30,132,3.2)
    deep=_s("東元","another",145,265,108,44,194,5.1)
    p,=generate_nfb_pad_patterns([deep,shallow],plate_thickness_mm=2,tooling=rule)
    part=build_nfb_pad_draft_part(p,parent_base_id="base_plate:nfb_layer:0",
                                 owner_hole_id="nfb-any")
    assert part.render_data.unfolded_topology.width==pytest.approx(158)
    assert [row["len"] for row in part.x_profile]==pytest.approx((36,86,36))
    assert part.render_data.metadata["source_brand"]=="東元"

def test_real_fold_profiles_put_both_legs_on_same_base_contact_side():
    from ae_engine.assembly_geometry_folded_mesh import (
        folded_profile_segment_center_from_envelope,
    )
    rule=read_pad_tooling_rule()
    shallow=_s("士林","100HN-s",75,130,68,25,111,3.2)
    deeper=_s("士林","3P400SN",140,257,107,44,194,5.1)
    p,=generate_nfb_pad_patterns([shallow,deeper],plate_thickness_mm=2,tooling=rule)
    pad=build_nfb_pad_draft_part(p,parent_base_id="base_plate",owner_hole_id="nfb:trial")
    left=folded_profile_segment_center_from_envelope(pad.x_profile,0)
    core=folded_profile_segment_center_from_envelope(pad.x_profile,1)
    right=folded_profile_segment_center_from_envelope(pad.x_profile,2)
    assert left[1] == pytest.approx(right[1],abs=1e-8)
    assert (core[1]-left[1]) == pytest.approx(
        (p.rise_mm+p.plate_thickness_mm/2)/2,abs=1e-8)
    assert pad.x_profile[0]["angle"] == pad.x_profile[1]["angle"]
    assert left[1] < core[1]  # Both tabs project rearward (-Z) toward physical Base Plate


def test_pad_preview_cutting_and_bends_survive_real_dxf_roundtrip(tmp_path):
    """Draft DXF is a geometry receipt, NEVER official MFG export approval."""
    import ezdxf
    from ae_engine.dxf_serialization import save_scene_dxf
    from ae_engine.sheetmetal_drawing import LinePrimitive
    rule=read_pad_tooling_rule()
    shallow=_s("東元","selected-small",75,130,68,25,111,3.2)
    deep=_s("東元","selected-large",140,257,107,44,194,5.1)
    pattern,=generate_nfb_pad_patterns([shallow,deep],
        plate_thickness_mm=2,tooling=rule)
    pad=build_nfb_pad_draft_part(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:dxf:unreleased",
    )
    path=tmp_path/"pad-preview-NOT-MFG.dxf"
    save_scene_dxf(path,pad.render_data.scene)
    reopened=ezdxf.readfile(path)
    entities=tuple(reopened.modelspace())
    outer=[e for e in entities if e.dxftype()=="LWPOLYLINE"
           and e.dxf.layer=="CUTTING" and e.closed]
    screws=[e for e in entities if e.dxftype()=="CIRCLE"
            and e.dxf.layer=="CUTTING"]
    bends=[e for e in entities if e.dxftype()=="LINE" and e.dxf.layer=="BEND"]
    assert (len(outer),len(screws),len(bends))==(1,4,2)
    assert len(tuple(outer[0].get_points("xy"))) == len(pattern.unfolded_outline_xy_mm)
    assert sorted(round(float(e.dxf.start.x),5) for e in bends)==list(
        map(float,pattern.bend_stations_x_mm))
    assert pad.render_data.metadata["manufacturing_ready"] is False



@pytest.mark.parametrize("forged", (False, True))
def test_actual_generated_pad_cannot_escape_through_direct_single_part_manufacturing_dxf(
    tmp_path, forged,
):
    from dataclasses import replace
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    a=_s("士林","100HN-s",75,130,68,25,111,3.2)
    b=_s("士林","3P400SN",140,257,107,44,194,5.1)
    pattern,=generate_nfb_pad_patterns(
        [a,b],plate_thickness_mm=2,tooling=read_pad_tooling_rule()
    )
    part=build_nfb_pad_draft_part(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:direct-export",
    )
    render=part.render_data
    if forged:
        render=replace(render,metadata={
            **render.metadata,
            "manufacturing_ready":True,
            "formed_geometry_verified":True,
            "assembly_mating_verified":True,
        })
    dest=tmp_path/"attempt-to-bypass-PAD-manufacturing-gate.dxf"
    with pytest.raises(ValueError,match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_part_render_data_dxf(render,dest)
    assert not dest.exists()
