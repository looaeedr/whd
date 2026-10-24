# -*- coding: utf-8 -*-
"""#1500 world-X bridge / source-profile CSV contract unit tests.

Use a mock typed MFG-1 proof for bridge mapping only; the real DXF
source reader still runs. Full geometry verification is separately covered
by #1497's own product regression, not invented by these unit tests.
"""
from hashlib import sha256
from types import SimpleNamespace
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft,add_nfb_draft_slot
from ae_engine.receiving_nfb_ui1a_edits import editable_nfb_draft,set_nfb_manual_x
from ae_engine.receiving_nfb_cutting_manufacturing import (
    NfbUpperSourceProfile,read_nfb_runtime_source_profiles_csv,
)
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender,VALIDATED,
)
from ae_engine.receiving_nfb_ui1b_bridge import (
    verify_nfb_ui1a_for_submit,assert_live_verified_nfb,submit_live_verified_nfb,
    copy_live_verified_nfb,
)
import ae_engine.receiving_nfb_ui1b_bridge as bridge


def _setup(tmp_path,monkeypatch):
    original=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline(
        [(0,0),(57,0),(57,96),(0,96)],close=True,
        dxfattribs={"color":150},
    )
    doc.saveas(original)
    digest=sha256(original.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        "士林",original.name,digest,"TEST_HANDLE",(57,96),
        "SOURCE_OBSERVED_UNCERTIFIED","TEST_V1",
    )
    draft=editable_nfb_draft(new_nfb_ui1a_draft(set_brand="士林"))
    draft=add_nfb_draft_slot(draft,0,filename=original.name,source_brand="士林")
    draft=set_nfb_manual_x(draft,0,0,17.5)
    unit=draft["layers"][0]["slots"][0]["unit_id"]
    bay={"stable_id":"bay-a"}
    layout={"sets":[{"stable_id":"set-a","switch_brand":"士林","bays":[bay]}]}
    scope=NfbPhysicalScope("set-a","bay-a","v1",True,"inner-a",
                           middle_plate_part_ids=("middle-a",))
    emitted=[]
    def manufacturing(_snapshot,_door,*,holes,index_path,source_path,profile,existing_claims=()):
        assert Path(source_path)==original
        assert profile.source_sha256==digest
        emitted.extend(holes)
        return NfbValidatedInnerDoorRender(
            render_data=SimpleNamespace(metadata={
                "nfb_trial_status":VALIDATED,
                "nfb_trial_export_approved":True,
            }),
            part_id="inner-a",
            indexed_model_key=("士林",original.name),
            source_sha256=digest,
            physical_hole_ids=tuple(h.physical_hole_id for h in holes),
            verified_hole_locations=tuple(
                (h.physical_hole_id,h.world_x_mm,h.layer_count,h.slot_index,h.rotation_deg)
                for h in holes
            ),
        )
    monkeypatch.setattr(bridge,"configured_nfb_inner_door_render_data",manufacturing)
    return {
        "draft":draft,"layout":layout,"set_index":0,"bay_index":0,
        "version_id":"v1","snapshot":{"model":"受電箱"},
        "inner_door_id":"door-a","physical_scope":scope,
        "world_x_by_unit":{unit:0.0},
        "datum_revision":"operator-measured-inner-a-v1",
        "datum_snapshot":{"bay_width_mm":800,"panel_id":"inner-a"},
        "index_path":tmp_path/"開關索引.csv",
        "source_path":original,"profile":profile,
    },unit,emitted


def test_verified_bridge_never_uses_tentative_x_offset_as_world_x(tmp_path,monkeypatch):
    kwargs,unit,emitted=_setup(tmp_path,monkeypatch)
    verified=verify_nfb_ui1a_for_submit(**kwargs)
    assert verified.can_submit
    assert verified.config["holes"][0]["manual_x_mm"]==0.0
    assert verified.config["holes"][0]["operator_offset_mm"]==17.5
    assert emitted[0].world_x_mm==0.0
    assert emitted[0].physical_hole_id=="nfb:set-a:bay-a:"+unit
    assert verified.config["holes"][0]["manual_x_state"]=="CONFIRMED"
    assert verified.source_inventory.source_sha256==kwargs["profile"].source_sha256
    assert verified.held_parts==("middle-a",)


