# -*- coding: utf-8 -*-
"""#2517: Receiving topology edit cannot partly remove GUI deletion protection."""
from copy import deepcopy
import inspect

import ae_engine
import pytest
from ae_engine import manufacturing_api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, resize_receiving_sets,
    receiving_destructive_tail_ids, receiving_layout_stable_ids,
    resize_receiving_operator_topology_with_removed_ids,
)
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, ReceivingDestructiveEditConfirmationRequired,
)


def layout_three():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )


def state(adapter):
    return deepcopy((
        adapter.layout, adapter.selection,
        adapter._persisted_ids, adapter._session_dirty_ids,
    ))


def test_public_identity_bay_shrink_and_source_unchanged():
    assert manufacturing_api.resize_receiving_operator_topology_with_removed_ids is (
        resize_receiving_operator_topology_with_removed_ids
    )
    assert ae_engine.resize_receiving_operator_topology_with_removed_ids is (
        resize_receiving_operator_topology_with_removed_ids
    )
    layout = layout_three()
    before = deepcopy(layout)
    candidate, removed = manufacturing_api.resize_receiving_operator_topology_with_removed_ids(
        layout, set_index=0, bay_count=1,
    )
    assert layout == before
    assert removed == receiving_destructive_tail_ids(layout, set_index=0, bay_count=1)
    assert set(removed) == (
        set(receiving_layout_stable_ids(layout))
        - set(receiving_layout_stable_ids(candidate))
    )
    assert len(candidate["sets"][0]["bays"]) == 1
    assert len(candidate["sets"][0]["joints"]) == 0


def test_set_shrink_and_bay_growth_reuse_existing_engine_rules():
    layout = resize_receiving_sets(layout_three(), set_count=2)
    candidate, removed = manufacturing_api.resize_receiving_operator_topology_with_removed_ids(
        layout, set_count=1,
    )
    assert removed == receiving_destructive_tail_ids(layout, set_count=1)
    assert candidate == resize_receiving_sets(layout, set_count=1)
    grown, absent = manufacturing_api.resize_receiving_operator_topology_with_removed_ids(
        candidate, set_index=0, bay_count=4,
    )
    assert absent == ()
    assert len(grown["sets"][0]["bays"]) == 4
    assert grown["sets"][0]["bays"][0] == candidate["sets"][0]["bays"][0]


@pytest.mark.parametrize("options", (
    {}, {"set_index": 0, "bay_count": 1, "set_count": 1},
    {"set_index": 0, "set_count": 1}, {"set_index": True, "bay_count": 1},
    {"set_index": -1, "bay_count": 1}, {"set_index": 77, "bay_count": 1},
    {"set_index": 0, "bay_count": 0}, {"set_count": 0}, {"set_count": True},
))
def test_invalid_requests_keep_canonical_layout(options):
    original = layout_three()
    before = deepcopy(original)
    with pytest.raises((ValueError, IndexError, TypeError)):
        manufacturing_api.resize_receiving_operator_topology_with_removed_ids(
            original, **options,
        )
    assert original == before


@pytest.mark.parametrize("mode", ("bay", "set"))
def test_engine_failure_never_mutates_gui_protection_or_prompts(monkeypatch, mode):
    original = layout_three()
    if mode == "set":
        original = resize_receiving_sets(original, set_count=2)
    called = []
    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: called.append(ids) or True,
    )
    adapter.select_bay(2)
    adapter.mark_current_bay_dirty()
    before = state(adapter)

    def fail(*_args, **_kwargs):
        raise ValueError("ENGINE_SOURCE_REJECTED")

    monkeypatch.setattr(manufacturing_api, "resize_receiving_operator_topology_with_removed_ids", fail)
    with pytest.raises(ValueError, match="ENGINE_SOURCE_REJECTED"):
        (adapter.set_bay_count(1) if mode == "bay" else adapter.set_set_count(1))
    assert state(adapter) == before and called == []


@pytest.mark.parametrize("mode", ("bay", "set"))
def test_denied_destructive_confirmation_keeps_source_and_marks(mode):
    original = layout_three()
    if mode == "set":
        original = resize_receiving_sets(original, set_count=2)
    called = []
    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: called.append(ids) or False,
    )
    adapter.select_bay(2)
    adapter.mark_current_bay_dirty()
    before = state(adapter)
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        (adapter.set_bay_count(1) if mode == "bay" else adapter.set_set_count(1))
    assert state(adapter) == before and len(called) == 1


@pytest.mark.parametrize("mode", ("bay", "set"))
def test_successful_gui_shrink_commits_only_actual_physical_removals(mode):
    original = layout_three()
    if mode == "set":
        original = resize_receiving_sets(original, set_count=2)
    called = []
    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: called.append(ids) or True,
    )
    before = set(adapter._persisted_ids)
    adapter.select_bay(2)
    adapter.mark_current_bay_dirty()
    if mode == "bay":
        removed = receiving_destructive_tail_ids(original, set_index=0, bay_count=1)
        adapter.set_bay_count(1)
    else:
        removed = receiving_destructive_tail_ids(original, set_count=1)
        adapter.set_set_count(1)
    assert len(called) == 1
    assert set(called[0]) <= set(removed)
    assert adapter._persisted_ids == before - set(removed)
    assert adapter._session_dirty_ids <= set(receiving_layout_stable_ids(adapter.layout))


def test_gui_uses_one_public_engine_transaction_not_two_split_calls():
    for name in ("set_bay_count", "set_set_count"):
        body = inspect.getsource(getattr(ReceivingSetBayAdapter, name))
        assert "manufacturing_api.resize_receiving_operator_topology_with_removed_ids(" in body
        assert "manufacturing_api.receiving_destructive_tail_ids(" not in body
    assert "manufacturing_api.resize_receiving_bays_with_family_defaults(" not in inspect.getsource(
        ReceivingSetBayAdapter.set_bay_count
    )
