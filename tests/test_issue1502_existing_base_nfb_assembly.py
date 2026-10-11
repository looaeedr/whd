# -*- coding: utf-8 -*-
"""#1502 physical upper base/ear slots/NFB share original manufacturing owner."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import save_part_render_data_dxf
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.sheetmetal_drawing import PolylinePrimitive, CirclePrimitive


def _snapshot():
    snapshot = apply_family_defaults({
        "model": "受電箱", "w":800., "h":1600., "d":350., "t":2.,
        "fw":29., "door_gap_w":3.5, "door_gap_h":3.5,
    })
    snapshot.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.,[1100.,500.]]],
        "inner_doors":[{
            "stable_id":"upper","cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    return snapshot


def _upper_base(pattern="LEFT_FLAT_SIDE"):
    central=pattern=="CENTER_DOUBLE_SIDE_FOLD"
    return BasePlatePartSpec(
        width=800.,height=1100.,thickness=2.,
        shrink_top=20.,shrink_bottom=20.,
        shrink_left=85. if central else 45.,
        shrink_right=85. if central else 45.,
        bend=20.,model_name="受電箱",
        receiving_bend_pattern=pattern,
        physical_id="base_plate_c1_r1",
    )


def _native_original(tmp_path):
    path=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    upper=m.add_lwpolyline(
        [(0.,350.),(57.,350.),(57.,446.),(0.,446.)],
        close=True,dxfattribs={"color":150},
    )
    lower=m.add_lwpolyline(
        [(-50.,0.),(50.,0.),(50.,257.),(-50.,257.)],
        close=True,dxfattribs={"color":3},
    )
    for x in (-40.,-25.,70.,85.):
        m.add_circle((x,398.),2.,dxfattribs={"color":30})
    corners=((35.,410.),(45.,410.),(45.,420.),(35.,420.))
    for i in range(4):
        m.add_line(corners[i],corners[(i+1)%4],dxfattribs={"color":30})
    for x in (10.,16.,22.,28.):
        m.add_line((x,435.),(x+3.,435.),dxfattribs={"color":212})
    for x in (-10.,10.):
        for y in (110.,130.):
            m.add_circle((x,y),1.4,dxfattribs={"color":3})
    doc.saveas(path)
    digest=sha256(path.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        brand="士林",indexed_filename=path.name,
        source_sha256=digest,upper_handle=upper.dxf.handle,
        upper_size_mm=(57.,96.),
        source_alias_status="SOURCE_ALIAS_SHA256_IDENTICAL",
        revision="SYNTHETIC_TWO_GROUP_1502",
    )
    return path,profile,lower.dxf.handle


def _verified(profile):
    locations=(
        ("nfb:upper:1", -100., 1, 0, 0),
        ("nfb:upper:2", 100., 1, 0, 90),
    )
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,
            "nfb_trial_export_approved":True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=(profile.brand,profile.indexed_filename),
        source_sha256=profile.source_sha256,
        physical_hole_ids=tuple(row[0] for row in locations),
        verified_hole_locations=locations,
    )


def _build(tmp_path, *, base=None, snapshot=None, proof=None):
    path,profile,lower=_native_original(tmp_path)
    return build_existing_receiving_base_with_verified_nfb(
        snapshot=snapshot or _snapshot(),
        inner_door_id="upper",
        base_spec=base or _upper_base(),
        verified_inner_door=proof or _verified(profile),
        source_path=path,
        profile=profile,
        lower_reference_handle=lower,
    )


@pytest.mark.parametrize("pattern",("LEFT_FLAT_SIDE","CENTER_DOUBLE_SIDE_FOLD","RIGHT_FLAT_SIDE"))
def test_existing_upper_base_ear_NFB_finalscene_are_one_real_part(tmp_path,pattern):
    combined=_build(tmp_path,base=_upper_base(pattern))
    assert not combined.manufacturing_ready
    real=combined.render_data
    assert real.metadata["stable_id"]=="base_plate_c1_r1"
    assert real.metadata["nfb_base_mfg2_release_approved"] is False
    assert real.metadata["nfb_physical_hole_ids"]==(
        "nfb:upper:1","nfb:upper:2",
    )
    cuts=[x for x in real.scene.primitives if
          isinstance(x,PolylinePrimitive) and x.layer=="CUTTING" and x.closed]
    # Exterior + 4 EAR slots + 2 upper native source closed contours.
    assert len(cuts)==7
    native=[x for x in real.scene.primitives if
            isinstance(x,CirclePrimitive)
            and x.source_type=="NFB_LOWER_NATIVE_FIXING_CIRCLE"]
    assert len(native)==8  # 4 original lower screw circles per verified NFB
    assert len({x.source_id for x in native})==8
    assert real.material.area>0
    assert real.unfolded_topology.piece_id=="base_plate_c1_r1"
    assert real.metadata["nfb_source_sha256"]==combined.projection.source_sha256
    # Headless original serialization must use the SAME FinalScene, not a
    # freshly generated legacy base without the configured NFB features.
    out=tmp_path/(pattern+".dxf")
    save_part_render_data_dxf(real,out)
    imported=ezdxf.readfile(out).modelspace()
    assert len(imported.query("CIRCLE[layer=='CUTTING']"))>=8
    assert len(imported.query("LWPOLYLINE[layer=='CUTTING']"))>=7
    assert len(imported.query("LWPOLYLINE[layer=='MARKING']"))>=8


def test_lower_bay_does_not_create_second_base_plate(tmp_path):
    with pytest.raises(ValueError,match="upper cell"):
        _build(tmp_path,base=replace(_upper_base(),physical_id="base_plate_c1_r2"))
    with pytest.raises(ValueError,match="physical ID"):
        _build(tmp_path,base=replace(_upper_base(),physical_id="base_plate"))


def test_source_owner_and_geometry_fail_closed(tmp_path):
    with pytest.raises(ValueError,match="bend-pattern"):
        _build(tmp_path,base=replace(_upper_base(),receiving_bend_pattern=None))
    with pytest.raises(ValueError,match="actual upper cell"):
        _build(tmp_path,base=replace(_upper_base(),height=1600.))
    with pytest.raises(ValueError,match="box W/T"):
        _build(tmp_path,base=replace(_upper_base(),width=900.))
    with pytest.raises(ValueError,match="Receiving cabinet"):
        _build(tmp_path,base=replace(_upper_base(),model_name="金庫型"))
