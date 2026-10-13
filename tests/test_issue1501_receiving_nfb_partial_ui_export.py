# -*- coding: utf-8 -*-
"""#1501 UI-to-real-writer contract; no UI status/flag can mint a DXF."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
from ae_engine.receiving_nfb_ui1b_bridge import NfbVerifiedDraftSubmission
from gui_modules.application import receiving_nfb_partial_export_action as action


def _case(monkeypatch, *, changed_source=False):
    digest="8" * 64
    name="400_140X257_107.dxf"
    profile=NfbUpperSourceProfile(
        "士林",name,("9"*64 if changed_source else digest),
        "585",(57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    )
    scope=NfbPhysicalScope("set-a","bay-a","v1",True,"inner-part")
    snapshot={
        "model":"受電箱","w":800.,"h":1600.,"t":2.,
        "multi_door_enabled":True,
        "inner_doors":[{"stable_id":"upper","cell_key":"0:0"}],
    }
    hole={"physical_hole_id":"nfb:bay-a:hole-1",
          "manual_x_mm":0.,"layer_count":1,"slot_index":0,
          "rotation_deg":90,"model_filename":name}
    bay={"stable_id":"bay-a","nfb_config_submitted":True,
         "nfb_config":{"holes":[hole]}}
    layout={"sets":[{"stable_id":"set-a","switch_brand":"士林",
                     "bays":[bay]}]}
    bundle=NfbVerifiedDraftSubmission(
        set_index=0,bay_index=0,version_id="v1",
        config=bay["nfb_config"],scope=scope,
        source_inventory=SimpleNamespace(source_sha256=digest),
        verified_door=SimpleNamespace(
            indexed_model_key=("士林",name),
            render_data=SimpleNamespace(metadata={
                "nfb_source_handle":digest+":585",
                "nfb_profile_revision":"v2",
            }),
        ),
        readiness=SimpleNamespace(can_submit=True),
        source_path="/real/士林/400_140X257_107(1).dxf",
        snapshot_at_verification=snapshot.copy(),
        bay_at_verification={"stable_id":"bay-a"},
    )
    physical=SimpleNamespace(
        stable_id="inner-part",cell_key="0:0",inner_door_id="upper",
    )
    monkeypatch.setattr(
        action.cabinet_family_policy,"derive_inner_door_panels",
        lambda snapshot: (physical,),
    )
    monkeypatch.setattr(
        action,"read_nfb_runtime_source_profiles_csv",
        lambda path: (profile,),
    )
    # This action contract mocks DXF I/O; actual format rebinding is tested
    # separately against real saved ezdxf bytes in #1502.
    monkeypatch.setattr(action,"resolve_editable_nfb_source_profile",
                        lambda path, *, profile: profile)
    hits=[]
    def exporter(snapshot, inner_id, output_path, **kwargs):
        hits.append((snapshot,inner_id,output_path,kwargs))
        return str(output_path),SimpleNamespace(actual_export_count=1)
    monkeypatch.setattr(
        action,"export_current_nfb_inner_door_partial_dxf",exporter,
    )
    arguments={
        "layout":layout,
        "current_snapshot":snapshot,
        "output_path":Path("nfb_inner_partial.dxf"),
    }
    return bundle,arguments,hits


def test_operator_export_reaches_existing_live_writer_with_real_saved_world_x(monkeypatch):
    bundle,args,hits=_case(monkeypatch)
    path,manifest=action.export_verified_receiving_nfb_inner_door(
        bundle,**args,
    )
    assert path==str(args["output_path"])
    assert manifest.actual_export_count==1
    assert len(hits)==1
    snapshot,inner_id,dest,params=hits[0]
    assert snapshot is args["current_snapshot"]
    assert inner_id=="upper"
    assert dest==args["output_path"]
    assert params["physical_scope"] is bundle.scope
    assert params["saved_bay"] is args["layout"]["sets"][0]["bays"][0]
    assert params["holes"][0].world_x_mm==0.
    assert params["holes"][0].rotation_deg==90
    assert params["holes"][0].physical_hole_id=="nfb:bay-a:hole-1"
    assert [part.part_id for part in params["actual_parts"]]==["inner-part"]
    assert params["overwrite"] is False


@pytest.mark.parametrize("failure",[
    "missing_evidence","moved_panel","changed_brand",
    "restored_bay","changed_world_x_geometry","wrong_physical_part",
])
def test_stale_or_invalid_session_never_calls_writer(monkeypatch,failure):
    bundle,args,hits=_case(monkeypatch)
    if failure=="missing_evidence":
        bundle=None
    elif failure=="moved_panel":
        args["current_snapshot"]=dict(args["current_snapshot"],w=750.)
    elif failure=="changed_brand":
        args["layout"]["sets"][0]["switch_brand"]="東元"
    elif failure=="restored_bay":
        args["layout"]["sets"][0]["bays"][0]["nfb_config_submitted"]=False
    elif failure=="changed_world_x_geometry":
        args["current_snapshot"]=dict(args["current_snapshot"],t=3.)
    elif failure=="wrong_physical_part":
        pass  # frozen bundle: replace below
    if failure=="wrong_physical_part":
        from dataclasses import replace
        bundle=replace(bundle,scope=NfbPhysicalScope(
            "set-a","bay-a","v1",True,"wrong-inner-part",
        ))
    with pytest.raises((ValueError,TypeError,AttributeError)):
        action.export_verified_receiving_nfb_inner_door(bundle,**args)
    assert hits==[]


def test_stale_session_source_mismatch_does_not_write(monkeypatch):
    bundle,args,hits=_case(monkeypatch,changed_source=True)
    with pytest.raises(ValueError,match="重新核對"):

        action.export_verified_receiving_nfb_inner_door(bundle,**args)
    assert hits==[]


def test_profile_handle_changed_on_same_dxf_bytes_requires_reverification(monkeypatch):
    bundle,args,hits=_case(monkeypatch)
    changed=NfbUpperSourceProfile(
        "士林","400_140X257_107.dxf","8"*64,
        "587",(57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    )
    monkeypatch.setattr(
        action,"read_nfb_runtime_source_profiles_csv",
        lambda path:(changed,),
    )
    with pytest.raises(ValueError,match="handle"):
        action.export_verified_receiving_nfb_inner_door(bundle,**args)
    assert hits==[]


def test_saved_holes_missing_or_unsubmitted_fail_closed(monkeypatch):
    bundle,args,hits=_case(monkeypatch)
    bay=args["layout"]["sets"][0]["bays"][0]
    bay["nfb_config"]["holes"]=[]
    with pytest.raises(ValueError,match="沒有實際加工孔"):
        action.export_verified_receiving_nfb_inner_door(bundle,**args)
    assert hits==[]


@pytest.mark.parametrize("key,value",[
    ("model","金庫型"),
    ("fw",50.),
    ("door_gap_w",2.0),
    ("door_gap_h",2.0),
    ("door_layout_scope","another-bay"),
    ("door_layout_columns",("new-column",)),
])
def test_manifest_and_export_share_geometry_staleness_keys(monkeypatch,key,value):
    bundle,args,hits=_case(monkeypatch)
    current=dict(args["current_snapshot"],**{key:value})
    assert action.nfb_verification_geometry_changed(
        current,bundle.snapshot_at_verification,
    )
    args["current_snapshot"]=current
    with pytest.raises(ValueError,match="實體內門已變更"):
        action.export_verified_receiving_nfb_inner_door(bundle,**args)
    assert hits==[]


def test_verified_geometry_fingerprint_accepts_unchanged_snapshot(monkeypatch):
    bundle,args,hits=_case(monkeypatch)
    assert not action.nfb_verification_geometry_changed(
        args["current_snapshot"],bundle.snapshot_at_verification,
    )
    with pytest.raises(TypeError,match="two snapshots"):
        action.nfb_verification_geometry_changed(None,{})
