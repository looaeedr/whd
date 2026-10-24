# -*- coding: utf-8 -*-
"""#1500 product transaction acceptance: atomic per-Bay NFB, cancel, copy, restore/undo."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.receiving_layout import new_receiving_layout,resize_receiving_bays
from ae_engine.receiving_nfb_dxf_source import NfbSourceInventory
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
from ae_engine.receiving_nfb_manufacturing_release import NfbValidatedInnerDoorRender,VALIDATED
from ae_engine.receiving_nfb_transactions import (
    submit_nfb_bays,copy_submitted_nfb_bay,restore_nfb_bays_unconfigured,
    undo_nfb_transaction,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter

SHA="1"*64
PART="inner_door:upper:panel"


def layout():
    source=new_receiving_layout(width=800,height=1600,depth=350)
    return resize_receiving_bays(source,set_index=0,bay_count=2)


def config(*,x=0,owner="nfb:0:slot1",state="CONFIRMED",offset=5,filename="400_140X257_107.dxf"):
    return {"holes":[{
        "physical_hole_id":owner,
        "model_filename":filename,
        "manual_x_state":state,
        "manual_x_mm":x,
        "datum_revision":"w800t2",
        "datum_snapshot":{"width":800,"t":2},
        "operator_offset_mm":[0,offset],
        "rotation_deg":90,
        "slot_index":0,
    }],"layer_count":1}


def evidence(row,bi,*,status="ready",inventory=None,x=0,slot=0):
    bay=row["sets"][0]["bays"][bi]
    scope=NfbPhysicalScope(
        set_id=row["sets"][0]["stable_id"],bay_id=bay["stable_id"],
        version_id="v1",submitted=True,inner_door_part_id=PART,
        base_plate_part_ids=("base_plate:upper",),
        middle_plate_part_ids=("middle_plate:upper",),
    )
    src=inventory or NfbSourceInventory(
        source_path="sample.dxf",source_sha256=SHA,source_id="NFB-DXF:"+SHA,
        status="SOURCE_OBSERVED_UNCERTIFIED",entities=(),
        diagnostics=(),process_aci_entity_counts=((30,0),(150,1),(212,0)),
        unresolved_color_entities=0,grouped_entity_counts=(("modelspace",1),),
    )
    door=None if status=="blocked" else NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,"nfb_trial_export_approved":True,
        }),
        part_id=PART,indexed_model_key=("士林","400_140X257_107.dxf"),
        source_sha256=SHA,physical_hole_ids=(f"nfb:{bi}:slot1",),
        verified_hole_locations=((f"nfb:{bi}:slot1",float(x),1,slot,90),),
    )
    return scope,src,door


def do_submit(row, *, yes=True,configs=None,evidences=None, indices=(0,)):
    if configs is None:
        configs={i:config(owner=f"nfb:{i}:slot1") for i in indices}
    if evidences is None:
        evidences={i:evidence(row,i) for i in indices}
    return submit_nfb_bays(
        row,set_index=0,bay_indices=indices,version_id="v1",
        configs=configs,evidence=evidences,confirm=lambda _:yes,
    )


def test_first_submission_includes_held_plates_in_warning_but_commits_inner_config():
    row=layout()
    before=deepcopy(row)
    pending=do_submit(row,yes=False)
    assert not pending.changed and pending.receipt is None
    assert pending.layout==before and row==before
    previews=[]
    result=submit_nfb_bays(
        row,set_index=0,bay_indices=(0,),version_id="v1",
        configs={0:config()},evidence={0:evidence(row,0)},
        confirm=lambda preview:previews.append(preview) or True,
    )
    assert result.changed
    assert result.preview.can_commit
    assert "middle_plate:upper" in result.preview.held_parts
    assert "inner_door:upper:panel" in result.preview.impacted_parts
    assert result.layout["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert result.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_mm"]==0
    assert "nfb_config" not in result.layout["sets"][0]["bays"][1]
    assert row==before
    assert previews[0].action=="SUBMIT"
    undone=undo_nfb_transaction(result.layout,result.receipt)
    assert undone==before


def test_invalid_source_x_scope_or_one_bay_collision_atomic():
    row=layout()
    before=deepcopy(row)
    for cfg,src,scope in [
        ({0:config(state="RECONFIRM_REQUIRED")}, {0:evidence(row,0)},(0,)),
        ({0:config(x=None)}, {0:evidence(row,0)},(0,)),
        ({0:config(x=25)}, {0:evidence(row,0,x=0)},(0,)),
        ({0:config()}, {0:evidence(row,0,slot=1)},(0,)),
        ({0:config(filename="wrong.dxf")}, {0:evidence(row,0)},(0,)),
        ({0:config(owner="nfb:wrong:slot1")}, {0:evidence(row,0)},(0,)),
        ({0:config()}, {0:evidence(row,1)},(0,)),
        ({0:config()}, {0:evidence(row,0,status="blocked")},(0,)),
        ({0:config(),1:config(state="NONE",owner="nfb:1:slot1")},
         {0:evidence(row,0),1:evidence(row,1)},(0,1)),
    ]:
        with pytest.raises((ValueError,TypeError)):
            do_submit(row,configs=cfg,evidences=src,indices=scope)
        assert row==before


def test_unconfigured_source_copy_forbidden_and_overwrite_needs_confirmation():
    row=layout()
    with pytest.raises(ValueError,match="UNCONFIGURED"):
        copy_submitted_nfb_bay(
            row,set_index=0,source_bay_index=0,target_bay_index=1,
            version_id="v1",target_config=config(owner="nfb:target:slot1"),
            evidence=evidence(row,1),confirm=lambda p: True,
        )
    first=do_submit(row).layout
    with pytest.raises(ValueError,match="offset"):
        copy_submitted_nfb_bay(
            first,set_index=0,source_bay_index=0,target_bay_index=1,
            version_id="v1",target_config=config(owner="nfb:1:slot1",offset=999),
            evidence=evidence(first,1),confirm=lambda p:True,
        )
    with pytest.raises(ValueError,match="independent"):
        copy_submitted_nfb_bay(
            first,set_index=0,source_bay_index=0,target_bay_index=1,
            version_id="v1",target_config=config(owner="nfb:0:slot1"),
            evidence=evidence(first,1),confirm=lambda p:True,
        )
    with pytest.raises(ValueError,match="confirmation"):
        copy_submitted_nfb_bay(
            first,set_index=0,source_bay_index=0,target_bay_index=1,
            version_id="v1",target_config=None,
            evidence=evidence(first,1),confirm=lambda p:True,
        )
    cancelled=copy_submitted_nfb_bay(
        first,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=config(owner="nfb:1:slot1",x=100),
        evidence=evidence(first,1,x=100),confirm=lambda p:False,
    )
    assert not cancelled.changed and cancelled.layout==first
    result=copy_submitted_nfb_bay(
        first,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=config(owner="nfb:1:slot1",x=100),
        evidence=evidence(first,1,x=100),confirm=lambda p:True,
    )
    assert result.preview.action=="COPY_SUBMIT"
    target=result.layout["sets"][0]["bays"][1]["nfb_config"]
    assert target["holes"][0]["manual_x_mm"]==100
    target["holes"][0]["operator_offset_mm"][0]=77
    assert first["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["operator_offset_mm"]==[0,5]
    updated=copy_submitted_nfb_bay(
        result.layout,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=config(owner="nfb:1:slot1",x=200),
        evidence=evidence(result.layout,1,x=200),confirm=lambda p:True,
    )
    assert updated.preview.action=="COPY_OVERWRITE"
    assert undo_nfb_transaction(updated.layout,updated.receipt)==result.layout


def test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy():
    row=do_submit(layout()).layout
    original=deepcopy(row)
    cancelled=restore_nfb_bays_unconfigured(
        row,set_index=0,bay_indices=(0,),confirm=lambda p:False,
    )
    assert not cancelled.changed and cancelled.layout==row
    done=restore_nfb_bays_unconfigured(
        row,set_index=0,bay_indices=(0,),confirm=lambda p:True,
    )
    assert done.changed and "nfb_config" not in done.layout["sets"][0]["bays"][0]
    assert row==original
    assert undo_nfb_transaction(done.layout,done.receipt)==original
    mutated=deepcopy(done.layout)
    mutated["sets"][0]["bays"][0]["nfb_config_submitted"]=True
    mutated["sets"][0]["bays"][0]["nfb_config"]=config(x=55)
    with pytest.raises(ValueError,match="conflict"):
        undo_nfb_transaction(mutated,done.receipt)


def test_adapter_undo_preserves_sibling_changes_and_native_owner():
    adapter=ReceivingSetBayAdapter(layout())
    starting=adapter.layout
    event=adapter.submit_nfb_to_bays(
        set_index=0,bay_indices=(0,),version_id="v1",
        configs={0:config()},evidence={0:evidence(starting,0)},
        confirm=lambda p:True,
    )
    assert event.changed and adapter.nfb_can_undo
    adapter._layout["sets"][0]["bays"][1]["door_state"]={"multi_door_enabled":False}
    adapter.undo_last_nfb_transaction()
    assert "nfb_config" not in adapter.layout["sets"][0]["bays"][0]
    assert adapter.layout["sets"][0]["bays"][1]["door_state"]=={"multi_door_enabled":False}
    assert not adapter.nfb_can_undo
    with pytest.raises(ValueError,match="復原"):
        adapter.undo_last_nfb_transaction()



def test_real_mfg1_submit_does_not_invent_middle_plate_from_inner_color150():
    # #1502 authority: NFB upper Color150 belongs to real INNER DOOR.
    # With no real middle part ID, an illustrative drawing is not a plate.
    row=layout()
    scope,inventory,door=evidence(row,0)
    scope=NfbPhysicalScope(
        set_id=scope.set_id,bay_id=scope.bay_id,version_id=scope.version_id,
        submitted=True,inner_door_part_id=scope.inner_door_part_id,
    )
    previews=[]
    result=submit_nfb_bays(
        row,set_index=0,bay_indices=(0,),version_id="v1",
        configs={0:config()},evidence={0:(scope,inventory,door)},
        confirm=lambda p:previews.append(p) or True,
    )
    assert result.changed
    assert result.preview.can_commit
    assert "MIDDLE_PLATE_PHYSICAL_ID_UNRESOLVED" not in (
        result.preview.dependency_warnings
    )
    assert result.layout["sets"][0]["bays"][0]["nfb_config_submitted"]
    from ae_engine.receiving_nfb_part_readiness import derive_nfb_part_readiness
    readiness=derive_nfb_part_readiness(
        scope,source_inventory=inventory,verified_inner_door=door,
    )
    assert readiness.filter_export_part_ids((scope.inner_door_part_id,)) == (
        (scope.inner_door_part_id,), (),
    )
    # A *real* middle plate still requires its own MFG-2 machining proof.
    physical=replace(scope,middle_plate_part_ids=("middle_plate:upper",))
    with_middle=derive_nfb_part_readiness(
        physical,source_inventory=inventory,verified_inner_door=door,
    )
    assert with_middle.can_submit
    assert with_middle.for_part("middle_plate:upper").status=="BLOCKED"
    with pytest.raises(ValueError,match="not manufacturing-ready"):
        with_middle.filter_export_part_ids((
            scope.inner_door_part_id,"middle_plate:upper",
        ))



def test_copy_submitted_source_into_independently_verified_target_unit_id():
    base=layout()
    old=config(owner="nfb:0:slot1",x=0)
    old["holes"][0]["unit_id"]="physical-source-unit"
    source=do_submit(base,configs={0:old}).layout
    target=config(owner="nfb:1:slot1",x=100)
    target["holes"][0]["unit_id"]="physical-target-unit"
    warnings=[]
    result=copy_submitted_nfb_bay(
        source,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=target,
        evidence=evidence(source,1,x=100),
        confirm=lambda preview:warnings.append(preview) or True,
    )
    assert result.changed
    assert warnings[0].action=="COPY_SUBMIT"
    committed=result.layout["sets"][0]["bays"][1]["nfb_config"]["holes"][0]
    original=result.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert committed["unit_id"]=="physical-target-unit"
    assert original["unit_id"]=="physical-source-unit"
    assert committed["physical_hole_id"]!=original["physical_hole_id"]
    assert committed["manual_x_mm"]==100
    assert original["manual_x_mm"]==0
    assert committed["rotation_deg"]==original["rotation_deg"]==90
    assert committed["operator_offset_mm"]==original["operator_offset_mm"]
    assert undo_nfb_transaction(result.layout,result.receipt)==source
    canceled=copy_submitted_nfb_bay(
        source,set_index=0,source_bay_index=0,target_bay_index=1,
        version_id="v1",target_config=target,
        evidence=evidence(source,1,x=100),confirm=lambda _:False,
    )
    assert not canceled.changed and canceled.layout==source


@pytest.mark.parametrize("nonboolean_reply", [1, "yes", [], None])
def test_ac34_nonboolean_operator_confirmation_never_commits_or_restores(nonboolean_reply):
    """Operator callbacks must return actual bool, never truthy/falsy aliases."""
    original = layout()
    before = deepcopy(original)
    with pytest.raises(TypeError, match="explicit boolean"):
        do_submit(original, yes=nonboolean_reply)
    assert original == before

    submitted = do_submit(original, yes=True).layout
    stable = deepcopy(submitted)
    with pytest.raises(TypeError, match="explicit boolean"):
        restore_nfb_bays_unconfigured(
            submitted, set_index=0, bay_indices=(0,),
            confirm=lambda _: nonboolean_reply,
        )
    assert submitted == stable
    rejected = restore_nfb_bays_unconfigured(
        submitted, set_index=0, bay_indices=(0,), confirm=lambda _: False,
    )
    assert rejected.changed is False and rejected.layout == submitted


@pytest.mark.parametrize(("basis_field", "stale_value"), (
    ("rotation_deg", 180),
    ("rotation_deg", "90"),
    ("model_filename", "different-source-model.dxf"),
))
def test_ac23_submitted_x_datum_must_match_recorded_model_and_rotation(
    basis_field, stale_value,
):
    """A genuine ready cutting render cannot reapprove the OLD X datum."""
    original = layout()
    frozen = deepcopy(original)
    submitted = config(owner="nfb:0:slot1")
    hole = submitted["holes"][0]
    hole["datum_snapshot"].update({
        "rotation_deg": 90,
        "model_filename": hole["model_filename"],
    })
    hole["datum_snapshot"][basis_field] = stale_value
    with pytest.raises(ValueError, match="datum|reconfirm|confirmation"):
        do_submit(
            original,
            configs={0: submitted},
            evidences={0: evidence(original, 0)},
        )
    assert original == frozen
    assert "nfb_config" not in original["sets"][0]["bays"][0]


def test_ac23_matching_explicit_model_rotation_datum_keeps_verified_submit():
    original = layout()
    supplied = config(owner="nfb:0:slot1")
    hole = supplied["holes"][0]
    hole["datum_snapshot"].update({
        "rotation_deg": 90,
        "model_filename": hole["model_filename"],
    })
    committed = do_submit(original, configs={0: supplied}).layout
    assert committed["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert committed["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0


@pytest.mark.parametrize("bad_width", (750, None, True))
def test_ac23_live_bay_width_source_mismatch_blocks_confirmed_submit(bad_width):
    """A transaction cannot succeed and only *then* demote stale X to draft."""
    original = layout()
    frozen = deepcopy(original)
    supplied = config(owner="nfb:0:slot1")
    snapshot = supplied["holes"][0]["datum_snapshot"]
    if bad_width is None:
        supplied["holes"][0]["model_filename"] = "nfbv5:士林:2P400"
        snapshot.pop("width")
    else:
        snapshot["width"] = bad_width
    # Keep the CUTTING proof's model identity aligned even for numeric V5,
    # so this assertion isolates the missing/stale physical Bay width.
    current_evidence = evidence(original, 0)
    if bad_width is None:
        scope, inventory, verified = current_evidence
        current_evidence = (
            scope, inventory,
            replace(verified, indexed_model_key=("士林", "nfbv5:士林:2P400")),
        )
    with pytest.raises(ValueError, match="operator confirmation|Bay|datum|reconfirm"):
        do_submit(
            original, configs={0: supplied},
            evidences={0: current_evidence},
        )
    assert original == frozen
    assert "nfb_config" not in original["sets"][0]["bays"][0]


def test_ac23_copied_bay_stale_width_rejects_before_transaction():
    """Copy needs its own Bay's X authority, not the source Bay approval."""
    first = do_submit(layout()).layout
    frozen = deepcopy(first)
    destination = config(owner="nfb:1:slot1", x=100)
    destination["holes"][0]["datum_snapshot"]["width"] = 750
    with pytest.raises(ValueError, match="operator confirmation"):
        copy_submitted_nfb_bay(
            first,
            set_index=0, source_bay_index=0, target_bay_index=1,
            version_id="v1", target_config=destination,
            evidence=evidence(first, 1, x=100),
            confirm=lambda _: True,
        )
    assert first == frozen
    assert "nfb_config" not in first["sets"][0]["bays"][1]


