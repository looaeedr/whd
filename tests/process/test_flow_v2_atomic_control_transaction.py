from dataclasses import replace

import pytest

from tools.control_transaction import (
    ControlTransactionConflict,
    ControlTransactionError,
    ControlTransactionReplay,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_record import RunState, TransactionState, execution_record_fingerprint, execution_record_from_payload


def _record_payload(**overrides):
    payload = {
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 3,
        "issue": 844,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER",
        "owner_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "governance/issue844-unified-execution-record-20260928",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "ACTIVE",
        "semantic_state": "IMPLEMENTING",
        "next_action": {"kind": "APPLY_COMMIT", "args": {}, "display": "apply candidate commit"},
        "lease": {
            "token": "lease-a",
            "invocation_identity": "scheduled:00:run-a",
            "expires_at": "2026-09-28T01:00:00Z",
        },
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": 842, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T00:30:00Z",
    }
    payload.update(overrides)
    return payload


def _record(**overrides):
    return execution_record_from_payload(_record_payload(**overrides))



def _yieldable_record():
    return replace(
        _record(),
        transaction=TransactionState(
            id="tx-substantive-before-yield",
            kind="RECONCILE",
            status="RECONCILED",
            expected_fingerprint="f" * 64,
            invocation_identity="scheduled:00:run-a",
        ),
    )


def test_prepare_transaction_binds_generation_fingerprint_and_exact_identity():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-844-apply-1")

    assert plan.issue == 844
    assert plan.kind == "APPLY_COMMIT"
    assert plan.expected_generation == 3
    assert plan.expected_fingerprint == execution_record_fingerprint(record)
    assert plan.expected_work_branch == record.work_branch
    assert plan.expected_head_sha == record.head_sha
    assert plan.expected_target_sha == record.target_sha


def test_apply_commit_is_one_atomic_transition_without_authorized_intermediate_state():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-844-apply-1")

    updated = execute_transaction(
        record,
        plan,
        effect={
            "head_sha": "d" * 40,
            "next_action": {"kind": "START_QA", "args": {}, "display": "start exact QA"},
            "semantic_state": "GREEN",
            "updated_at": "2026-09-28T00:31:00Z",
        },
    )

    assert updated.head_sha == "d" * 40
    assert updated.generation == 4
    assert updated.next_action.kind == "START_QA"
    assert updated.transaction.id == "tx-844-apply-1"
    assert updated.transaction.kind == "APPLY_COMMIT"
    assert updated.transaction.status == "RECONCILED"
    assert updated.transaction.expected_fingerprint == plan.expected_fingerprint


def test_stale_plan_fails_closed_when_record_changed_after_prepare():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-stale")
    changed = execution_record_from_payload(
        _record_payload(
            generation=4,
            head_sha="e" * 40,
            next_action={"kind": "START_QA", "args": {}, "display": "other writer advanced"},
        )
    )

    with pytest.raises(ControlTransactionConflict, match="fingerprint|generation|head"):
        execute_transaction(
            changed,
            plan,
            effect={
                "head_sha": "f" * 40,
                "next_action": {"kind": "START_QA", "args": {}, "display": "start QA"},
                "updated_at": "2026-09-28T00:32:00Z",
            },
        )


def test_replaying_consumed_plan_is_rejected_instead_of_reapplying_mutation():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-replay")
    updated = execute_transaction(
        record,
        plan,
        effect={
            "head_sha": "d" * 40,
            "next_action": {"kind": "START_QA", "args": {}, "display": "start QA"},
            "updated_at": "2026-09-28T00:31:00Z",
        },
    )

    with pytest.raises(ControlTransactionReplay, match="already applied"):
        execute_transaction(
            updated,
            plan,
            effect={
                "head_sha": "d" * 40,
                "next_action": {"kind": "START_QA", "args": {}, "display": "start QA"},
                "updated_at": "2026-09-28T00:31:00Z",
            },
        )


def test_start_qa_locks_exact_current_head_and_single_active_run():
    record = _record(next_action={"kind": "START_QA", "args": {}, "display": "start QA"})
    plan = prepare_transaction(record, kind="START_QA", transaction_id="tx-qa")
    updated = execute_transaction(
        record,
        plan,
        effect={
            "run_id": 36370000001,
            "run_head_sha": "b" * 40,
            "purpose": "FLOW_V2_FOCUSED_QA",
            "run_status": "in_progress",
            "next_action": {"kind": "POLL_RUN", "args": {"run_id": 36370000001}, "display": "poll exact run"},
            "updated_at": "2026-09-28T00:33:00Z",
        },
    )

    assert updated.state == "VERIFYING"
    assert updated.active_run.id == 36370000001
    assert updated.active_run.head_sha == updated.head_sha

    second_plan = prepare_transaction(updated, kind="START_QA", transaction_id="tx-qa-2")
    with pytest.raises(ControlTransactionError, match="active_run"):
        execute_transaction(
            updated,
            second_plan,
            effect={
                "run_id": 36370000002,
                "run_head_sha": "b" * 40,
                "purpose": "DUPLICATE",
                "run_status": "queued",
                "next_action": {"kind": "POLL_RUN", "args": {}, "display": "poll"},
                "updated_at": "2026-09-28T00:34:00Z",
            },
        )


def test_integrating_head_advance_can_reenter_exact_qa_before_merge():
    accepted = _record(
        state="INTEGRATING",
        semantic_state="GREEN",
        next_action={"kind": "MERGE", "args": {}, "display": "merge accepted head"},
        qa={"last_accepted_run": 36370000001, "accepted_head_sha": "b" * 40},
    )

    apply_plan = prepare_transaction(
        accepted,
        kind="APPLY_COMMIT",
        transaction_id="tx-integrating-advance",
    )
    advanced = execute_transaction(
        accepted,
        apply_plan,
        effect={
            "head_sha": "d" * 40,
            "next_action": {
                "kind": "START_QA",
                "args": {},
                "display": "revalidate exact advanced head",
            },
            "semantic_state": "QA_INVALIDATED_BY_HEAD_ADVANCE",
            "updated_at": "2026-09-28T00:32:00Z",
        },
    )
    assert advanced.state == "INTEGRATING"
    assert advanced.head_sha == "d" * 40
    assert advanced.qa.accepted_head_sha == "b" * 40

    start_plan = prepare_transaction(
        advanced,
        kind="START_QA",
        transaction_id="tx-integrating-qa",
    )
    running = execute_transaction(
        advanced,
        start_plan,
        effect={
            "run_id": 36370000002,
            "run_head_sha": "d" * 40,
            "purpose": "FLOW_V2_REVALIDATE_ADVANCED_INTEGRATING_HEAD",
            "run_status": "completed",
            "next_action": {
                "kind": "POLL_QA",
                "args": {"run_id": 36370000002},
                "display": "poll revalidation run",
            },
            "updated_at": "2026-09-28T00:33:00Z",
        },
    )
    assert running.state == "VERIFYING"
    assert running.active_run.head_sha == "d" * 40

    accept_plan = prepare_transaction(
        running,
        kind="ACCEPT_QA",
        transaction_id="tx-integrating-accept",
    )
    reaccepted = execute_transaction(
        running,
        accept_plan,
        effect={
            "run_id": 36370000002,
            "run_head_sha": "d" * 40,
            "conclusion": "success",
            "next_state": "INTEGRATING",
            "next_action": {
                "kind": "MERGE",
                "args": {},
                "display": "merge revalidated head",
            },
            "updated_at": "2026-09-28T00:34:00Z",
        },
    )
    assert reaccepted.state == "INTEGRATING"
    assert reaccepted.qa.accepted_head_sha == "d" * 40
    assert reaccepted.qa.last_accepted_run == 36370000002

    merge_plan = prepare_transaction(
        reaccepted,
        kind="MERGE",
        transaction_id="tx-integrating-merge",
    )
    merged = execute_transaction(
        reaccepted,
        merge_plan,
        effect={
            "merged_sha": "e" * 40,
            "target_sha": "e" * 40,
            "next_action": {
                "kind": "FINALIZE",
                "args": {},
                "display": "finalize",
            },
            "updated_at": "2026-09-28T00:35:00Z",
        },
    )
    assert merged.closure.merged_sha == "e" * 40
    assert merged.target_sha == "e" * 40


def test_accept_qa_requires_exact_active_run_and_promotes_accepted_head():
    base = _record(next_action={"kind": "START_QA", "args": {}, "display": "start QA"})
    start = prepare_transaction(base, kind="START_QA", transaction_id="tx-qa")
    running = execute_transaction(
        base,
        start,
        effect={
            "run_id": 36370000001,
            "run_head_sha": "b" * 40,
            "purpose": "FLOW_V2_FOCUSED_QA",
            "run_status": "completed",
            "next_action": {"kind": "POLL_RUN", "args": {"run_id": 36370000001}, "display": "poll exact run"},
            "updated_at": "2026-09-28T00:33:00Z",
        },
    )
    accept = prepare_transaction(running, kind="ACCEPT_QA", transaction_id="tx-accept")
    accepted = execute_transaction(
        running,
        accept,
        effect={
            "run_id": 36370000001,
            "run_head_sha": "b" * 40,
            "conclusion": "success",
            "next_state": "INTEGRATING",
            "next_action": {"kind": "MERGE", "args": {}, "display": "merge accepted head"},
            "updated_at": "2026-09-28T00:35:00Z",
        },
    )

    assert accepted.active_run is None
    assert accepted.qa.last_accepted_run == 36370000001
    assert accepted.qa.accepted_head_sha == "b" * 40
    assert accepted.state == "INTEGRATING"
    assert accepted.next_action.kind == "MERGE"


def test_yield_clears_only_runtime_lease_and_preserves_nonterminal_task():
    record = _yieldable_record()
    plan = prepare_transaction(
        record, kind="YIELD", transaction_id="tx-yield",
        invocation_identity="scheduled:00:run-a",
    )
    yielded = execute_transaction(
        record,
        plan,
        effect={"updated_at": "2026-09-28T00:36:00Z"},
    )

    assert yielded.state == "ACTIVE"
    assert yielded.lease is None
    assert yielded.owner_id == record.owner_id
    assert yielded.slot_id == "worker.slot.1"
    assert yielded.next_action.kind == "APPLY_COMMIT"


def test_handoff_changes_owner_atomically_but_keeps_work_identity():
    record = _record()
    plan = prepare_transaction(record, kind="HANDOFF", transaction_id="tx-handoff")
    handed = execute_transaction(
        record,
        plan,
        effect={
            "owner_kind": "INTERACTIVE",
            "owner_id": "chatgpt.flowv2.1",
            "lane_id": None,
            "slot_id": "worker.slot.1",
            "lease": None,
            "updated_at": "2026-09-28T00:37:00Z",
        },
    )

    assert handed.owner_kind == "INTERACTIVE"
    assert handed.owner_id == "chatgpt.flowv2.1"
    assert handed.lane_id is None
    assert handed.slot_id == "worker.slot.1"
    assert handed.work_branch == record.work_branch
    assert handed.head_sha == record.head_sha
    assert handed.next_action == record.next_action


def test_merge_then_finalize_reaches_done_without_half_terminal_state():
    record = _record(
        state="INTEGRATING",
        next_action={"kind": "MERGE", "args": {}, "display": "merge accepted head"},
        qa={"last_accepted_run": 36370000001, "accepted_head_sha": "b" * 40},
    )
    merge_plan = prepare_transaction(record, kind="MERGE", transaction_id="tx-merge")
    merged = execute_transaction(
        record,
        merge_plan,
        effect={
            "merged_sha": "e" * 40,
            "target_sha": "e" * 40,
            "next_action": {"kind": "FINALIZE", "args": {}, "display": "close and release"},
            "updated_at": "2026-09-28T00:38:00Z",
        },
    )

    assert merged.state == "INTEGRATING"
    assert merged.closure.merged_sha == "e" * 40
    assert merged.target_sha == "e" * 40
    assert merged.next_action.kind == "FINALIZE"

    finalize_plan = prepare_transaction(merged, kind="FINALIZE", transaction_id="tx-final")
    done = execute_transaction(
        merged,
        finalize_plan,
        effect={
            "issue_closed": True,
            "released_at": "2026-09-28T00:39:00Z",
            "updated_at": "2026-09-28T00:39:00Z",
        },
    )

    assert done.state == "DONE"
    assert done.next_action is None
    assert done.lease is None
    assert done.closure.issue_closed is True
    assert done.closure.released_at == "2026-09-28T00:39:00Z"


def test_merge_requires_qa_acceptance_for_current_head():
    record = _record(
        state="INTEGRATING",
        next_action={"kind": "MERGE", "args": {}, "display": "merge"},
        qa={"last_accepted_run": 36370000001, "accepted_head_sha": "9" * 40},
    )
    plan = prepare_transaction(record, kind="MERGE", transaction_id="tx-bad-merge")

    with pytest.raises(ControlTransactionError, match="accepted_head"):
        execute_transaction(
            record,
            plan,
            effect={
                "merged_sha": "e" * 40,
                "target_sha": "e" * 40,
                "next_action": {"kind": "FINALIZE", "args": {}, "display": "finalize"},
                "updated_at": "2026-09-28T00:38:00Z",
            },
        )


def test_handoff_changes_only_owner_routing_and_preserves_slot_and_exact_next_action():
    record = _record()
    plan = prepare_transaction(record, kind="HANDOFF", transaction_id="tx-handoff-preserve")

    updated = execute_transaction(
        record,
        plan,
        effect={
            "owner_kind": "SCHEDULER",
            "owner_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
            "lane_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
            "updated_at": "2026-09-28T02:25:00Z",
        },
    )

    assert updated.owner_id == "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
    assert updated.lane_id == "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
    assert updated.slot_id == record.slot_id
    assert updated.work_branch == record.work_branch
    assert updated.head_sha == record.head_sha
    assert updated.target_sha == record.target_sha
    assert updated.next_action == record.next_action
    assert updated.lease is None


def test_handoff_rejects_slot_rebind():
    record = _record()
    plan = prepare_transaction(record, kind="HANDOFF", transaction_id="tx-handoff-slot-drift")

    with pytest.raises(ControlTransactionError, match="slot_id"):
        execute_transaction(
            record,
            plan,
            effect={
                "owner_kind": "SCHEDULER",
                "owner_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "lane_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "slot_id": "worker.slot.2",
                "updated_at": "2026-09-28T02:25:00Z",
            },
        )


def test_handoff_rejects_next_action_rewrite():
    record = _record()
    plan = prepare_transaction(record, kind="HANDOFF", transaction_id="tx-handoff-action-drift")

    with pytest.raises(ControlTransactionError, match="next_action"):
        execute_transaction(
            record,
            plan,
            effect={
                "owner_kind": "SCHEDULER",
                "owner_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "lane_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "next_action": {"kind": "MERGE", "args": {}, "display": "rewrite scope"},
                "updated_at": "2026-09-28T02:25:00Z",
            },
        )


def test_transaction_records_exact_invocation_identity_when_supplied():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="APPLY_COMMIT",
        transaction_id="tx-invocation-bound",
        invocation_identity="scheduled:00:run-a",
    )
    updated = execute_transaction(
        record,
        plan,
        effect={
            "head_sha": "d" * 40,
            "next_action": {"kind": "START_QA", "args": {}, "display": "start qa"},
            "updated_at": "2026-09-28T00:40:00Z",
        },
    )

    assert updated.transaction.invocation_identity == "scheduled:00:run-a"


