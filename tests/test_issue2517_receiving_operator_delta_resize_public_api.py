# -*- coding: utf-8 -*-
"""#2517 Receiving +/- cross-Set Bay edit is one Engine-owned atomic candidate."""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    append_receiving_set, new_receiving_layout, resize_receiving_bays,
    receiving_layout_stable_ids,
    resize_receiving_operator_connections_by_delta_with_removed_ids as owner,
)
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingDestructiveEditConfirmationRequired,
    ReceivingSetBayAdapter, ReceivingSwitchProjectionAdapter,
)


def _two_sets():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    layout = append_receiving_set(layout)
    return resize_receiving_bays(layout, set_index=1, bay_count=2)


def _state(adapter):
    return deepcopy((
        adapter.layout, adapter.selection,
        adapter._persisted_ids, adapter._session_dirty_ids,
    ))


def test_public_root_facade_and_absolute_resize_parity():
    assert api.resize_receiving_operator_connections_by_delta_with_removed_ids is owner
    assert ae_engine.resize_receiving_operator_connections_by_delta_with_removed_ids is owner
    assert "resize_receiving_operator_connections_by_delta_with_removed_ids" in ae_engine.__all__
    original = _two_sets()
    before = deepcopy(original)
    candidate, removed, changed = owner(original, set_index=1, delta=-1)
    expected, expected_removed = api.resize_receiving_operator_topology_with_removed_ids(
        original, set_index=1, bay_count=1,
    )
    assert changed is True
    assert candidate == expected
    assert removed == expected_removed
    assert set(removed) == (
        set(receiving_layout_stable_ids(original))
        - set(receiving_layout_stable_ids(candidate))
    )
    assert original == before


def test_growth_uses_live_receiving_family_defaults():
    layout = _two_sets()
    expected, removed = api.resize_receiving_operator_topology_with_removed_ids(
        layout, set_index=1, bay_count=3,
    )
    result, delta_removed, changed = owner(layout, set_index=1, delta=1)
    assert changed is True and delta_removed == removed == ()
    assert result == expected
    assert result["sets"][0] == layout["sets"][0]


def test_minimum_one_bay_clamp_is_engine_noop():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    before = deepcopy(layout)
    for delta in (-1, -10, 0):
        candidate, removed, changed = owner(layout, set_index=0, delta=delta)
        assert candidate == before and candidate is not layout
        assert removed == () and changed is False
    assert layout == before


@pytest.mark.parametrize("index,delta", (
    (True, 1), (0, True), (0, 1.0), (0, "1"),
    ("0", 1), (-1, 1), (9, 1), (None, 1), (0, None),
))
def test_rejected_engine_operands_leave_real_source_unmodified(index, delta):
    original = _two_sets()
    before = deepcopy(original)
    with pytest.raises((ValueError, IndexError)):
        owner(original, set_index=index, delta=delta)
    assert original == before


def test_cross_set_denied_destructive_edit_preserves_selection_and_dirty_ids():
    original = _two_sets()
    calls = []
    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: calls.append(ids) or False,
    )
    adapter.select_bay(2)
    adapter.mark_current_bay_dirty()
    initial = _state(adapter)
    switch = ReceivingSwitchProjectionAdapter(adapter)
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        switch.resize_connections(1, -1)
    assert _state(adapter) == initial
    assert len(calls) == 1
    assert original["sets"][1]["bays"][1]["stable_id"] in calls[0]


def test_cross_set_engine_failure_does_not_prompt_or_change_selected_set(monkeypatch):
    original = _two_sets()
    calls = []
    adapter = ReceivingSetBayAdapter(
        original, confirm_destructive=lambda ids: calls.append(ids) or True,
    )
    adapter.select_bay(2)
    before = _state(adapter)

    def reject(*_args, **_kwargs):
        raise ValueError("ENGINE_REJECTED_SOURCE")

    monkeypatch.setattr(
        api, "resize_receiving_operator_connections_by_delta_with_removed_ids", reject,
    )
    with pytest.raises(ValueError, match="ENGINE_REJECTED_SOURCE"):
        ReceivingSwitchProjectionAdapter(adapter).resize_connections(1, 1)
    assert _state(adapter) == before and calls == []


def test_cross_set_growth_family_invalid_never_switches_selection(monkeypatch):
    from ae_engine.cabinet_types import receiving

    adapter = ReceivingSetBayAdapter(_two_sets())
    before = _state(adapter)
    monkeypatch.setitem(receiving.BOX_BODY_DEFAULTS, "w", 801.5)
    with pytest.raises(ValueError, match="受電箱預設"):
        ReceivingSwitchProjectionAdapter(adapter).resize_connections(1, 1)
    assert _state(adapter) == before


def test_cross_set_approval_commits_exact_removed_id_and_selection_together():
    original = _two_sets()
    deleted = original["sets"][1]["bays"][1]["stable_id"]
    approvals = []
    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: approvals.append(ids) or True,
    )
    adapter.select_bay(2)
    adapter.mark_current_bay_dirty()
    assert ReceivingSwitchProjectionAdapter(adapter).resize_connections("1", "-1") is True
    assert len(adapter.layout["sets"][1]["bays"]) == 1
    assert adapter.selection.set_index == 1 and adapter.selection.bay_index == 0
    assert deleted in approvals[0]
    assert deleted not in adapter._persisted_ids
    assert deleted not in adapter._session_dirty_ids
    assert original["sets"][1]["bays"][1]["stable_id"] == deleted


def test_clamped_noop_from_another_set_does_not_switch_selection():
    layout = _two_sets()
    layout = resize_receiving_bays(layout, set_index=1, bay_count=1)
    adapter = ReceivingSetBayAdapter(layout)
    before = _state(adapter)
    assert ReceivingSwitchProjectionAdapter(adapter).resize_connections(1, -1) is False
    assert _state(adapter) == before


def test_true_text_operator_delta_and_gui_delegation():
    adapter = ReceivingSetBayAdapter(_two_sets())
    assert ReceivingSwitchProjectionAdapter(adapter).resize_connections("1", "1") is True
    assert len(adapter.layout["sets"][1]["bays"]) == 3
    assert adapter.selection.set_index == 1 and adapter.selection.bay_index == 0
    source = getsource(ReceivingSwitchProjectionAdapter.resize_connections)
    assert "return self.adapter.resize_connections(index, delta)" in source
    assert "max(1" not in source
    assert "select_set(" not in source
    core = getsource(ReceivingSetBayAdapter.resize_connections)
    assert "max(1" not in core
    assert "select_set(" not in core
    assert "manufacturing_api.resize_receiving_operator_connections_by_delta_with_removed_ids(" in core
    assert core.index("self._confirm_if_required(removed)") < core.index("self._layout = candidate")
