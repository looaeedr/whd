# -*- coding: utf-8 -*-
"""#1502 source separation uses original native handles, NOT ACI alone."""
from hashlib import sha256
import os
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_nfb_source_regions import (
    UPPER,LOWER,OBSERVED,DEFERRED,
    inspect_nfb_original_source_regions,
)


def _file(tmp_path,*,crossing=False,with_insert=False):
    path=tmp_path/"400_140X257_107.dxf"
    d=ezdxf.new("R2010")
    m=d.modelspace()
    up=m.add_lwpolyline([(0,350),(57,350),(57,446),(0,446)],
                         close=True,dxfattribs={"color":150})
    lo=m.add_lwpolyline([(-40,0),(104,0),(104,257),(-40,257)],
                         close=True,dxfattribs={"color":3})
    m.add_circle((5,310),2,dxfattribs={"color":30})
    m.add_line((-20,360),(-10,360),dxfattribs={"color":212})
    m.add_line((-20,100),(-10,100),dxfattribs={"color":212})
    m.add_circle((5,100),2,dxfattribs={"color":3})
    if crossing:
        m.add_line((0,230),(1,365),dxfattribs={"color":212})
    if with_insert:
        block=d.blocks.new(name="U")
        block.add_circle((0,0),2,dxfattribs={"color":30})
        m.add_blockref("U",(12,334))
    d.saveas(path)
    return path,up.dxf.handle,lo.dxf.handle,sha256(path.read_bytes()).hexdigest()


def _read(path,up,lo,digest):
    return inspect_nfb_original_source_regions(
        path,indexed_filename="400_140X257_107.dxf",
        expected_sha256=digest,
        upper_reference_handle=up,lower_reference_handle=lo,
        expected_upper_width_mm=57,expected_upper_height_mm=96,
    )


def test_native_groups_keep_aci212_upper_and_lower_separately(tmp_path):
    path,up,lo,digest=_file(tmp_path)
    proof=_read(path,up,lo,digest)
    assert proof.source_sha256==digest
    assert proof.upper.reference_handle==up
    assert proof.lower.reference_handle==lo
    assert dict(proof.upper.effective_color_counts)=={30:1,150:1,212:1}
    assert dict(proof.lower.effective_color_counts)=={3:2,212:1}
    assert len(proof.upper.entity_handles)==3
    assert len(proof.lower.entity_handles)==3
    assert proof.status==OBSERVED and proof.lower.region_status==DEFERRED
    assert not proof.manufacturing_ready
    assert not proof.upper.manufacturing_ready
    assert not proof.lower.manufacturing_ready
    assert 257<proof.separation_y_mm<350


def test_cross_boundary_source_entity_is_ambiguous_not_auto_assigned(tmp_path):
    path,up,lo,digest=_file(tmp_path,crossing=True)
    with pytest.raises(ValueError,match="crosses"):
        _read(path,up,lo,digest)


def test_hash_handle_size_and_upper_lower_owner_fail_closed(tmp_path):
    path,up,lo,digest=_file(tmp_path)
    with pytest.raises(ValueError,match="SHA"):
        _read(path,up,lo,"0"*64)
    with pytest.raises(ValueError,match="anchors"):
        _read(path,up,up,digest)
    with pytest.raises(ValueError,match="anchors"):
        _read(path,"NONEXISTENT",lo,digest)
    with pytest.raises(ValueError,match="typed closed source"):
        inspect_nfb_original_source_regions(
            path,indexed_filename=path.name,expected_sha256=digest,
            upper_reference_handle=lo,lower_reference_handle=up,
        )
    with pytest.raises(ValueError,match="width"):
        inspect_nfb_original_source_regions(
            path,indexed_filename=path.name,expected_sha256=digest,
            upper_reference_handle=up,lower_reference_handle=lo,
            expected_upper_width_mm=58,
        )


def test_insert_complex_group_is_not_silently_flattened_into_a_plate(tmp_path):
    path,up,lo,digest=_file(tmp_path,with_insert=True)
    with pytest.raises(ValueError,match="INSERT"):
        _read(path,up,lo,digest)


def test_optional_actual_shihlin_original_has_4_upper_212_and_23_lower_212():
    source=os.environ.get("WHD_NFB_ORIGINAL_DXF")
    if not source:
        pytest.skip("original customer DXF not checked into GitHub")
    path=Path(source)
    if path.name!="400_140X257_107.dxf":
        pytest.skip("exact indexed original source required")
    real=inspect_nfb_original_source_regions(
        path,indexed_filename=path.name,
        expected_sha256="8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3",
        upper_reference_handle="585",lower_reference_handle="597",
        expected_upper_width_mm=57,expected_upper_height_mm=96,
    )
    assert len(real.upper.entity_handles)==13
    assert len(real.lower.entity_handles)==28
    assert dict(real.upper.effective_color_counts)=={30:8,150:1,212:4}
    assert dict(real.lower.effective_color_counts)=={3:5,212:23}
    assert not real.manufacturing_ready
