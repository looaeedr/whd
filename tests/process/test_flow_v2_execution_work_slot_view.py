from dataclasses import replace

import pytest

from tools.execution_record import execution_record_from_payload
from tools.execution_work_slot_view import (
    FIXED_SLOT_IDS,
    WorkSlotViewError,
    project_work_slots,
)


LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"


def _record(issue: int, *, slot_id: str | None, state: str = "ACTIVE"):
    done = state == "DONE"
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 2,
        "issue": issue,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "NONE" if done else "SCHEDULER",
        "owner_id": "NONE" if done else LANE_A,
        "lane_id": None if done else LANE_A,
        "slot_id": slot_id,
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": f"work/issue-{issue}",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": state,
        "semantic_state": state,
        "next_action": None if done else {"kind": "APPLY_COMMIT", "args": {}, "display": "continue exact work"},
        "lease": None,
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": (
            {"merged_sha": None, "issue_closed": True, "released_at": "2026-09-28T02:20:00Z"}
            if done else
            {"merged_sha": None, "issue_closed": False, "released_at": None}
        ),
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T02:10:00Z",
    })


def test_projection_always_returns_four_fixed_slots_and_only_record_backed_occupancy():
    records = [_record(844, slot_id="worker.slot.2")]

    slots = project_work_slots(records)

    assert tuple(slot.slot_id for slot in slots) == FIXED_SLOT_IDS
    assert slots[0].status == "EMPTY"
    assert slots[1].status == "EMPTY"
    assert slots[2].status == "BOUND"
    assert slots[2].issue == 844
    assert slots[2].owner_id == LANE_A
    assert slots[2].next_action_kind == "APPLY_COMMIT"
    assert slots[3].status == "EMPTY"


def test_unbound_nonterminal_record_does_not_get_guessed_into_an_empty_slot():
    slots = project_work_slots([_record(844, slot_id=None)])

    assert all(slot.status == "EMPTY" for slot in slots)
    assert all(slot.issue is None for slot in slots)


def test_terminal_record_does_not_occupy_slot_even_if_historical_slot_id_remains():
    slots = project_work_slots([_record(844, slot_id="worker.slot.1", state="DONE")])

    assert slots[0].status == "EMPTY"


def test_two_nonterminal_records_cannot_occupy_same_slot():
    with pytest.raises(WorkSlotViewError, match="duplicate slot occupancy"):
        project_work_slots([
            _record(844, slot_id="worker.slot.1"),
            _record(845, slot_id="worker.slot.1"),
        ])


def test_unknown_slot_identity_fails_closed_instead_of_creating_a_fifth_slot():
    with pytest.raises(WorkSlotViewError, match="unknown slot_id"):
        project_work_slots([_record(844, slot_id="worker.slot.4")])


def test_projection_is_deterministic_across_record_order():
    a = _record(844, slot_id="worker.slot.1")
    b = _record(845, slot_id="worker.slot.3")

    assert project_work_slots([a, b]) == project_work_slots([b, a])
