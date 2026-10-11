# -*- coding: utf-8 -*-
"""#1502 NFB lower source group CIRCLE ownership -> actual center-base holes.

NFB lower OTHER geometry is still excluded. No guessed version/slot mapping;
two alternative 4-hole rectangles share a source center and stay distinct.
"""
from dataclasses import replace
from hashlib import sha256
from math import sqrt
import csv
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_middle_fixing_holes import (
    ROLE, SOURCE_ONLY, inspect_middle_base_nfb_fixing_holes,
)
from tests.test_issue1502_actual_base_three_variants_source import _case, COLS


def _source(tmp_path):
    source,index,rows=_case(tmp_path)
    doc=ezdxf.readfile(source)
    m=doc.modelspace()
    # Replace test's solitary placeholder circle on the middle with real
    # independent NFB four-fixing-hole rectangles, including an alternate
    # quartet at the same switch X center.
    for e in tuple(m):
        if e.dxftype()=="CIRCLE" and 30<float(e.dxf.center.x)<50:
            m.delete_entity(e)
    specs=(
        (32.,36.,7.,12.),
        (39.,43.,7.,12.),
        (44.,48.,7.,12.),
        (31.8,36.2,8.,11.),
    )
    for left,right,bottom,top in specs:
        for x in (left,right):
            for y in (bottom,top):
                m.add_circle((x,y),1.6,dxfattribs={"color":7})
    doc.saveas(source)
    rows[1]["circle_count"]="16"
    digest=sha256(source.read_bytes()).hexdigest()
    for row in rows:row["sha256"]=digest
    with index.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return source,index,rows


def _normalized(tmp_path,source, *,left_right_bend=False,move=False):
    converted=tmp_path/"受電箱底板(4).dxf"
    doc=ezdxf.new("R2013")
    doc.header["$INSUNITS"]=4
    doc.layers.new("CUTTING")
    doc.layers.new("BENDING")
    m=doc.modelspace()
    original=ezdxf.readfile(source)
    center_rows=[
        e for e in original.modelspace()
        if e.dxftype()=="CIRCLE" and 30<e.dxf.center.x<50
    ]
    for n,e in enumerate(center_rows):
        x=float(e.dxf.center.x) + (0.2 if move and n==0 else 0)
        y=float(e.dxf.center.y);r=float(e.dxf.radius)
        vertices=[(x+r,y,sqrt(2)-1),(x,y+r,sqrt(2)-1),
                  (x-r,y,sqrt(2)-1),(x,y-r,sqrt(2)-1)]
        m.add_lwpolyline(
            vertices,format="xyb",close=True,dxfattribs={"layer":"CUTTING"}
        )
    if left_right_bend:
        m.add_line((10.,3.),(20.,3.),dxfattribs={"layer":"BENDING"})
        m.add_line((60.,3.),(70.,3.),dxfattribs={"layer":"BENDING"})
    doc.saveas(converted)
    return converted


def test_16_source_circles_are_NFB_lower_fixing_candidates_not_lower_plate(tmp_path):
    original,index,_=_source(tmp_path)
    before=original.read_bytes()
    evidence=inspect_middle_base_nfb_fixing_holes(original,index_path=index)
    assert evidence.original_source_sha256==sha256(before).hexdigest()
    assert evidence.status==SOURCE_ONLY and not evidence.manufacturing_ready
    assert evidence.raw_circle_count==16
    assert len(evidence.quartets)==4
    assert all(len(q.original_handles)==4 and q.role==ROLE for q in evidence.quartets)
    assert all(q.circle_radius==pytest.approx(1.6) for q in evidence.quartets)
    assert sorted(round(q.horizontal_pitch,4) for q in evidence.quartets)==[
        4.,4.,4.,4.4,
    ]
    # Separate overlapping source quartets; none are discarded/deduplicated.
    assert len({h for q in evidence.quartets for h in q.original_handles})==16
    assert before==original.read_bytes()


def test_processed_closed_bulge_circles_match_exact_original_centers_and_radii(tmp_path):
    original,index,_=_source(tmp_path)
    converted=_normalized(tmp_path,original,left_right_bend=True)
    data=inspect_middle_base_nfb_fixing_holes(
        original,index_path=index,converted_dxf_path=converted
    )
    assert data.converted_circle_match
    assert len(data.fold_layer_conflicts)==2
    assert all("BENDING_LAYER_CONFLICTS_WITH_USER_FLAT_RULE" in row
               for row in data.fold_layer_conflicts)
    assert not data.manufacturing_ready
    with pytest.raises(ValueError,match="differ from original"):
        inspect_middle_base_nfb_fixing_holes(
            original,index_path=index,converted_dxf_path=_normalized(
                tmp_path,original,move=True
            )
        )


def test_missing_one_circle_fails_instead_of_renumbering_physical_holes(tmp_path):
    original,index,rows=_source(tmp_path)
    doc=ezdxf.readfile(original)
    circle=next(e for e in doc.modelspace()
                if e.dxftype()=="CIRCLE" and 30<e.dxf.center.x<50)
    doc.modelspace().delete_entity(circle)
    doc.saveas(original)
    digest=sha256(original.read_bytes()).hexdigest()
    for row in rows:row["sha256"]=digest
    rows[1]["circle_count"]="15"
    with index.open("w",encoding="utf-8",newline="") as h:
        writer=csv.DictWriter(h,fieldnames=COLS)
        writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match="two-row|16 native"):
        inspect_middle_base_nfb_fixing_holes(original,index_path=index)


def test_optional_original_400_fixing_holes_and_converted_variant():
    from pathlib import Path
    raw=os.environ.get("WHD_RECEIVING_ACTUAL_BASE_DXF")
    if not raw:
        pytest.skip("original actual user CAD bytes not stored in GitHub")
    converted=os.environ.get("WHD_RECEIVING_CONVERTED_BASE_DXF")
    evidence=inspect_middle_base_nfb_fixing_holes(
        raw,converted_dxf_path=converted,
    )
    assert evidence.original_source_sha256==(
        "0a817ccedf83b22ca407e7d620d4de99b58aee716bd365742c994e09add24685"
    )
    assert evidence.raw_circle_count==16
    assert [round(q.horizontal_pitch) for q in evidence.quartets]==[30,35,30,30]
    assert sorted(round(q.vertical_pitch) for q in evidence.quartets)==[126,132,132,132]
    assert len({q.center_xy for q in evidence.quartets})==3
    if converted:
        assert evidence.converted_circle_match
        assert len(evidence.fold_layer_conflicts)==4
