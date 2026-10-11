# -*- coding: utf-8 -*-
"""#1502 original upper Color30 closed native CUTTING and Color212 MARKING."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_upper_base_source import (
    OBSERVED, inspect_nfb_upper_base_native_process,
)


def _source(tmp_path, *, missing_line=False, crossing=False, duplicate=False,
            bad_color=False, upper_mark_closed=True):
    path=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    upper=m.add_lwpolyline(
        [(0,350),(57,350),(57,446),(0,446)],
        close=True,dxfattribs={"color":150},
    )
    lower=m.add_lwpolyline(
        [(-40,0),(104,0),(104,257),(-40,257)],
        close=True,dxfattribs={"color":3},
    )
    circles=[
        m.add_circle((10+10*i,318),2,dxfattribs={"color":30})
        for i in range(4)
    ]
    corners=(
        [(65,315),(95,315),(95,335),(65,335)]
        if not crossing
        else [(65,315),(95,335),(65,335),(95,315)]
    )
    lines=[]
    for i in range(3 if missing_line else 4):
        a,b=corners[i],corners[(i+1)%4]
        lines.append(m.add_line(a,b,dxfattribs={"color":30}))
    if duplicate:
        m.add_line(corners[0],corners[1],dxfattribs={"color":30})
    marks=[
        m.add_lwpolyline(
            [(65+i*5,370),(65+i*5,385)],
            close=upper_mark_closed,
            dxfattribs={"color":(211 if bad_color and i==0 else 212)},
        )
        for i in range(4)
    ]
    lower_mark=m.add_line((10,100),(50,100),dxfattribs={"color":212})
    doc.saveas(path)
    sha=sha256(path.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        "士林",path.name,sha,upper.dxf.handle,
        (57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    )
    return path,profile,lower.dxf.handle,tuple(c.dxf.handle for c in circles),tuple(
        l.dxf.handle for l in lines
    ),tuple(e.dxf.handle for e in marks),lower_mark.dxf.handle


def test_shihlin_upper_native_color30_cutting_lines_are_closed_without_new_edges(tmp_path):
    source,profile,lower,circles,lines,marks,lower_mark=_source(tmp_path)
    before=source.read_bytes()
    result=inspect_nfb_upper_base_native_process(
        source,profile=profile,lower_reference_handle=lower,
    )
    assert result.status==OBSERVED and not result.manufacturing_ready
    assert result.source_sha256==profile.source_sha256
    assert result.upper_color150_handle==profile.upper_handle
    assert result.upper_color150_center_xy_mm==pytest.approx((28.5,398.))
    assert {item.source_handle for item in result.base_cutting_circles}==set(circles)
    assert len(result.base_cutting_closed_loops)==1
    loop=result.base_cutting_closed_loops[0]
    assert set(loop.source_handles)==set(lines)
    assert len(loop.vertices_xy_mm)==4
    assert loop.source_color_aci==30
    assert all(item.source_color_aci==30 for item in result.base_cutting_circles)
    assert {x.source_handle for x in result.base_marking_entities}==set(marks)
    assert all(item.source_color_aci==212 for item in result.base_marking_entities)
    assert all(item.source_closed is True for item in result.base_marking_entities)
    assert lower_mark in result.lower_deferred_handles
    assert lower_mark not in {m.source_handle for m in result.base_marking_entities}
    assert source.read_bytes()==before
    assert all(c.radius_mm==2 for c in result.base_cutting_circles)


@pytest.mark.parametrize("failure",(
    "missing_line","crossing","duplicate","bad_color",
))
def test_bad_color30_graph_and_ambiguous_process_color_fail_closed(tmp_path,failure):
    source,profile,lower,*_= _source(tmp_path,**{failure:True})
    with pytest.raises(ValueError):
        inspect_nfb_upper_base_native_process(
            source,profile=profile,lower_reference_handle=lower,
        )


def test_marking_can_remain_open_without_becoming_cutting(tmp_path):
    source,profile,lower,*_=_source(tmp_path,upper_mark_closed=False)
    item=inspect_nfb_upper_base_native_process(
        source,profile=profile,lower_reference_handle=lower,
    )
    assert len(item.base_marking_entities)==4
    assert all(mark.source_closed is False for mark in item.base_marking_entities)
    assert len(item.base_cutting_circles)==4
    assert len(item.base_cutting_closed_loops)==1


def test_exact_source_sha_and_upper_anchor_must_match(tmp_path):
    source,profile,lower,*_=_source(tmp_path)
    with pytest.raises(ValueError,match="SHA"):
        inspect_nfb_upper_base_native_process(
            source,profile=replace(profile,source_sha256="0"*64),
            lower_reference_handle=lower,
        )
    with pytest.raises(ValueError,match="anchors"):
        inspect_nfb_upper_base_native_process(
            source,profile=profile,lower_reference_handle=profile.upper_handle,
        )


def test_optional_shihlin_original_byte_replay_verifies_4_circles_4_lines_4_marks(tmp_path):
    real=os.environ.get("WHD_NFB_ORIGINAL_DXF")
    if not real:
        pytest.skip("original customer DXF is not checked into GitHub")
    path=Path(real)
    if path.name!="400_140X257_107.dxf":
        pytest.skip("exact Shihlin indexed original only")
    digest="8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
    profile=NfbUpperSourceProfile(
        "士林",path.name,digest,"585",(57.,96.),
        "SOURCE_ALIAS_SHA256_IDENTICAL","NFB-1497-SHIHLIN400-SOURCE-BYTE-IDENTITY-V2",
    )
    proof=inspect_nfb_upper_base_native_process(
        path,profile=profile,lower_reference_handle="597",
    )
    assert len(proof.base_cutting_circles)==4
    assert sum(len(loop.source_handles) for loop in proof.base_cutting_closed_loops)==4
    assert len(proof.base_marking_entities)==4
    assert len(proof.lower_deferred_handles)==28
    assert proof.source_sha256==digest
    assert not proof.manufacturing_ready
