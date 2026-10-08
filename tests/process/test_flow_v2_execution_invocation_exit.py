import json
from pathlib import Path
import pytest
from dataclasses import replace

from tools.execution_invocation_exit import (InvocationExitError, assert_durable_terminal_exit, build_host_exit_proof, classify_invocation_exit)
from tools.execution_record import (
    ActionSpec,
    BlockerState,
    ClosureState,
    LeaseState,
    RunState,
    TransactionState,
    MutationScopeState,
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


@pytest.mark.parametrize("host_boundary", [False, True])
def test_done_with_other_executable_leaf_forbids_invocation_return(host_boundary):
    result = classify_invocation_exit(
        _record("DONE"),
        invocation_identity=INV,
        now=NOW,
        host_boundary=host_boundary,
        alternative_executable_leaf_count=1,
    )
    assert result.decision == "CONTINUE_OTHER_EXECUTABLE_LEAF"
    assert result.may_return is False
    assert result.requires_yield is False


def test_done_with_other_executable_leaf_cannot_mint_host_exit_proof():
    with pytest.raises(InvocationExitError, match="CONTINUE_OTHER_EXECUTABLE_LEAF"):
        build_host_exit_proof(
            _record("DONE"),
            invocation_identity=INV,
            now=NOW,
            alternative_executable_leaf_count=1,
        )


def test_done_without_other_executable_leaf_stays_terminal_at_host_boundary():
    result = classify_invocation_exit(
        _record("DONE"),
        invocation_identity=INV,
        now=NOW,
        host_boundary=True,
        alternative_executable_leaf_count=0,
    )
    assert result.decision == "TASK_TERMINAL"
    assert result.may_return is True


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


def test_active_remote_run_continues_polling_until_terminal():
    result = classify_invocation_exit(_record("VERIFYING"), invocation_identity=INV, now=NOW)
    assert result.decision == "CONTINUE_REMOTE_QA_POLL"
    assert result.may_return is False
    assert result.requires_yield is False


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
    assert result.decision == "CONTINUE_EXECUTION"
    assert result.requires_yield is False
    assert result.next_action_kind == "APPLY_COMMIT"

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


def test_completed_yield_with_other_executable_leaf_must_continue_same_invocation():
    record = _record("ACTIVE")
    yielded = replace(
        record,
        lease=None,
        transaction=TransactionState(
            id="tx-yield-other-leaf",
            kind="YIELD",
            status="RECONCILED",
            expected_fingerprint="e" * 64,
            invocation_identity=INV,
        ),
    )
    result = classify_invocation_exit(
        yielded,
        invocation_identity=INV,
        now=NOW,
        alternative_executable_leaf_count=1,
    )
    assert result.decision == "CONTINUE_OTHER_EXECUTABLE_LEAF"
    assert result.may_return is False
    assert result.requires_yield is False


def test_alternative_executable_leaf_count_rejects_invalid_values():
    with pytest.raises(InvocationExitError, match="alternative_executable_leaf_count"):
        classify_invocation_exit(
            _record("ACTIVE"),
            invocation_identity=INV,
            now=NOW,
            alternative_executable_leaf_count=-1,
        )


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


def _repository_content_done_record():
    return replace(
        _record("DONE"),
        mutation_scope=MutationScopeState(
            target_branch="cleanup/2d-3d-sync",
            base_sha="a" * 40,
            write_paths=("AGENTS.md",),
            delete_paths=(),
            reservation_state="RELEASED",
        ),
        closure=ClosureState(merged_sha="c" * 40, issue_closed=True, released_at="2026-09-28T01:50:00Z"),
        target_sha="c" * 40,
    )


def _root_sync_receipt_for_done():
    from tools.post_integration_durability import build_root_sync_receipt
    return build_root_sync_receipt(
        accepted_sha="c" * 40, accepted_tree_sha="d" * 40,
        root_head_sha="c" * 40, root_tree_sha="d" * 40,
    )


def _lane_delivery_receipt_for_done():
    from tools.post_integration_durability import build_lane_delivery_receipt
    return build_lane_delivery_receipt(
        lane="docs", issue=844, generation=2, merged_sha="c" * 40,
        manifest_digest="e" * 64, delivered_paths=["AGENTS.md"], lane_state_after="EMPTY",
    )


def test_workspace_done_returns_without_retired_lane_cleanup_evidence():
    result = classify_invocation_exit(_repository_content_done_record(), invocation_identity=INV, now=NOW)
    assert result.decision == "TASK_TERMINAL"
    assert result.may_return is True


def test_repository_content_done_returns_after_lane_finalization_without_root_sync():
    result = classify_invocation_exit(
        _repository_content_done_record(),
        invocation_identity=INV,
        now=NOW,
        root_sync_receipt=None,
        lane_delivery_receipt=None,
    )
    assert result.decision == "TASK_TERMINAL"
    assert result.may_return is True


def test_repository_content_done_also_accepts_verified_optional_root_sync():
    result = classify_invocation_exit(
        _repository_content_done_record(),
        invocation_identity=INV,
        now=NOW,
        root_sync_receipt=_root_sync_receipt_for_done(),
        lane_delivery_receipt=None,
    )
    assert result.decision == "TASK_TERMINAL"
    assert result.may_return is True
