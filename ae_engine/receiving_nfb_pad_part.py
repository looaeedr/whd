# -*- coding: utf-8 -*-
"""Unreleased PAD physical sheet from the common model-independent generator.

Uses the ordinary WHD FinalScene PartRenderData, BEND guides and fold profiles;
NO special DXF path and NO manufacturing authorization. Its world installation
and contact with the base require an independent physical-skin mating proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from shapely.geometry import Polygon

from .manufacturing_render_data import (
    FoldGuide, MaterialSegment, PartRenderData, UnfoldedBlankTopology,
    material_polygon_from_final_scene,
)
from .receiving_nfb_pad_generator import PadPattern, read_pad_tooling_rule
from .sheetmetal_drawing import DrawingScene


@dataclass(frozen=True)
class NfbPadDraftPart:
    part_id: str
    parent_base_id: str
    owner_hole_id: str
    pattern: PadPattern
    render_data: PartRenderData
    x_profile: tuple[dict, ...]
    y_profile: tuple[dict, ...]
    physical_z_placement_verified: bool = False
    manufacturing_ready: bool = False


def build_nfb_pad_draft_part(
    pattern: PadPattern, *, parent_base_id: str, owner_hole_id: str,
) -> NfbPadDraftPart:
    """Produce real 2D material and 3D signed fold data from ONE PAD pattern.

    The 2 mm tongue is an extension of the leg TIP, beyond the normal blank
    envelope. Therefore source dimensions 37+71+37 describe 145 mm of main
    blank, while the actual CUTTING bbox is 149 mm wide and the BEND x coords
    are 39 and 110. Using a 145-mm profile clips the tongues in WHD 3D.
    """
    if not isinstance(pattern, PadPattern) or pattern.manufacturing_ready:
        raise ValueError("PAD 須使用通用產生器未放行來源")
    if not isinstance(parent_base_id, str) or not parent_base_id.startswith("base_plate"):
        raise ValueError("PAD 缺少真正底板所屬身分")
    if not isinstance(owner_hole_id, str) or not owner_hole_id.strip():
        raise ValueError("PAD 缺少 NFB 安裝孔身分")
    rule = read_pad_tooling_rule()
    if pattern.tooling_revision != rule.revision:
        raise ValueError("PAD 共用加工規則已修改，需重新計算")
    p = rule.tab_projection_mm
    a, b = pattern.bend_stations_x_mm
    h = float(pattern.formed_height_mm)
    total_w = float(pattern.blank_width_mm) + 2*p
    expected = (pattern.side_leg_blank_mm + p,
                pattern.side_leg_blank_mm + p + pattern.centre_web_blank_mm)
    if (not all(isclose(x,y,abs_tol=1e-7) for x,y in zip((a,b),expected))
            or not (0 < a < b < total_w)
            or not isclose(total_w-b,a,abs_tol=1e-7)
            or h <= 0):
        raise ValueError("PAD 共用折線與含凸耳外框不一致")
    contour = Polygon(pattern.unfolded_outline_xy_mm)
    if (not contour.is_valid or not isclose(contour.area,
            pattern.blank_width_mm * h +
            4*rule.tab_projection_mm*rule.tab_height_mm, abs_tol=1e-6)
            or any(not isclose(v,w,abs_tol=1e-6) for v,w in zip(
                contour.bounds,(0.,0.,total_w,h)))):
        raise ValueError("PAD 四個 2mm 凸耳的真下料輪廓不一致")
    sid = f"nfb_pad:{owner_hole_id}"
    scene = DrawingScene()
    scene.add_polyline(pattern.unfolded_outline_xy_mm, layer="CUTTING",
                       closed=True, color=3)
    for i, xy in enumerate(pattern.pad_unfolded_screw_centres_xy_mm):
        from shapely.geometry import Point
        bore = Point(*xy).buffer(pattern.screw_diameter_mm/2, quad_segs=48)
        if not contour.contains(bore):
            raise ValueError("PAD 螺絲孔超出本體材料或落在凸耳外")
        scene.add_circle(xy,pattern.screw_diameter_mm/2,
                         layer="CUTTING",color=3,
                         source_type="PAD_SELECTED_NFB_CSV",
                         source_id=f"{owner_hole_id}:pad_screw:{i+1}")
    for station in (a,b):
        scene.add_line((station,0.),(station,h),layer="BEND")
    material = material_polygon_from_final_scene(scene)
    if material.is_empty or not material.is_valid or material.area >= contour.area:
        raise ValueError("PAD 真材料開孔失敗")
    topology = UnfoldedBlankTopology(
        piece_id=sid,
        x_segments=(
            MaterialSegment("X","PAD_LEFT_LEG_WITH_TONGUE",a,rule.revision),
            MaterialSegment("X","PAD_MOUNTING_WEB",b-a,rule.revision),
            MaterialSegment("X","PAD_RIGHT_LEG_WITH_TONGUE",total_w-b,rule.revision),
        ),
        y_segments=(MaterialSegment("Y","PAD_HEIGHT",h,rule.revision),),
        source="RECEIVING_NFB_PAD_COMMON_TOOLING",revision=1,
    )
    fold_guides=(FoldGuide("x",a,0.,h),FoldGuide("x",b,0.,h))
    render=PartRenderData(
        scene=scene,material=material,
        fold_guides=fold_guides,unfolded_topology=topology,
        metadata={
            "stable_id":sid,
            "physical_part_role":"NFB_PAD",
            "nfb_deferred_manufacturing_role":"PAD",
            "parent_base_id":parent_base_id,
            "owner_hole_id":owner_hole_id,
            "source_brand":pattern.brand,
            "source_model":pattern.model,
            "formed_main_size_mm":(pattern.formed_width_mm,pattern.formed_height_mm),
            "source_pad_depth_step_mm":pattern.rise_mm,
            "source_pad_thickness_mm":pattern.plate_thickness_mm,
            "source_tooling_revision":rule.revision,
            "formed_geometry_verified":False,
            "assembly_mating_verified":False,
            "manufacturing_ready":False,
        },
    )
    # Three segment x fold: each vertical leg bends in the same direction,
    # core is the central NFB mounting web. The two tabs extend the tips.
    x_profile=(
        # The sharp-fold engine maps material length onto a mid-surface.
        # A real T sheet has its end along the two vertical legs at the
        # OUTSIDE finished face, while CUTTING and BEND retain the exact
        # original 37+71+37 source lengths. Add only T/2 to the formed
        # mid-surface projection, never a blank/bend allowance.
        {"len":a,"angle":90.,"core":"PAD_LEFT_LEG",
         "phase6_key":"PAD_LEFT_LEG","formed_length":a+pattern.plate_thickness_mm/2},
        {"len":b-a,"angle":90.,"core":"W_PART"},
        {"len":total_w-b,"core":"PAD_RIGHT_LEG",
         "phase6_key":"PAD_RIGHT_LEG",
         "formed_length":total_w-b+pattern.plate_thickness_mm/2},
    )
    y_profile=({"len":h,"core":"H"},)
    return NfbPadDraftPart(
        part_id=sid,parent_base_id=parent_base_id,owner_hole_id=owner_hole_id,
        pattern=pattern,render_data=render,
        x_profile=x_profile,y_profile=y_profile,
    )
