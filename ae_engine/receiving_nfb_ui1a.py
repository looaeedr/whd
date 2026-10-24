# -*- coding: utf-8 -*-
"""#1491 NFB UI-1A transient physical-slot view model.

One brand owner: current Receiving Set.switch_brand. Layer/slot values are
explicit overrides, not duplicated Set authorities. The operator can override
with the SAME brand; it remains OVERRIDE until explicitly reset to INHERIT.
Draft-only: absolutely no write to ReceivingLayout, project, DXF, or MFG.

Pitch is nominal center-to-center distance, never an absolute X coordinate.
For 1100 top cell, Y values are nominal; otherwise Y is unknown. Source
filenames must be selected anew on a changed effective brand.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Mapping

from .receiving_switch_layout import RECEIVING_SWITCH_BRANDS
from .receiving_nfb_x_projection import nominal_nfb_x_group
from .receiving_nfb_y_projection import approved_nominal_y_mm

INHERIT = "INHERIT"
OVERRIDE = "OVERRIDE"
NEEDS_RESELECTION = "NEEDS_RESELECTION"
PREVIEW_ONLY = "UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY"


def _brand(value):
    if value not in RECEIVING_SWITCH_BRANDS:
        raise ValueError("NFB brand must be a registered Receiving switch brand")
    return value


def _override(mode=INHERIT, value=None):
    if mode not in (INHERIT, OVERRIDE):
        raise ValueError("NFB brand override mode invalid")
    if mode == INHERIT:
        if value is not None:
            raise ValueError("NFB inherit may not carry a second brand")
        return {"mode": INHERIT, "value": None}
    return {"mode": OVERRIDE, "value": _brand(value)}


def new_nfb_ui1a_draft(*, set_brand, layer_count=1, model_layers=("", "")):
    from .receiving_shared_settings import switch_filenames_in_layer
    owner = _brand(set_brand)
    if type(layer_count) is not int or layer_count not in (1, 2):
        raise ValueError("NFB physical layers must be 1 or 2")
    if not isinstance(model_layers, (list, tuple)) or len(model_layers) != 2:
        raise ValueError("NFB existing model layers must have two slots")
    rows = []
    for i in range(2):
        names = switch_filenames_in_layer(model_layers[i])
        rows.append({"brand": _override(), "slots": [
            {"brand": _override(), "filename": name, "source_brand": owner}
            for name in names
        ]})
    if layer_count == 1 and rows[1]["slots"]:
        raise ValueError("NFB cannot hide populated second physical layer")
    return {"set_brand": owner, "layer_count": layer_count,
            "layers": rows, "status": PREVIEW_ONLY}


def _revoke_changed_brand_x(before, updated):
    """Never reuse another effective brand's operator-confirmed X source."""
    for layer_index, layer in enumerate(updated["layers"]):
        for slot_index, slot in enumerate(layer["slots"]):
            if (effective_nfb_slot_brand(before, layer_index, slot_index)
                    == effective_nfb_slot_brand(updated, layer_index, slot_index)):
                continue
            # Bare UI-1A preview slots do not yet have any X evidence.
            if not any(k in slot for k in (
                    "manual_x_mm", "manual_x_state",
                    "datum_snapshot", "datum_revision")):
                continue
            slot["datum_snapshot"] = None
            slot.pop("datum_revision", None)
            if slot.get("manual_x_mm") is None:
                slot["manual_x_state"] = "NONE"
            else:
                slot["manual_x_state"] = (
                    "RECONFIRM_REQUIRED"
                    if slot.get("manual_x_state") in (
                        "CONFIRMED", "RECONFIRM_REQUIRED"
                    ) else "UNVERIFIED_BASIS"
                )
    return updated


def reconcile_set_brand(draft, new_brand):
    """Retain file and provenance on brand change, never replace automatically."""
    updated = deepcopy(draft)
    updated["set_brand"] = _brand(new_brand)
    return _revoke_changed_brand_x(draft, updated)


def set_nfb_draft_layer_count(draft, count):
    if type(count) is not int or count not in (1, 2):
        raise ValueError("NFB layer count must be one or two")
    updated = deepcopy(draft)
    if count == 1 and updated["layers"][1]["slots"]:
        raise ValueError("NFB second physical layer contains slots; remove them first")
    updated["layer_count"] = count
    return updated


