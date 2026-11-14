"""#2517 Receiving real Set +/- must be one public Engine source transaction."""
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


def test_root_and_facade_use_identical_canonical_set_action():
    assert ae_engine.adjust_receiving_operator_set_count_with_removed_ids is (
        api.adjust_receiving_operator_set_count_with_removed_ids
    )
    assert "adjust_receiving_operator_set_count_with_removed_ids" in ae_engine.__all__


def test_plus_minus_uses_exact_absolute_engine_set_topology_and_deleted_ids():
    source = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    original = deepcopy(source)
    grown, removed, changed = api.adjust_receiving_operator_set_count_with_removed_ids(
        source, delta=1,
    )
    expected, expected_removed = api.resize_receiving_operator_topology_with_removed_ids(
        source, set_count=2,
    )
    assert changed and removed == expected_removed == () and grown == expected
    assert grown["sets"][0] == original["sets"][0]
    assert grown["sets"][1]["bays"][0]["panel_name"] == "P3"
    shrunk, removed, changed = api.adjust_receiving_operator_set_count_with_removed_ids(
        grown, delta=-1,
    )
    expected, expected_removed = api.resize_receiving_operator_topology_with_removed_ids(
        grown, set_count=1,
    )
    assert changed and shrunk == expected and removed == expected_removed
    assert set(removed) == {
        grown["sets"][1]["stable_id"], grown["sets"][1]["bays"][0]["stable_id"],
    }
    assert shrunk["next_panel_number"] == grown["next_panel_number"]
    assert source == original


@pytest.mark.parametrize("delta", (True, 1.5, "1", None, [], {}, float("inf")))
def test_invalid_operator_delta_never_modifies_project(delta):
    source = _layout()
    before = deepcopy(source)
    with pytest.raises((TypeError, ValueError)):
        api.adjust_receiving_operator_set_count_with_removed_ids(source, delta=delta)
    assert source == before


def test_one_set_minimum_and_zero_delta_are_engine_noops():
    source = _layout()
    for delta in (-1, -100, 0):
        result, removed, changed = api.adjust_receiving_operator_set_count_with_removed_ids(
            source, delta=delta,
        )
        assert not changed and removed == () and result == source
        assert result is not source


def test_actual_add_remove_buttons_delegate_engine_set_action():
    adapter = ReceivingSetBayAdapter(_layout())
    switch = ReceivingSwitchProjectionAdapter(adapter)
    assert "adjust_receiving_operator_set_count_with_removed_ids(" in getsource(
        ReceivingSetBayAdapter.apply_set_delta
    )
    source = getsource(ReceivingSwitchProjectionAdapter)
    assert "self.adapter.apply_set_delta(1)" in source
    assert "self.adapter.apply_set_delta(-1)" in source
    assert switch.add_layer() is True
    assert switch.connection_counts() == (1, 1)
    assert switch.remove_layer() is True
    assert switch.remove_layer() is False
    assert switch.connection_counts() == (1,)


def test_declined_removal_leaves_set_selection_and_dirty_protection_unchanged():
    source = api.resize_receiving_operator_topology_with_removed_ids(
        _layout(), set_count=2,
    )[0]
    calls = []
    adapter = ReceivingSetBayAdapter(
        source, persisted_ids=api.receiving_layout_stable_ids(source),
        confirm_destructive=lambda ids: calls.append(ids) or False,
    )
    switch = ReceivingSwitchProjectionAdapter(adapter)
    adapter.select_set(2)
    adapter.mark_current_bay_dirty()
    before = _state(adapter)
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        switch.remove_layer()
    assert _state(adapter) == before
    assert len(calls) == 1
    assert source["sets"][1]["stable_id"] in calls[0]


def test_engine_failure_does_not_touch_selection_or_session_state(monkeypatch):
    source = api.resize_receiving_operator_topology_with_removed_ids(
        _layout(), set_count=2,
    )[0]
    adapter = ReceivingSetBayAdapter(source)
    switch = ReceivingSwitchProjectionAdapter(adapter)
    adapter.select_set(2)
    before = _state(adapter)

    def reject(*_args, **_kwargs):
        raise ValueError("SOURCE_VALIDATION_FAILED")

    monkeypatch.setattr(
        api, "adjust_receiving_operator_set_count_with_removed_ids", reject,
    )
    with pytest.raises(ValueError, match="SOURCE_VALIDATION_FAILED"):
        switch.remove_layer()
    assert _state(adapter) == before


def test_real_project_save_reload_keeps_generated_set_identity(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
    grown, _, _ = api.adjust_receiving_operator_set_count_with_removed_ids(
        _layout(), delta=2,
    )
    snapshot = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2.0,
        "receiving_layout": grown,
    }
    target = write_project(tmp_path / "set-delta.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": snapshot,
    })
    saved = read_project(target)["snapshot"]
    assert api.normalize_receiving_layout(saved["receiving_layout"]) == grown
