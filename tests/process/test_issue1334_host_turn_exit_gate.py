import json
from dataclasses import replace

import pytest

from tools.execution_invocation_exit import (
    HOST_EXIT_PROOF_SCHEMA,
    InvocationExitError,
    build_host_exit_proof,
    validate_host_exit_proof,
)
from tools.execution_record import TransactionState, execution_record_from_payload
from tools.flow_v2_runtime_observation import RuntimeObservationError, project_interactive_liveness
from tools.interactive_runtime_liveness import (
    InteractiveRuntimeLivenessError,
    parse_interactive_runtime_end_comment,
)
from tools.runtime_report_identity import (
    RuntimeReportIdentityError,
    assert_runtime_report_event_allowed,
    build_runtime_report_identity,
    format_runtime_report_prefix,
)


ISSUE = 1334
INV = "chatgpt.issue1334.impl.work1"
OTHER = "codex.issue1334.other"
UTC_NOW = "2026-10-06T16:30:00Z"
LATER = "2026-10-06T16:31:01Z"
HEAD = "a" * 40
LANE = "chatgpt.flowv2.work1"


def _record(*, done=False, lease_invocation=INV):
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 2,
        "issue": ISSUE,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "NONE" if done else "SCHEDULER",
        "owner_id": "NONE" if done else LANE,
        "lane_id": None if done else LANE,
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": HEAD,
        "work_branch": "work/issue-1334",
        "head_sha": HEAD,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": HEAD,
        "state": "DONE" if done else "ACTIVE",
        "semantic_state": "TERMINAL_SUCCESS" if done else "CLAIMED",
        "next_action": None if done else {
            "kind": "START_BRANCH",
            "args": {},
            "display": "implement exact tested diff",
        },
        "lease": None if done else {
            "token": "lease-1334",
            "invocation_identity": lease_invocation,
            "expires_at": "2026-10-06T16:40:00Z",
        },
        "active_run": None,
        "transaction": (
            {
                "id": "tx-finalize",
                "kind": "FINALIZE",
                "status": "RECONCILED",
                "expected_fingerprint": "b" * 64,
                "invocation_identity": INV,
            }
            if done
            else {
                "id": "tx-acquire",
                "kind": "ACQUIRE",
                "status": "RECONCILED",
                "expected_fingerprint": "c" * 64,
                "invocation_identity": INV,
            }
        ),
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {
            "merged_sha": HEAD if done else None,
            "issue_closed": done,
            "released_at": "2026-10-06T16:29:00Z" if done else None,
        },
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-10-06T16:29:00Z",
    })


def _identity(record, *, invocation=INV):
    return build_runtime_report_identity(
        handler="工作1",
        owner=record.owner_id,
        issue=ISSUE,
        slot="worker.slot.1",
        invocation_identity=invocation,
        runtime_kind="INTERACTIVE",
    )


def _end_comment(proof, *, invocation=INV):
    return {
        "id": 1334001,
        "created_at": UTC_NOW,
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_INTERACTIVE_RUNTIME_END_V1\n"
            f"issue={ISSUE}\n"
            "slot_id=worker.slot.1\n"
            f"worker={LANE}\n"
            f"invocation_identity={invocation}\n"
            "conversation_identity=chat.issue1334\n"
            f"claim_blob_sha={'b' * 40}\n"
            "branch=work/issue-1334\n"
            f"head_sha={HEAD}\n"
            "executor_source=chat\n"
            f"ended_at={UTC_NOW}\n"
            "reason=DONE\n"
            "host_exit_proof="
            + json.dumps(proof, separators=(",", ":"))
        ),
    }


def test_acquire_only_pending_start_branch_cannot_mint_host_exit_proof():
    record = _record()
    with pytest.raises(
        InvocationExitError,
        match="HOST_EXIT_BLOCKED.*SCHEDULER_EXECUTION_NO_PROGRESS",
    ):
        build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)


