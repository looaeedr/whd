# -*- coding: utf-8 -*-
"""Actual Phase6 Matplotlib draw consumes PAD skin, not just a DTO or mesh."""
from types import SimpleNamespace

import pytest
from matplotlib.figure import Figure
from shapely.geometry import box

from ae_engine.receiving_nfb_pad_generator import (
    generate_nfb_pad_patterns, read_pad_tooling_rule,
)
from ae_engine.receiving_nfb_pad_assembly_preview import (
    NfbPadDisplaySkin, pad_physical_preview_world_mesh,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_contracts import (
    AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
)
from phase6_final_scene_renderer import Phase6FinalSceneView


def _source(name,w,h,d,px,py,diameter):
    return SimpleNamespace(
        brand="士林",model=name,width_mm=w,height_mm=h,depth_mm=d,
        screw_pitch_mm=(px,py),screw_diameter_mm=diameter,
        screw_offset_x_mm=0.,screw_offset_y_mm=0.,
    )


@pytest.mark.parametrize("rotation",(0,90,180,270))
def test_real_matplotlib_assembly_renderer_draws_selected_pad_with_no_mfg_authority(rotation):
    a=_source("100HN-s",75,130,68,25,111,3.2)
    b=_source("3P400SN",140,257,107,44,194,5.1)
    pad,=generate_nfb_pad_patterns((a,b),plate_thickness_mm=2,
                                   tooling=read_pad_tooling_rule())
    world=pad_physical_preview_world_mesh(
        pad,parent_base_id="base_plate",owner_hole_id="nfb:visual",
        world_x=0.,world_y=0.,base_front_world_z_mm=-120.,
        rotation_deg=rotation,
    )
    display=NfbPadDisplaySkin(
        part_id="nfb_pad:nfb:visual",parent_base_id="base_plate",
        owner_hole_id="nfb:visual",world_triangles=world,
        base_front_world_z_mm=-120.,pad_front_world_z_mm=-81.,
        rise_mm=39.,
    )
    base=AssemblyScenePart(
        part_key="base_plate",
        render_data=SimpleNamespace(
            scene=DrawingScene(),material=box(0,0,160,200),
            fold_guides=(),
        ),
        x_profile=({"len":160.,"core":"W"},),
        y_profile=({"len":200.,"core":"H"},),
        placement="offset",offset=(0.,0.,-120.),
    )
    scene=AssemblySceneRenderData(
        assembly_parts=(base,),
        visible_part_keys=("base_plate",),
        formed_nfb_pad_skins=(display,),
    )
    figure=Figure()
    ax=figure.add_subplot(111,projection="3d")
    renderer=Phase6FinalSceneView(SimpleNamespace(ax3d=ax))
    result=renderer.render(FinalSceneViewRequest(
        render_data=scene,x_profile=(),y_profile=(),
        part_key="assembly",finished_dimensions=(800.,1600.,350.),
        thickness=2.,
    ))
    assert result
    assert renderer.last_formed_pad_display_ids==("nfb_pad:nfb:visual",)
    assert len(ax.collections)>=2  # physical base plus full PAD
    assert display.manufacturing_ready is False


def test_mfg_approved_pad_is_rejected_by_display_not_smuggled_into_parts():
    from dataclasses import replace
    a=_source("100HN-s",75,130,68,25,111,3.2)
    b=_source("3P400SN",140,257,107,44,194,5.1)
    pad,=generate_nfb_pad_patterns((a,b),plate_thickness_mm=2,
                                   tooling=read_pad_tooling_rule())
    triangles=pad_physical_preview_world_mesh(
        pad,parent_base_id="base_plate",owner_hole_id="nfb:visual",
        world_x=0.,world_y=0.,base_front_world_z_mm=-120.)
    # The preview must fail closed if any path claims MFG approval.
    display=NfbPadDisplaySkin(
        part_id="nfb_pad:nfb:visual",parent_base_id="base_plate",
        owner_hole_id="nfb:visual",world_triangles=triangles,
        base_front_world_z_mm=-120.,pad_front_world_z_mm=-81.,rise_mm=39.,
    )
    base=AssemblyScenePart(
        part_key="base_plate",render_data=SimpleNamespace(
            scene=DrawingScene(),material=box(0,0,160,200),fold_guides=()),
        x_profile=({"len":160.,"core":"W"},),
        y_profile=({"len":200.,"core":"H"},),
        placement="offset",offset=(0.,0.,-120.),
    )
    scene=AssemblySceneRenderData(
        assembly_parts=(base,),visible_part_keys=("base_plate",),
        formed_nfb_pad_skins=(replace(display,manufacturing_ready=True),),
    )
    figure=Figure()
    renderer=Phase6FinalSceneView(
        SimpleNamespace(ax3d=figure.add_subplot(111,projection="3d")))
    with pytest.raises(ValueError,match="PAD_3D_PREVIEW_SOURCE_OR_MFG_GATE_INVALID"):
        renderer.render(FinalSceneViewRequest(
            render_data=scene,x_profile=(),y_profile=(),part_key="assembly",
            finished_dimensions=(800.,1600.,350.),thickness=2.,
        ))
