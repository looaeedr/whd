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


@pytest.mark.parametrize("rotation",(0,90,180,270))
def test_actual_folded_pad_skin_entire_base_slab_clearance_and_adversarial_interference(rotation):
    from ae_engine.receiving_nfb_v5_configured_inner_door import AXES
    from ae_engine.receiving_nfb_pad_base_mating import (
        verify_real_pad_mesh_tab_engagement,
        verify_pad_solid_inside_real_base_cutouts,
    )
    from ae_engine.receiving_nfb_pad_assembly_preview import (
        pad_physical_preview_world_mesh,
    )
    shallow=_spec("東元","A",75,130,68,(25,111),3.2)
    deep=_spec("東元","B",140,257,107,(44,194),5.1)
    pattern,=generate_nfb_pad_patterns(
        (shallow,deep),plate_thickness_mm=2.,tooling=read_pad_tooling_rule())
    ux,uy=AXES[rotation]
    def rotate(xy):
        x,y=xy
        return (355+x*ux[0]+y*uy[0],150+x*ux[1]+y*uy[1])
    actual=tuple(tuple(rotate(point) for point in square)
                 for square in pattern.base_square_holes_xy_mm)
    world_x,world_y,base_z=147.,260.,-150.
    tris=pad_physical_preview_world_mesh(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:local-slab",
        world_x=world_x,world_y=world_y,base_front_world_z_mm=base_z,
        rotation_deg=rotation)
    squares=verify_real_pad_mesh_tab_engagement(
        tris,pattern,actual,world_x_mm=world_x,world_y_mm=world_y,
        base_front_world_z_mm=base_z,rotation_deg=rotation)
    verify_pad_solid_inside_real_base_cutouts(
        tris,squares,base_front_world_z_mm=base_z,thickness_mm=2.)
    # A corrupted triangle can still have the original four tab tips at
    # the correct bottom Z. The full solid/slab check must independently
    # reject the inwardly intruding material.
    altered=list(tris)
    altered.append((
        (world_x,world_y,base_z-0.5),
        (world_x+6,world_y,base_z-0.5),
        (world_x,world_y+6,base_z-1.5),
    ))
    with pytest.raises(ValueError,match="PAD_BASE_SLAB_SOLID_INTERFERES"):
        verify_pad_solid_inside_real_base_cutouts(
            altered,squares,base_front_world_z_mm=base_z,thickness_mm=2.)