def test_expired_lease_can_be_reacquired_only_by_same_owner_lane():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-reacquire",
        invocation_identity="scheduled:20:run-b",
    )
    updated = execute_transaction(
        record,
        plan,
        effect={
            "observed_at": "2026-09-28T01:00:00Z",
            "owner_kind": record.owner_kind,
            "owner_id": record.owner_id,
            "lane_id": record.lane_id,
            "slot_id": record.slot_id,
            "lease": {
                "token": "lease-b",
                "invocation_identity": "scheduled:20:run-b",
                "expires_at": "2026-09-28T01:05:00Z",
            },
            "next_action": {
                "kind": record.next_action.kind,
                "args": record.next_action.args,
                "display": record.next_action.display,
            },
            "semantic_state": record.semantic_state,
            "updated_at": "2026-09-28T01:00:00Z",
        },
    )

    assert updated.owner_id == record.owner_id
    assert updated.lane_id == record.lane_id
    assert updated.lease.invocation_identity == "scheduled:20:run-b"
    assert updated.transaction.invocation_identity == "scheduled:20:run-b"


def test_live_lease_cannot_be_replaced_by_new_invocation():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-live-conflict",
        invocation_identity="scheduled:20:run-b",
    )

    with pytest.raises(ControlTransactionError, match="live lease"):
        execute_transaction(
            record,
            plan,
            effect={
                "observed_at": "2026-09-28T00:59:59Z",
                "owner_kind": record.owner_kind,
                "owner_id": record.owner_id,
                "lane_id": record.lane_id,
                "slot_id": record.slot_id,
                "lease": {
                    "token": "lease-b",
                    "invocation_identity": "scheduled:20:run-b",
                    "expires_at": "2026-09-28T01:05:00Z",
                },
                "next_action": {
                    "kind": record.next_action.kind,
                    "args": record.next_action.args,
                    "display": record.next_action.display,
                },
                "updated_at": "2026-09-28T00:59:59Z",
            },
        )


