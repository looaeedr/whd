# -*- coding: utf-8 -*-
"""User-certified A-left/B-right/C-divider/D-top Receiving source identities."""
from __future__ import annotations

import hashlib
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_frame_baseline import (
    certified_source_catalog, frame_source_file, receiving_frame_source,
)
from ae_engine.inner_door_frames import derive_inner_door_frames
from ae_engine.manufacturing_api import build_inner_door_frame_render_data, save_part_render_data_dxf
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive, LinePrimitive


def _sample_frame(side, span):
    return derive_inner_door_frames("upper",spans={side:span},thickness=2.0,included_sides=(side,))[0]


def test_actual_coreelec_source_files_are_immutable_and_roles_unambiguous():
    p=frame_source_file()
    assert p.is_file()
    assert p.name == "框.dxf"
    assert p.parent.name == "受電箱"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == "52697809369828c718cc2ef9aff7915b2352da7d24ed07312b12c183c8f2e2dc"
    cat=certified_source_catalog(p)
    assert {r:(v["role"],v["blank_width"],v["sample_span"]) for r,v in cat.items()} == {
        "A":("left",90.0,1098.0),
        "B":("right",110.0,1098.0),
        "C":("divider",158.0,796.0),
        "D":("top",90.0,696.0),
    }


@pytest.mark.parametrize("role,tag,width,sample_span,bend_stations,holes",[
    ("left","A",90.0,1098.0,(22.0,68.0),0),
    ("right","B",110.0,1098.0,(22.0,42.0,88.0),0),
    ("top","D",90.0,696.0,(22.0,68.0),2),
])
def test_real_source_2d_bends_holes_and_blank_sizes(role,tag,width,sample_span,bend_stations,holes):
    f=_sample_frame(role,sample_span)
    assert f.blank_width == width
    outline,source_holes,metadata=receiving_frame_source(role,material_width=width,span=f.span)
    assert metadata["receiving_frame_source_tag"]==tag
    assert len(source_holes)==holes
    data=build_inner_door_frame_render_data(f)
    cutting=[p for p in data.scene.primitives if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"]
    assert len(cutting)==1
    assert len(cutting[0].points)==len(outline)
    assert cutting[0].points==outline
    assert tuple(round(float(p.position),4) for p in data.fold_guides)==bend_stations
    assert data.material.bounds == pytest.approx((0,0,width,sample_span))
    assert len([p for p in data.scene.primitives if isinstance(p,CirclePrimitive) and p.layer=="CUTTING"])==holes


@pytest.mark.parametrize("role,expected_notch_depth",[
    ("left",20.3),("right",50.0),
])
def test_source_corner_reliefs_follow_top_end_at_other_panel_height(role,expected_notch_depth):
    size=1300.0
    f=_sample_frame(role,size)
    data=build_inner_door_frame_render_data(f)
    outline=next(p for p in data.scene.primitives if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING")
    ys=[float(p.y) for p in outline.points]
    assert max(ys)==pytest.approx(size)
    assert any(abs(y-(size-expected_notch_depth))<1e-6 for y in ys)
    assert data.material.bounds[3]==pytest.approx(size)
    assert data.metadata["receiving_frame_source_reference_span"]==1098.0


def test_D_two_source_holes_keep_same_offset_at_both_longitudinal_ends():
    f=_sample_frame("top",800.0)
    data=build_inner_door_frame_render_data(f)
    holes=[p for p in data.scene.primitives if isinstance(p,CirclePrimitive)]
    assert len(holes)==2
    assert sorted(round(p.center.y,4) for p in holes)==[10.5,789.5]
    assert all(p.center.x==pytest.approx(16.0) and p.radius==pytest.approx(3.2) for p in holes)


def test_frame_source_DXF_export_is_reopenable_with_true_notches_and_holes(tmp_path):
    for role,length in (("left",1098.),("right",1098.),("top",696.)):
        f=_sample_frame(role,length)
        d=build_inner_door_frame_render_data(f)
        path=tmp_path/f"{role}.dxf"
        save_part_render_data_dxf(d,path)
        ms=ezdxf.readfile(path).modelspace()
        assert len([e for e in ms if e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="CUTTING"])==1
        expected=2 if role=="top" else 0
        assert len([e for e in ms if e.dxftype()=="CIRCLE" and e.dxf.layer=="CUTTING"])==expected


def test_optional_nonreceiving_bottom_is_not_invented_from_part_D():
    frame=_sample_frame("bottom",700)
    data=build_inner_door_frame_render_data(frame)
    assert data.metadata.get("receiving_frame_source_tag") is None
    assert data.material.bounds==pytest.approx((0,0,90,700))


def test_receiving_1100_upper_bay_side_frames_reach_head_and_divider_in_actual_3d():
    """Independent DXF vs installation oracle: no 50-mm top-frame deduction."""
    from ae_engine.cabinet_types import receiving
    from ae_engine.cabinet_types import policy as family_policy
    from ae_engine.inner_door_frames import derive_all_inner_door_frames
    from ae_engine.assembly_placement import resolve_inner_door_frame_placement
    from ae_engine.contracts import FoldProfileSegment, ResolvedManufacturingPart
    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry

    snapshot = receiving.apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0,
        "d": 350.0, "t": 2.0, "fw": 29.0,
    })
    sample = certified_source_catalog()
    frames = derive_all_inner_door_frames(receiving.derive_inner_door_frame_sets(snapshot))
    side_frames = tuple(frame for frame in frames if frame.side in ("left", "right"))
    assert len(side_frames) == 2
    frame_by_side = {frame.side: frame for frame in frames}

    for side, source_id, width in (("left", "A", 90.0), ("right", "B", 110.0)):
        frame = frame_by_side[side]
        assert frame.span == pytest.approx(1098.0)
        assert frame.span == pytest.approx(sample[source_id]["sample_span"])
        assert frame.blank_width == pytest.approx(width)
        data = build_inner_door_frame_render_data(frame)
        assert data.material.bounds == pytest.approx((0, 0, width, 1098.0))

    upper = receiving.inner_door_vertical_frame_contract(snapshot, "upper")
    assert upper["top_terminal_y"] == pytest.approx(798.0)  # Head inside face = H/2 - T
    assert upper["lower_terminal_y"] == pytest.approx(-300.0)  # Shared Divider boundary
    assert upper["span"] == pytest.approx(1098.0)

    physical_parts = []
    for frame in frames:
        assembly = resolve_inner_door_frame_placement(snapshot, "upper", frame.side)
        physical_parts.append(ResolvedManufacturingPart(
            part_key=frame.stable_id,
            render_data=build_inner_door_frame_render_data(frame),
            x_profile=frame.fold_profile,
            y_profile=(FoldProfileSegment(length=frame.span),),
            placement=assembly.placement_kind,
            offset=assembly.world_offset,
        ))

    geometry = _phase6_build_joint_world_geometry(
        tuple(physical_parts), (800.0, 1600.0, 350.0), 2.0,
    )
    for frame in side_frames:
        skins = geometry["mapped_skin_triangles_by_part"][frame.stable_id]
        vertices = [point for skin in skins for point in skin.world]
        assert vertices
        assert min(p[1] for p in vertices) == pytest.approx(-300.0)
        assert max(p[1] for p in vertices) == pytest.approx(798.0)
        assert max(p[1] for p in vertices) - min(p[1] for p in vertices) == pytest.approx(1098.0)

    top = frame_by_side["top"]
    assert top.span == pytest.approx(sample["D"]["sample_span"])
    top_skins = geometry["mapped_skin_triangles_by_part"][top.stable_id]
    top_vertices = [point for skin in top_skins for point in skin.world]
    assert min(p[1] for p in top_vertices) == pytest.approx(750.0)
    assert max(p[1] for p in top_vertices) == pytest.approx(798.0)
