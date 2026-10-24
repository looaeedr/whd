# -*- coding: utf-8 -*-
"""#1493 NFB physical-slot editing in the SAME UI-1A transient draft.

Immutable operations with one reversible transaction per user action. Stable
unit identity survives ordering and undo. Reordering/insertion/deletion drops
stale physical-X offsets only in the touched layer; model replacement (Q16)
preserves its coordinate draft but invalidates source geometry confidence.
No direct Hole Editor writes, manufacturing geometry or persisted NFBConfig.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite

from .receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, _get_slot, _get_layer, _override,
    select_nfb_slot_model,
)

NONE = "NONE"
UNVERIFIED = "UNVERIFIED_BASIS"
RECONFIRM = "RECONFIRM_REQUIRED"
ROTATIONS = (0,90,180,270)


def _rotation_override(mode=INHERIT,value=None):
    if mode not in (INHERIT,OVERRIDE):
        raise ValueError("NFB rotation override mode invalid")
    if mode == INHERIT:
        if value is not None:
            raise ValueError("NFB inherited rotation cannot hold an override")
        return {"mode":INHERIT,"value":None}
    if type(value) is not int or value not in ROTATIONS:
        raise ValueError("NFB unit rotation must be 0/90/180/270")
    return {"mode":OVERRIDE,"value":value}


def editable_nfb_draft(draft):
    state=deepcopy(draft)
    seen=set()
    next_number=int(state.get("_next_unit_number",1))
    if next_number < 1:
        raise ValueError("NFB next unit number must be positive")
    # Reserve existing persisted IDs first: mixed legacy rows can lack IDs,
    # while a saved allocator counter can lag behind already-assigned IDs.
    reserved=set()
    for layer in state["layers"]:
        for slot in layer["slots"]:
            if "unit_id" not in slot:
                continue
            uid=slot["unit_id"]
            if not isinstance(uid,str) or not uid or uid in reserved:
                raise ValueError("NFB draft unit IDs must be unique")
            reserved.add(uid)
    for i,layer in enumerate(state["layers"]):
        layer.setdefault("rotation_deg",0)
        if layer["rotation_deg"] not in ROTATIONS or type(layer["rotation_deg"]) is not int:
            raise ValueError("NFB layer rotation must be 0/90/180/270")
        for slot in layer["slots"]:
            if "unit_id" not in slot:
                while f"nfb:ui1a:unit:{next_number}" in reserved:
                    next_number+=1
                slot["unit_id"]=f"nfb:ui1a:unit:{next_number}"
                reserved.add(slot["unit_id"])
                next_number+=1
            if not isinstance(slot["unit_id"],str) or slot["unit_id"] in seen:
                raise ValueError("NFB draft unit IDs must be unique")
            seen.add(slot["unit_id"])
            slot.setdefault("rotation",_rotation_override())
            slot.setdefault("manual_x_state",NONE)
            slot.setdefault("manual_x_mm",None)
            slot.setdefault("datum_snapshot",None)
            if slot["rotation"]["mode"]==OVERRIDE:
                if type(slot["rotation"]["value"]) is not int or slot["rotation"]["value"] not in ROTATIONS:
                    raise ValueError("NFB slot angle invalid")
            if (slot["manual_x_mm"] is not None
                    and (type(slot["manual_x_mm"]) not in (int,float)
                         or not isfinite(slot["manual_x_mm"]))):
                raise ValueError("NFB X offset must be finite")
    while f"nfb:ui1a:unit:{next_number}" in reserved:
        next_number+=1
    state["_next_unit_number"]=next_number
    return state


def _reset_layer_x(layer):
    for slot in layer["slots"]:
        slot["manual_x_mm"]=None
        slot["manual_x_state"]=NONE
        slot["datum_snapshot"]=None
        slot.pop("datum_revision",None)


def insert_nfb_slot(draft, layer_index, position, *, filename=None, brand=None):
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    if type(position) is not int or not 0<=position<=len(layer["slots"]):
        raise ValueError("NFB insertion position invalid")
    if filename is not None:
        from .receiving_nfb_model_identity import validate_stored_model_ref
        validate_stored_model_ref(filename)
    uid=f"nfb:ui1a:unit:{state['_next_unit_number']}"
    state["_next_unit_number"]+=1
    layer["slots"].insert(position,{
        "unit_id":uid,"filename":filename,"source_brand":brand if filename else None,
        "brand":_override(),"rotation":_rotation_override(),
        "manual_x_state":NONE,"manual_x_mm":None,"datum_snapshot":None,
    })
    _reset_layer_x(layer)
    return state


def delete_nfb_slot(draft,layer_index,position):
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    if type(position) is not int or not 0<=position<len(layer["slots"]):
        raise ValueError("NFB delete position invalid")
    layer["slots"].pop(position)
    _reset_layer_x(layer)
    return state


def move_nfb_slot(draft,layer_index,source_index,target_index):
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    n=len(layer["slots"])
    if (type(source_index) is not int or type(target_index) is not int
            or not 0<=source_index<n or not 0<=target_index<n):
        raise ValueError("NFB reorder indices invalid")
    if source_index==target_index:return state
    picked=layer["slots"].pop(source_index)
    layer["slots"].insert(target_index,picked)
    _reset_layer_x(layer)
    return state


def replace_nfb_slot_model(draft,layer_index,slot_index,filename,*,catalog):
    state=editable_nfb_draft(draft)
    old=_get_slot(state,layer_index,slot_index)
    before=old["filename"],old["source_brand"]
    result=select_nfb_slot_model(state,layer_index,slot_index,filename,catalog=catalog)
    current=_get_slot(result,layer_index,slot_index)
    if before!=(current["filename"],current["source_brand"]):
        # A changed model invalidates its old X source revision even when
        # an older draft carried no explicit coordinate.
        current["datum_snapshot"]=None
        current.pop("datum_revision",None)
        if current["manual_x_mm"] is not None:
            current["manual_x_state"]=UNVERIFIED
    return result


def _invalidate_effective_rotation_x(slot):
    """Keep the operator's X offset, never reuse an old rotation's datum."""
    slot["datum_snapshot"] = None
    slot.pop("datum_revision", None)
    if slot["manual_x_mm"] is not None:
        slot["manual_x_state"] = (
            RECONFIRM if slot["manual_x_state"] == "CONFIRMED" else UNVERIFIED
        )
    else:
        slot["manual_x_state"] = NONE


def set_nfb_layer_rotation(draft,layer_index,angle):
    if type(angle) is not int or angle not in ROTATIONS:
        raise ValueError("NFB angle must be 0/90/180/270; mirrors forbidden")
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    if layer["rotation_deg"] != angle:
        # Only inheriting slots effectively rotate. Explicit rotations and
        # all other layers retain their independent X source approvals.
        for slot in layer["slots"]:
            if slot["rotation"]["mode"] == INHERIT:
                _invalidate_effective_rotation_x(slot)
    layer["rotation_deg"]=angle
    return state


def set_nfb_slot_rotation(draft,layer_index,slot_index,*,mode,value=None):
    if mode==OVERRIDE and (type(value) is not int or value not in ROTATIONS):
        raise ValueError("NFB slot angle must be quarter-turn, no mirror")
    if mode==INHERIT and value is not None:
        raise ValueError("NFB inherited rotation has no separate value")
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    slot=_get_slot(state,layer_index,slot_index)
    old_effective = (
        slot["rotation"]["value"] if slot["rotation"]["mode"] == OVERRIDE
        else layer["rotation_deg"]
    )
    rotation=_rotation_override(mode,value)
    next_effective = value if mode == OVERRIDE else layer["rotation_deg"]
    if old_effective != next_effective:
        _invalidate_effective_rotation_x(slot)
    slot["rotation"]=rotation
    return state


def effective_nfb_rotation(draft,layer_index,slot_index):
    state=editable_nfb_draft(draft)
    row=_get_slot(state,layer_index,slot_index)["rotation"]
    return (row["value"] if row["mode"]==OVERRIDE else
            _get_layer(state,layer_index)["rotation_deg"])


def set_nfb_manual_x(draft,layer_index,slot_index,offset_mm,*,datum=None):
    state=editable_nfb_draft(draft)
    slot=_get_slot(state,layer_index,slot_index)
    if offset_mm is None:
        slot["manual_x_mm"]=None
        slot["manual_x_state"]=NONE
        slot["datum_snapshot"]=None
        slot.pop("datum_revision",None)
        return state
    if type(offset_mm) not in (int,float) or not isfinite(offset_mm):
        raise ValueError("NFB manual X offset must be finite, including zero")
    slot["manual_x_mm"]=float(offset_mm)
    slot["manual_x_state"]=UNVERIFIED
    slot["datum_snapshot"]=deepcopy(datum)
    # A freshly authored draft X is never approved by a prior revision.
    slot.pop("datum_revision",None)
    return state


@dataclass(frozen=True)
class NfbXResetImpact:
    """The exact before→after physical unit IDs whose X datum was removed.

    This is a preview/transaction receipt for operator visibility only,
    never a new source of world-X or permission to manufacture.
    """
    layer_index: int
    unit_ids: tuple[str, ...]

    @property
    def count(self):
        return len(self.unit_ids)


def nfb_x_reset_impact(before, after, layer_index):
    """Count only formerly placed/datum-bearing slots actually cleared.

    Include a deleted slot if its X or datum was present; never count an
    untouched sibling layer, a newly inserted empty slot, or a change of
    offset value as though the original X was *cleared*.
    """
    old = _get_layer(editable_nfb_draft(before), layer_index)
    new = _get_layer(editable_nfb_draft(after), layer_index)
    remaining = {slot["unit_id"]: slot for slot in new["slots"]}
    affected = []
    for slot in old["slots"]:
        had_basis = (
            slot["manual_x_mm"] is not None
            or slot["manual_x_state"] != NONE
            or slot["datum_snapshot"] is not None
        )
        if not had_basis:
            continue
        current = remaining.get(slot["unit_id"])
        if current is None or (
            current["manual_x_mm"] is None
            and current["manual_x_state"] == NONE
            and current["datum_snapshot"] is None
        ):
            affected.append(slot["unit_id"])
    return NfbXResetImpact(layer_index, tuple(affected))


@dataclass(frozen=True)
class NfbUi1aEditReceipt:
    action: str
    old_draft: dict
    new_draft: dict


class NfbUi1aEditSession:
    """One modal session, no project mutation before #1500 explicit submission."""
    def __init__(self,draft):
        self.original=editable_nfb_draft(draft)
        self.current=deepcopy(self.original)
        self._history=[]

    def apply(self,action,operation,*args,**kwargs):
        if not isinstance(action,str) or not action:
            raise ValueError("NFB transaction action name required")
        # Callbacks are external edit operations.  They may mutate their input
        # before raising on an invalid/colliding geometry.  Keep the live
        # transaction immutable until validation succeeds.
        isolated=deepcopy(self.current)
        candidate=editable_nfb_draft(operation(isolated,*args,**kwargs))
        if candidate==self.current:return None
        receipt=NfbUi1aEditReceipt(action,deepcopy(self.current),deepcopy(candidate))
        self.current=candidate
        self._history.append(receipt)
        return receipt

    def undo(self):
        if not self._history:
            raise ValueError("NFB UI-1A draft has no undo transaction")
        receipt=self._history[-1]
        if self.current!=receipt.new_draft:
            raise ValueError("NFB UI-1A undo conflict: current draft diverged")
        self.current=deepcopy(receipt.old_draft)
        self._history.pop()
        return receipt

    def cancel(self):
        self.current=deepcopy(self.original)
        self._history.clear()
        return deepcopy(self.current)

    def escape(self):
        return self.cancel()

    @property
    def dirty(self):
        return self.current!=self.original
