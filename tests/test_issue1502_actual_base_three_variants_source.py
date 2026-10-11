# -*- coding: utf-8 -*-
"""#1502 actual user base plate: THREE drawings, left/right flat, middle bent.

Only the uploaded source is a source of truth. These tests do not certify
manufacturing CUTTING, bend axes, mm scale or the mapping of option to NFB.
"""
import csv
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_actual_base_source import (
    _PATTERN_ROLES,
    inspect_receiving_nfb_actual_base,
    link_actual_base_to_verified_inner_door_nfb,
)
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)

KEYS=("LEFT_FLAT","CENTER_BENT","RIGHT_FLAT")
COLS=(
    "source_filename","sha256","pattern_key","fold_policy",
    "anchor_handle","min_x","max_x","line_count","arc_count",
    "circle_count","marking_211_lines","units_contract",
    "manufacturing_status",
)


def _case(tmp_path):
    source=tmp_path/"受電箱底板(1).dxf"
    doc=ezdxf.new("R2018")
    doc.header["$INSUNITS"]=0
    m=doc.modelspace()
    rows=[]
    for key, left, right in (
        ("LEFT_FLAT",10.,20.),
        ("CENTER_BENT",30.,50.),
        ("RIGHT_FLAT",60.,70.),
    ):
        anchor=m.add_line((left+1.,3.),(right-1.,3.),
                          dxfattribs={"color":7})
        m.add_circle(((left+right)/2.,6.),.5,dxfattribs={"color":7})
        m.add_arc(((left+right)/2.,9.),.6,0,180,dxfattribs={"color":7})
        count=1
        if key=="RIGHT_FLAT":
            m.add_line((left+2.,12.),(right-2.,12.),
                       dxfattribs={"color":211})
            count=2
        rows.append({
            "source_filename":source.name,
            "pattern_key":key,
            "fold_policy":_PATTERN_ROLES[key],
            "anchor_handle":anchor.dxf.handle,
            "min_x":str(left),
            "max_x":str(right),
            "line_count":str(count),
            "arc_count":"1",
            "circle_count":"1",
            "marking_211_lines":"1" if count==2 else "0",
            "units_contract":"DXF_INSUNITS_0_UNSPECIFIED",
            "manufacturing_status":"SOURCE_ONLY",
        })
    # Native CAD text or dimensions aren't NFB holes or CNC cutting.
    m.add_text("Q=11",dxfattribs={"height":2.}).set_placement((16.,14.))
    doc.saveas(source)
    digest=sha256(source.read_bytes()).hexdigest()
    for row in rows:
        row["sha256"]=digest
    index=tmp_path/"受電箱底板圖樣索引.csv"
    with index.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    return source,index,rows


def _proof():
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,
            "nfb_trial_export_approved":True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=("士林","400_140X257_107.dxf"),
        source_sha256="f"*64,
        physical_hole_ids=("nfb:h1","nfb:h2"),
        verified_hole_locations=(
            ("nfb:h1",-90.,1,0,0),("nfb:h2",90.,1,0,0),
        ),
    )


def test_three_source_variants_do_not_split_one_sheet_or_restore_lower_base(tmp_path):
    path,index,_=_case(tmp_path)
    before=path.read_bytes()
    source=inspect_receiving_nfb_actual_base(path,index_path=index)
    assert len(source.patterns)==3
    assert tuple(p.key for p in source.patterns)==KEYS
    assert tuple(p.fold_policy for p in source.patterns)==tuple(
        _PATTERN_ROLES[k] for k in KEYS
    )
    assert tuple(len(p.native_line_handles) for p in source.patterns)==(1,1,2)
    assert tuple(len(p.native_arc_handles) for p in source.patterns)==(1,1,1)
    assert tuple(len(p.native_circle_handles) for p in source.patterns)==(1,1,1)
    assert tuple(len(p.native_mark211_handles) for p in source.patterns)==(0,0,1)
    assert all(p.original_units=="DXF_INSUNITS_0_UNSPECIFIED" for p in source.patterns)
    assert not source.manufacturing_ready
    assert all(not p.manufacturing_ready for p in source.patterns)
    assert before==path.read_bytes()


