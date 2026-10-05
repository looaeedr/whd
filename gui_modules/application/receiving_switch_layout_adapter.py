# -*- coding: utf-8 -*-
"""Application facade for Receiving switch layer/connection input state."""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from ae_engine.receiving_switch_layout import (
    normalize_receiving_switch_layout,
    resize_switch_layers,
    set_layer_connection_count,
    set_switch_brand,
)


class ReceivingSwitchLayoutAdapter:
    """Own UI edits over one receiving_switch_layout value only.

    This adapter deliberately has no manufacturing/render callback.  A preview
    confirmation may hand a selected cell to a separate authoritative opening
    resolver, but +/- layer/connection edits never do so.
    """

    def __init__(self, layout: Mapping[str, object] | None) -> None:
        self._layout = normalize_receiving_switch_layout(layout)

    @property
    def layout(self) -> dict[str, object]:
        return deepcopy(self._layout)

    @property
    def brand(self) -> str:
        return str(self._layout["switch_brand"])

    def connection_counts(self) -> tuple[int, ...]:
        return tuple(int(row["connection_count"]) for row in self._layout["layers"])

    def connection_count(self, layer_index: int) -> int:
        index = int(layer_index)
        rows = self._layout["layers"]
        if index < 0 or index >= len(rows):
            raise IndexError("Receiving switch layer_index out of range")
        return int(rows[index]["connection_count"])

    def set_brand(self, brand: object) -> bool:
        updated = set_switch_brand(self._layout, brand)
        changed = updated != self._layout
        self._layout = updated
        return changed

    def add_layer(self) -> None:
        self._layout = resize_switch_layers(self._layout, len(self._layout["layers"]) + 1)

    def remove_layer(self) -> bool:
        current = len(self._layout["layers"])
        if current <= 1:
            return False
        self._layout = resize_switch_layers(self._layout, current - 1)
        return True

    def resize_connections(self, layer_index: int, delta: int) -> bool:
        current = self.connection_count(layer_index)
        wanted = max(1, current + int(delta))
        if wanted == current:
            return False
        self._layout = set_layer_connection_count(
            self._layout,
            layer_index=int(layer_index),
            connection_count=wanted,
        )
        return True
