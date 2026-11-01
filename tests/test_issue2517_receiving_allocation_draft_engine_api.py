"""#2517: Receiving candidate quantity draft transitions belong to public Engine API."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import AllocationDraft, manufacturing_api, validate_quantity_allocation
from gui_modules.application.receiving_quantity_allocation_ui import ReceivingQuantityAllocationUI


def _state(draft):
    return deepcopy((
        draft.counts, draft.quantities, draft.assigned,
        draft.step, draft.active_version,
    ))


def test_public_engine_quantity_draft_and_gui_compatibility():
    assert manufacturing_api.AllocationDraft is AllocationDraft
    assert manufacturing_api.validate_quantity_allocation is validate_quantity_allocation
    assert "from ae_engine.manufacturing_api import AllocationDraft, validate_quantity_allocation" in (
        Path(ReceivingQuantityAllocationUI.__module__.replace(".", "/") + ".py").read_text()
    )


def test_engine_replacement_preserves_count_and_order_but_invalidates_only_selected_role():
    draft = AllocationDraft((2, 1))
    draft.add_version("head", "head-v1")
    draft.set_quantity("head", "head-v1", 1)
    draft.add_version("head", "head-v2")
    draft.set_quantity("head", "head-v2", 2)
    draft.add_version("tail", "tail-v1")
    draft.set_quantity("tail", "tail-v1", 3)
    draft.select_version("head", "head-v1")
    draft.assign("head", 0, 0)
    draft.select_version("tail", "tail-v1")
    draft.assign("tail", 1, 0)
    tail_before = deepcopy((draft.quantities["tail"], draft.assigned["tail"], draft.active_version["tail"]))
    draft.set_step("head", 2)
    draft.replace_version("head", "head-v1", "head-v3", ("head-v2", "head-v3"))
    assert list(draft.quantities["head"].items()) == [("head-v3", 1), ("head-v2", 2)]
    assert draft.assigned["head"] == {}
    assert draft.active_version["head"] == "head-v3"
    assert draft.step["head"] == 1
    assert (draft.quantities["tail"], draft.assigned["tail"], draft.active_version["tail"]) == tail_before
    assert draft.ready_for_positioning("head")


@pytest.mark.parametrize("old,new,available", [
    ("missing", "head-v3", ("head-v3",)),
    ("head-v1", "head-v2", ("head-v1", "head-v2")),
    ("head-v1", "head-v3", ("head-v1",)),
    ("head-v1", "", ("",)),
    ("head-v1", None, ()),
])
def test_rejected_candidate_replace_is_atomic(old, new, available):
    draft = AllocationDraft((1,))
    draft.add_version("head", "head-v1")
    draft.add_version("head", "head-v2")
    before = _state(draft)
    with pytest.raises(ValueError):
        draft.replace_version("head", old, new, available)
    assert _state(draft) == before


def test_engine_selection_and_step_gate_do_not_mutate_on_invalid_action():
    draft = AllocationDraft((2,))
    draft.add_version("head", "head-v1")
    before = _state(draft)
    with pytest.raises(ValueError, match="數量"):
        draft.set_step("head", 2)
    with pytest.raises(ValueError, match="候選版本"):
        draft.select_version("head", "missing")
    with pytest.raises(ValueError, match="步驟"):
        draft.set_step("head", True)
    assert _state(draft) == before
    draft.set_quantity("head", "head-v1", 2)
    draft.set_step("head", 2)
    assert draft.step["head"] == 2
    draft.set_step("head", 1)
    assert draft.step["head"] == 1


def test_gui_replaces_candidate_through_engine_without_direct_business_mutation():
    draft = AllocationDraft((1,))
    draft.add_version("head", "head-v1")
    draft.set_quantity("head", "head-v1", 1)
    ui = object.__new__(ReceivingQuantityAllocationUI)
    ui.role = "head"
    ui.draft = draft
    ui.reconcile = lambda: {"head": ("head-v1", "head-v3")}
    rendered = []
    ui.on_render = lambda: rendered.append(True)
    ui._replace_version("head-v1", "head-v3")
    assert draft.quantities["head"] == {"head-v3": 1}
    ui._select_version("head-v3")
    assert rendered == [True]
    gui_source = Path("gui_modules/application/receiving_quantity_allocation_ui.py").read_text()
    assert "self.draft.quantities[self.role] =" not in gui_source
    assert "self.draft.active_version[self.role] =" not in gui_source
    assert "self.draft.step.__setitem__" not in gui_source
