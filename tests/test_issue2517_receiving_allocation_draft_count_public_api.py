# -*- coding: utf-8 -*-
"""#2517: Receiving candidate count clicks are Engine-owned draft edits."""
from copy import deepcopy
import inspect

import ae_engine
import pytest
from ae_engine import manufacturing_api
from ae_engine.receiving_quantity_allocation import (
    AllocationDraft, adjust_receiving_candidate_draft_quantity,
)
from gui_modules.application.receiving_quantity_allocation_ui import (
    ReceivingQuantityAllocationUI,
)


def _draft():
    draft = AllocationDraft((2,))
    draft.add_version("head", "head-v1")
    draft.add_version("tail", "tail-v1")
    return draft


def _state(draft):
    return deepcopy((
        draft.counts, draft.quantities, draft.assigned,
        draft.step, draft.active_version,
    ))


def test_public_root_and_facade_are_canonical_engine_callable():
    assert manufacturing_api.adjust_receiving_candidate_draft_quantity is (
        adjust_receiving_candidate_draft_quantity
    )
    assert ae_engine.adjust_receiving_candidate_draft_quantity is (
        adjust_receiving_candidate_draft_quantity
    )


def test_plus_minus_and_zero_saturation_keep_head_tail_independent():
    draft = _draft()
    edit = manufacturing_api.adjust_receiving_candidate_draft_quantity
    assert edit(draft, "head", "head-v1", -1) == 0
    unchanged = _state(draft)
    assert edit(draft, "head", "head-v1", -1) == 0
    assert _state(draft) == unchanged
    assert edit(draft, "head", "head-v1", 1) == 1
    assert edit(draft, "head", "head-v1", 1) == 2
    draft.select_version("head", "head-v1")
    draft.set_step("head", 2)
    draft.assign("head", 0, 0)
    assert edit(draft, "head", "head-v1", -1) == 1
    assert draft.assigned["head"] == {}
    assert draft.step["head"] == 1
    assert draft.quantities["tail"] == {"tail-v1": 0}


@pytest.mark.parametrize("role,version_id,delta", (
    ("head", "head-v1", 0),
    ("head", "head-v1", 2),
    ("head", "head-v1", True),
    ("head", "head-v1", "-1"),
    ("head", "head-v1", None),
    ("tail", "head-v1", 1),
    ("head", "head-v999", 1),
    ("other", "head-v1", 1),
    ("head", [], 1),
))
def test_invalid_click_is_atomic(role, version_id, delta):
    draft = _draft()
    before = _state(draft)
    with pytest.raises((ValueError, TypeError, KeyError)):
        manufacturing_api.adjust_receiving_candidate_draft_quantity(
            draft, role, version_id, delta,
        )
    assert _state(draft) == before


def test_corrupt_draft_count_and_wrong_source_fail_before_write():
    draft = _draft()
    draft.quantities["head"]["head-v1"] = True
    before = _state(draft)
    with pytest.raises(ValueError, match="草稿數量"):
        manufacturing_api.adjust_receiving_candidate_draft_quantity(
            draft, "head", "head-v1", 1,
        )
    assert _state(draft) == before
    with pytest.raises(TypeError, match="草稿"):
        manufacturing_api.adjust_receiving_candidate_draft_quantity(
            {}, "head", "head-v1", 1,
        )


def test_real_gui_count_port_calls_engine_without_duplicate_policy():
    draft = _draft()
    ui = object.__new__(ReceivingQuantityAllocationUI)
    ui.role = "head"
    ui.draft = draft
    assert ui._count("head-v1", 1) == 1
    assert ui._count("head-v1", -1) == 0
    assert draft.quantities["head"] == {"head-v1": 0}
    source = inspect.getsource(ReceivingQuantityAllocationUI._count)
    assert "manufacturing_api.adjust_receiving_candidate_draft_quantity(" in source
    assert "max(" not in source
    assert "set_quantity(" not in source