def test_expired_lease_reacquire_cannot_change_owner_or_lane():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-owner-steal",
        invocation_identity="scheduled:B15:foreign",
    )

    with pytest.raises(ControlTransactionError, match="same owner/lane"):
        execute_transaction(
            record,
            plan,
            effect={
                "observed_at": "2026-09-28T01:00:00Z",
                "owner_kind": "SCHEDULER",
                "owner_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "lane_id": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
                "slot_id": record.slot_id,
                "lease": {
                    "token": "lease-b",
                    "invocation_identity": "scheduled:B15:foreign",
                    "expires_at": "2026-09-28T01:05:00Z",
                },
                "next_action": {
                    "kind": record.next_action.kind,
                    "args": record.next_action.args,
                    "display": record.next_action.display,
                },
                "updated_at": "2026-09-28T01:00:00Z",
            },
        )


def test_yield_requires_exact_lease_invocation_and_preserves_continuation():
    record = _yieldable_record()
    plan = prepare_transaction(
        record,
        kind="YIELD",
        transaction_id="tx-yield-exact",
        invocation_identity="scheduled:00:run-a",
    )
    yielded = execute_transaction(
        record,
        plan,
        effect={"updated_at": "2026-09-28T00:45:00Z"},
    )

    assert yielded.lease is None
    assert yielded.owner_id == record.owner_id
    assert yielded.slot_id == record.slot_id
    assert yielded.work_branch == record.work_branch
    assert yielded.head_sha == record.head_sha
    assert yielded.next_action == record.next_action
    assert yielded.transaction.invocation_identity == "scheduled:00:run-a"