def test_world_x_must_be_explicit_complete_and_finite(tmp_path,monkeypatch):
    kwargs,unit,_=_setup(tmp_path,monkeypatch)
    for bad in ({}, {unit:None},{unit:float("nan")},{unit:True},
                {unit:0,"not-in-draft":99}):
        with pytest.raises(ValueError,match="world-X|WORLD X"):
            verify_nfb_ui1a_for_submit(**{**kwargs,"world_x_by_unit":bad})
    assert kwargs["draft"]["layers"][0]["slots"][0]["manual_x_mm"]==17.5


def test_stale_scope_or_brand_mismatch_fails_before_verification(tmp_path,monkeypatch):
    kwargs,unit,emitted=_setup(tmp_path,monkeypatch)
    for altered in (
        {"version_id":"wrong"},
        {"bay_index":2},
        {"physical_scope":NfbPhysicalScope("set-a","bay-b","v1",True,"inner-a")},
        {"datum_revision":""},
        {"datum_snapshot":{}},
    ):
        with pytest.raises((ValueError,IndexError,KeyError)):
            verify_nfb_ui1a_for_submit(**{**kwargs,**altered})
    assert not emitted


def test_different_models_cannot_reuse_shihlin_profile(tmp_path,monkeypatch):
    kwargs,unit,emitted=_setup(tmp_path,monkeypatch)
    draft=editable_nfb_draft(add_nfb_draft_slot(kwargs["draft"],0,
                             filename="not-the-400.dxf",source_brand="士林"))
    second=draft["layers"][0]["slots"][1]["unit_id"]
    with pytest.raises(ValueError,match="not supported"):
        verify_nfb_ui1a_for_submit(**{**kwargs,"draft":draft,
                                     "world_x_by_unit":{unit:0,second:200}})
    assert not emitted


def test_runtime_csv_profiles_never_certify_sources_and_reject_bad_rows(tmp_path):
    path=tmp_path/"來源輪廓索引.csv"
    digest="d"*64
    header="brand,indexed_filename,source_sha256,upper_handle,upper_width_mm,upper_height_mm,source_alias_status,revision"
    good=f"士林,400_140X257_107.dxf,{digest},585,57,96,SOURCE_ALIAS_UNCERTIFIED,v1"
    path.write_text("\ufeff"+header+"\n"+good+"\n",encoding="utf-8")
    items=read_nfb_runtime_source_profiles_csv(path)
    assert len(items)==1 and items[0].upper_size_mm==(57,96)
    assert items[0].source_alias_status=="SOURCE_ALIAS_UNCERTIFIED"
    path.write_text(header+"\n"+good+"\n"+good+"\n",encoding="utf-8")
    with pytest.raises(ValueError,match="duplicate"):
        read_nfb_runtime_source_profiles_csv(path)
    path.write_text(header+"\n"+good.replace(digest,"bad")+"\n",encoding="utf-8")
    with pytest.raises(ValueError,match="SHA256"):
        read_nfb_runtime_source_profiles_csv(path)



def test_live_submit_rechecks_bay_source_and_snapshot_before_adapter_write(tmp_path,monkeypatch):
    kwargs,unit,_=_setup(tmp_path,monkeypatch)
    verified=verify_nfb_ui1a_for_submit(**kwargs)
    called=[]
    class Adapter:
        def __init__(self):
            self.layout=kwargs["layout"]
        def submit_nfb_to_bays(self,**arguments):
            called.append(arguments)
            return SimpleNamespace(changed=True)
    adapter=Adapter()
    assert assert_live_verified_nfb(
        adapter,verified,current_snapshot=kwargs["snapshot"],
    ) is True
    outcome=submit_live_verified_nfb(
        adapter,verified,current_snapshot=kwargs["snapshot"],
        confirm=lambda preview:True,
    )
    assert outcome.changed
    assert len(called)==1
    assert called[0]["configs"][0]["holes"][0]["manual_x_mm"]==0.0
    with pytest.raises(ValueError,match="geometry"):
        submit_live_verified_nfb(
            adapter,verified,current_snapshot={**kwargs["snapshot"],"w":999},
            confirm=lambda preview:True,
        )
    assert len(called)==1
    adapter.layout["sets"][0]["bays"][0]["width"]=1200
    with pytest.raises(ValueError,match="Bay has changed"):
        assert_live_verified_nfb(adapter,verified,current_snapshot=kwargs["snapshot"])
    assert len(called)==1


