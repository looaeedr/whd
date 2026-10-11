# -*- coding: utf-8 -*-
"""#1502 actual NFB bottom plate three native source-only DXF roundtrips."""
from pathlib import Path
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_actual_base_preview_split import (
    REFERENCE_ONLY,split_actual_nfb_base_reference_dxf,
)
from tests.test_issue1502_actual_base_native_loops import (
    _with_real_closed_outlines,
)
from tests.test_issue1502_actual_base_three_variants_source import _proof


def test_three_exact_ref_source_dxf_roundtrips_preserve_handles_and_no_CNC_approval(tmp_path):
    src,index=_with_real_closed_outlines(tmp_path)
    original_bytes=src.read_bytes()
    files=split_actual_nfb_base_reference_dxf(src,tmp_path,index_path=index)
    assert len(files)==3
    assert [p.pattern_key for p in files]==[
        "LEFT_FLAT","CENTER_BENT","RIGHT_FLAT",
    ]
    assert all(not p.manufacturing_ready and p.status==REFERENCE_ONLY for p in files)
    assert [p.native_loop_count for p in files]==[1,1,1]
    assert [p.unresolved_white_handle_count for p in files]==[0,0,1]
    expected=sum(len(p.original_handles) for p in files)
    original=ezdxf.readfile(src)
    assert expected==len(original.modelspace())
    all_handles=set()
    for p in files:
        output=Path(p.output_path)
        assert output.is_file()
        assert "來源預覽_禁止下料" in output.name
        doc=ezdxf.readfile(output)
        handles={e.dxf.handle for e in doc.modelspace()}
        assert handles==set(p.original_handles)
        assert not handles.intersection(all_handles)
        all_handles.update(handles)
    assert original_bytes==src.read_bytes()


def test_source_variants_must_never_overwrite_existing_or_make_more_parts(tmp_path):
    source,index=_with_real_closed_outlines(tmp_path)
    first=split_actual_nfb_base_reference_dxf(source,tmp_path,index_path=index)
    with pytest.raises(FileExistsError,match="overwrite"):
        split_actual_nfb_base_reference_dxf(source,tmp_path,index_path=index)
    assert len(first)==3
    assert len(list(tmp_path.glob("*_來源預覽_禁止下料.dxf")))==3


def test_selected_base_follows_actual_verified_NFB_no_new_position(tmp_path):
    source,index=_with_real_closed_outlines(tmp_path)
    with pytest.raises(ValueError,match="requires verified"):
        split_actual_nfb_base_reference_dxf(
            source,tmp_path,index_path=index,pattern_key="CENTER_BENT",
        )
    with pytest.raises(ValueError,match="select one explicit"):
        split_actual_nfb_base_reference_dxf(
            source,tmp_path,index_path=index,verified_inner_door=_proof(),
        )
    result=split_actual_nfb_base_reference_dxf(
        source,tmp_path,index_path=index,
        pattern_key="CENTER_BENT",verified_inner_door=_proof(),
    )
    assert len(result)==1 and result[0].pattern_key=="CENTER_BENT"
    assert not result[0].manufacturing_ready


def test_optional_user_original_exact_dxf_split_counts_and_source_preserved(tmp_path):
    value=os.environ.get("WHD_RECEIVING_ACTUAL_BASE_DXF")
    if not value:
        pytest.skip("uploaded original DXF not committed into GitHub")
    path=Path(value)
    before=path.read_bytes()
    pieces=split_actual_nfb_base_reference_dxf(path,tmp_path)
    assert [len(p.original_handles) for p in pieces]==[34,53,84]
    assert [p.native_loop_count for p in pieces]==[5,5,9]
    assert [p.unresolved_white_handle_count for p in pieces]==[0,0,12]
    assert path.read_bytes()==before
