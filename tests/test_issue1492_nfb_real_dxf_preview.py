# -*- coding: utf-8 -*-
"""#1492 true DXF source viewport, missing source, cache and transformations."""
from math import isclose
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_nfb_2d_preview import (
    NfbDxfPreviewCache, Nfb2DViewport, PREVIEW_ONLY, MISSING, UNREADABLE,
    sampled_source_strokes, resolve_indexed_dxf_path,
)
from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source


def _index(tmp_path):
    parent=tmp_path/"基準檔"/"開孔"/"NFB"
    parent.mkdir(parents=True)
    path=parent/"開關索引.csv"
    path.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "A,400_140X257_107.dxf,107,TECO.dxf,80,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    return path


def _real(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    d=ezdxf.new("R2010")
    m=d.modelspace()
    m.add_line((7,9),(18,21),dxfattribs={"color":30})
    m.add_circle((20,22),5,dxfattribs={"color":150})
    m.add_arc((40,41),7,start_angle=30,end_angle=140,
              dxfattribs={"color":212})
    m.add_lwpolyline(
        [(0,0,0.5),(20,0,0),(20,12,0),(0,12,0)],
        format="xyb",close=True,dxfattribs={"color":150},
    )
    d.saveas(path)
    return path


def test_missing_and_unindexed_dxf_cannot_show_fake_contour(tmp_path):
    index=_index(tmp_path)
    cache=NfbDxfPreviewCache()
    missing=cache.load("士林","400_140X257_107.dxf",index_path=index)
    assert missing.status==MISSING
    assert missing.strokes==() and missing.bounds is None
    assert missing.source_sha256 is None and not missing.manufacturing_ready
    assert "未找到" in missing.reason
    assert Path(missing.source_path).parent.name=="士林"
    with pytest.raises(ValueError,match="not indexed"):
        cache.load("東元","400_140X257_107.dxf",index_path=index)


def test_native_arc_circle_bulge_and_aci_preserved_in_real_source_strokes(tmp_path):
    index=_index(tmp_path)
    source=_real(index.parent/"士林"/"400_140X257_107.dxf")
    cache=NfbDxfPreviewCache()
    before=cache.parse_count
    result=cache.load("士林",source.name,index_path=index)
    assert result.status==PREVIEW_ONLY and result.source_sha256
    assert result.entity_count==4 and len(result.strokes)==4
    assert cache.parse_count==before+1
    assert result.approved_source_pivot is None
    assert result.manufacturing_ready is False
    assert {item[0] for item in result.strokes}=={30,150,212}
    inv=inspect_nfb_dxf_source(source)
    circle=next(e for e in inv.entities if e.dxf_type=="CIRCLE")
    arc=next(e for e in inv.entities if e.dxf_type=="ARC")
    poly=next(e for e in inv.entities if e.dxf_type=="LWPOLYLINE")
    c=sampled_source_strokes(circle)
    assert len(c)>20 and isclose(max(x for x,y in c),25,abs_tol=.2)
    assert isclose(min(x for x,y in c),15,abs_tol=.2)
    a=sampled_source_strokes(arc)
    assert len(a)>10
    assert a[0][0]==pytest.approx(40+7*3**.5/2)
    assert a[0][1]==pytest.approx(41+7/2)
    p=sampled_source_strokes(poly)
    assert len(p)>10
    assert any(abs(y)>1e-3 for x,y in p[:8])  # curved bulge, not straight chord


def test_pan_zoom_reset_never_reopens_source_or_changes_manufacturing(tmp_path):
    index=_index(tmp_path)
    source=_real(index.parent/"400_140X257_107.dxf")
    cache=NfbDxfPreviewCache()
    preview=cache.load("士林",source.name,index_path=index)
    vp=Nfb2DViewport()
    vp.set_source(preview)
    original=vp.strokes_for_canvas(400,300)
    count=cache.parse_count
    cxcy=(vp.cx,vp.cy)
    assert len(original)==4
    w=vp.to_world(115,87,400,300)
    vp.zoom(1.3,400,300,anchor=(115,87))
    assert vp.to_world(115,87,400,300)==pytest.approx(w)
    vp.pan(30,18)
    assert (vp.cx,vp.cy)!=cxcy
    assert len(vp.strokes_for_canvas(400,300))==4
    # repeated selection and all local viewport changes reuse source object
    assert cache.load("士林",source.name,index_path=index) is preview
    assert cache.parse_count==count
    vp.reset(400,300)
    assert vp.strokes_for_canvas(400,300)==original
    assert not preview.manufacturing_ready


def test_cache_changes_with_real_source_identity_and_bounded_memory(tmp_path):
    index=_index(tmp_path)
    source=_real(index.parent/"400_140X257_107.dxf")
    cache=NfbDxfPreviewCache(max_entries=2)
    first=cache.load("士林",source.name,index_path=index)
    assert cache.load("士林",source.name,index_path=index) is first
    d=ezdxf.readfile(source)
    d.modelspace().add_line((100,0),(120,20))
    d.saveas(source)
    second=cache.load("士林",source.name,index_path=index)
    assert second.source_sha256!=first.source_sha256
    assert second.entity_count==5
    assert cache.parse_count==2
    assert len(cache._entries)==1
    # The same filename under another brand is not a cache alias.
    with pytest.raises(ValueError,match="not indexed"):
        cache.load("東元",source.name,index_path=index)


def test_missing_then_present_reloads_without_project_write(tmp_path):
    index=_index(tmp_path)
    cache=NfbDxfPreviewCache()
    old=cache.load("士林","400_140X257_107.dxf",index_path=index)
    source=_real(index.parent/"士林"/"400_140X257_107.dxf")
    new=cache.load("士林",source.name,index_path=index)
    assert old.status==MISSING and new.status==PREVIEW_ONLY
    assert cache.parse_count==2
    assert index.read_bytes().startswith(b"\xef\xbb\xbf")


def test_canvas_world_roundtrip_and_reject_invalid_zoom(tmp_path):
    vp=Nfb2DViewport()
    vp.reset(320,240)
    vp.pan(10,20)
    point=(5.25,-7.5)
    pixel=vp.to_screen(*point,320,240)
    assert vp.to_world(*pixel,320,240)==pytest.approx(point)
    with pytest.raises(ValueError,match="zoom"):
        vp.zoom(0,320,240)