def test_live_submit_rejects_changed_or_missing_original_source(tmp_path,monkeypatch):
    kwargs,_,_=_setup(tmp_path,monkeypatch)
    verified=verify_nfb_ui1a_for_submit(**kwargs)
    class Adapter:
        layout=kwargs["layout"]
        def submit_nfb_to_bays(self,**arguments):
            pytest.fail("stale source must never reach canonical submit")
    source=kwargs["source_path"]
    source.write_bytes(source.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="changed since verification"):
        submit_live_verified_nfb(
            Adapter(),verified,current_snapshot=kwargs["snapshot"],
            confirm=lambda _:True,
        )
    source.unlink()
    with pytest.raises(ValueError,match="missing since verification"):
        assert_live_verified_nfb(Adapter(),verified,current_snapshot=kwargs["snapshot"])



def test_live_copy_requires_submitted_source_and_exact_target_bundle(tmp_path,monkeypatch):
    kwargs,unit,_=_setup(tmp_path,monkeypatch)
    layout=kwargs["layout"]
    layout["sets"][0]["bays"].append({
        "stable_id":"bay-b","nfb_config_submitted":True,
        "nfb_config":{"holes":[{"physical_hole_id":"source-independently-configured"}]},
    })
    bundle=verify_nfb_ui1a_for_submit(**kwargs)  # target is Bay 0
    calls=[]
    class Adapter:
        def __init__(self):
            self.layout=layout
        def copy_submitted_nfb_to_bay(self,**arguments):
            calls.append(arguments)
            return SimpleNamespace(changed=True)
    adapter=Adapter()
    outcome=copy_live_verified_nfb(
        adapter,source_bay_index=1,target_bundle=bundle,
        current_snapshot=kwargs["snapshot"],confirm=lambda _:True,
    )
    assert outcome.changed
    assert calls[0]["source_bay_index"]==1
    assert calls[0]["target_bay_index"]==0
    assert calls[0]["evidence"][0]==bundle.scope
    assert calls[0]["target_config"]==bundle.config
    with pytest.raises(ValueError,match="distinct"):
        copy_live_verified_nfb(
            adapter,source_bay_index=0,target_bundle=bundle,
            current_snapshot=kwargs["snapshot"],confirm=lambda _:True,
        )
    assert len(calls)==1
    layout["sets"][0]["bays"][1].pop("nfb_config_submitted")
    with pytest.raises(ValueError,match="UNCONFIGURED"):
        copy_live_verified_nfb(
            adapter,source_bay_index=1,target_bundle=bundle,
            current_snapshot=kwargs["snapshot"],confirm=lambda _:True,
        )
    assert len(calls)==1


@pytest.mark.parametrize("changed_value", (
    ("operator_offset_mm", 999.0),
    ("manual_x_mm", 20.0),
    ("rotation_deg", 180),
    ("datum_revision", "stale-datum"),
    ("model_filename", "other.dxf"),
))
def test_staged_nfb_bundle_mutation_fails_before_transaction_write(
    tmp_path, monkeypatch, changed_value,
):
    kwargs,_,_=_setup(tmp_path,monkeypatch)
    bundle=verify_nfb_ui1a_for_submit(**kwargs)
    key,replacement=changed_value
    bundle.config["holes"][0][key]=replacement
    writes=[]
    class Adapter:
        layout=kwargs["layout"]
        def submit_nfb_to_bays(self,**arguments):
            writes.append(arguments)
            return SimpleNamespace(changed=True)
    adapter=Adapter()
    with pytest.raises(ValueError,match="staged config changed"):
        assert_live_verified_nfb(
            adapter,bundle,current_snapshot=kwargs["snapshot"],
        )
    with pytest.raises(ValueError,match="staged config changed"):
        submit_live_verified_nfb(
            adapter,bundle,current_snapshot=kwargs["snapshot"],
            confirm=lambda _:True,
        )
    assert not writes
    assert "nfb_config" not in kwargs["layout"]["sets"][0]["bays"][0]


def test_staged_nfb_added_follow_field_and_nested_datum_mutation_fail_closed(
    tmp_path,monkeypatch,
):
    kwargs,_,_=_setup(tmp_path,monkeypatch)
    good=verify_nfb_ui1a_for_submit(**kwargs)
    class Adapter:
        layout=kwargs["layout"]
    assert assert_live_verified_nfb(Adapter(),good,
                                    current_snapshot=kwargs["snapshot"])
    good.config["holes"][0]["brand_follow_mode"]="FORCE"
    with pytest.raises(ValueError,match="staged config changed"):
        assert_live_verified_nfb(Adapter(),good,
                                 current_snapshot=kwargs["snapshot"])
    fresh=verify_nfb_ui1a_for_submit(**kwargs)
    fresh.config["holes"][0]["datum_snapshot"]["bay_width_mm"]=750
    with pytest.raises(ValueError,match="staged config changed"):
        assert_live_verified_nfb(Adapter(),fresh,
                                 current_snapshot=kwargs["snapshot"])


