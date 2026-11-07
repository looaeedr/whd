"""#2517: Receiving physical Set/Bay +/- click uses one public Engine delta."""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, ReceivingSwitchProjectionAdapter,
    ReceivingDestructiveEditConfirmationRequired,
)


def _layout():
    return new_receiving_layout(width=800, height=1600, depth=350)


def _state(adapter):
    return deepcopy((
        adapter.layout, adapter.selection, adapter._persisted_ids,
        adapter._session_dirty_ids,
    ))


def test_root_and_manufacturing_api_are_same_engine_callable():
    assert ae_engine.adjust_receiving_operator_topology_with_removed_ids is (
        api.adjust_receiving_operator_topology_with_removed_ids
    )


def test_real_bay_plus_and_tail_shrink_equal_existing_engine_topology():
    source = _layout()
    frozen = deepcopy(source)
    grown, removed, changed = api.adjust_receiving_operator_topology_with_removed_ids(
        source, set_index=0, delta=2,
    )
    expected, expected_removed = api.resize_receiving_operator_topology_with_removed_ids(
        source, set_index=0, bay_count=3,
    )
    assert changed and removed == expected_removed == () and grown == expected
    assert len(grown["sets"][0]["joints"]) == 2
    shrunk, removed, changed = api.adjust_receiving_operator_topology_with_removed_ids(
        grown, set_index=0, delta=-100,
    )
    expected, expected_removed = api.resize_receiving_operator_topology_with_removed_ids(
        grown, set_index=0, bay_count=1,
    )
    assert changed and shrunk == expected and removed == expected_removed
    assert source == frozen


def test_set_plus_minus_and_minimum_preserve_physical_identity():
    source = _layout()
    grown, removed, changed = api.adjust_receiving_operator_topology_with_removed_ids(
        source, delta=1,
    )
    assert changed and removed == ()
    assert grown == api.resize_receiving_operator_topology_with_removed_ids(
        source, set_count=2,
    )[0]
    assert grown["sets"][1]["bays"][0]["panel_name"] == "P2"
    shrunk, removed, changed = api.adjust_receiving_operator_topology_with_removed_ids(
        grown, delta=-1,
    )
    assert changed and shrunk == source
    assert set(removed) == {"receiving:set:2", "receiving:set:2:bay:1"}
    unchanged, nothing, changed = api.adjust_receiving_operator_topology_with_removed_ids(
        source, delta=-1,
    )
    assert not changed and nothing == () and unchanged == source


@pytest.mark.parametrize("params", [
    {"delta": True},
    {"delta": 1.0},
    {"delta": "1"},
    {"delta": None},
    {"delta": 1, "set_index": True},
    {"delta": 1, "set_index": -1},
    {"delta": 1, "set_index": 4},
    {"delta": 1, "set_index": "0"},
])
def test_invalid_delta_and_set_identity_do_not_touch_source(params):
    source = _layout()
    original = deepcopy(source)
    with pytest.raises((ValueError, TypeError, IndexError)):
        api.adjust_receiving_operator_topology_with_removed_ids(source, **params)
    assert source == original


def test_noop_at_minimum_or_zero_delta_has_no_deleted_ids():
    source = _layout()
    for options in ({"delta": 0}, {"delta": -10},
                    {"delta": 0, "set_index": 0},
                    {"delta": -10, "set_index": 0}):
        candidate, removed, changed = api.adjust_receiving_operator_topology_with_removed_ids(
            source, **options,
        )
        assert candidate == source and removed == () and changed is False


def test_gui_real_buttons_delegate_bay_and_set_actions_to_public_engine():
    adapter = ReceivingSetBayAdapter(_layout())
    switch = ReceivingSwitchProjectionAdapter(adapter)
    assert "manufacturing_api.adjust_receiving_operator_topology_with_removed_ids(" in (
        getsource(ReceivingSetBayAdapter.apply_topology_delta)
    )
    assert "max(1, current + delta)" not in getsource(
        ReceivingSwitchProjectionAdapter.resize_connections
    )
    assert switch.resize_connections("0", "+2") is True
    assert switch.connection_counts() == (3,)
    assert switch.resize_connections(0, "-99") is True
    assert switch.connection_counts() == (1,)
    assert switch.resize_connections(0, -1) is False
    assert switch.add_layer() is True
    assert switch.connection_counts() == (1, 1)
    assert switch.remove_layer() is True
    assert switch.remove_layer() is False
    assert switch.connection_counts() == (1,)


def test_destructive_denial_preserves_original_selection_and_bookkeeping():
    source = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    source = api.resize_receiving_operator_topology_with_removed_ids(
        source, set_count=2,
    )[0]
    called = []
    adapter = ReceivingSetBayAdapter(
        source, persisted_ids=api.receiving_layout_stable_ids(source),
        confirm_destructive=lambda ids: called.append(ids) or False,
    )
    switch = ReceivingSwitchProjectionAdapter(adapter)
    adapter.select_set(2)
    adapter.mark_current_bay_dirty()
    before = _state(adapter)
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        switch.resize_connections(0, -1)
    assert _state(adapter) == before
    assert len(called) == 1
    assert "receiving:set:1:bay:2" in called[0]


def test_engine_reject_does_not_switch_GUI_selection(monkeypatch):
    source = api.resize_receiving_operator_topology_with_removed_ids(
        _layout(), set_count=2,
    )[0]
    adapter = ReceivingSetBayAdapter(source)
    switch = ReceivingSwitchProjectionAdapter(adapter)
    adapter.select_set(2)
    before = _state(adapter)

    def reject(*_args, **_kwargs):
        raise ValueError("ENGINE_SOURCE_REJECTED")

    monkeypatch.setattr(
        api, "adjust_receiving_operator_topology_with_removed_ids", reject,
    )
    with pytest.raises(ValueError, match="ENGINE_SOURCE_REJECTED"):
        switch.resize_connections(0, 1)
    assert _state(adapter) == before


def test_saved_real_set_bay_topology_survives_project_reload(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
    source = _layout()
    grown, _, _ = api.adjust_receiving_operator_topology_with_removed_ids(
        source, delta=1,
    )
    grown, _, _ = api.adjust_receiving_operator_topology_with_removed_ids(
        grown, set_index=1, delta=1,
    )
    snapshot = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2.0,
        "receiving_layout": grown,
    }
    result = write_project(tmp_path / "physical-topology-delta.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": snapshot,
    })
    loaded = read_project(result)["snapshot"]
    assert api.normalize_receiving_layout(loaded["receiving_layout"]) == grown