def test_yield_rejects_immediate_post_acquire_without_substantive_progress():
    record = replace(
        _record(),
        transaction=TransactionState(
            id="tx-acquire-only",
            kind="ACQUIRE",
            status="RECONCILED",
            expected_fingerprint="a" * 64,
            invocation_identity="scheduled:00:run-a",
        ),
    )
    plan = prepare_transaction(
        record,
        kind="YIELD",
        transaction_id="tx-yield-after-acquire",
        invocation_identity="scheduled:00:run-a",
    )
    with pytest.raises(ControlTransactionError, match="CONTINUE_EXECUTION"):
        execute_transaction(
            record,
            plan,
            effect={"updated_at": "2026-09-28T00:45:00Z"},
        )


def test_yield_rejects_foreign_invocation_and_next_action_rewrite():
    record = _record()
    foreign_plan = prepare_transaction(
        record,
        kind="YIELD",
        transaction_id="tx-yield-foreign",
        invocation_identity="scheduled:20:other",
    )
    with pytest.raises(ControlTransactionError, match="lease invocation"):
        execute_transaction(
            record,
            foreign_plan,
            effect={"updated_at": "2026-09-28T00:45:00Z"},
        )

    own_plan = prepare_transaction(
        record,
        kind="YIELD",
        transaction_id="tx-yield-rewrite",
        invocation_identity="scheduled:00:run-a",
    )
    with pytest.raises(ControlTransactionError, match="next_action"):
        execute_transaction(
            record,
            own_plan,
            effect={
                "next_action": {"kind": "MERGE", "args": {}, "display": "scope drift"},
                "updated_at": "2026-09-28T00:45:00Z",
            },
        )


