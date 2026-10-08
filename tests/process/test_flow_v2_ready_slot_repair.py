"""Native READY repair remains fail-closed, typed, and never a fake ACQUIRE."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import tools.control_transaction_production_executor as prod
from tools.control_transaction_production_executor import (
    ProductionExecutorError, assert_unique_ready_slot_candidate,
    plan_ready_slot_repair, repair_ready_slot,
)
from tools.control_transaction import ControlTransactionConflict
from tools.execution_dispatch_ingress import DispatchIngressRequest, plan_dispatch_ingress
from tools.execution_record import ActionSpec, LeaseState, QAState

NOW = datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
SHA = "a" * 40
LANE = "chatgpt.flowv2.work1"
INV = "chatgpt.issue1433.slotrepair.test"


def ready(number, slot):
    return plan_dispatch_ingress(DispatchIngressRequest(
        issue=number, execution_intent="EXECUTE_TICKET",
        authority_kind="USER_EXPLICIT", authority_ref=f"test:{number}",
        source_branch="cleanup/2d-3d-sync", source_sha=SHA,
        work_branch=f"work/issue-{number}", target_branch="cleanup/2d-3d-sync",
        target_sha=SHA, slot_id=slot,
    )).record


def active(number, slot, lane=LANE, expired=False):
    expiry = NOW + timedelta(seconds=-1 if expired else 900)
    return replace(
        ready(number, slot), state="ACTIVE", semantic_state="CLAIMED",
        generation=2, owner_kind="SCHEDULER", owner_id=lane, lane_id=lane,
        next_action=ActionSpec(kind="START_BRANCH", args={}),
        lease=LeaseState(token="test-opaque", invocation_identity=INV, expires_at=expiry.isoformat()),
    )


def records():
    return {
        1331: active(1331, "worker.slot.0", "chatgpt.flowv2.work0"),
        1431: ready(1431, "worker.slot.0"),
        1433: active(1433, "worker.slot.1"),
        1385: active(1385, "worker.slot.2", "chatgpt.flowv2.work2"),
    }


def call(records_override=None, **overrides):
    args = dict(
        authority_issue=1433, expected_authority_generation=2,
        target_issue=1431, expected_target_generation=1,
        expected_old_slot_id="worker.slot.0", new_slot_id="worker.slot.3",
        lane_id=LANE, invocation_identity=INV, observed_at=NOW,
    )
    args.update(overrides)
    return plan_ready_slot_repair(records_override if records_override is not None else records(), **args)


def test_prevent_duplicate_ready_occupancy():
    with pytest.raises(ProductionExecutorError, match="DISPATCH_READY_SLOT_COLLISION"):
        assert_unique_ready_slot_candidate(
            {1331: active(1331, "worker.slot.0", "chatgpt.flowv2.work0")},
            ready(1431, "worker.slot.0"),
        )


def test_accept_unique_ready_occupancy():
    assert_unique_ready_slot_candidate(
        {1331: active(1331, "worker.slot.0", "chatgpt.flowv2.work0")},
        ready(1431, "worker.slot.3"),
    ) is None


def test_preexisting_duplicate_elsewhere_must_not_stop_unrelated_free_slot():
    source = records()  # legacy collision: #1331 and #1431 both slot0
    assert_unique_ready_slot_candidate(source, ready(1450, "worker.slot.3")) is None
    with pytest.raises(ProductionExecutorError, match="DISPATCH_READY_SLOT_COLLISION"):
        assert_unique_ready_slot_candidate(source, ready(1451, "worker.slot.0"))


def test_repair_can_fix_one_collision_while_another_old_slot_is_duplicated():
    source = records()
    source[1400] = ready(1400, "worker.slot.2")
    result = call(source)
    assert result.slot_id == "worker.slot.3"


def test_repair_changes_only_slot_generation_time_and_real_audit_history():
    original = records()[1431]
    repaired = call()
    assert repaired.slot_id == "worker.slot.3" and repaired.generation == 2
    assert repaired.state == "READY" and repaired.lease is None
    assert repaired.owner_id == original.owner_id == "NONE"
    assert repaired.next_action == original.next_action
    assert repaired.head_sha == original.head_sha
    assert repaired.qa == original.qa and repaired.closure == original.closure
    assert repaired.recovery_history[-1]["kind"] == "READY_SLOT_REPAIR"
    assert original.slot_id == "worker.slot.0"


@pytest.mark.parametrize("override", [
    {"expected_authority_generation": 1},
    {"expected_target_generation": 2},
    {"expected_old_slot_id": "worker.slot.1"},
    {"new_slot_id": "worker.slot.2"},
    {"new_slot_id": "worker.slot.0"},
    {"new_slot_id": "worker.slot.4"},
    {"lane_id": "chatgpt.flowv2.work0"},
    {"invocation_identity": "foreign-invocation"},
    {"authority_issue": 1431},
    {"target_issue": 1433},
])
def test_reject_invalid_identity_and_occupied_slot(override):
    with pytest.raises(ProductionExecutorError):
        call(**override)


def test_reject_expired_authority_lease():
    items = records()
    items[1433] = active(1433, "worker.slot.1", expired=True)
    with pytest.raises(ProductionExecutorError, match="lease expired"):
        call(items)


def test_reject_target_claimed_or_with_qa():
    items = records()
    items[1431] = active(1431, "worker.slot.0")
    with pytest.raises(ProductionExecutorError, match="unclaimed READY"):
        call(items)
    items = records()
    items[1431] = replace(items[1431], qa=QAState(last_accepted_run=1234, accepted_head_sha=SHA))
    with pytest.raises(ProductionExecutorError, match="unclaimed READY"):
        call(items)


def test_writer_rejects_stale_coord_without_writing(monkeypatch):
    monkeypatch.setattr(prod, "_load_state", lambda *a: ("newhead", "tree", records()))
    def must_not_write(*a, **kw):
        raise AssertionError("stale CAS must never write")
    monkeypatch.setattr(prod, "_write_state", must_not_write)
    with pytest.raises(ControlTransactionConflict, match="coord head drift"):
        repair_ready_slot(
            repo="looaeedr/whd", token="fake", coord_branch="coord/execution-v2",
            authority_issue=1433, expected_authority_generation=2,
            target_issue=1431, expected_target_generation=1,
            expected_old_slot_id="worker.slot.0", new_slot_id="worker.slot.3",
            lane_id=LANE, invocation_identity=INV, expected_coord_head="oldhead",
        )


def test_writer_atomic_commit_and_postwrite_readback(monkeypatch):
    # Production authorizer uses real current time. Ensure fixture lease is live in test.
    items = records()
    items[1433] = replace(
        items[1433], lease=LeaseState(
            token="opaque", invocation_identity=INV,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        ),
    )
    calls = []
    def load(*a):
        if not calls:
            return "currenthead", "tree", items
        return "nexthead", "nexttree", calls[-1]
    def write(*a, **kw):
        calls.append(kw["records"])
        assert kw["parent_sha"] == "currenthead"
        assert items[1331] is kw["records"][1331]
        assert kw["records"][1431].slot_id == "worker.slot.3"
        return "nexthead", "blob"
    monkeypatch.setattr(prod, "_load_state", load)
    monkeypatch.setattr(prod, "_write_state", write)
    result = repair_ready_slot(
        repo="looaeedr/whd", token="fake", coord_branch="coord/execution-v2",
        authority_issue=1433, expected_authority_generation=2,
        target_issue=1431, expected_target_generation=1,
        expected_old_slot_id="worker.slot.0", new_slot_id="worker.slot.3",
        lane_id=LANE, invocation_identity=INV, expected_coord_head="currenthead",
    )
    assert result["result"] == "APPLIED"
    assert result["post_state"] == "READY"
    assert result["post_slot_id"] == "worker.slot.3"
    assert len(calls) == 1
