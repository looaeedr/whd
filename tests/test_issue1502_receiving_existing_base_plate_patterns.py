# -*- coding: utf-8 -*-
"""#1502 receiving DRAWN Base Plate patterns in the EXISTING Base Plate owner."""
from dataclasses import replace

import ezdxf
import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import (
    build_part_render_data, generate_part,
)
from ae_engine.sheetmetal_drawing import PolylinePrimitive, CirclePrimitive, LinePrimitive
from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_LEFT,
    RECEIVING_BASE_PATTERN_CENTER,
    RECEIVING_BASE_PATTERN_RIGHT,
)


def _spec(pattern, *, part_id="base_plate"):
    central=pattern == RECEIVING_BASE_PATTERN_CENTER
    right=pattern == RECEIVING_BASE_PATTERN_RIGHT
    return BasePlatePartSpec(
        width=800.,height=280. if central else 360. if right else 340.,
        thickness=2.,shrink_top=20.,shrink_bottom=20.,
        shrink_left=85. if central else 45.,
        shrink_right=85. if central else 45.,
        bend=20.,model_name="受電箱",
        receiving_bend_pattern=pattern,physical_id=part_id,
    )


@pytest.mark.parametrize("pattern,dimensions,y_pitch,bends,raw_xpitch",[
    (RECEIVING_BASE_PATTERN_LEFT,(710.,300.),210.,2,670.),
    (RECEIVING_BASE_PATTERN_CENTER,(772.,240.),140.,6,732.),
    (RECEIVING_BASE_PATTERN_RIGHT,(710.,320.),210.,2,670.),
])
def test_receiving_original_base_part_now_uses_three_real_shaped_bend_patterns(
    pattern,dimensions,y_pitch,bends,raw_xpitch,tmp_path,
):
    spec=_spec(pattern)
    rendered=build_part_render_data(spec)
    assert rendered.material.bounds==pytest.approx((0.,0.,*dimensions))
    assert rendered.metadata["stable_id"]=="base_plate"
    assert rendered.metadata["receiving_bend_pattern"]==pattern
    assert rendered.metadata["receiving_nfb_base_mfg2_release_approved"] is False
    assert rendered.unfolded_topology.piece_id=="base_plate"
    assert rendered.unfolded_topology.width==pytest.approx(dimensions[0])
    assert rendered.unfolded_topology.height==pytest.approx(dimensions[1])
    cuts=[v for v in rendered.scene.primitives
          if isinstance(v,PolylinePrimitive)
          and v.layer=="CUTTING" and v.closed]
    assert len(cuts)==5 # 1 real plate outline + 4 real ear-mount slots
    assert len([v for v in rendered.scene.primitives if isinstance(v,LinePrimitive)
                and v.layer=="BEND"])==bends
    assert not any(isinstance(v,CirclePrimitive) and
                   v.source_type=="base_plate_mount"
                   for v in rendered.scene.primitives)
    ear_slots=cuts[1:]
    assert all(len(s.points)>100 for s in ear_slots)
    centers=[]
    for shape in ear_slots:
        xs=[point.x for point in shape.points]
        ys=[point.y for point in shape.points]
        assert max(xs)-min(xs)==pytest.approx(25.,abs=.02)
        assert max(ys)-min(ys)==pytest.approx(11.,abs=.02)
        centers.append(((min(xs)+max(xs))/2.,(min(ys)+max(ys))/2.))
    assert sorted(set(round(v[0],6) for v in centers)) == [
        20.,dimensions[0]-20.
    ]
    assert sorted(set(round(v[1],6) for v in centers))==pytest.approx([
        dimensions[1]/2.-y_pitch/2.,
        dimensions[1]/2.+y_pitch/2.,
    ])
    assert (dimensions[0]-40.)==pytest.approx(raw_xpitch)
    assert rendered.material.area < dimensions[0]*dimensions[1]

    # No new exporter: existing generate_part resolves the same final scene.
    out=tmp_path/(pattern+".dxf")
    result=generate_part(spec,out)
    assert result.part_kind=="base_plate"
    msp=ezdxf.readfile(out).modelspace()
    final_cuts=[e for e in msp if e.dxftype()=="LWPOLYLINE"
                and e.dxf.layer=="CUTTING" and e.closed]
    final_bends=[e for e in msp if e.dxftype()=="LINE" and e.dxf.layer=="BEND"]
    assert len(final_cuts)==5
    assert len(final_bends)==bends


def test_center_corrected_thickness_chain_produces_772_not_774():
    geom=build_part_render_data(_spec(RECEIVING_BASE_PATTERN_CENTER))
    xsegs=geom.unfolded_topology.x_segments
    assert [(x.name,x.length) for x in xsegs] == [
        ("ear_side_return_left",71.),
        ("base_face",630.),
        ("ear_side_return_right",71.),
    ]
    assert sum(x.length for x in xsegs)==772.
    x0=min(point.x for p in geom.scene.primitives
           if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING"
           for point in p.points)
    assert x0==0


def test_flat_variant_has_no_side_bending_and_keeps_top_bottom_20():
    for pattern in (RECEIVING_BASE_PATTERN_LEFT,RECEIVING_BASE_PATTERN_RIGHT):
        geom=build_part_render_data(_spec(pattern))
        bends=[v for v in geom.scene.primitives
               if isinstance(v,LinePrimitive) and v.layer=="BEND"]
        assert len(bends)==2
        assert all(v.p1.y==v.p2.y for v in bends)
        assert {round(v.p1.y,5) for v in bends}=={20.,geom.unfolded_topology.height-20.}


def test_receiving_illustration_cannot_override_family_or_mount_hole_datum():
    pattern=RECEIVING_BASE_PATTERN_CENTER
    state=_spec(pattern)
    invalid=[
        replace(state,model_name="金庫型"),
        replace(state,thickness=3.),
        replace(state,width=750.),
        replace(state,receiving_bend_pattern="guess"),
    ]
    for spec in invalid:
        with pytest.raises(ValueError):
            build_part_render_data(spec)
