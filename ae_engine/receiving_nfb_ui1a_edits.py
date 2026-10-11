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
    for i,layer in enumerate(state["layers"]):
        layer.setdefault("rotation_deg",0)
        if layer["rotation_deg"] not in ROTATIONS or type(layer["rotation_deg"]) is not int:
            raise ValueError("NFB layer rotation must be 0/90/180/270")
        for slot in layer["slots"]:
            if "unit_id" not in slot:
                slot["unit_id"]=f"nfb:ui1a:unit:{next_number}"
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
    state["_next_unit_number"]=next_number
    return state


def _reset_layer_x(layer):
    for slot in layer["slots"]:
        slot["manual_x_mm"]=None
        slot["manual_x_state"]=NONE
        slot["datum_snapshot"]=None


def insert_nfb_slot(draft, layer_index, position, *, filename=None, brand=None):
    state=editable_nfb_draft(draft)
    layer=_get_layer(state,layer_index)
    if type(position) is not int or not 0<=position<=len(layer["slots"]):
        raise ValueError("NFB insertion position invalid")
    if filename is not None and (not isinstance(filename,str) or
            not filename.endswith(".dxf") or "/" in filename or "\\" in filename):
        raise ValueError("NFB selected source filename invalid")
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
        if current["manual_x_mm"] is not None:
            current["manual_x_state"]=UNVERIFIED
            # Q16 retains the operator offset, but never the old source datum.
            current["datum_snapshot"]=None
    return result


def set_nfb_layer_rotation(draft,layer_index,angle):
    if type(angle) is not int or angle not in ROTATIONS:
        raise ValueError("NFB angle must be 0/90/180/270; mirrors forbidden")
    state=editable_nfb_draft(draft)
    _get_layer(state,layer_index)["rotation_deg"]=angle
    return state


def set_nfb_slot_rotation(draft,layer_index,slot_index,*,mode,value=None):
    if mode==OVERRIDE and (type(value) is not int or value not in ROTATIONS):
        raise ValueError("NFB slot angle must be quarter-turn, no mirror")
    if mode==INHERIT and value is not None:
        raise ValueError("NFB inherited rotation has no separate value")
    state=editable_nfb_draft(draft)
    _get_slot(state,layer_index,slot_index)["rotation"]=_rotation_override(mode,value)
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
        return state
    if type(offset_mm) not in (int,float) or not isfinite(offset_mm):
        raise ValueError("NFB manual X offset must be finite, including zero")
    slot["manual_x_mm"]=float(offset_mm)
    slot["manual_x_state"]=UNVERIFIED
    slot["datum_snapshot"]=deepcopy(datum)
    return state


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
        candidate=editable_nfb_draft(operation(self.current,*args,**kwargs))
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
