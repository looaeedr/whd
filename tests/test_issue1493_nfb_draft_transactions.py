# -*- coding: utf-8 -*-
"""#1493 slot transaction / Q16 and physical X integrity regression."""
from copy import deepcopy
import pytest

from ae_engine.receiving_nfb_ui1a import (
    INHERIT,OVERRIDE,new_nfb_ui1a_draft,
)
from ae_engine.receiving_nfb_ui1a_edits import (
    NONE,UNVERIFIED,editable_nfb_draft,insert_nfb_slot,
    delete_nfb_slot,move_nfb_slot,replace_nfb_slot_model,
    set_nfb_manual_x,set_nfb_layer_rotation,set_nfb_slot_rotation,
    effective_nfb_rotation,NfbUi1aEditSession,
)

MODEL="400_140X257_107.dxf"

def initial():
    return editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林",layer_count=2,model_layers=([MODEL,MODEL],[MODEL]),
    ))


def test_insert_delete_reorder_reset_only_touched_layer_x():
    state=initial()
    a=set_nfb_manual_x(state,0,0,12)
    b=set_nfb_manual_x(a,0,1,0)
    c=set_nfb_manual_x(b,1,0,99)
    other=deepcopy(c["layers"][1])
    old_ids=[s["unit_id"] for s in c["layers"][0]["slots"]]
    swapped=move_nfb_slot(c,0,0,1)
    assert [s["unit_id"] for s in swapped["layers"][0]["slots"]]==old_ids[::-1]
    assert all(s["manual_x_state"]==NONE and s["manual_x_mm"] is None
               for s in swapped["layers"][0]["slots"])
    assert swapped["layers"][1]==other
    inserted=insert_nfb_slot(c,0,1)
    assert len(inserted["layers"][0]["slots"])==3
    assert inserted["layers"][1]==other
    assert all(s["manual_x_mm"] is None for s in inserted["layers"][0]["slots"])
    assert inserted["layers"][0]["slots"][1]["filename"] is None
    removed=delete_nfb_slot(c,0,0)
    assert removed["layers"][1]==other
    assert c["layers"][0]["slots"][0]["manual_x_mm"]==12
    assert c["layers"][0]["slots"][1]["manual_x_mm"]==0


def test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry():
    state=set_nfb_manual_x(initial(),0,0,0,datum={"old":"reference"})
    old=state["layers"][0]["slots"][0]
    updated=replace_nfb_slot_model(state,0,0,"S2.dxf",
        catalog={"士林":(MODEL,"S2.dxf")})
    new=updated["layers"][0]["slots"][0]
    assert new["unit_id"]==old["unit_id"]
    assert new["manual_x_mm"]==0
    assert new["manual_x_state"]==UNVERIFIED
    assert new["datum_snapshot"] is None
    assert updated["layers"][0]["slots"][1]==state["layers"][0]["slots"][1]
    assert updated["layers"][1]==state["layers"][1]
    assert state["layers"][0]["slots"][0]["filename"]==MODEL
    with pytest.raises(ValueError,match="current brand CSV"):
        replace_nfb_slot_model(state,0,0,"impostor.dxf",catalog={"士林":(MODEL,)})


def test_angle_inherit_explicit_same_override_no_mirror():
    state=initial()
    changed=set_nfb_layer_rotation(state,0,90)
    assert effective_nfb_rotation(changed,0,0)==90
    same=set_nfb_slot_rotation(changed,0,0,mode=OVERRIDE,value=90)
    assert same["layers"][0]["slots"][0]["rotation"]=={"mode":OVERRIDE,"value":90}
    assert effective_nfb_rotation(same,0,0)==90
    assert effective_nfb_rotation(same,0,1)==90
    changed_again=set_nfb_layer_rotation(same,0,180)
    assert effective_nfb_rotation(changed_again,0,0)==90
    assert effective_nfb_rotation(changed_again,0,1)==180
    followed=set_nfb_slot_rotation(changed_again,0,0,mode=INHERIT)
    assert effective_nfb_rotation(followed,0,0)==180
    for angle in (-90,45,360,True):
        with pytest.raises(ValueError):
            set_nfb_layer_rotation(state,0,angle)
    with pytest.raises(ValueError):
        set_nfb_slot_rotation(state,0,0,mode=OVERRIDE,value=-90)


def test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions():
    first=initial()
    session=NfbUi1aEditSession(first)
    before=deepcopy(session.current)
    session.apply("X_EDIT",set_nfb_manual_x,0,0,32,datum={"basis":"draft"})
    session.apply("ANGLE",set_nfb_slot_rotation,0,0,mode=OVERRIDE,value=270)
    session.apply("REORDER",move_nfb_slot,0,0,1)
    assert session.dirty
    assert all(x["manual_x_state"]==NONE for x in session.current["layers"][0]["slots"])
    receipt=session.undo()
    assert receipt.action=="REORDER"
    assert session.current["layers"][0]["slots"][0]["manual_x_mm"]==32
    session.undo()
    assert session.current["layers"][0]["slots"][0]["rotation"]["mode"]==INHERIT
    session.undo()
    assert session.current==before and not session.dirty
    with pytest.raises(ValueError,match="no undo"):
        session.undo()
    session.apply("INSERT",insert_nfb_slot,0,1,filename=MODEL,brand="士林")
    assert session.escape()==before
    assert not session.dirty
    assert first==before


def test_invalid_edit_keeps_batch_atomic_and_source_unchanged():
    session=NfbUi1aEditSession(initial())
    before=deepcopy(session.current)
    with pytest.raises(ValueError):
        session.apply("BAD_X",set_nfb_manual_x,0,0,float("nan"))
    assert not session.dirty and session.current==before
    with pytest.raises(ValueError):
        session.apply("BAD_ORDER",move_nfb_slot,0,9,0)
    assert session.current==before
    with pytest.raises(ValueError):
        session.apply("BAD_SLOT",insert_nfb_slot,0,-1)
    assert session.current==before
    with pytest.raises(ValueError,match="finite"):
        set_nfb_manual_x(initial(),0,0,float("inf"))
