# -*- coding: utf-8 -*-
"""One PAD generator, every brand and model, no product-keyed constants."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon

from ae_engine.receiving_nfb_pad_generator import (
    read_pad_tooling_rule, generate_nfb_pad_patterns,
)


def _spec(brand, model, w, h, depth, px, py, dia=3.2):
    return SimpleNamespace(brand=brand,model=model,width_mm=w,height_mm=h,
        depth_mm=depth,screw_pitch_mm=(px,py),screw_diameter_mm=dia,
        screw_offset_x_mm=0.,screw_offset_y_mm=0.)


def test_original_source_100hn_is_formula_not_product_switch():
    rule=read_pad_tooling_rule()
    shallow=_spec("士林","100HN-s",75,130,68,25,111)
    deep=_spec("士林","3P400SN",140,257,107,44,194,5.1)
    generated=generate_nfb_pad_patterns([shallow,deep],plate_thickness_mm=2,
                                        tooling=rule)
    assert len(generated)==1
    p=generated[0]
    assert p.switch_index==0
    assert (p.rise_mm,p.side_leg_blank_mm,p.centre_web_blank_mm,
            p.blank_width_mm)==(39,37,71,145)
    assert p.bend_stations_x_mm==(37,108)
    assert Polygon(p.formed_outline_xy_mm).area==pytest.approx(75*130+4*2*5)
    assert Polygon(p.formed_outline_xy_mm).bounds==(-39.5,-65.,39.5,65.)
    assert Polygon(p.unfolded_outline_xy_mm).bounds==(-2.,0.,147.,130.)
    assert len(p.base_square_holes_xy_mm)==4
    assert {((s[0][0]+s[2][0])/2,(s[0][1]+s[2][1])/2)
            for s in p.base_square_holes_xy_mm}=={
                (-36.,-47.5),(36.,-47.5),(-36.,47.5),(36.,47.5)}
    assert set(p.base_screw_centres_xy_mm)=={
        (-12.5,-55.5),(12.5,-55.5),(-12.5,55.5),(12.5,55.5)}
    assert p.manufacturing_ready is False


def test_other_brand_model_same_formula_changes_all_dimensions():
    rule=read_pad_tooling_rule()
    shallow=_spec("東元","OTHER_SOURCE",90,155,72,30,132)
    deep=_spec("東元","DEEP_SOURCE",145,265,108,44,194,5.1)
    p,=generate_nfb_pad_patterns([deep,shallow],
        plate_thickness_mm=2,tooling=rule)
    assert (p.switch_index,p.rise_mm,p.side_leg_blank_mm,
            p.centre_web_blank_mm,p.blank_width_mm)==(1,36,34,86,154)
    assert {((s[0][0]+s[2][0])/2,(s[0][1]+s[2][1])/2)
            for s in p.base_square_holes_xy_mm}=={
                (-43.5,-60.),(43.5,-60.),(-43.5,60.),(43.5,60.)}
    assert set(p.pad_screw_centres_xy_mm)=={
        (-15.,-66.),(15.,-66.),(-15.,66.),(15.,66.)}


def test_any_number_of_shallower_units_in_one_tier():
    rule=read_pad_tooling_rule()
    source=lambda d: _spec("士林",f"model-{d}",75,130,d,25,111)
    patterns=generate_nfb_pad_patterns([source(107),source(68),source(80)],
        plate_thickness_mm=2,tooling=rule)
    assert [p.rise_mm for p in patterns]==[39,27]
    assert [p.switch_index for p in patterns]==[1,2]
    assert generate_nfb_pad_patterns([source(107),source(107)],
        plate_thickness_mm=2,tooling=rule)==()


def test_other_sheet_thickness_recomputes_not_product_constant():
    rule=read_pad_tooling_rule()
    s=_spec("士林","A",75,130,68,25,111)
    d=_spec("士林","B",140,257,107,44,194)
    p,=generate_nfb_pad_patterns([s,d],plate_thickness_mm=3,tooling=rule)
    assert (p.side_leg_blank_mm,p.centre_web_blank_mm,p.blank_width_mm)==(36,69,141)


def test_missing_and_invalid_sources_reject_instead_of_guessing():
    rule=read_pad_tooling_rule()
    good=_spec("士林","A",75,130,68,25,111)
    deep=_spec("士林","B",140,257,107,44,194)
    for bad in (replace(good,depth_mm=None) if hasattr(good,'__dataclass_fields__')
                else SimpleNamespace(**{**vars(good),'depth_mm':None}),
                SimpleNamespace(**{**vars(good),'screw_pitch_mm':None}),
                SimpleNamespace(**{**vars(good),'screw_diameter_mm':None})):
        with pytest.raises(ValueError):
            generate_nfb_pad_patterns([bad,deep],plate_thickness_mm=2,tooling=rule)
    with pytest.raises(ValueError):
        generate_nfb_pad_patterns([good,_spec("士林","C",100,155,69,25,111)],
            plate_thickness_mm=2,tooling=rule)
