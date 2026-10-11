# -*- coding: utf-8 -*-
"""#1502: NFB Color30/212 positions come ONLY from verified door NFB holes."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.manufacturing_render_data import (
    PartRenderData, MaterialSegment, UnfoldedBlankTopology,
    material_polygon_from_final_scene,
)
from ae_engine.receiving_nfb_base_process_projection import (
    NfbActualBaseWorkFace, project_verified_nfb_base_process,
)
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from ae_engine.receiving_nfb_upper_base_source import (
    NfbUpperBaseSourceProcess, NfbNativeBaseCircle,
    NfbNativeBaseClosedLoop, NfbNativeBaseMark,
)
from ae_engine.sheetmetal_drawing import DrawingScene, CirclePrimitive, PolylinePrimitive

SHA = "f" * 64
MODEL = "400_140X257_107.dxf"


def _snapshot():
    data = apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    data.update({
        "multi_door_enabled": True, "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    return data


def _verified(*, locations=None):
    points = locations or (
        ("nfb:A", -90.0, 1, 0, 0),
        ("nfb:B", 90.0, 1, 0, 90),
    )
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status": VALIDATED,
            "nfb_trial_export_approved": True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=("士林", MODEL),
        source_sha256=SHA,
        physical_hole_ids=tuple(x[0] for x in points),
        verified_hole_locations=points,
    )


def _source():
    # Synthetic original NFB DXF source pivot, independent of the real box
    # coordinate. Hole and marking have offsets relative to upper Color150.
    return NfbUpperBaseSourceProcess(
        source_sha256=SHA, indexed_filename=MODEL,
        upper_color150_handle="585", upper_color150_center_xy_mm=(20., 100.),
        base_cutting_circles=(
            NfbNativeBaseCircle("C30_A", (10.,90.), 2.),),
        base_cutting_closed_loops=(
            NfbNativeBaseClosedLoop(
                ("LINE1", "LINE2", "LINE3", "LINE4"),
                ((30.,90.),(40.,90.),(40.,100.),(30.,100.)),
            ),),
        base_marking_entities=(
            NfbNativeBaseMark("M212", "LINE",
                              ((50.,100.),(60.,100.)),()),),
        lower_deferred_handles=("LOWER_SOURCE_NOT_CONSUMED",),
    )


def _base(*, actual_part_id="receiving:upper:base", ear_at=None):
    scene = DrawingScene()
    scene.add_polyline(
        ((0.,0.),(500.,0.),(500.,500.),(0.,500.)),
        closed=True,layer="CUTTING",
    )
    if ear_at:
        scene.add_circle(ear_at, 5.,layer="CUTTING",color=3,
                         source_type="EAR_MOUNT",source_id="ear:mount:1")
    topology=UnfoldedBlankTopology(
        piece_id=actual_part_id,
        x_segments=(MaterialSegment("X","real_face_width",500.,"REAL_BASE_TEST"),),
        y_segments=(MaterialSegment("Y","real_face_height",500.,"REAL_BASE_TEST"),),
        source="REAL_BASE_TEST",revision=1,
    )
    actual = PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        unfolded_topology=topology,
        metadata={"stable_id":actual_part_id},
    )
    return NfbActualBaseWorkFace(
        physical_part_id=actual_part_id,
        actual_render=actual,
        world_face_center_xy_mm=(0.,250.),
        unfolded_face_center_uv_mm=(250.,250.),
        face_outline_uv_mm=((0.,0.),(500.,0.),(500.,500.),(0.,500.)),
    )


def _project(*, proof=None, src=None, base=None):
    return project_verified_nfb_base_process(
        snapshot=_snapshot(), inner_door_id="upper",
        verified_inner_door=proof or _verified(),
        native_source=src or _source(), target=base or _base(),
    )


def test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks():
    result=_project()
    assert not result.manufacturing_ready
    assert result.owner_hole_ids == ("nfb:A","nfb:B")
    assert result.source_sha256==SHA
    assert result.physical_part_id=="receiving:upper:base"
    assert len(result.cutting)==4  # each NFB: circle + closed native contour
    assert len(result.marking)==2
    circles=[x for x in result.cutting if isinstance(x,CirclePrimitive)]
    assert [(x.center.x,x.center.y) for x in circles]==pytest.approx([
        (150.,240.), (340.,240.), # 90-deg rotation around source pivot
    ])
    assert all(x.color==30 and x.source_type=="NFB_COLOR30" for x in circles)
    assert {x.source_id for x in circles}=={"nfb:A:C30_A","nfb:B:C30_A"}
    assert all(x.layer=="MARKING" and x.color==212 for x in result.marking)
    assert {x.layer for x in result.source_process_scene().primitives}=={
        "CUTTING","MARKING",
    }


def test_both_ear_mount_and_nfb_screw_holes_remain_distinct_and_original_untouched():
    base=_base(ear_at=(100.,100.))
    before=tuple(base.actual_render.scene.primitives)
    result=_project(base=base)
    assert tuple(base.actual_render.scene.primitives)==before
    assert len(result.cutting)==4
    assert all(getattr(x,"source_type",None)!="EAR_MOUNT" for x in result.cutting)
    # All NFB features derive from the door, not the ear/box dimensions.
    altered=_verified(locations=(
        ("nfb:A",-60.,1,0,0),("nfb:B",60.,1,0,90),
    ))
    moved=_project(proof=altered,base=base)
    original_center=next(x.center.x for x in result.cutting if isinstance(x,CirclePrimitive))
    moved_center=next(x.center.x for x in moved.cutting if isinstance(x,CirclePrimitive))
    assert moved_center-original_center==pytest.approx(30.)
    assert tuple(base.actual_render.scene.primitives)==before


def test_wrong_real_part_or_source_must_not_generate_unverified_base_cutting():
    base=_base()
    for bad in (
        replace(base,physical_part_id="other_part"),
        replace(base,face_outline_uv_mm=((600.,600.),(700.,600.),
                                          (700.,700.),(600.,700.))),
    ):
        with pytest.raises(ValueError):
            _project(base=bad)
    with pytest.raises(ValueError,match="source differs"):
        _project(src=replace(_source(),source_sha256="0"*64))
    with pytest.raises(ValueError,match="CUTTING must be verified"):
        _project(proof=replace(_verified(),manufacturing_ready=False))
    with pytest.raises(ValueError,match="identity incomplete"):
        _project(proof=replace(_verified(),physical_hole_ids=("nfb:A",)))


def test_ear_mount_overlap_is_not_silently_overcut_as_NFB():
    # NFB A: (150,240), so a legacy ear or existing cutting hole there must
    # not be overwritten just because the physical part already exists.
    with pytest.raises(ValueError,match="ear mounting material"):
        _project(base=_base(ear_at=(150.,240.)))


def test_no_lower_group_no_phantom_middle_no_dxf_release():
    projection=_project()
    assert projection.manufacturing_ready is False
    assert projection.status.endswith("NOT_RELEASED")
    assert projection.source_model==MODEL
    # No manufacturing opening may come from lower spacer or illustrative
    # middle-base drawing handles.
    handles={getattr(p,"source_id","") for p in projection.cutting}
    assert not any("LOWER_SOURCE_NOT_CONSUMED" in x for x in handles)
    assert all(isinstance(x,(CirclePrimitive,PolylinePrimitive))
               for x in projection.cutting)