def set_nfb_layer_brand(draft, layer_index, *, mode, value=None):
    updated = deepcopy(draft)
    _check_layer(updated, layer_index)
    updated["layers"][layer_index]["brand"] = _override(mode, value)
    return _revoke_changed_brand_x(draft, updated)


def set_nfb_slot_brand(draft, layer_index, slot_index, *, mode, value=None):
    updated = deepcopy(draft)
    slot = _get_slot(updated, layer_index, slot_index)
    slot["brand"] = _override(mode, value)
    return _revoke_changed_brand_x(draft, updated)


def add_nfb_draft_slot(draft, layer_index, *, filename=None, source_brand=None):
    updated = deepcopy(draft)
    _check_layer(updated, layer_index)
    if layer_index >= updated["layer_count"]:
        raise ValueError("NFB hidden physical layer cannot accept slots")
    if filename is not None:
        from .receiving_nfb_model_identity import validate_stored_model_ref
        validate_stored_model_ref(filename)
    current = effective_nfb_layer_brand(updated, layer_index)
    source = _brand(source_brand or current) if filename else None
    updated["layers"][layer_index]["slots"].append({
        "brand": _override(), "filename": filename, "source_brand": source,
    })
    return updated


def select_nfb_slot_model(draft, layer_index, slot_index, filename, *,
                          catalog: Mapping[str, tuple[str,...]]):
    updated = deepcopy(draft)
    slot = _get_slot(updated,layer_index,slot_index)
    actual = effective_nfb_slot_brand(updated, layer_index, slot_index)
    if (not isinstance(filename,str)
            or filename not in catalog.get(actual, ())):
        raise ValueError("NFB filename must be selected from current brand CSV")
    if filename.startswith("nfbv5:"):
        # A caller-supplied list is not authority to relabel a typed V5
        # identity. Re-check the actual brand-owned numeric CSV on selection.
        from .receiving_nfb_model_identity import selected_numeric_spec
        if selected_numeric_spec(actual, filename) is None:
            raise ValueError("NFB V5 model identity/source does not match effective brand CSV")
    if ((slot.get("filename"), slot.get("source_brand"))
            != (filename, actual) and any(
                field in slot for field in (
                    "manual_x_mm", "manual_x_state",
                    "datum_snapshot", "datum_revision"
                ))):
        # The unwrapped selection API is also called by other UI paths.
        # Never leave the prior model's world-X proof attached to this unit.
        slot["datum_snapshot"] = None
        slot.pop("datum_revision", None)
        if "manual_x_mm" in slot or "manual_x_state" in slot:
            if slot.get("manual_x_mm") is None:
                slot["manual_x_state"] = "NONE"
            elif slot.get("manual_x_state") in ("CONFIRMED", "RECONFIRM_REQUIRED"):
                slot["manual_x_state"] = "RECONFIRM_REQUIRED"
            else:
                slot["manual_x_state"] = "UNVERIFIED_BASIS"
    slot["filename"] = filename
    slot["source_brand"] = actual
    return updated


def remove_nfb_draft_slot(draft, layer_index, slot_index):
    updated = deepcopy(draft)
    slots = _get_layer(updated,layer_index)["slots"]
    if type(slot_index) is not int or not 0 <= slot_index < len(slots):
        raise IndexError("NFB physical slot index out of range")
    slots.pop(slot_index)
    return updated


def _check_layer(draft, i):
    if type(i) is not int or not 0 <= i < draft["layer_count"]:
        raise ValueError("NFB physical layer must be visible and valid")


def _get_layer(draft, i):
    _check_layer(draft,i)
    return draft["layers"][i]


def _get_slot(draft, i, j):
    slots = _get_layer(draft, i)["slots"]
    if type(j) is not int or not 0 <= j < len(slots):
        raise IndexError("NFB physical slot index out of range")
    return slots[j]


def effective_nfb_layer_brand(draft, i):
    row = _get_layer(draft,i)["brand"]
    return row["value"] if row["mode"] == OVERRIDE else draft["set_brand"]


def effective_nfb_slot_brand(draft, i, j):
    slot = _get_slot(draft,i,j)
    return (slot["brand"]["value"] if slot["brand"]["mode"] == OVERRIDE
            else effective_nfb_layer_brand(draft,i))


