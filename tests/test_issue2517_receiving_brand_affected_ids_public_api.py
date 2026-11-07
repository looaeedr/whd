# -*- coding: utf-8 -*-
"""#2517 NFB brand change impacts real Set/Bay identity through public Engine."""
from copy import deepcopy
from inspect import getsource

import pytest
import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays, append_receiving_set
from ae_engine.receiving_nfb_brand_transition import (
    update_receiving_one_set_nfb_parent_brand_with_affected_ids as one_owner,
    update_receiving_all_set_nfb_parent_brand_with_affected_ids as all_owner,
)
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, ReceivingSwitchProjectionAdapter,
    ReceivingDestructiveEditConfirmationRequired,
)


def _source():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    return append_receiving_set(resize_receiving_bays(layout, set_index=0, bay_count=2))


def _ids(layout, indices):
    return tuple(
        item
        for i in indices
        for item in (
            str(layout["sets"][i]["stable_id"]),
            *(str(b["stable_id"]) for b in layout["sets"][i]["bays"]),
        )
    )


def test_root_facade_and_existing_brand_contracts():
    assert ae_engine.update_receiving_one_set_nfb_parent_brand_with_affected_ids is one_owner
    assert api.update_receiving_one_set_nfb_parent_brand_with_affected_ids is one_owner
    assert ae_engine.update_receiving_all_set_nfb_parent_brand_with_affected_ids is all_owner
    assert api.update_receiving_all_set_nfb_parent_brand_with_affected_ids is all_owner
    assert "update_receiving_one_set_nfb_parent_brand_with_affected_ids" in ae_engine.__all__
    assert "update_receiving_all_set_nfb_parent_brand_with_affected_ids" in ae_engine.__all__
    original = _source()
    previous, old_changed = api.update_receiving_one_set_nfb_parent_brand(original, 0, "東元")
    candidate, changed, ids = one_owner(original, 0, "東元")
    assert (candidate, changed) == (previous, old_changed)
    assert ids == _ids(candidate, (0,))


def test_all_set_changes_report_only_unmodified_set_exclusion_and_noop():
    original = _source()
    before = deepcopy(original)
    selected, changed, ids = one_owner(original, 0, "東元")
    assert changed is True and ids == _ids(selected, (0,))
    whole, changed, ids = all_owner(selected, "東元")
    assert changed is True and ids == _ids(whole, (1,))
    same, changed, ids = all_owner(whole, "東元")
    assert changed is False and ids == ()
    assert same == whole and same is not whole
    assert original == before


def test_gui_marks_unpersisted_bay_and_set_and_prevents_silent_tail_delete():
    adapter = ReceivingSetBayAdapter(_source())
    assert adapter.set_brand("東元") is True
    assert adapter._session_dirty_ids == set(_ids(adapter.layout, (0,)))
    before = adapter.layout
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired) as exc:
        adapter.set_bay_count(1)
    assert before["sets"][0]["bays"][1]["stable_id"] in exc.value.stable_ids
    assert adapter.layout == before
    assert adapter.set_global_brand("東元") is True
    assert adapter._session_dirty_ids == set(_ids(adapter.layout, (0, 1)))
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        adapter.set_set_count(1)
    assert adapter.set_global_brand("東元") is False
    assert adapter._session_dirty_ids == set(_ids(adapter.layout, (0, 1)))


def test_switch_facade_reads_engine_changed_not_gui_brand_comparison():
    adapter = ReceivingSetBayAdapter(_source())
    switch = ReceivingSwitchProjectionAdapter(adapter)
    assert switch.set_brand("東元") is True
    assert switch.set_brand("東元") is False
    source = getsource(ReceivingSwitchProjectionAdapter.set_brand)
    assert "return self.adapter.set_brand(brand)" in source
    assert "self.brand != brand" not in source


@pytest.mark.parametrize("bad", (None, True, "未知廠牌", {}, 99))
def test_bad_brand_atomic_layout_and_protection(bad):
    source = _source()
    before = deepcopy(source)
    adapter = ReceivingSetBayAdapter(source)
    for operation in (
        lambda: one_owner(source, 0, bad),
        lambda: all_owner(source, bad),
        lambda: adapter.set_brand(bad),
        lambda: adapter.set_global_brand(bad),
    ):
        with pytest.raises((ValueError, TypeError)):
            operation()
        assert source == before
        assert adapter.layout == before
        assert adapter._session_dirty_ids == set()


def test_gui_seams_consume_engine_affected_physical_ids():
    one = getsource(ReceivingSetBayAdapter.set_brand)
    all_sets = getsource(ReceivingSetBayAdapter.set_global_brand)
    assert "update_receiving_one_set_nfb_parent_brand_with_affected_ids(" in one
    assert "update_receiving_all_set_nfb_parent_brand_with_affected_ids(" in all_sets
    for source in (one, all_sets):
        assert "self._session_dirty_ids.update(affected_ids)" in source
        assert '["bays"]' not in source