def test_progress_checkpoint_status_are_visible_but_never_return_authority():
    record = _record()
    identity = _identity(record)
    for event in ("PROGRESS", "CHECKPOINT", "STATUS"):
        assert assert_runtime_report_event_allowed(event, identity)
        prefix = format_runtime_report_prefix(identity, event=event)
        assert "處理者：工作1" in prefix

    with pytest.raises(RuntimeReportIdentityError, match="EXIT host-exit proof rejected"):
        format_runtime_report_prefix(
            identity,
            event="EXIT",
            execution_record=record,
            now=UTC_NOW,
        )


def test_done_record_mints_bound_proof_and_allows_terminal_report():
    record = _record(done=True)
    proof = build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)
    assert proof["schema"] == HOST_EXIT_PROOF_SCHEMA
    assert proof["decision"] == "TASK_TERMINAL"
    assert validate_host_exit_proof(
        proof,
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    ) == proof

    prefix = format_runtime_report_prefix(
        _identity(record),
        event="TERMINAL",
        execution_record=record,
        host_exit_proof=proof,
        now=UTC_NOW,
    )
    assert "owner=NONE" in prefix


def test_lane_busy_allows_exit_but_cannot_claim_terminal():
    record = _record(lease_invocation=OTHER)
    proof = build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)
    assert proof["decision"] == "LANE_BUSY"
    assert assert_runtime_report_event_allowed(
        "EXIT",
        _identity(record),
        record=record,
        exit_proof=proof,
        now=UTC_NOW,
    )
    with pytest.raises(
        RuntimeReportIdentityError,
        match="TERMINAL report requires TASK_TERMINAL",
    ):
        assert_runtime_report_event_allowed(
            "TERMINAL",
            _identity(record),
            record=record,
            exit_proof=proof,
            now=UTC_NOW,
        )


def test_stale_or_expired_proof_fails_closed():
    record = _record(done=True)
    proof = build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)
    stale = replace(record, generation=record.generation + 1)
    with pytest.raises(InvocationExitError, match="generation mismatch"):
        validate_host_exit_proof(
            proof,
            stale,
            invocation_identity=INV,
            now=UTC_NOW,
        )
    with pytest.raises(InvocationExitError, match="expired"):
        validate_host_exit_proof(
            proof,
            record,
            invocation_identity=INV,
            now=LATER,
        )


def test_interactive_end_requires_structural_host_exit_proof():
    record = _record(done=True)
    proof = build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)
    parsed = parse_interactive_runtime_end_comment(_end_comment(proof))
    assert parsed["host_exit_proof"]["decision"] == "TASK_TERMINAL"

    comment = _end_comment(proof)
    comment["body"] = comment["body"].rsplit("\nhost_exit_proof=", 1)[0]
    with pytest.raises(
        InteractiveRuntimeLivenessError,
        match="missing required keys",
    ):
        parse_interactive_runtime_end_comment(comment)


def test_interactive_end_projection_revalidates_proof_against_current_record():
    record = _record(done=True)
    proof = build_host_exit_proof(record, invocation_identity=INV, now=UTC_NOW)
    parsed = parse_interactive_runtime_end_comment(_end_comment(proof))
    parsed["runtime_status"] = "ENDED"
    observation = project_interactive_liveness(parsed, record=record)
    assert observation["event"] == "EXIT"
    assert observation["liveness_state"] == "ENDED"

    stale = replace(record, generation=record.generation + 1)
    with pytest.raises(RuntimeObservationError, match="host-exit proof rejected"):
        project_interactive_liveness(parsed, record=stale)


def test_fabricated_may_return_true_cannot_override_current_classifier():
    record = _record()
    fake = {
        "schema": HOST_EXIT_PROOF_SCHEMA,
        "version": 1,
        "issue": ISSUE,
        "generation": record.generation,
        "record_fingerprint": "f" * 64,
        "invocation_identity": INV,
        "decision": "TASK_TERMINAL",
        "may_return": True,
        "requires_yield": False,
        "next_action_kind": None,
        "active_run_id": None,
        "classified_at": UTC_NOW,
    }
    with pytest.raises(InvocationExitError):
        validate_host_exit_proof(
            fake,
            record,
            invocation_identity=INV,
            now=UTC_NOW,
        )