@pytest.mark.parametrize("indices", (
    None, 0, [0, []], [[0]], [True], ["0"], [0, 0], [-1], [999],
))
def test_ac23_malformed_highlighted_bay_selection_rejected_atomically(indices):
    """An invalid Bay selector cannot reach operator confirmation or mutate."""
    original = layout()
    frozen = deepcopy(original)
    called = []
    with pytest.raises(ValueError, match="distinct real highlighted Bays"):
        restore_nfb_bays_unconfigured(
            original, set_index=0, bay_indices=indices,
            confirm=lambda _: called.append(True) or True,
        )
    assert called == []
    assert original == frozen


def test_ac23_two_bay_stale_second_datum_blocks_both_and_skips_confirmation():
    """An otherwise good Bay must not be partly committed before Bay 2 fails."""
    original = layout()
    unchanged = deepcopy(original)
    config0 = config(owner="nfb:0:slot1", x=0)
    config1 = config(owner="nfb:1:slot1", x=0)
    config1["holes"][0]["datum_snapshot"]["width"] = 750
    callbacks = []
    with pytest.raises(ValueError, match="operator confirmation"):
        submit_nfb_bays(
            original, set_index=0, bay_indices=(0, 1), version_id="v1",
            configs={0: config0, 1: config1},
            evidence={0: evidence(original, 0), 1: evidence(original, 1)},
            confirm=lambda _: callbacks.append("unexpected") or True,
        )
    assert callbacks == []
    assert original == unchanged
    assert all("nfb_config" not in bay for bay in original["sets"][0]["bays"])


