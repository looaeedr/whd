"""Atomic, memory-only Receiving mode ownership; files contain the active mode."""
from copy import deepcopy
from collections.abc import Mapping

from phase6_quantity_model import QuantityModel, QUANTITY_MODE, SET_BAY_MODE
from ae_engine.cabinet_types import receiving
from ae_engine.receiving_quantity_box import BOX_KEY, positive_dimension, project_common_box


def fresh_receiving_mode(mode, dimensions, *, thickness=2.0):
    """Start from Family defaults and confirmed dimensions, never another Bay."""
    from ae_engine.sheetmetal_part_adapters import complete_partition
    from ae_engine.receiving_layout import (
        new_receiving_layout, ensure_receiving_layout, _validate_common_receiving_state,
        RECEIVING_DOOR_STATE_KEYS,
    )
    if mode not in {QUANTITY_MODE, SET_BAY_MODE}:
        raise ValueError("不合法的受電箱操作模式")
    if not isinstance(dimensions, Mapping):
        raise ValueError("請明確確認 W/H/D")
    dims = {axis: positive_dimension(dimensions.get(axis), axis) for axis in ("w", "h", "d")}
    result = receiving.apply_family_defaults({"t": positive_dimension(thickness, "t")})
    from phase6_workspace_controller import DEFAULT_EXISTING_PARTS
    from phase6_workspace_state import PART_ORDER
    result["existing_parts"] = [key for key in PART_ORDER if key in DEFAULT_EXISTING_PARTS]
    result.update(dims)
    # Complete the Family's user-owned partitions through the canonical helper.
    defaults = receiving.default_door_layout_columns()
    widths = complete_partition([row[0] for row in defaults[:-1]], dims["w"])
    if not widths.valid or len(widths.values) != len(defaults):
        raise ValueError("W 不符合 Family 門分割")
    columns = []
    for width, (_, heights) in zip(widths.values, defaults):
        partition = complete_partition(heights[:-1], dims["h"])
        if not partition.valid or len(partition.values) != len(heights):
            raise ValueError("H 不符合 Family 門分割")
        columns.append([width, list(partition.values)])
    result["door_layout_columns"] = columns
    result["receiving_layout"] = new_receiving_layout(
        width=dims["w"], height=dims["h"], depth=dims["d"])
    result = ensure_receiving_layout(result)
    result["active_mode"] = mode
    _validate_common_receiving_state(result)
    if mode == QUANTITY_MODE:
        result["quantity"] = QuantityModel().snapshot()
        result[BOX_KEY] = {
            **dims, "back_panel_mode": "FULL", "inner_door_layers": 1,
            "switch_brand": "士林",
            "door_state": {key: deepcopy(result[key]) for key in RECEIVING_DOOR_STATE_KEYS if key in result},
        }
        result = project_common_box(result)
    return result


class ReceivingModeSession:
    """Only successful transitions mutate active state or session buffers."""

    def __init__(self, snapshot, *, validator=None):
        if not receiving.is_receiving_snapshot(snapshot):
            raise ValueError("雙向模式僅適用於受電箱")
        self._active = deepcopy(dict(snapshot))
        mode = self._active.get("active_mode", SET_BAY_MODE)
        self._check_mode(mode)
        self._mode = mode
        self._buffers = {}
        self._validator = validator

    @staticmethod
    def _check_mode(mode):
        if mode not in {QUANTITY_MODE, SET_BAY_MODE}:
            raise ValueError("不合法的受電箱操作模式")

    def snapshot(self):
        return deepcopy(self._active)

    def needs_initialization(self, target):
        self._check_mode(target)
        return target != self._mode and target not in self._buffers

    def switch(self, target, *, dimensions=None, current_snapshot=None):
        self._check_mode(target)
        if target == self._mode:
            return False
        current = deepcopy(dict(current_snapshot)) if current_snapshot is not None else self.snapshot()
        if current.get("active_mode", SET_BAY_MODE) != self._mode:
            raise ValueError("目前編輯狀態的模式不符")
        if target in self._buffers:
            candidate = deepcopy(self._buffers[target])
        else:
            if dimensions is None:
                return False
            candidate = fresh_receiving_mode(target, dimensions, thickness=current.get("t", 2.0))
            if self._validator is not None:
                self._validator(deepcopy(candidate))
        # One project allocator spans both memory-only mode buffers. Retain
        # history without copying any inactive physical sheet into a new mode.
        from phase6_custom_parts import CustomPartCatalog
        def catalog(snapshot):
            return CustomPartCatalog(snapshot.get("custom_parts") or
                                     dict(snapshot.get("workspace") or {}).get("custom_parts"))
        next_id = max(catalog(value).snapshot()["next_id"]
                      for value in (current, candidate, *self._buffers.values()))
        if next_id > 1:
            payload = catalog(candidate).snapshot()
            payload["next_id"] = next_id
            candidate["custom_parts"] = payload
            if "workspace" in candidate:
                candidate["workspace"]["custom_parts"] = deepcopy(payload)
        self._buffers[self._mode] = current
        self._active = candidate
        self._mode = target
        return True