def _two_verified_bays(tmp_path, monkeypatch):
    """Real source DXF and individually fingerprinted world-X per physical Bay."""
    from dataclasses import replace

    kwargs, _, _ = _setup(tmp_path, monkeypatch)
    kwargs["layout"]["sets"][0]["bays"].append({"stable_id": "bay-b"})
    first = verify_nfb_ui1a_for_submit(**kwargs)
    second_input = dict(kwargs)
    second_input.update({
        "bay_index": 1,
        "physical_scope": replace(kwargs["physical_scope"], bay_id="bay-b"),
    })
    second = verify_nfb_ui1a_for_submit(**second_input)
    assert first.config["holes"][0]["physical_hole_id"] != second.config["holes"][0]["physical_hole_id"]
    return kwargs, first, second


def test_ac28_source_verified_two_bay_submit_is_one_atomic_operator_transaction(
    tmp_path, monkeypatch,
):
    """Batch has exactly one confirmation and distinct per-Bay source authority."""
    from types import SimpleNamespace
    from ae_engine.receiving_nfb_ui1b_bridge import submit_live_verified_nfb_batch

    kwargs, first, second = _two_verified_bays(tmp_path, monkeypatch)
    calls, confirmations = [], []

    class Adapter:
        layout = kwargs["layout"]
        def submit_nfb_to_bays(self, **arguments):
            calls.append(arguments)
            assert arguments["bay_indices"] == (0, 1)
            assert set(arguments["configs"]) == {0, 1}
            assert set(arguments["evidence"]) == {0, 1}
            assert all(
                arguments["evidence"][bi][2].physical_hole_ids[0]
                == arguments["configs"][bi]["holes"][0]["physical_hole_id"]
                for bi in (0, 1)
            )
            arguments["confirm"](SimpleNamespace(
                impacted_parts=("inner-a",), blocking_reasons=(),
            ))
            return SimpleNamespace(changed=True)

    outcome = submit_live_verified_nfb_batch(
        Adapter(), (second, first),
        current_snapshots={0: kwargs["snapshot"], 1: kwargs["snapshot"]},
        confirm=lambda preview: confirmations.append(preview) or True,
    )
    assert outcome.changed
    assert len(calls) == len(confirmations) == 1


def test_ac28_stale_second_bay_aborts_full_batch_before_confirmation(
    tmp_path, monkeypatch,
):
    from ae_engine.receiving_nfb_ui1b_bridge import submit_live_verified_nfb_batch

    kwargs, first, second = _two_verified_bays(tmp_path, monkeypatch)
    called = []

    class Adapter:
        layout = kwargs["layout"]
        def submit_nfb_to_bays(self, **arguments):
            called.append(arguments)
            raise AssertionError("Batch must never partially commit")

    kwargs["layout"]["sets"][0]["bays"][1]["width"] = 750
    with pytest.raises(ValueError, match="Bay has changed"):
        submit_live_verified_nfb_batch(
            Adapter(), (first, second),
            current_snapshots={0: kwargs["snapshot"], 1: kwargs["snapshot"]},
            confirm=lambda preview: called.append(preview) or True,
        )
    assert called == []


@pytest.mark.parametrize("invalid", ("duplicate", "mixed_version", "missing_snapshot"))
def test_ac28_batch_rejects_mixed_or_ambiguous_physical_owners_before_confirmation(
    tmp_path, monkeypatch, invalid,
):
    from dataclasses import replace
    from ae_engine.receiving_nfb_ui1b_bridge import submit_live_verified_nfb_batch

    kwargs, first, second = _two_verified_bays(tmp_path, monkeypatch)
    bundles = (first, first) if invalid == "duplicate" else (
        first, replace(second, version_id="v2")
        if invalid == "mixed_version" else second
    )
    snapshots = (
        {0: kwargs["snapshot"]}
        if invalid == "missing_snapshot"
        else {0: kwargs["snapshot"], 1: kwargs["snapshot"]}
    )
    class Adapter:
        layout = kwargs["layout"]
        def submit_nfb_to_bays(self, **_):
            pytest.fail("Invalid physical batch must not commit")

    with pytest.raises(ValueError, match="batch|Set/Bay/version|snapshot"):
        submit_live_verified_nfb_batch(
            Adapter(), bundles, current_snapshots=snapshots,
            confirm=lambda _: pytest.fail("Invalid batch must not confirm"),
        )
