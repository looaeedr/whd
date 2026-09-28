# Mirror governance is validated by the paired PR hard gate; this file tests runtime slot routing.
from dataclasses import replace

import pytest

from tools.execution_dispatch_ingress import DispatchIngressRequest, plan_dispatch_ingress
from tools.execution_work_slot_view import (
    WorkSlotViewError,
    select_first_available_work_slot,
)


def _record(issue: int, slot_id: str):
    return plan_dispatch_ingress(
        DispatchIngressRequest(
            issue=issue,
            execution_intent="EXECUTE_TICKET",
            authority_kind="WORK_SLOT_ASSIGNMENT",
            authority_ref=f"test-slot-{slot_id}",
            source_branch="main",
            source_sha="a" * 40,
            work_branch=f"work/issue-{issue}",
            target_branch="cleanup/2d-3d-sync",
            target_sha="b" * 40,
            slot_id=slot_id,
        )
    ).record


def test_default_work0_routing_uses_slot0_when_empty():
    assert select_first_available_work_slot(()) == "worker.slot.0"


def test_default_work0_routing_auto_increments_to_first_empty_slot():
    records = (
        _record(1001, "worker.slot.0"),
        _record(1002, "worker.slot.1"),
    )
    assert select_first_available_work_slot(records) == "worker.slot.2"


def test_done_record_does_not_block_its_slot():
    done = replace(
        _record(1001, "worker.slot.0"),
        state="DONE",
        semantic_state="DONE",
    )
    assert select_first_available_work_slot((done,)) == "worker.slot.0"


def test_explicit_start_slot_only_moves_up_and_does_not_wrap():
    records = (_record(1003, "worker.slot.2"),)
    assert (
        select_first_available_work_slot(records, start_slot_id="worker.slot.2")
        == "worker.slot.3"
    )


def test_all_slots_occupied_fails_closed():
    records = tuple(
        _record(1100 + index, f"worker.slot.{index}")
        for index in range(4)
    )
    with pytest.raises(WorkSlotViewError, match="NO_AVAILABLE_WORK_SLOT"):
        select_first_available_work_slot(records)
