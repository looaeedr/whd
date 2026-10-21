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
    assert [s["angle"] for s in part.x_profile[:2]]==[-90.,90.]
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
