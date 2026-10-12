# -*- coding: utf-8 -*-
"""#1500 true DXF/backend life cycle: submit -> copy -> Undo -> reopen -> restore.

Unlike earlier transaction mocks this test genuinely reads DXF bytes,
manufactures three closed CUTTING features on a WHD 723-mm door, then uses
those specific per-hole X/Y/rotation witnesses to transact between Bays.
The source itself is generated inside the test; this is NOT a declaration
that the user's original Shihlin DXF underwent interactive GUI acceptance.
It verifies actual DXF parsing, 723-mm inner-door placement, and native
Receiving transactions in a single repeatable canonical product acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_layout, resize_receiving_bays,
)
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, configured_nfb_inner_door_render_data,
)
from ae_engine.receiving_nfb_part_readiness import (
    NfbPhysicalScope, READY, derive_nfb_part_readiness,
)
from ae_engine.receiving_nfb_transactions import (
    copy_submitted_nfb_bay, restore_nfb_bays_unconfigured, submit_nfb_bays,
    undo_nfb_transaction,
)
from ae_engine.receiving_nfb_x_projection import resolve_w800_three_whd_x
from ae_engine.receiving_nfb_w800_three_cutting import (
    NfbW800ThreeRow, save_w800_three_nfb_inner_door_dxf,
)


def _physical_w800_upper():
    snapshot=apply_family_defaults({
        "model":"受電箱", "w":800., "h":1600., "d":350.,
        "t":2., "fw":29., "door_gap_w":3.5, "door_gap_h":3.5,
    })
    snapshot.update({
        "multi_door_enabled": True, "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800., [1100., 500.]]],
        "inner_doors": [{
            "stable_id":"upper", "cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    return snapshot


def _real_dxf(tmp_path):
    filename="400_140X257_107.dxf"
    index=tmp_path/"開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,"+filename+",107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    source=tmp_path/filename
    doc=ezdxf.new("R2010")
    upper=doc.modelspace().add_lwpolyline(
        [(0.,0.),(57.,0.),(57.,96.),(0.,96.)],
        close=True,dxfattribs={"color":150},
    )
    doc.saveas(source)
    digest=sha256(source.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        brand="士林",indexed_filename=filename,source_sha256=digest,
        upper_handle=str(upper.dxf.handle),upper_size_mm=(57.,96.),
        source_alias_status="SOURCE_OBSERVED_UNCERTIFIED",
        revision="1500_REAL_DXF_SYNTHETIC_TEST_ONLY",
    )
    inventory=inspect_nfb_dxf_source(source)
    assert inventory.source_sha256==digest
    assert dict(inventory.process_aci_entity_counts)[150]==1
    return index,source,profile,inventory


def _proof(snapshot, saved, bay_index, *, index, source, profile, inventory):
    row=saved["sets"][0]
    bay=row["bays"][bay_index]
    holes=[]
    config_holes=[]
    for xslot in range(3):
        actual=resolve_w800_three_whd_x(snapshot,"upper",slot_index=xslot)
        physical=f"nfb:{row['stable_id']}:{bay['stable_id']}:unit:{xslot}"
        holes.append(NfbConfiguredInnerDoorHole(
            physical_hole_id=physical,
            world_x_mm=actual.box_world_x_mm,
            layer_count=1,slot_index=0,rotation_deg=0,
        ))
        config_holes.append({
            "physical_hole_id":physical,
            "unit_id":f"{bay['stable_id']}:unit:{xslot}",
            "model_filename":profile.indexed_filename,
            "manual_x_state":"CONFIRMED",
            "manual_x_mm":actual.box_world_x_mm,
            "datum_revision":actual.revision,
            "datum_snapshot":{
                "part_id":actual.part_id,
                "blank_width_mm":actual.unfolded_blank_width_mm,
            },
            "rotation_deg":0,"layer_count":1,"slot_index":0,
            "operator_offset_mm":[0,0],
            "source_brand":profile.brand,
        })
    verified=configured_nfb_inner_door_render_data(
        snapshot,"upper",holes=tuple(holes),
        index_path=index,source_path=source,profile=profile,
    )
    assert verified.manufacturing_ready
    assert len(verified.physical_hole_ids)==3
    assert tuple(round(p[1],5) for p in verified.verified_hole_locations)==(
        -180.,0.,180.,
    )
    scope=NfbPhysicalScope(
        set_id=row["stable_id"],bay_id=bay["stable_id"],
        version_id="v1",submitted=True,
        inner_door_part_id=verified.part_id,
    )
    readiness=derive_nfb_part_readiness(
        scope,source_inventory=inventory,verified_inner_door=verified,
    )
    assert readiness.can_submit
    assert readiness.for_part("inner_door:upper:panel").status==READY
    return {
        "layer_count":1, "holes":config_holes,
        "source_sha256":inventory.source_sha256,
    }, (scope,inventory,verified)


def test_real_dxf_submit_copy_undo_reopen_restore_is_atomic(tmp_path):
    index,source,profile,inventory=_real_dxf(tmp_path)
    snapshot=_physical_w800_upper()
    layout=resize_receiving_bays(
        new_receiving_layout(width=800,height=1600,depth=350),
        set_index=0,bay_count=2,
    )
    before=deepcopy(layout)
    cfg0,proof0=_proof(
        snapshot,layout,0,index=index,source=source,
        profile=profile,inventory=inventory,
    )
    previews=[]
    cancelled=submit_nfb_bays(
        layout,set_index=0,bay_indices=(0,),version_id="v1",
        configs={0:cfg0},evidence={0:proof0},
        confirm=lambda p:previews.append(p) or False,
    )
    assert not cancelled.changed
    assert cancelled.layout==before and layout==before
    assert previews[0].action=="SUBMIT"
    assert "inner_door:upper:panel" in previews[0].impacted_parts
    confirmed=submit_nfb_bays(
        layout,set_index=0,bay_indices=(0,),version_id="v1",
        configs={0:cfg0},evidence={0:proof0},confirm=lambda _:True,
    )
    assert confirmed.changed and confirmed.receipt is not None
    first=confirmed.layout
    assert first["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert first["sets"][0]["bays"][1].get("nfb_config_submitted") is not True

    cfg1,proof1=_proof(
        snapshot,first,1,index=index,source=source,
        profile=profile,inventory=inventory,
    )
    cancelled_copy=copy_submitted_nfb_bay(
        first,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=cfg1,evidence=proof1,
        confirm=lambda _:False,
    )
    assert not cancelled_copy.changed and cancelled_copy.layout==first
    copied=copy_submitted_nfb_bay(
        first,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=cfg1,evidence=proof1,
        confirm=lambda _:True,
    )
    assert copied.changed and copied.preview.action=="COPY_SUBMIT"
    both=copied.layout
    nfb0=both["sets"][0]["bays"][0]["nfb_config"]
    nfb1=both["sets"][0]["bays"][1]["nfb_config"]
    assert nfb0["holes"][0]["physical_hole_id"]!=nfb1["holes"][0]["physical_hole_id"]
    assert nfb0["holes"][0]["unit_id"]!=nfb1["holes"][0]["unit_id"]
    assert undo_nfb_transaction(both,copied.receipt)==first

    # Simulated project save/open; NFBConfig is actual user persistence, not
    # the short-lived verified physical proof from a prior process.
    reopened=normalize_receiving_layout(json.loads(json.dumps(both)))
    assert reopened==both
    assert reopened["sets"][0]["bays"][0]["nfb_config"]==nfb0
    assert reopened["sets"][0]["bays"][1]["nfb_config"]==nfb1
    fresh_cfg,fresh_proof=_proof(
        snapshot,reopened,0,index=index,source=source,
        profile=profile,inventory=inventory,
    )
    assert fresh_cfg==nfb0
    assert fresh_proof[2].source_sha256==inventory.source_sha256

    # Reopen alone grants no stored READY: derive a fresh source+panel proof
    # then create the real DXF, just as original bytes are rechecked on export.
    output=tmp_path/"reopened-verified-original.dxf"
    save_w800_three_nfb_inner_door_dxf(
        snapshot,"upper",output,
        rows=(NfbW800ThreeRow(
            layer_index=0,
            physical_hole_ids=tuple(
                hole["physical_hole_id"] for hole in nfb0["holes"]
            ),
        ),),
        index_path=index,source_path=source,profile=profile,
    )
    exported=ezdxf.readfile(output)
    cuttings=[e for e in exported.modelspace()
              if e.dxftype()=="LWPOLYLINE"
              and e.dxf.layer=="CUTTING" and e.closed]
    assert len(cuttings)==4  # real WHD outer blank plus three real NFB holes

    restored_cancelled=restore_nfb_bays_unconfigured(
        reopened,set_index=0,bay_indices=(0,1),confirm=lambda _:False,
    )
    assert not restored_cancelled.changed
    assert restored_cancelled.layout==reopened
    restored=restore_nfb_bays_unconfigured(
        reopened,set_index=0,bay_indices=(0,1),confirm=lambda _:True,
    )
    assert restored.changed
    assert all("nfb_config" not in b and b.get("nfb_config_submitted") is not True
               for b in restored.layout["sets"][0]["bays"])
    assert undo_nfb_transaction(restored.layout,restored.receipt)==reopened
    assert before==layout