@pytest.mark.parametrize("malformed_locations", (
    (("nfb:0:slot1", "0", 1, 0, 90),),
    (("nfb:0:slot1", True, 1, 0, 90),),
    (("nfb:0:slot1", 0., True, 0, 90),),
    (("nfb:0:slot1", 0., 1, False, 90),),
    (("nfb:0:slot1", 0., 1, 0, "90"),),
    (["nfb:0:slot1", 0., 1, 0, 90],),
    (("nfb:0:slot1", 0., 1, 0),),
    (([], 0., 1, 0, 90),),
))
def test_ac23_malformed_verified_cutting_witness_rejects_before_operator_confirmation(
    malformed_locations,
):
    """A typed render with malformed real hole observations is never consent."""
    original = layout()
    before = deepcopy(original)
    scope, source, verified = evidence(original, 0)
    corrupted = replace(verified, verified_hole_locations=malformed_locations)
    confirmation = []
    with pytest.raises(ValueError, match="verified physical X/Y/rotation evidence"):
        submit_nfb_bays(
            original, set_index=0, bay_indices=(0,), version_id="v1",
            configs={0: config(owner="nfb:0:slot1")},
            evidence={0: (scope, source, corrupted)},
            confirm=lambda _: confirmation.append(True) or True,
        )
    assert confirmation == []
    assert original == before
    assert "nfb_config" not in original["sets"][0]["bays"][0]


