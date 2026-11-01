# -*- coding: utf-8 -*-
"""#2517 Receiving singleton Door controls Save/Reload are Engine owned."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import (
    append_receiving_set, new_receiving_layout, normalize_receiving_layout,
    resize_receiving_bays, update_receiving_bay,
)
from gui_modules.application import fold_designer_snapshot_projection as gui


def _source():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        door_state={"inner_doors": [{"offset_mm": 80}], "multi_door_enabled": False},
    )
    return {
        "model": "受電箱",
        "active_mode": "set_bay",
        "receiving_layout": layout,
        "inner_doors": [{"offset_mm": 70}, {"offset_mm": 105}],
        "multi_door_enabled": True,
        "door_layout_columns": [[800., [800., 800.]]],
        "door_handle_edges": {"door_c0_r0": "LEFT"},
        "door_layout_scope": "main",
        "door_nameplate_center_datum_top": 85.,
    }


def test_single_bay_live_root_door_controls_reconcile_true_saved_bay_without_mutating_source():
    snapshot = _source()
    before = deepcopy(snapshot)
    result = manufacturing_api.project_receiving_single_bay_door_controls(snapshot)
    assert snapshot == before
    assert result is not snapshot["receiving_layout"]
    persisted = normalize_receiving_layout(result)
    door = persisted["sets"][0]["bays"][0]["door_state"]
    assert door["inner_doors"] == [{"offset_mm": 70}, {"offset_mm": 105}]
    assert door["multi_door_enabled"] is True
    assert door["door_layout_columns"] == [[800., [800., 800.]]]
    assert door["door_handle_edges"] == {"door_c0_r0": "LEFT"}
    assert door["door_nameplate_center_datum_top"] == 85.
    result["sets"][0]["bays"][0]["door_state"]["inner_doors"][0]["offset_mm"] = 999
    assert snapshot == before


@pytest.mark.parametrize("field,value", [
    ("model", "金庫型"),
    ("active_mode", "quantity"),
    ("inner_doors", []),
])
def test_non_owned_root_inputs_never_rewrite_saved_receiving_bay(field, value):
    snap = _source()
    snap[field] = value
    before = deepcopy(snap)
    assert manufacturing_api.project_receiving_single_bay_door_controls(snap) is None
    assert snap == before


def test_multiple_bays_or_sets_never_borrow_root_gui_door_state():
    original = _source()
    for layout in (
        resize_receiving_bays(original["receiving_layout"], set_index=0, bay_count=2),
        append_receiving_set(original["receiving_layout"]),
    ):
        snap = {**original, "receiving_layout": layout}
        before = deepcopy(snap)
        assert manufacturing_api.project_receiving_single_bay_door_controls(snap) is None
        assert snap == before
        assert snap["receiving_layout"]["sets"][0]["bays"][0]["door_state"] == (
            layout["sets"][0]["bays"][0]["door_state"]
        )


def test_broken_single_set_or_layout_does_not_fabricate_physical_bay():
    snap = _source()
    snap["receiving_layout"] = {"sets": ["invalid"], "schema": "receiving-layout-v1"}
    with pytest.raises(ValueError, match="SINGLE_BAY_SET_SOURCE_INVALID"):
        manufacturing_api.project_receiving_single_bay_door_controls(snap)
    snap = _source()
    snap["receiving_layout"]["sets"][0]["bays"][0]["width"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        manufacturing_api.project_receiving_single_bay_door_controls(snap)


def test_gui_workspace_snapshot_only_delegates_persisted_door_state_to_engine():
    source = inspect.getsource(gui._snapshot_workspace_state)
    assert "manufacturing_api.project_receiving_single_bay_door_controls(snapshot)" in source
    assert "update_receiving_bay(" not in source
    assert "RECEIVING_DOOR_STATE_KEYS" not in source
    assert 'snapshot["receiving_layout"] = bay_layout' in source
