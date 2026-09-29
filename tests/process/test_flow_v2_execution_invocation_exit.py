import json
from pathlib import Path
import pytest
from dataclasses import replace

from tools.execution_invocation_exit import (InvocationExitError, assert_durable_terminal_exit, classify_invocation_exit)
from tools.execution_record import (
    ActionSpec,
    BlockerState,
    ClosureState,
    LeaseState,
    RunState,
    TransactionState,
    ExecutionRecordError,
    execution_record_from_payload,
)


INV = "scheduled:00:run-a"
OTHER = "scheduled:20:run-b"
NOW = "2026-09-28T02:00:00Z"
ROOT = Path(__file__).resolve().parents[2]


def _record(state="ACTIVE", *, lease_invocation=INV, lease_expires="2026-09-28T02:05:00Z"):
    done = state == "DONE"
    blocked = state == "BLOCKED"
    verifying = state == "VERIFYING"
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 4,
        "issue": 844,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "NONE" if done else "SCHEDULER",
        "owner_id": "NONE" if done else "scheduler.a",
        "lane_id": None if done else "scheduler.a",
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "work/issue-844",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": state,
        "semantic_state": state,
        "next_action": None if done else {
            "kind": "POLL_QA" if verifying else "WAIT_EXTERNAL" if blocked else "APPLY_COMMIT",
            "args": ({"run_id": 36370000999, "head_sha": "b" * 40} if verifying else {"blocker_kind": "EXTERNAL_DEPENDENCY"} if blocked else {"candidate_commit_sha": "d" * 40}),
            "display": "continue exact action",
        },
        "lease": None if done else {
            "token": "lease-a",
            "invocation_identity": lease_invocation,
            "expires_at": lease_expires,
        },
        "active_run": (
            {"id": 36370000999, "head_sha": "b" * 40, "purpose": "QA", "status": "in_progress"}
            if verifying else None
        ),
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": (
            {"kind": "EXTERNAL_DEPENDENCY", "evidence": "external system", "recheck_after": None}
            if blocked else None
        ),
        "closure": (
            {"merged_sha": None, "issue_closed": True, "released_at": "2026-09-28T01:50:00Z"}
            if done else {"merged_sha": None, "issue_closed": False, "released_at": None}
        ),
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T01:59:00Z",
    })


def test_done_task_is_terminal_without_yield():
    result = classify_invocation_exit(_record("DONE"), invocation_identity=INV, now=NOW)
    assert result.decision == "TASK_TERMINAL"
    assert result.may_return is True
    assert result.requires_yield is False


def test_other_live_lease_is_safe_lane_busy_return_not_task_terminal():
    result = classify_invocation_exit(
        _record("ACTIVE", lease_invocation=OTHER), invocation_identity=INV, now=NOW
    )
    assert result.decision == "LANE_BUSY"
    assert result.may_return is True
    assert result.requires_yield is False


def test_expired_other_lease_requires_acquire_before_any_exit_claim():
    result = classify_invocation_exit(
        _record("ACTIVE", lease_invocation=OTHER, lease_expires=NOW), invocation_identity=INV, now=NOW
    )
    assert result.decision == "ACQUIRE_REQUIRED"
    assert result.may_return is False


def test_current_invocation_with_executable_action_must_continue():
    result = classify_invocation_exit(_record("ACTIVE"), invocation_identity=INV, now=NOW)
    assert result.decision == "CONTINUE_EXECUTION"
    assert result.may_return is False


def test_active_remote_run_can_yield_between_physical_runtimes():
    result = classify_invocation_exit(_record("VERIFYING"), invocation_identity=INV, now=NOW)
    assert result.decision == "YIELD_REQUIRED_REMOTE_WAIT"
    assert result.may_return is False
    assert result.requires_yield is True


def test_genuine_durable_blocker_can_yield_but_remains_nonterminal():
    result = classify_invocation_exit(_record("BLOCKED"), invocation_identity=INV, now=NOW)
    assert result.decision == "YIELD_REQUIRED_BLOCKED"
    assert result.may_return is False
    assert result.requires_yield is True


def test_host_boundary_requires_current_invocation_substantive_transaction_before_yield():
    record = _record("ACTIVE")
    current_tx = TransactionState(
        id="tx-current",
        kind="APPLY_COMMIT",
        status="RECONCILED",
        expected_fingerprint="d" * 64,
        invocation_identity=INV,
    )
    result = classify_invocation_exit(
        replace(record, transaction=current_tx),
        invocation_identity=INV,
        now=NOW,
        host_boundary=True,
    )
    assert result.decision == "YIELD_REQUIRED_HOST_BOUNDARY"
    assert result.requires_yield is True

    other_tx = replace(current_tx, invocation_identity=OTHER)
    other_result = classify_invocation_exit(
        replace(record, transaction=other_tx),
        invocation_identity=INV,
        now=NOW,
        host_boundary=True,
    )
    assert other_result.decision == "SCHEDULER_EXECUTION_NO_PROGRESS"
    assert other_result.may_return is False