@pytest.mark.parametrize("bool_in", ("configs", "evidence"))
def test_ac23_boolean_bay_mapping_keys_cannot_alias_integer_target(bool_in):
    """True == 1 in Python, but never a valid NFB Bay ownership key."""
    original = layout()
    frozen = deepcopy(original)
    cfg = {1: config(owner="nfb:1:slot1")}
    proof = {1: evidence(original, 1)}
    if bool_in == "configs":
        cfg = {True: config(owner="nfb:1:slot1")}
    else:
        proof = {True: evidence(original, 1)}
    confirmed = []
    with pytest.raises(ValueError, match="configs/evidence"):
        submit_nfb_bays(
            original, set_index=0, bay_indices=(1,), version_id="v1",
            configs=cfg, evidence=proof,
            confirm=lambda _: confirmed.append(True) or True,
        )
    assert confirmed == []
    assert original == frozen
    assert "nfb_config" not in original["sets"][0]["bays"][1]


@pytest.mark.parametrize(("owner_key", "other_value"), (
    ("set_id", "another-physical-set"),
    ("bay_id", "another-physical-bay"),
    ("version_id", "previous-version"),
    ("cutting_source_sha256", "0" * 64),
    ("cutting_source_sha256", True),
))
def test_ac23_explicit_datum_owner_change_requires_new_operator_approval(
    owner_key, other_value,
):
    """Old per-hole Set/Bay/version/CUTTING source X proof cannot be reused."""
    original = layout()
    frozen = deepcopy(original)
    supplied = config(owner="nfb:0:slot1")
    supplied["holes"][0]["datum_snapshot"][owner_key] = other_value
    confirmed = []
    with pytest.raises(
        ValueError,
        match=r"(X datum owner.*reconfirmation|operator confirmation for each physical hole)",
    ):
        submit_nfb_bays(
            original, set_index=0, bay_indices=(0,), version_id="v1",
            configs={0: supplied}, evidence={0: evidence(original, 0)},
            confirm=lambda _: confirmed.append(True) or True,
        )
    assert confirmed == []
    assert original == frozen
    assert "nfb_config" not in original["sets"][0]["bays"][0]


