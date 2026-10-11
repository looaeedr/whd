# -*- coding: utf-8 -*-
"""#1496: per-brand unique source color evidence is NEVER missing->zero."""
from dataclasses import replace
import csv

import ezdxf
import pytest

from ae_engine.receiving_nfb_index_sources import (
    NO_SOURCE, UNCERTIFIED, audit_unique_nfb_index_sources,
    build_nfb_indexed_color_evidence,
)


def _fixture(tmp_path):
    index = tmp_path / "開關索引.csv"
    with index.open("w", encoding="utf-8-sig", newline="") as out:
        writer=csv.writer(out)
        writer.writerow(("圖塊名稱","士林","深","東元","深","伍菱","深"))
        writer.writerow(("K1","A.dxf","107","A.dxf","99","A.dxf","101"))
        writer.writerow(("K2","a.DXF","107","A.dxf","99","無對應檔案",""))
    root=tmp_path/"NFB"
    (root/"士林").mkdir(parents=True)
    (root/"伍菱").mkdir(parents=True)
    shihlin=ezdxf.new("R2010")
    m=shihlin.modelspace()
    m.add_lwpolyline(
        ((0,0),(57,0),(57,96),(0,96)),close=True,
        dxfattribs={"color":150},
    )
    m.add_circle((5,5),3,dxfattribs={"color":30})
    m.add_line((0,0),(10,0),dxfattribs={"color":212})
    shihlin.saveas(root/"士林"/"A.dxf")
    # A real, valid, empty original has VERIFIED zero observed entities;
    # this does NOT certify it as a manufacturable NFB model.
    empty=ezdxf.new("R2010")
    empty.saveas(root/"伍菱"/"A.dxf")
    return index,root


def test_unique_model_links_keep_missing_unknown_distinct_from_real_zero(tmp_path):
    index,root=_fixture(tmp_path)
    catalog,audited=audit_unique_nfb_index_sources(index,nfb_root=root)
    assert catalog.records_read==2
    assert len(catalog.sources)==len(audited)==3
    rows=build_nfb_indexed_color_evidence(catalog,audited)
    assert [r.brand for r in rows]==["士林","東元","伍菱"]
    by_brand={r.brand:r for r in rows}
    shihlin=by_brand["士林"]
    assert shihlin.status==UNCERTIFIED
    assert shihlin.source_sha256 is not None
    assert (shihlin.aci30_count,shihlin.aci150_count,shihlin.aci212_count)==(1,1,1)
    assert len(shihlin.model_links)==2
    assert {r.model_key for r in shihlin.model_links}=={"K1","K2"}
    assert not shihlin.manufacturing_ready

    # SAME basename for other manufacturer is NOT the Shihlin source.
    teco=by_brand["東元"]
    assert teco.status==NO_SOURCE
    assert teco.source_sha256 is None
    assert (teco.aci30_count,teco.aci150_count,teco.aci212_count)==(None,None,None)
    assert len(teco.model_links)==2
    assert not teco.manufacturing_ready

    wuling=by_brand["伍菱"]
    assert wuling.status==UNCERTIFIED
    assert (wuling.aci30_count,wuling.aci150_count,wuling.aci212_count)==(0,0,0)
    assert len(wuling.model_links)==1
    assert not wuling.manufacturing_ready


def test_unresolved_native_color_cannot_masquerade_as_zero(tmp_path):
    index,root=_fixture(tmp_path)
    bad=ezdxf.new("R2010")
    bad.modelspace().add_line((0,0),(1,1),dxfattribs={"color":0})
    bad.saveas(root/"伍菱"/"A.dxf")
    catalog,audits=audit_unique_nfb_index_sources(index,nfb_root=root)
    rows=build_nfb_indexed_color_evidence(catalog,audits)
    wuling=next(row for row in rows if row.brand=="伍菱")
    assert wuling.source_sha256 is not None
    assert wuling.status=="SOURCE_UNRESOLVED_UNKNOWN"
    assert wuling.diagnostic is not None
    assert (wuling.aci30_count,wuling.aci150_count,wuling.aci212_count)==(None,None,None)
    assert not wuling.manufacturing_ready
    audited=next(row for row in audits if row.source.brand=="伍菱")
    assert audited.process_color_entity_counts is None


def test_unsupported_original_geometry_propagates_unknown_not_false_zero(tmp_path):
    index,root=_fixture(tmp_path)
    source=ezdxf.new("R2010")
    source.modelspace().add_ellipse(
        (0,0),major_axis=(10,0),ratio=.5,
    )
    source.saveas(root/"伍菱"/"A.dxf")
    cat,audit=audit_unique_nfb_index_sources(index,nfb_root=root)
    rows=build_nfb_indexed_color_evidence(cat,audit)
    wuling=next(x for x in rows if x.brand=="伍菱")
    assert wuling.status=="SOURCE_UNRESOLVED_UNKNOWN"
    assert wuling.aci30_count is None
    assert wuling.source_sha256 is not None


def test_missing_duplicate_and_foreign_audit_rejected_instead_of_merged(tmp_path):
    index,root=_fixture(tmp_path)
    catalog,audits=audit_unique_nfb_index_sources(index,nfb_root=root)
    with pytest.raises(ValueError,match="incomplete"):
        build_nfb_indexed_color_evidence(catalog,audits[:2])
    with pytest.raises(ValueError,match="duplicate"):
        build_nfb_indexed_color_evidence(catalog,(*audits,audits[0]))
    foreign=replace(audits[0],source=replace(audits[0].source,brand="NOT_INDEXED"))
    with pytest.raises(ValueError,match="foreign"):
        build_nfb_indexed_color_evidence(catalog,(foreign,*audits[1:]))
    poisoned=replace(audits[0],source=replace(audits[0].source,links=()))
    with pytest.raises(ValueError,match="links differ"):
        build_nfb_indexed_color_evidence(catalog,(poisoned,*audits[1:]))
