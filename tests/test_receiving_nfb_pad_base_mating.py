# -*- coding: utf-8 -*-
"""Four PAD locator squares use one parametric model rule at any V5 rotation."""
from types import SimpleNamespace
import pytest
from shapely.geometry import Polygon

from ae_engine.receiving_nfb_pad_generator import read_pad_tooling_rule, generate_nfb_pad_patterns
from ae_engine.receiving_nfb_pad_base_mating import project_pad_base_squares
from ae_engine.receiving_nfb_numeric_panel_projection import NfbPanelDatum


def _spec(brand, model, w, h, d, pitch, diameter):
    return SimpleNamespace(brand=brand, model=model, width_mm=w,
        height_mm=h, depth_mm=d, screw_pitch_mm=pitch,
        screw_diameter_mm=diameter, screw_offset_x_mm=0.,
        screw_offset_y_mm=0.)


@pytest.mark.parametrize("axes", (
    ((1,0),(0,1)), ((0,1),(-1,0)),
    ((-1,0),(0,-1)), ((0,-1),(1,0)),
))
def test_selected_nfb_four_squares_rotate_with_its_real_base_datum(axes):
    p, = generate_nfb_pad_patterns((
        _spec("東元","A",75,130,68,(25,111),3.2),
        _spec("東元","B",140,257,107,(44,194),5.1),
    ), plate_thickness_mm=2, tooling=read_pad_tooling_rule())
    datum=NfbPanelDatum("base_plate","base-plate",(160.,50.),*axes)
    squares=project_pad_base_squares(datum,p)
    assert len(squares)==4
    assert all(Polygon(square).area==pytest.approx(36.) for square in squares)
    expected={datum.map_xy(((a[0][0]+a[2][0])/2,(a[0][1]+a[2][1])/2))
              for a in p.base_square_holes_xy_mm}
    actual={(sum(v[0] for v in square)/4,sum(v[1] for v in square)/4)
            for square in squares}
    assert actual==expected


def test_base_holes_must_not_borrow_inner_door_datum():
    p,=generate_nfb_pad_patterns((
        _spec("伍菱","A",75,130,68,(25,111),3.2),
        _spec("伍菱","B",140,257,107,(44,194),5.1),
    ),plate_thickness_mm=2,tooling=read_pad_tooling_rule())
    with pytest.raises(ValueError):
        project_pad_base_squares(NfbPanelDatum("door","inner-door",
            (0.,0.),(1,0),(0,1)),p)
