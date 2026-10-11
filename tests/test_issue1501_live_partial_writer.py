# -*- coding: utf-8 -*-
"""#1501 actual DXF export protected by LIVE original and saved physical proof."""
from hashlib import sha256

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_manufacturing_release import NfbConfiguredInnerDoorHole
from ae_engine.receiving_nfb_export_manifest import (
    NfbActualPart,INNER_DOOR,MIDDLE_PLATE,
)
from ae_engine.receiving_nfb_partial_export_writer import (
    export_current_nfb_inner_door_partial_dxf,
)
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope


def _case(tmp_path):
    snapshot=apply_family_defaults({
        "model":"受電箱","w":800.,"h":1600.,"d":350.,
        "t":2.,"fw":29.,"door_gap_w":3.5,"door_gap_h":3.5,
    })
    snapshot.update({
        "multi_door_enabled":True,
        "door_layout_scope":"receiving-main",
        "door_layout_columns":[[800.,[1100.,500.]]],
        "inner_doors":[{
            "stable_id":"upper","cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    inner=next(p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
               if p.inner_door_id=="upper")
    index=tmp_path/"開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    source=tmp_path/"400_140X257_107(1).dxf"
    d=ezdxf.new("R2010")
    entity=d.modelspace().add_lwpolyline(
        [(0.,0.),(57.,0.),(57.,96.),(0.,96.)],
        close=True,dxfattribs={"color":150},
    )
    d.saveas(source)
    profile=NfbUpperSourceProfile(
        "士林","400_140X257_107.dxf",sha256(source.read_bytes()).hexdigest(),
        entity.dxf.handle,(57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    )
    hole=NfbConfiguredInnerDoorHole("nfb:bay-a:hole-1",0.,1,0,90)
    bay={
        "stable_id":"bay-a",
        "nfb_config_submitted":True,
        "nfb_config":{"holes":[{
            "physical_hole_id":hole.physical_hole_id,
            "model_filename":profile.indexed_filename,
            "manual_x_mm":hole.world_x_mm,
            "manual_x_state":"CONFIRMED",
            "datum_revision":"operator-world-X-rev1",
            "datum_snapshot":{"w":800,"panel_id":inner.stable_id},
            "layer_count":1,"slot_index":0,"rotation_deg":90,
        }]},
    }
    scope=NfbPhysicalScope(
        "set-a","bay-a","v1",True,inner.stable_id,
        middle_plate_part_ids=("middle-a",),
    )
    args=dict(
        snapshot=snapshot,inner_door_id="upper",
        output_path=tmp_path/"inner_verified.dxf",
        saved_bay=bay,set_brand="士林",physical_scope=scope,
        actual_parts=(
            NfbActualPart(inner.stable_id,INNER_DOOR,2),
            NfbActualPart("middle-a",MIDDLE_PLATE,1),
        ),
        holes=(hole,),index_path=index,source_path=source,profile=profile,
    )
    return args


def test_actual_dxf_writer_emits_only_verified_inner_cutting_and_reports_partial(tmp_path):
    opts=_case(tmp_path)
    path,manifest=export_current_nfb_inner_door_partial_dxf(**opts)
    assert str(opts["output_path"])==str(path)
    assert opts["output_path"].exists()
    assert manifest.partial_only
    assert manifest.authorized_part_ids==(opts["physical_scope"].inner_door_part_id,)
    assert manifest.actual_export_count==2
    assert manifest.held_actual_count==1
    assert manifest.held_rows[0].part_id=="middle-a"
    model=ezdxf.readfile(path).modelspace()
    contours=[e for e in model if e.dxftype()=="LWPOLYLINE"
              and e.dxf.layer=="CUTTING" and e.closed]
    assert len(contours)==2
    assert contours[-1].dxf.color==3
    with pytest.raises((OSError,FileExistsError,ValueError)):
        export_current_nfb_inner_door_partial_dxf(**opts)


def test_changed_original_bytes_stops_before_any_output(tmp_path):
    opts=_case(tmp_path)
    source=opts["source_path"]
    source.write_bytes(source.read_bytes()+b"outdated")
    with pytest.raises(ValueError,match="SHA"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


@pytest.mark.parametrize("change,value",[
    ("manual_x_mm",20.),
    ("rotation_deg",0),
    ("slot_index",1),
    ("model_filename","unrelated.dxf"),
])
def test_saved_nfb_config_mismatch_rejects_export(tmp_path,change,value):
    opts=_case(tmp_path)
    opts["saved_bay"]["nfb_config"]["holes"][0][change]=value
    with pytest.raises(ValueError,match="BLOCKED"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


def test_bad_part_scope_and_missing_physical_part_never_write(tmp_path):
    opts=_case(tmp_path)
    opts["actual_parts"]=(NfbActualPart("unverified-inner",INNER_DOOR),)
    with pytest.raises(ValueError,match="absent/ambiguous"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


def test_unsubmitted_or_cross_bay_evidence_never_write(tmp_path):
    opts=_case(tmp_path)
    scope=opts["physical_scope"]
    opts["saved_bay"]["stable_id"]="wrong"
    with pytest.raises(ValueError,match="Bay stable ID"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()
    from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
    opts["physical_scope"]=NfbPhysicalScope(
        scope.set_id,scope.bay_id,scope.version_id,False,scope.inner_door_part_id,
    )
    with pytest.raises(ValueError,match="submitted"):
        export_current_nfb_inner_door_partial_dxf(**opts)
