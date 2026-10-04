# -*- coding: utf-8 -*-
"""Receiving switch layer/connection configuration authority.

This input state is deliberately separate from ``receiving_layout`` (the
multi-cabinet Set/Bay manufacturing topology).  Changing layer/connection counts
is configuration-only and must never create manufacturing geometry by itself.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

RECEIVING_SWITCH_LAYOUT_SCHEMA = "receiving-switch-layout-v1"
RECEIVING_SWITCH_BRANDS = ("士林", "東元", "三菱", "伍菱", "順山")
RECEIVING_SWITCH_LAYOUT_KEY = "receiving_switch_layout"


def _brand(value: object) -> str:
    text = str(value or RECEIVING_SWITCH_BRANDS[0]).strip()
    if text not in RECEIVING_SWITCH_BRANDS:
        raise ValueError(f"unsupported Receiving switch brand: {value!r}")
    return text


def _count(value: object, *, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if result < 1:
        raise ValueError(f"{label} must be >= 1")
    return result


def new_receiving_switch_layout(*, brand: object = RECEIVING_SWITCH_BRANDS[0]) -> dict[str, object]:
    return {
        "schema": RECEIVING_SWITCH_LAYOUT_SCHEMA,
        "switch_brand": _brand(brand),
        "layers": [
            {
                "stable_id": "receiving:switch-layer:1",
                "connection_count": 1,
            }
        ],
    }


def normalize_receiving_switch_layout(layout: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(layout, Mapping):
        return new_receiving_switch_layout()
    if str(layout.get("schema") or "") != RECEIVING_SWITCH_LAYOUT_SCHEMA:
        raise ValueError(f"unsupported Receiving switch layout schema: {layout.get('schema')!r}")
    raw_layers = layout.get("layers")
    if not isinstance(raw_layers, (list, tuple)) or not raw_layers:
        raise ValueError("Receiving switch layout must contain at least one layer")
    layers: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_layers, start=1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Receiving switch layer {index} must be a mapping")
        stable_id = str(raw.get("stable_id") or f"receiving:switch-layer:{index}").strip()
        if not stable_id or stable_id in seen:
            raise ValueError(f"invalid or duplicate Receiving switch layer stable_id: {stable_id!r}")
        seen.add(stable_id)
        layers.append(
            {
                "stable_id": stable_id,
                "connection_count": _count(
                    raw.get("connection_count", 1),
                    label=f"Receiving switch layer {index} connection_count",
                ),
            }
        )
    return {
        "schema": RECEIVING_SWITCH_LAYOUT_SCHEMA,
        "switch_brand": _brand(layout.get("switch_brand")),
        "layers": layers,
    }


def ensure_receiving_switch_layout(snapshot: Mapping[str, object] | None) -> dict[str, object]:
    result = deepcopy(dict(snapshot or {}))
    result[RECEIVING_SWITCH_LAYOUT_KEY] = normalize_receiving_switch_layout(
        result.get(RECEIVING_SWITCH_LAYOUT_KEY)
    )
    return result


def set_switch_brand(layout: Mapping[str, object], brand: object) -> dict[str, object]:
    result = normalize_receiving_switch_layout(layout)
    result["switch_brand"] = _brand(brand)
    return result


def resize_switch_layers(layout: Mapping[str, object], layer_count: object) -> dict[str, object]:
    result = normalize_receiving_switch_layout(layout)
    wanted = _count(layer_count, label="Receiving switch layer_count")
    layers = list(result["layers"])
    while len(layers) < wanted:
        index = len(layers) + 1
        layers.append(
            {
                "stable_id": f"receiving:switch-layer:{index}",
                "connection_count": 1,
            }
        )
    del layers[wanted:]
    result["layers"] = layers
    return normalize_receiving_switch_layout(result)


def set_layer_connection_count(
    layout: Mapping[str, object], *, layer_index: int, connection_count: object
) -> dict[str, object]:
    result = normalize_receiving_switch_layout(layout)
    index = int(layer_index)
    layers = list(result["layers"])
    if index < 0 or index >= len(layers):
        raise IndexError("Receiving switch layer_index out of range")
    row = deepcopy(dict(layers[index]))
    row["connection_count"] = _count(
        connection_count,
        label=f"Receiving switch layer {index + 1} connection_count",
    )
    layers[index] = row
    result["layers"] = layers
    return normalize_receiving_switch_layout(result)