def nfb_ui1a_preview(draft, *, bay_width_mm, upper_cell_height_mm,
                     catalog: Mapping[str,tuple[str,...]] | None = None,
                     layer_heights_mm=None):
    """No absolute X, no CUTTING and no claim of manufacturing readiness."""
    if draft.get("status") != PREVIEW_ONLY:
        raise ValueError("NFB preview requires an unsubmitted draft")
    if type(draft.get("layer_count")) is not int or draft["layer_count"] not in (1,2):
        raise ValueError("NFB physical layer count invalid")
    if type(bay_width_mm) not in (int,float) or not isfinite(float(bay_width_mm)):
        raise ValueError("NFB Bay width is invalid")
    if type(upper_cell_height_mm) not in (int,float) or not isfinite(float(upper_cell_height_mm)):
        raise ValueError("NFB upper cell height is invalid")
    if layer_heights_mm is not None:
        from .receiving_shared_settings import validate_setting
        verified_heights = validate_setting(
            "inner_door_layer_heights_mm", layer_heights_mm,
        )
        if verified_heights[draft["layer_count"] - 1] >= float(upper_cell_height_mm):
            raise ValueError("每層高度須位於目前作業區的頂部至底部之間")
        ys = tuple(verified_heights[:draft["layer_count"]])
    else:
        ys = (approved_nominal_y_mm(draft["layer_count"])
              if abs(float(upper_cell_height_mm)-1100.0)<1e-6 else None)
    # One live CSV read per effective brand, not one per slot. The original
    # CSV may disappear between selection and preview; stale V5 references
    # must become NEEDS_RESELECTION rather than MODEL_SELECTED.
    from .receiving_nfb_model_identity import numeric_model_refs
    v5_sources = {}
    def v5_model_current(brand, filename):
        if not filename.startswith("nfbv5:"):
            return True  # legacy DXF identities retain their older contract
        if brand not in v5_sources:
            try:
                v5_sources[brand] = set(numeric_model_refs(brand))
            except (OSError, ValueError):
                v5_sources[brand] = set()
        return filename in v5_sources[brand]

    layers = []
    for i in range(draft["layer_count"]):
        slots = draft["layers"][i]["slots"]
        pitch = None
        if len(slots):
            try:
                pitch = nominal_nfb_x_group(int(bay_width_mm), len(slots)).adjacent_distances_mm if float(bay_width_mm).is_integer() else None
            except ValueError:
                pitch = None
        values = []
        for j,slot in enumerate(slots):
            brand = effective_nfb_slot_brand(draft,i,j)
            filename = slot["filename"]
            status = ("EMPTY" if filename is None else
                      NEEDS_RESELECTION if (slot["source_brand"] != brand or
                          not v5_model_current(brand, filename) or
                          (catalog is not None and filename not in catalog.get(brand,())))
                      else "MODEL_SELECTED")
            values.append({"slot_index":j, "filename":filename,
                           "effective_brand":brand,
                           "brand_mode":slot["brand"]["mode"],
                           "status":status, "absolute_x_mm":None,
                           # Relative pitch is never a physical X position.
                           # Explicit per-check UNKNOWN values prevent a
                           # consumer from treating missing collision/bounds
                           # evidence as a successful validation.
                           "verification": {
                               "absolute_x": "UNVERIFIED",
                               "collision": "UNVERIFIED",
                               "bounds": "UNVERIFIED",
                           }})
        layers.append({"layer_index":i, "effective_brand":effective_nfb_layer_brand(draft,i),
                       "brand_mode":draft["layers"][i]["brand"]["mode"],
                       "nominal_y_from_top_mm":ys[i] if ys is not None else None,
                       "adjacent_x_mm":pitch, "absolute_x_mm":None,
                       "slots":values})
    from .receiving_nfb_pad_depth_policy import preview_nfb_pad_depth
    pad = preview_nfb_pad_depth(draft)
    return {"status":PREVIEW_ONLY, "can_manufacture":False,
            "has_absolute_x":False, "is_1100_y_known":ys is not None,
            "layers":layers,
            "pad_depth_preview": {
                "status":pad.status,
                "depth_mm":pad.depth_mm,
                "candidate_delta_mm":pad.candidate_delta_mm,
                "shallower_unit_index":pad.shallower_unit_index,
                "manufacturing_ready":False,
            }}
