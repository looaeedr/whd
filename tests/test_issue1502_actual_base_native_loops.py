# -*- coding: utf-8 -*-
"""#1502 actual flat / bent / flat base native loop source audit."""
import csv
from hashlib import sha256
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_actual_base_contours import (
    audit_receiving_nfb_actual_base_contours,
)
from tests.test_issue1502_actual_base_three_variants_source import (
    COLS, _case,
)


def _with_real_closed_outlines(tmp_path, *,missing_middle_segment=False,
                               right_open_extra=True):
    path,index,rows=_case(tmp_path)
    doc=ezdxf.readfile(path)
    m=doc.modelspace()
    for row in rows:
        anchor=doc.entitydb[row["anchor_handle"]]
        a=anchor.dxf.start
        b=anchor.dxf.end
        high=float(a.y)+10.
        new=[
            ((b.x,b.y),(b.x,high)),
            ((b.x,high),(a.x,high)),
            ((a.x,high),(a.x,a.y)),
        ]
        if missing_middle_segment and row["pattern_key"]=="CENTER_BENT":
            new=new[:2]
        for start,end in new:
            m.add_line(start,end,dxfattribs={"color":7})
        row["line_count"]=str(int(row["line_count"])+len(new))
    if right_open_extra:
        m.add_line((62.,19.),(68.,19.),dxfattribs={"color":7})
        rows[2]["line_count"]=str(int(rows[2]["line_count"])+1)
    doc.saveas(path)
    digest=sha256(path.read_bytes()).hexdigest()
    for row in rows:row["sha256"]=digest
    with index.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=COLS)
        writer.writeheader();writer.writerows(rows)
    return path,index


def test_three_independent_native_outer_contours_and_open_auxiliary_not_cut(tmp_path):
    path,index=_with_real_closed_outlines(tmp_path)
    original=path.read_bytes()
    audits=audit_receiving_nfb_actual_base_contours(path,index_path=index)
    assert [a.pattern_key for a in audits]==[
        "LEFT_FLAT","CENTER_BENT","RIGHT_FLAT",
    ]
    assert [len(a.closed_loop_handle_groups) for a in audits]==[1,1,1]
    assert [len(a.native_outer_loop_handles) for a in audits]==[4,4,4]
    assert [len(a.unresolved_white_source_handles) for a in audits]==[0,0,1]
    assert [len(a.original_mark211_handles) for a in audits]==[0,0,1]
    assert [a.manufacturing_ready for a in audits]==[False,False,False]
    assert path.read_bytes()==original


def test_missing_middle_native_outer_edge_is_not_repaired_or_certified(tmp_path):
    path,index=_with_real_closed_outlines(tmp_path,missing_middle_segment=True)
    before=path.read_bytes()
    with pytest.raises(ValueError,match="outer contour"):
        audit_receiving_nfb_actual_base_contours(path,index_path=index)
    assert path.read_bytes()==before


def test_optional_original_real_DXF_exact_loop_groups_and_12_open_right_lines():
    path=os.environ.get("WHD_RECEIVING_ACTUAL_BASE_DXF")
    if not path:
        pytest.skip("user's actual uploaded base DXF not published to CI")
    audits=audit_receiving_nfb_actual_base_contours(path)
    assert [a.pattern_key for a in audits]==[
        "LEFT_FLAT","CENTER_BENT","RIGHT_FLAT",
    ]
    assert [len(a.closed_loop_handle_groups) for a in audits]==[5,5,9]
    assert [len(a.unresolved_white_source_handles) for a in audits]==[0,0,12]
    assert [len(a.native_outer_loop_handles) for a in audits]==[8,20,8]
    assert [len(a.original_circle_handles) for a in audits]==[8,16,6]
    assert [len(a.original_mark211_handles) for a in audits]==[0,0,26]
    assert all(not a.manufacturing_ready for a in audits)
