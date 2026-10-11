# -*- coding: utf-8 -*-
"""#1502 native NFB LOWER four-circle source vs actual base fixing signatures."""
from hashlib import sha256

import ezdxf
import pytest

from ae_engine.receiving_nfb_lower_fixing_match import (
    STATUS, match_lower_nfb_source_fixing_circles,
)
from ae_engine.receiving_nfb_middle_fixing_holes import (
    inspect_middle_base_nfb_fixing_holes,
)
from tests.test_issue1502_middle_nfb_fixing_holes import _source


def _lower_original(tmp_path, *, width=4.,height=5.,radius=1.6):
    path=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    up=m.add_lwpolyline(
        [(0,350),(57,350),(57,446),(0,446)],
        close=True,dxfattribs={"color":150},
    )
    low=m.add_lwpolyline(
        [(0,0),(144,0),(144,257),(0,257)],
        close=True,dxfattribs={"color":3},
    )
    c=[]
    for x in (50.,50.+width):
        for y in (40.,40.+height):
            c.append(m.add_circle((x,y),radius,dxfattribs={"color":3}))
    # Other LOWER pad/mark shapes remain excluded, even if originally
    # present beside the CIRCLEs.
    m.add_line((10,90),(30,90),dxfattribs={"color":212})
    doc.saveas(path)
    return path,sha256(path.read_bytes()).hexdigest(),up.dxf.handle,low.dxf.handle,tuple(e.dxf.handle for e in c)


def _match(actual, original, digest, up, low):
    return match_lower_nfb_source_fixing_circles(
        actual,original,indexed_filename="400_140X257_107.dxf",
        nfb_source_sha256=digest,
        upper_reference_handle=up,
        lower_reference_handle=low,
    )


def test_lower_native_four_circles_match_multiple_verified_base_quartet_candidates(tmp_path):
    base,index,_=_source(tmp_path)
    evidence=inspect_middle_base_nfb_fixing_holes(base,index_path=index)
    nfb,digest,upper,lower,original_handles=_lower_original(tmp_path)
    proof=_match(evidence,nfb,digest,upper,lower)
    assert proof.status==STATUS and not proof.manufacturing_ready
    assert proof.nfb_lower_source_sha256==digest
    assert set(proof.nfb_lower_circle_handles)==set(original_handles)
    assert proof.lower_source_spacing_mm==pytest.approx((4.,5.))
    assert proof.lower_source_radius_mm==pytest.approx(1.6)
    assert len(proof.candidate_quartet_indices)==3
    assert proof.ambiguous_source_quartet is True
    assert all(evidence.quartets[k].horizontal_pitch==pytest.approx(4.)
               for k in proof.candidate_quartet_indices)


def test_source_alternative_quartet_unique_but_still_not_manufacturing(tmp_path):
    base,index,_=_source(tmp_path)
    evidence=inspect_middle_base_nfb_fixing_holes(base,index_path=index)
    nfb,digest,up,low,_=_lower_original(tmp_path,width=4.4,height=3.)
    match=_match(evidence,nfb,digest,up,low)
    assert len(match.candidate_quartet_indices)==1
    assert match.ambiguous_source_quartet is False
    assert not match.manufacturing_ready


@pytest.mark.parametrize("width,height,radius",[
    (6.,5.,1.6),(4.,7.,1.6),(4.,5.,2.2),
])
def test_source_lower_circle_size_mismatch_fails_closed(tmp_path,width,height,radius):
    base,index,_=_source(tmp_path)
    evidence=inspect_middle_base_nfb_fixing_holes(base,index_path=index)
    nfb,digest,up,low,_=_lower_original(
        tmp_path,width=width,height=height,radius=radius,
    )
    with pytest.raises(ValueError,match="differs"):
        _match(evidence,nfb,digest,up,low)


def test_modified_lower_source_sha_or_wrong_reference_rejected(tmp_path):
    base,index,_=_source(tmp_path)
    evidence=inspect_middle_base_nfb_fixing_holes(base,index_path=index)
    nfb,digest,up,low,_=_lower_original(tmp_path)
    with pytest.raises(ValueError,match="SHA"):
        _match(evidence,nfb,"0"*64,up,low)
    with pytest.raises(ValueError,match="anchors"):
        _match(evidence,nfb,digest,up,up)
