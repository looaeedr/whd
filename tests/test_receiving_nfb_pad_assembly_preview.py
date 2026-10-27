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


@pytest.mark.parametrize("stored_pattern",("LEFT_FLAT_SIDE","CENTER_DOUBLE_SIDE_FOLD"))
@pytest.mark.parametrize("rotation",(0,90,180,270))
def test_real_submitted_v5_left_base_2d_squares_feed_same_3d_pad_skins(rotation, stored_pattern):
    from copy import deepcopy
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.receiving_nfb_committed_final_scene import (
        apply_committed_csv_v5_to_canonical_parts,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
    from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
    from ae_engine.receiving_nfb_pad_assembly_preview import (
        build_committed_pad_assembly_display,
    )

    snap=_current()
    # Both fresh and legacy CENTER persisted settings must resolve the
    # same current source-backed LEFT+PAD for mixed CSV depth in one tier.
    snap["receiving_base_plate"]={
        "pattern":stored_pattern,"height":340.,
        "shrink_top":20.,"shrink_bottom":20.,
        "shrink_left":45.,"shrink_right":45.,"bend":20.,
    }
    rows=snap["nfb_config"]["holes"]
    rows[0].update(model_filename="nfbv5:士林:3P400SN",source_brand="士林")
    rows[1].update(model_filename="nfbv5:士林:100HN-s",source_brand="士林",rotation_deg=rotation)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    values=receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"]=="LEFT_FLAT_SIDE"
    base=_make(snap)
    installed=apply_committed_csv_v5_to_canonical_parts(snap,(base,))
    assert len(installed)==1
    derived=installed[0]
    assert dict(derived.render_data.metadata["nfb_v5_pad_square_owners"])=={
        rows[1]["physical_hole_id"]:4
    }
    squares=[row for row in derived.render_data.scene.primitives
             if isinstance(row,PolylinePrimitive) and row.closed
             and row.layer=="CUTTING" and row.color==30]
    assert len(squares)==4
    skins=build_committed_pad_assembly_display(snap,installed)
    assert len(skins)==1
    assert skins[0].owner_hole_id==rows[1]["physical_hole_id"]
    assert skins[0].parent_base_id=="base_plate"
    assert skins[0].rise_mm==pytest.approx(39.)
    assert skins[0].four_tab_mesh_mating_verified is True
    assert skins[0].manufacturing_ready is False
    assert skins[0].assembly_contact_certified is False
    bounds=triangle_bounds(skins[0].world_triangles)
    assert bounds[2][0]<skins[0].base_front_world_z_mm
    assert bounds[2][1]>skins[0].base_front_world_z_mm


@pytest.mark.parametrize("angle", [0,90,180,270])
def test_same_real_pad_rotates_as_selected_nfb_base_four_squares(angle):
    from ae_engine.receiving_nfb_v5_configured_inner_door import AXES
    shallow=_s("100HN-s",75,130,68,25,111,3.2)
    deep=_s("3P400SN",140,257,107,44,194,5.1)
    p,=generate_nfb_pad_patterns([shallow,deep],plate_thickness_mm=2.,
                                  tooling=read_pad_tooling_rule())
    kwargs=dict(pattern=p,parent_base_id="base_plate",owner_hole_id="nfb:rot",
                world_x=35.,world_y=70.,base_front_world_z_mm=-100.)
    base=pad_physical_preview_world_mesh(**kwargs,rotation_deg=0)
    rotated=pad_physical_preview_world_mesh(**kwargs,rotation_deg=angle)
    assert len(base)==len(rotated)
    ax,ay=AXES[angle]
    for first,other in zip(base,rotated):
        for old,p2 in zip(first,other):
            x,y,z=old
            expect=(35.+(x-35.)*ax[0]+(y-70.)*ay[0],
                    70.+(x-35.)*ax[1]+(y-70.)*ay[1],z)
            assert p2==pytest.approx(expect,abs=1e-5)



@pytest.mark.parametrize("fault",("square_removed","square_shifted","screw_shifted"))
def test_actual_pad_mating_refuses_stale_base_geometry_even_when_owner_metadata_says_four(fault):
    from copy import deepcopy
    from dataclasses import replace
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_drawing import (
        CirclePrimitive,PolylinePrimitive,DrawingScene,
    )
    from ae_engine.receiving_nfb_committed_final_scene import (
        apply_committed_csv_v5_to_canonical_parts,
    )
    from ae_engine.receiving_nfb_pad_assembly_preview import (
        build_committed_pad_assembly_display,
    )
    from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
    from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make

    snap=_current()
    snap["receiving_base_plate"]={
        "pattern":"LEFT_FLAT_SIDE","height":340.,
        "shrink_top":20.,"shrink_bottom":20.,
        "shrink_left":45.,"shrink_right":45.,"bend":20.,
    }
    rows=snap["nfb_config"]["holes"]
    rows[0].update(model_filename="nfbv5:士林:3P400SN",source_brand="士林")
    rows[1].update(model_filename="nfbv5:士林:100HN-s",source_brand="士林",
                   rotation_deg=90)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    installed=apply_committed_csv_v5_to_canonical_parts(snap,(_make(snap),))
    assert len(installed)==1
    original=installed[0].render_data
    assert dict(original.metadata["nfb_v5_pad_square_owners"]) == {
        rows[1]["physical_hole_id"]:4}
    items=list(original.scene.primitives)
    if fault=="screw_shifted":
        i=next(i for i,p in enumerate(items)
            if isinstance(p,CirclePrimitive)
            and p.source_id==rows[1]["physical_hole_id"]+":screw:1")
        p=items[i]
        items[i]=replace(p,center=Vec2(p.center.x+2.,p.center.y))
    else:
        i=next(i for i,p in enumerate(items)
            if isinstance(p,PolylinePrimitive) and p.closed
            and p.layer=="CUTTING" and p.color==30 and len(p.points)==4)
        if fault=="square_removed":
            del items[i]
        else:
            poly=items[i]
            items[i]=replace(poly,points=tuple(
                Vec2(q.x+5.,q.y) for q in poly.points))
    changed=replace(installed[0],render_data=replace(
        original,scene=DrawingScene(items)))
    # A stale metadata count or still-valid material must never conceal
    # that the actual selected NFB's locator/screw geometry drifted.
    with pytest.raises(ValueError,match="PAD_BASE_"):
        build_committed_pad_assembly_display(snap,(changed,))



@pytest.mark.parametrize("rotation",(0,90,180,270))
def test_real_folded_pad_four_tab_tips_enter_matching_base_cutting_squares(rotation):
    """True mesh tip vertices, NOT guessed labels, must mate 4 source holes."""
    from shapely.geometry import Point, Polygon
    from ae_engine.receiving_nfb_v5_configured_inner_door import AXES

    smaller=_s("100HN-s",75,130,68,25,111,3.2)
    reference=_s("3P400SN",140,257,107,44,194,5.1)
    pattern,=generate_nfb_pad_patterns(
        (smaller,reference),plate_thickness_mm=2.,tooling=read_pad_tooling_rule())
    world_x,world_y,base_z=147.,260.,-150.
    triangles=pad_physical_preview_world_mesh(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:tab-contact",
        world_x=world_x,world_y=world_y,base_front_world_z_mm=base_z,
        rotation_deg=rotation,
    )
    mins=triangle_bounds(triangles)
    assert mins is not None
    # Thickness-normal offset is on the vertical leg itself: the four tiny
    # tips project into the Base Plate's physical depth range, not hover.
    tip_world_z=mins[2][0]
    assert base_z-pattern.plate_thickness_mm-1e-5 <= tip_world_z <= base_z+1e-5
    vertices={
        (round(float(pt[0]),6),round(float(pt[1]),6))
        for tri in triangles for pt in tri
        if abs(float(pt[2])-tip_world_z) < 1e-5
    }
    assert vertices, "PAD_REAL_3D_TAB_TIPS_MISSING"
    ux,uy=AXES[rotation]
    def project(point):
        x,y=point
        return (world_x+x*ux[0]+y*uy[0],
                world_y+x*ux[1]+y*uy[1])
    squares=tuple(Polygon(tuple(project(v) for v in square))
                  for square in pattern.base_square_holes_xy_mm)
    assert len(squares)==4
    for square in squares:
        matches=[p for p in vertices if square.buffer(1e-5).covers(Point(p))]
        assert matches, (
            "PAD_REAL_3D_TAB_TIP_MISALIGNED_WITH_BASE_SQUARE",
            rotation,square.bounds,len(vertices),
        )



@pytest.mark.parametrize("rotation",(0,90,180,270))
@pytest.mark.parametrize("fault",("shift_world_x","shift_world_z","square_missing"))
def test_pad_real_mesh_mating_guard_rejects_mutated_triangles_or_base_cut(rotation,fault):
    """Adversarial real folded geometry must NOT become a displayed PAD skin."""
    from ae_engine.receiving_nfb_v5_configured_inner_door import AXES
    from ae_engine.receiving_nfb_pad_base_mating import (
        verify_real_pad_mesh_tab_engagement,
    )
    shallow=_s("100HN-s",75,130,68,25,111,3.2)
    deep=_s("3P400SN",140,257,107,44,194,5.1)
    pattern,=generate_nfb_pad_patterns(
        (shallow,deep),plate_thickness_mm=2.,tooling=read_pad_tooling_rule())
    ux,uy=AXES[rotation]
    def rotated(point):
        x,y=point
        return (355.+x*ux[0]+y*uy[0],150.+x*ux[1]+y*uy[1])
    cut_squares=tuple(tuple(rotated(pt) for pt in sq)
                      for sq in pattern.base_square_holes_xy_mm)
    triangles=pad_physical_preview_world_mesh(
        pattern,parent_base_id="base_plate",owner_hole_id="nfb:physical-mutant",
        world_x=147.,world_y=260.,base_front_world_z_mm=-150.,
        rotation_deg=rotation)
    accepted=verify_real_pad_mesh_tab_engagement(
        triangles,pattern,cut_squares,world_x_mm=147.,world_y_mm=260.,
        base_front_world_z_mm=-150.,rotation_deg=rotation)
    assert len(accepted)==4
    if fault=="square_missing":
        cut_squares=cut_squares[:3]
    else:
        dx,dz=(8.,0.) if fault=="shift_world_x" else (0.,1.)
        triangles=tuple(tuple((x+dx,y,z+dz) for x,y,z in tri)
                        for tri in triangles)
    with pytest.raises(ValueError,match="PAD_MESH_MATING_"):
        verify_real_pad_mesh_tab_engagement(
            triangles,pattern,cut_squares,world_x_mm=147.,world_y_mm=260.,
            base_front_world_z_mm=-150.,rotation_deg=rotation)
