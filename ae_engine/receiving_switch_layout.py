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
    # An absent stored brand keeps the established default; a corrupt
    # false/zero/nontext brand must never silently select another factory.
    if value is not None and not isinstance(value, str):
        raise ValueError(f"unsupported Receiving switch brand: {value!r}")
    # Only an absent value means the historical default. An explicitly
    # saved empty string is corrupt vendor authority, not a default request.
    text = RECEIVING_SWITCH_BRANDS[0] if value is None else value.strip()
    if text not in RECEIVING_SWITCH_BRANDS:
        raise ValueError(f"unsupported Receiving switch brand: {value!r}")
    return text


def _count(value: object, *, label: str) -> int:
    if isinstance(value, (bool, float)):
        raise ValueError(f"{label} must be an integer")
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
    if layout is None:
        return new_receiving_switch_layout()
    if not isinstance(layout, Mapping):
        raise ValueError("Receiving switch layout must be a mapping")
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
        source_id = raw.get("stable_id")
        if isinstance(source_id, bool):
            raise ValueError(f"invalid Receiving switch layer stable_id: {source_id!r}")
        stable_id = str(source_id or f"receiving:switch-layer:{index}").strip()
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
    # This is a physical tier selector: True must never alias index 1,
    # and fractional values must not be truncated to a different tier.
    if type(layer_index) is not int:
        raise ValueError("Receiving switch layer_index must be an integer")
    result = normalize_receiving_switch_layout(layout)
    index = layer_index
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

def apply_receiving_switch_operator_action(
    layout: Mapping[str, object] | None, *,
    operation: str, brand: object = None,
    layer_index: int | None = None, delta: int | None = None,
) -> tuple[dict[str, object], bool]:
    """Canonical physical Switch layer/connection operator transaction.

    Returns a detached normalized layout and a changed flag. Pure input
    selection does not manufacture a cutout or approve NFB model/source.
    """
    source = normalize_receiving_switch_layout(layout)
    if operation == "set_brand":
        candidate = set_switch_brand(source, brand)
    elif operation == "add_layer":
        candidate = resize_switch_layers(source, len(source["layers"]) + 1)
    elif operation == "remove_layer":
        count = len(source["layers"])
        if count <= 1:
            return source, False
        candidate = resize_switch_layers(source, count - 1)
    elif operation == "resize_connections":
        if type(layer_index) is not int or type(delta) is not int:
            raise ValueError("Receiving switch layer index/delta must be integers")
        if layer_index < 0 or layer_index >= len(source["layers"]):
            raise IndexError("Receiving switch layer_index out of range")
        current = source["layers"][layer_index]["connection_count"]
        wanted = max(1, current + delta)
        if wanted == current:
            return source, False
        candidate = set_layer_connection_count(
            source, layer_index=layer_index, connection_count=wanted,
        )
    else:
        raise ValueError(f"unsupported Receiving switch action: {operation!r}")
    return candidate, candidate != source