def test_reconcile_updates_live_identity_and_next_action_without_changing_owner_or_slot():
    record = _record()
    plan = prepare_transaction(record, kind="RECONCILE", transaction_id="tx-reconcile")
    next_action = {
        "kind": "START_QA",
        "args": {"workflow": "qa-flow-v2"},
        "display": "run exact QA",
    }
    updated = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-28T02:00:00Z",
            "observed_work_branch": record.work_branch,
            "observed_head_sha": "d" * 40,
            "observed_target_sha": "e" * 40,
            "semantic_state": "RECONCILED",
            "next_action": next_action,
        },
    )
    assert updated.head_sha == "d" * 40
    assert updated.target_sha == "e" * 40
    assert updated.owner_id == record.owner_id
    assert updated.lane_id == record.lane_id
    assert updated.slot_id == record.slot_id
    assert updated.next_action.kind == "START_QA"
    assert updated.transaction.kind == "RECONCILE"
    assert updated.transaction.status == "RECONCILED"


def test_reconcile_rejects_owner_or_slot_rewrite():
    record = _record()
    plan = prepare_transaction(record, kind="RECONCILE", transaction_id="tx-reconcile")
    base = {
        "updated_at": "2026-09-28T02:00:00Z",
        "observed_work_branch": record.work_branch,
        "observed_head_sha": record.head_sha,
        "observed_target_sha": record.target_sha,
        "next_action": {"kind": "START_QA", "args": {"workflow": "qa"}, "display": "qa"},
    }
    with pytest.raises(ControlTransactionError, match="owner_id"):
        execute_transaction(record, plan, effect={**base, "owner_id": "scheduler.foreign"})
    with pytest.raises(ControlTransactionError, match="slot_id"):
        execute_transaction(record, plan, effect={**base, "slot_id": "worker.slot.3"})


