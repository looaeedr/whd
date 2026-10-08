from dataclasses import replace

import pytest

from tools.control_transaction import (
    ControlTransactionError,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_invocation_exit import classify_invocation_exit
from tools.execution_record import (
    TransactionState,
    execution_record_from_payload,
)
from tools.host_return_surface_gate import classify_dispatch_completion


INV = "chatgpt.flowv2.work2.issue1403"
HEAD = "a" * 40


def _record():
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 5,
            "issue": 1385,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work2",
            "lane_id": "chatgpt.flowv2.work2",
            "slot_id": "worker.slot.2",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": HEAD,
            "work_branch": "work/issue-1385",
            "head_sha": HEAD,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": HEAD,
            "state": "ACTIVE",
            "semantic_state": "CLAIMED",
            "next_action": {
                "kind": "START_BRANCH",
                "args": {},
                "display": "start #1385",
            },
            "lease": {
                "token": "lease:1385:test:1",
                "invocation_identity": INV,
                "expires_at": "2026-10-08T02:00:00Z",
            },
            "active_run": None,
            "transaction": {
                "id": "tx-acquire",
                "kind": "ACQUIRE",
                "status": "RECONCILED",
                "expected_fingerprint": "b" * 64,
                "invocation_identity": INV,
            },
            "qa": {"last_accepted_run": None, "accepted_head_sha": None},
            "blocker": None,
            "closure": {
                "merged_sha": None,
                "issue_closed": False,
                "released_at": None,
            },
            "chain": {
                "parent_issue": 1374,
                "next_issue": None,
                "next_action": None,
            },
            "recovery_history": [],
            "updated_at": "2026-10-08T01:00:00Z",
        }
    )


def _handoff(record, *, owner_kind, owner_id, lane_id):
    plan = prepare_transaction(
        record,
        kind="HANDOFF",
        transaction_id="tx-handoff",
        invocation_identity=INV,
    )
    return execute_transaction(
        record,
        plan,
        effect={
            "owner_kind": owner_kind,
            "owner_id": owner_id,
            "lane_id": lane_id,
            "lease": None,
            "updated_at": "2026-10-08T01:01:00Z",
        },
    )


def test_execute_ticket_cannot_handoff_to_nobody():
    with pytest.raises(ControlTransactionError, match="named target owner"):
        _handoff(
            _record(),
            owner_kind="NONE",
            owner_id="NONE",
            lane_id=None,
        )


def test_execute_ticket_cannot_use_handoff_as_self_transition():
    with pytest.raises(ControlTransactionError, match="different target routing identity"):
        _handoff(
            _record(),
            owner_kind="SCHEDULER",
            owner_id="chatgpt.flowv2.work2",
            lane_id="chatgpt.flowv2.work2",
        )


def test_execute_ticket_can_handoff_to_named_different_owner():
    updated = _handoff(
        _record(),
        owner_kind="REMOTE_RUNTIME",
        owner_id="codex.workspace.dm8",
        lane_id=None,
    )
    assert updated.owner_kind == "REMOTE_RUNTIME"
    assert updated.owner_id == "codex.workspace.dm8"
    assert updated.slot_id == "worker.slot.2"
    assert updated.next_action.kind == "START_BRANCH"
    assert updated.lease is None


def test_null_owner_handoff_is_not_dispatch_completion_or_host_exit():
    record = replace(
        _record(),
        lease=None,
        owner_kind="NONE",
        owner_id="NONE",
        lane_id=None,
        transaction=TransactionState(
            id="tx-old-null-handoff",
            kind="HANDOFF",
            status="RECONCILED",
            expected_fingerprint="c" * 64,
            invocation_identity=INV,
        ),
    )
    dispatch = classify_dispatch_completion(record, invocation_identity=INV)
    assert dispatch.status == "DISPATCH_INCOMPLETE"
    assert dispatch.may_claim_complete is False

    exit_decision = classify_invocation_exit(
        record,
        invocation_identity=INV,
        now="2026-10-08T01:02:00Z",
        host_boundary=True,
    )
    assert exit_decision.decision == "ACQUIRE_REQUIRED"
    assert exit_decision.may_return is False


def test_named_owner_handoff_can_complete_dispatch_and_return():
    record = replace(
        _record(),
        lease=None,
        owner_kind="REMOTE_RUNTIME",
        owner_id="codex.workspace.dm8",
        lane_id=None,
        transaction=TransactionState(
            id="tx-named-handoff",
            kind="HANDOFF",
            status="RECONCILED",
            expected_fingerprint="d" * 64,
            invocation_identity=INV,
        ),
    )
    dispatch = classify_dispatch_completion(record, invocation_identity=INV)
    assert dispatch.status == "DISPATCH_COMPLETE_HANDOFF"
    assert dispatch.may_claim_complete is True

    exit_decision = classify_invocation_exit(
        record,
        invocation_identity=INV,
        now="2026-10-08T01:02:00Z",
        host_boundary=True,
    )
    assert exit_decision.decision == "HANDOFF_COMPLETE"
    assert exit_decision.may_return is True
