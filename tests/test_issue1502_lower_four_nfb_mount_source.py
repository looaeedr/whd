# -*- coding: utf-8 -*-
"""#1502 native lower NFB fixing circles, not the lower spacer/pad drawing."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import os

import ezdxf
import pytest

from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_lower_fixing_source import (
    inspect_nfb_lower_four_fixing_circles,
)


def _original(tmp_path, *, with_extra_circle=False, bad_screw_color=False):
    path=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    upper=m.add_lwpolyline(
        [(0,350),(57,350),(57,446),(0,446)],
        close=True,dxfattribs={"color":150},
    )
    lower=m.add_lwpolyline(
        [(-50,0),(50,0),(50,257),(-50,257)],
        close=True,dxfattribs={"color":3},
    )
    centers=[(-15,115),(15,115),(-15,145),(15,145)]
    circles=[
        m.add_circle(c,1.6,dxfattribs={
            "color": 212 if bad_screw_color and i==0 else 3,
        })
        for i,c in enumerate(centers)
    ]
    if with_extra_circle:
        m.add_circle((0,170),1.6,dxfattribs={"color":3})
    # Distinct lower-world information is preserved but never imported as
    # cutting/marking on the receiving base.
    m.add_line((-30,60),(30,60),dxfattribs={"color":212})
    m.add_arc((0,80),4,0,180,dxfattribs={"color":3})
    m.add_circle((20,380),2,dxfattribs={"color":30})
    doc.saveas(path)
    digest=sha256(path.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        brand="士林",indexed_filename=path.name,source_sha256=digest,
        upper_handle=upper.dxf.handle,upper_size_mm=(57.,96.),
        source_alias_status="SOURCE_ALIAS_SHA256_IDENTICAL",revision="test",
    )
    return path,profile,lower.dxf.handle,tuple(c.dxf.handle for c in circles)


def test_only_original_lower_four_circles_are_mounting_screws(tmp_path):
    source,profile,lower,handles=_original(tmp_path)
    before=source.read_bytes()
    result=inspect_nfb_lower_four_fixing_circles(
        source,profile=profile,lower_reference_handle=lower,
    )
    assert result.indexed_filename==profile.indexed_filename
    assert result.source_sha256==profile.source_sha256
    assert result.screw_group_center_xy_mm==pytest.approx((0.,130.))
    assert {x.source_handle for x in result.circles}==set(handles)
    assert len(result.circles)==4
    assert all(x.radius_mm==pytest.approx(1.6) for x in result.circles)
    assert result.manufacturing_ready is False
    assert source.read_bytes()==before


@pytest.mark.parametrize("altered",("with_extra_circle","bad_screw_color"))
def test_source_lower_circle_mismatch_cannot_guess_a_quartet(tmp_path,altered):
    source,profile,lower,_=_original(tmp_path,**{altered:True})
    with pytest.raises(ValueError):
        inspect_nfb_lower_four_fixing_circles(
            source,profile=profile,lower_reference_handle=lower,
        )


def test_native_lower_screw_needs_matching_upper_NFB_source_identity(tmp_path):
    source,profile,lower,_=_original(tmp_path)
    with pytest.raises(ValueError,match="SHA"):
        inspect_nfb_lower_four_fixing_circles(
            source,profile=replace(profile,source_sha256="0"*64),
            lower_reference_handle=lower,
        )
    with pytest.raises(ValueError,match="anchors"):
        inspect_nfb_lower_four_fixing_circles(
            source,profile=profile,lower_reference_handle=profile.upper_handle,
        )


def test_optional_real_shihlin_lower_circle_source_replay():
    env=os.environ.get("WHD_NFB_ORIGINAL_DXF")
    if not env:
        pytest.skip("real original NFB DXF is not checked into the GitHub tree")
    source=Path(env)
    if source.name!="400_140X257_107.dxf":
        pytest.skip("only original Shihlin NFB source filename supported")
    profile=NfbUpperSourceProfile(
        "士林",source.name,
        "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3",
        "585",(57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL",
        "NFB-1497-SHIHLIN400-SOURCE-BYTE-IDENTITY-V2",
    )
    got=inspect_nfb_lower_four_fixing_circles(
        source,profile=profile,lower_reference_handle="597",
    )
    assert len(got.circles)==4
    assert len({x.center_xy_mm for x in got.circles})==4
    assert got.manufacturing_ready is False