def test_option_explicitly_follows_verified_inner_door_nfb_not_old_base_plate(tmp_path):
    path,index,_=_case(tmp_path)
    source=inspect_receiving_nfb_actual_base(path,index_path=index)
    for option in KEYS:
        link=link_actual_base_to_verified_inner_door_nfb(
            source,option,verified_inner_door=_proof(),
        )
        assert link.base_pattern_key==option
        assert link.fold_policy==_PATTERN_ROLES[option]
        assert link.inner_door_part_id=="inner_door:upper:panel"
        assert link.verified_physical_hole_ids==("nfb:h1","nfb:h2")
        assert link.nfb_indexed_model_key==("士林","400_140X257_107.dxf")
        assert link.base_source_sha256 != link.nfb_source_sha256
        assert link.manufacturing_ready is False
        assert "NO_UV_RELEASE" in link.status
    with pytest.raises(ValueError,match="missing/ambiguous"):
        link_actual_base_to_verified_inner_door_nfb(
            source,"LOWER_BASE",verified_inner_door=_proof(),
        )


def test_unsubmitted_or_duplicate_actual_inner_door_holes_not_reused(tmp_path):
    path,index,_=_case(tmp_path)
    source=inspect_receiving_nfb_actual_base(path,index_path=index)
    verified=_proof()
    with pytest.raises(ValueError,match="live verified"):
        link_actual_base_to_verified_inner_door_nfb(
            source,"LEFT_FLAT",
            verified_inner_door=replace(verified,manufacturing_ready=False),
        )
    with pytest.raises(ValueError,match="hole identities"):
        link_actual_base_to_verified_inner_door_nfb(
            source,"MIDDLE_BENT",
            verified_inner_door=replace(verified,physical_hole_ids=("nfb:h1","nfb:h1")),
        )
    with pytest.raises(ValueError,match="hole identities"):
        link_actual_base_to_verified_inner_door_nfb(
            source,"RIGHT_FLAT",
            verified_inner_door=replace(verified,verified_hole_locations=()),
        )


def test_changed_DXF_bytes_or_fold_roles_never_pass_original_fingerprint(tmp_path):
    path,index,rows=_case(tmp_path)
    with path.open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError,match="SHA"):
        inspect_receiving_nfb_actual_base(path,index_path=index)
    path,index,rows=_case(tmp_path)
    rows[1]["fold_policy"]="NO_BEND_USER_CONFIRMED"
    with index.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError,match="flat/bent"):
        inspect_receiving_nfb_actual_base(path,index_path=index)


def test_x_crossing_or_extra_cut_or_corrupt_mark_cannot_become_source_option(tmp_path):
    path,index,rows=_case(tmp_path)
    original=ezdxf.readfile(path)
    original.modelspace().add_line((19.,0.),(31.,0.),dxfattribs={"color":7})
    original.saveas(path)
    new_sha=sha256(path.read_bytes()).hexdigest()
    for row in rows:
        row["sha256"]=new_sha
    with index.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError,match="crosses/escapes"):
        inspect_receiving_nfb_actual_base(path,index_path=index)


def test_optional_exact_uploaded_real_DXF_three_drawing_observation():
    value=os.environ.get("WHD_RECEIVING_ACTUAL_BASE_DXF")
    if not value:
        pytest.skip("user's original three-pattern DXF is not committed")
    result=inspect_receiving_nfb_actual_base(value)
    assert result.sha256=="0a817ccedf83b22ca407e7d620d4de99b58aee716bd365742c994e09add24685"
    assert tuple(p.key for p in result.patterns)==KEYS
    assert [len(p.native_circle_handles) for p in result.patterns]==[8,16,6]
    assert [len(p.native_arc_handles) for p in result.patterns]==[12,16,12]
    assert [len(p.native_line_handles) for p in result.patterns]==[12,20,66]
    assert [len(p.native_mark211_handles) for p in result.patterns]==[0,0,26]
    assert not result.manufacturing_ready
