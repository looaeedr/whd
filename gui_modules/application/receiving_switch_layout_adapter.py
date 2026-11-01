# -*- coding: utf-8 -*-
"""Application facade for Receiving switch layer/connection input state."""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from ae_engine import manufacturing_api


def _ui_exact_integer(value: object, *, label: str) -> int:
    """Accept real integer values or integer entry text, never bool/float."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"Receiving switch {label} must be an integer")
    if isinstance(value, str):
        raw = value.strip()
        if not raw or not raw.lstrip("+-").isdecimal():
            raise ValueError(f"Receiving switch {label} must be an integer")
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"Receiving switch {label} must be an integer") from exc
    return value


class ReceivingSwitchLayoutAdapter:
    """Own UI edits over one receiving_switch_layout value only.

    This adapter deliberately has no manufacturing/render callback.  A preview
    confirmation may hand a selected cell to a separate authoritative opening
    resolver, but +/- layer/connection edits never do so.
    """

    def __init__(self, layout: Mapping[str, object] | None) -> None:
        self._layout = manufacturing_api.normalize_receiving_switch_operator_layout(layout)

    @property
    def layout(self) -> dict[str, object]:
        return deepcopy(self._layout)

    @property
    def brand(self) -> str:
        return str(self._layout["switch_brand"])

    def connection_counts(self) -> tuple[int, ...]:
        return tuple(int(row["connection_count"]) for row in self._layout["layers"])

    def connection_count(self, layer_index: int) -> int:
        index = _ui_exact_integer(layer_index, label="layer_index")
        rows = self._layout["layers"]
        if index < 0 or index >= len(rows):
            raise IndexError("Receiving switch layer_index out of range")
        return int(rows[index]["connection_count"])

    def set_brand(self, brand: object) -> bool:
        self._layout, changed = manufacturing_api.apply_receiving_switch_operator_action(
            self._layout, operation="set_brand", brand=brand,
        )
        return changed

    def add_layer(self) -> None:
        self._layout, _ = manufacturing_api.apply_receiving_switch_operator_action(
            self._layout, operation="add_layer",
        )

    def remove_layer(self) -> bool:
        self._layout, changed = manufacturing_api.apply_receiving_switch_operator_action(
            self._layout, operation="remove_layer",
        )
        return changed

    def resize_connections(self, layer_index: int, delta: int) -> bool:
        index = _ui_exact_integer(layer_index, label="layer_index")
        adjustment = _ui_exact_integer(delta, label="delta")
        self._layout, changed = manufacturing_api.apply_receiving_switch_operator_action(
            self._layout, operation="resize_connections",
            layer_index=index, delta=adjustment,
        )
        return changed