def test_reconcile_rejects_head_move_with_active_run():
    record = replace(
        _record(),
        state="VERIFYING",
        active_run=RunState(id=123, head_sha="b" * 40, purpose="qa", status="in_progress"),
    )
    plan = prepare_transaction(record, kind="RECONCILE", transaction_id="tx-reconcile")
    with pytest.raises(ControlTransactionError, match="active_run"):
        execute_transaction(
            record,
            plan,
            effect={
                "updated_at": "2026-09-28T02:00:00Z",
                "observed_work_branch": record.work_branch,
                "observed_head_sha": "d" * 40,
                "observed_target_sha": record.target_sha,
                "next_action": {"kind": "POLL_QA", "args": {"run_id": 123, "head_sha": record.head_sha}, "display": "poll"},
            },
        )


def test_block_records_only_allowed_external_blocker_and_wait_action():
    record = _record()
    plan = prepare_transaction(record, kind="BLOCK", transaction_id="tx-block", invocation_identity="scheduled:00:run-a")
    blocked = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-28T02:10:00Z",
            "blocker_kind": "EXTERNAL_DEPENDENCY",
            "blocker_evidence": "provider ticket still pending",
            "recheck_after": "2026-09-28T02:30:00Z",
            "next_action": {
                "kind": "WAIT_EXTERNAL",
                "args": {"blocker_kind": "EXTERNAL_DEPENDENCY"},
                "display": "recheck provider ticket",
            },
        },
    )
    assert blocked.state == "BLOCKED"
    assert blocked.blocker.kind == "EXTERNAL_DEPENDENCY"
    assert blocked.next_action.kind == "WAIT_EXTERNAL"
    assert blocked.transaction.kind == "BLOCK"


def test_block_rejects_internal_or_mismatched_wait_action():
    record = _record()
    plan = prepare_transaction(record, kind="BLOCK", transaction_id="tx-block")
    base = {
        "updated_at": "2026-09-28T02:10:00Z",
        "blocker_kind": "EXTERNAL_DEPENDENCY",
        "blocker_evidence": "provider pending",
    }
    with pytest.raises((ControlTransactionError, ValueError), match="blocker"):
        execute_transaction(
            record, plan, effect={**base, "blocker_kind": "INTERNAL_RETRY", "next_action": {"kind": "WAIT_EXTERNAL", "args": {"blocker_kind": "INTERNAL_RETRY"}, "display": "wait"}}
        )
    with pytest.raises(ControlTransactionError, match="must match blocker"):
        execute_transaction(
            record, plan, effect={**base, "next_action": {"kind": "WAIT_EXTERNAL", "args": {"blocker_kind": "PLATFORM_FAILURE"}, "display": "wait"}}
        )


def test_reconcile_can_clear_blocker_only_with_explicit_blocked_to_active_transition():
    record = _record_payload(
        state="BLOCKED",
        semantic_state="BLOCKED",
        blocker={"kind": "EXTERNAL_DEPENDENCY", "evidence": "provider pending", "recheck_after": None},
        next_action={"kind": "WAIT_EXTERNAL", "args": {"blocker_kind": "EXTERNAL_DEPENDENCY"}, "display": "wait"},
    )
    blocked = execution_record_from_payload(record)
    plan = prepare_transaction(blocked, kind="RECONCILE", transaction_id="tx-unblock")
    active = execute_transaction(
        blocked,
        plan,
        effect={
            "updated_at": "2026-09-28T02:31:00Z",
            "observed_work_branch": blocked.work_branch,
            "observed_head_sha": blocked.head_sha,
            "observed_target_sha": blocked.target_sha,
            "state": "ACTIVE",
            "semantic_state": "IMPLEMENTING",
            "clear_blocker": True,
            "next_action": {"kind": "APPLY_COMMIT", "args": {"candidate_commit_sha": "d" * 40}, "display": "continue"},
        },
    )
    assert active.state == "ACTIVE"
    assert active.blocker is None
    assert active.next_action.kind == "APPLY_COMMIT"
