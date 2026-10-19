# -*- coding: utf-8 -*-
"""Restore typed NFB source selectors after the manufacturing DTO boundary.

The canonical manufacturing freeze intentionally writes every Real as float
to keep numeric fingerprints stable (2 and 2.0 are equivalent measurements).
However NFB layer_count, layer_index, slot_index and rotation_deg are discrete
identities, not numeric measurements. The consumer's strict type checks must
receive INTEGERS again. This is a detached DTO reconstruction only; never
promote NFB manufacturing readiness or alter operator-entered coordinates.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite


SELECTORS = frozenset((
    "layer_count", "layer_index", "slot_index", "rotation_deg",
))


def _selector(value, name):
    if type(value) is int:
        return value
    if type(value) is float and isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(f"RECEIVING_NFB_TRANSPORT_INVALID_SELECTOR:{name}")


def _config(raw):
    if not isinstance(raw, Mapping):
        raise ValueError("RECEIVING_NFB_TRANSPORT_CONFIG_INVALID")
    config = dict(raw)
    if "layer_count" in config:
        config["layer_count"] = _selector(config["layer_count"], "layer_count")
    rows = config.get("holes")
    if not isinstance(rows, (list, tuple)):
        raise ValueError("RECEIVING_NFB_TRANSPORT_HOLES_INVALID")
    holes = []
    for source in rows:
        if not isinstance(source, Mapping):
            raise ValueError("RECEIVING_NFB_TRANSPORT_HOLE_INVALID")
        row = dict(source)
        for name in SELECTORS & row.keys():
            row[name] = _selector(row[name], name)
        holes.append(row)
    config["holes"] = holes
    return config


def restore_receiving_nfb_dto_selectors(snapshot):
    """Detach current saved NFB selection from the already-thawed DTO map.

    Normalization is only for scopes with an *explicitly* submitted config.
    A draft never becomes submitted; incorrect/fractional selectors fail closed.
    Restores the same types in top-level, synthetic/current Bay and quantity
    version, so all source-identity comparisons remain consistent.
    """
    if not isinstance(snapshot, Mapping):
        raise TypeError("RECEIVING_NFB_TRANSPORT_REQUIRES_MAPPING")
    if snapshot.get("model") not in ("受電箱", "RECEIVING"):
        return dict(snapshot)
    data = dict(snapshot)
    if data.get("nfb_config_submitted") is True:
        data["nfb_config"] = _config(data.get("nfb_config"))
    selection = data.get("_receiving_runtime_selection")
    if isinstance(selection, Mapping):
        restored_selection = dict(selection)
        for name in ("set_index", "bay_index"):
            if name in restored_selection:
                restored_selection[name] = _selector(
                    restored_selection[name], name,
                )
        data["_receiving_runtime_selection"] = restored_selection
    layout = data.get("receiving_layout")
    if isinstance(layout, Mapping):
        sets = []
        for original_set in tuple(layout.get("sets") or ()):
            if not isinstance(original_set, Mapping):
                raise ValueError("RECEIVING_NFB_TRANSPORT_SET_INVALID")
            row = dict(original_set)
            bays = []
            for original_bay in tuple(row.get("bays") or ()):
                if not isinstance(original_bay, Mapping):
                    raise ValueError("RECEIVING_NFB_TRANSPORT_BAY_INVALID")
                bay = dict(original_bay)
                if bay.get("nfb_config_submitted") is True:
                    bay["nfb_config"] = _config(bay.get("nfb_config"))
                bays.append(bay)
            row["bays"] = bays
            sets.append(row)
        data["receiving_layout"] = {**layout, "sets": sets}
    quantity = data.get("quantity")
    if isinstance(quantity, Mapping):
        versions = []
        for original in tuple(quantity.get("versions") or ()):
            if not isinstance(original, Mapping):
                raise ValueError("RECEIVING_NFB_TRANSPORT_VERSION_INVALID")
            version = dict(original)
            if version.get("nfb_config_submitted") is True:
                version["nfb_config"] = _config(version.get("nfb_config"))
            versions.append(version)
        data["quantity"] = {**quantity, "versions": versions}
    return data