def test_ac23_explicit_matching_owner_source_preserves_valid_approved_zero_x():
    original = layout()
    supplied = config(owner="nfb:0:slot1")
    supplied["holes"][0]["datum_snapshot"].update({
        "set_id": original["sets"][0]["stable_id"],
        "bay_id": original["sets"][0]["bays"][0]["stable_id"],
        "version_id": "v1",
        "cutting_source_sha256": SHA,
    })
    result = do_submit(original, configs={0: supplied})
    assert result.changed is True
    hole = result.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_mm"] == 0 and hole["manual_x_state"] == "CONFIRMED"


def test_ac23_copy_target_rejects_explicit_original_bay_datum_owner():
    original = do_submit(layout()).layout
    frozen = deepcopy(original)
    source_bay = original["sets"][0]["bays"][0]["stable_id"]
    target = config(owner="nfb:1:slot1", x=100)
    target["holes"][0]["datum_snapshot"].update({
        "bay_id": source_bay, "version_id": "v1",
        "cutting_source_sha256": SHA,
    })
    confirmed = []
    with pytest.raises(
        ValueError,
        match=r"(X datum owner.*reconfirmation|operator confirmation for each physical hole)",
    ):
        copy_submitted_nfb_bay(
            original, set_index=0, source_bay_index=0, target_bay_index=1,
            version_id="v1", target_config=target,
            evidence=evidence(original, 1, x=100),
            confirm=lambda _: confirmed.append(True) or True,
        )
    assert confirmed == []
    assert original == frozen
    assert "nfb_config" not in original["sets"][0]["bays"][1]


@pytest.mark.parametrize("huge_x", (10 ** 400, -(10 ** 400)))
def test_ac28_huge_integer_cutting_x_blocks_batch_before_confirmation(huge_x):
    """A bad hole in Bay 2 cannot skip Bay 1 or call approval for either."""
    original = layout()
    frozen = deepcopy(original)
    _, _, actual = evidence(original, 1)
    corrupt = replace(
        actual,
        verified_hole_locations=(("nfb:1:slot1", huge_x, 1, 0, 90),),
    )
    scope1, inventory1, _ = evidence(original, 1)
    called = []
    with pytest.raises(ValueError, match="verified physical X/Y/rotation evidence"):
        submit_nfb_bays(
            original, set_index=0, bay_indices=(0, 1), version_id="v1",
            configs={
                0: config(owner="nfb:0:slot1"),
                1: config(owner="nfb:1:slot1"),
            },
            evidence={
                0: evidence(original, 0),
                1: (scope1, inventory1, corrupt),
            },
            confirm=lambda _: called.append(True) or True,
        )
    assert called == []
    assert original == frozen
    assert all("nfb_config" not in bay for bay in original["sets"][0]["bays"])