def test_completed_yield_is_machine_proof_for_physical_return():
    record = _record("ACTIVE")
    yielded = replace(
        record,
        lease=None,
        transaction=TransactionState(
            id="tx-yield",
            kind="YIELD",
            status="RECONCILED",
            expected_fingerprint="e" * 64,
            invocation_identity=INV,
        ),
    )
    result = classify_invocation_exit(yielded, invocation_identity=INV, now=NOW)
    assert result.decision == "YIELDED"
    assert result.may_return is True
    assert result.requires_yield is False


def test_host_boundary_rejects_acquire_only_as_no_progress():
    record = _record("ACTIVE")
    acquire_tx = TransactionState(
        id="tx-acquire-only",
        kind="ACQUIRE",
        status="RECONCILED",
        expected_fingerprint="a" * 64,
        invocation_identity=INV,
    )
    result = classify_invocation_exit(
        replace(record, transaction=acquire_tx),
        invocation_identity=INV,
        now=NOW,
        host_boundary=True,
    )
    assert result.decision == "SCHEDULER_EXECUTION_NO_PROGRESS"
    assert result.may_return is False
    assert result.requires_yield is False


def test_terminal_tail_finalize_cannot_yield_after_reconciled_merge_or_reconcile():
    base = _record("ACTIVE")
    terminal_tail = replace(
        base,
        state="INTEGRATING",
        semantic_state="MERGED",
        next_action=ActionSpec(kind="FINALIZE", args={}, display="finalize terminal tail"),
    )
    for kind in ("MERGE", "RECONCILE"):
        tx = TransactionState(
            id=f"tx-{kind.lower()}",
            kind=kind,
            status="RECONCILED",
            expected_fingerprint="f" * 64,
            invocation_identity=INV,
        )
        result = classify_invocation_exit(
            replace(terminal_tail, transaction=tx),
            invocation_identity=INV,
            now=NOW,
            host_boundary=True,
        )
        assert result.decision == "CONTINUE_TERMINAL_TAIL"
        assert result.may_return is False
        assert result.requires_yield is False


def test_functional_success_cannot_claim_terminal_before_durable_done():
    base = _record("ACTIVE")
    merged_tail = replace(
        base,
        state="INTEGRATING",
        semantic_state="MERGED",
        next_action=ActionSpec(kind="FINALIZE", args={}, display="finish durable tail"),
    )
    with pytest.raises(InvocationExitError, match="DURABLE_TERMINAL_EXIT_BLOCKED"):
        assert_durable_terminal_exit(merged_tail)


def test_done_record_rejects_uncleared_owner_identity():
    done = _record("DONE")
    with pytest.raises(ExecutionRecordError, match="DONE record must clear owner identity"):
        replace(
            done,
            owner_kind="SCHEDULER",
            owner_id="scheduler.a",
            lane_id="scheduler.a",
        )


def test_terminal_green_merge_tail_cannot_yield_at_host_boundary():
    base = _record("ACTIVE")
    merge_tail = replace(
        base,
        state="INTEGRATING",
        semantic_state="QA_ACCEPTED",
        next_action=ActionSpec(
            kind="MERGE",
            args={"pr_number": 1035},
            display="merge accepted exact-head candidate",
        ),
        qa=replace(
            base.qa,
            last_accepted_run=36604683925,
            accepted_head_sha=base.head_sha,
        ),
    )
    for kind in ("ACCEPT_QA", "CONSUME_QA", "ACQUIRE"):
        tx = TransactionState(
            id=f"tx-{kind.lower()}",
            kind=kind,
            status="RECONCILED",
            expected_fingerprint="a" * 64,
            invocation_identity=INV,
        )
        result = classify_invocation_exit(
            replace(merge_tail, transaction=tx),
            invocation_identity=INV,
            now=NOW,
            host_boundary=True,
        )
        assert result.decision == "CONTINUE_TERMINAL_TAIL"
        assert result.may_return is False
        assert result.requires_yield is False


def test_terminal_exit_contract_forbids_green_boundary_yield():
    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_DURABLE_TERMINAL_EXIT_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["terminal_green_is_stop_authority"] is False
    assert payload["terminal_green_policy"] == "CONSUME_AND_CONTINUE_SAME_INVOCATION"
    assert payload["terminal_tail_actions"] == ["MERGE", "FINALIZE"]
    assert payload["host_boundary_yield_forbidden_in_terminal_tail"] is True
    assert payload["terminal_tail_exit_decision"] == "CONTINUE_TERMINAL_TAIL"
