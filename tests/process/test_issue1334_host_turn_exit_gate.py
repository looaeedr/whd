import json
from dataclasses import replace

import pytest

from tools.execution_invocation_exit import (
    InvocationExitError,
    build_host_exit_proof,
    validate_host_exit_proof,
)
from tools.execution_record import (
    ActionSpec,
    TransactionState,
    execution_record_from_payload,
)
from tools.flow_v2_runtime_observation import (
    RuntimeObservationError,
    project_interactive_liveness,
)
from tools.interactive_runtime_liveness import (
    InteractiveRuntimeLivenessError,
    parse_interactive_runtime_end_comment,
)
from tools.runtime_report_identity import (
    RuntimeReportIdentityError,
    assert_runtime_report_event_allowed,
    build_runtime_report_identity,
)


ISSUE = 1334
INV = "chatgpt.issue1334.impl.work1"
OTHER = "codex.issue1334.other"
NOW = "2026-10-07T00:30:00+08:00"
UTC_NOW = "2026-10-06T16:30:00Z"


def _record(*, done=False, lease_invocation=INV):
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 2,
        "issue": ISSUE,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "NONE" if done else "SCHEDULER",
        "owner_id": "NONE" if done else "chatgpt.flowv2.work1",
        "lane_id": None if done else "chatgpt.flowv2.work1",
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "work/issue-1334",
        "head_sha": "a" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "a" * 40,
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
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {
            "merged_sha": "a" * 40 if done else None,
            "issue_closed": done,
            "released_at": "2026-10-06T16:29:00Z" if done else None,
        },
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-10-06T16:29:00Z",
    })


def _identity(record=None, invocation=INV):
    return build_runtime_report_identity(
        handler="工作1",
        owner=(record.owner_id if record is not None else "chatgpt.flowv2.work1"),
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
            "worker=chatgpt.flowv2.work1\n"
            f"invocation_identity={invocation}\n"
            "conversation_identity=chat.issue1334\n"
            f"claim_blob_sha={'b' * 40}\n"
            "branch=work/issue-1334\n"
            f"head_sha={'a' * 40}\n"
            "executor_source=chat\n"
            f"ended_at={UTC_NOW}\n"
            "reason=DONE\n"
            "host_exit_proof="
            + json.dumps(proof, separators=(",", ":"))
        ),
    }


def test_acquire_only_pending_start_branch_cannot_mint_host_exit_proof():
    record = replace(
        _record(),
        transaction=TransactionState(
            id="tx-acquire",
            kind="ACQUIRE",
            status="RECONCILED",
            expected_fingerprint="c" * 64,
            invocation_identity=INV,
        ),
    )
    with pytest.raises(
        InvocationExitError,
        match="HOST_EXIT_BLOCKED.*SCHEDULER_EXECUTION_NO_PROGRESS",
    ):
        build_host_exit_proof(
            record,
            invocation_identity=INV,
            now=UTC_NOW,
        )


def test_done_record_mints_and_validates_terminal_host_exit_proof():
    record = _record(done=True)
    proof = build_host_exit_proof(
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    )
    assert proof["decision"] == "TASK_TERMINAL"
    assert proof["may_return"] is True
    assert validate_host_exit_proof(
        proof,
        record=record,
        invocation_identity=INV,
        now=UTC_NOW,
    ) == proof
    assert assert_runtime_report_event_allowed(
        "TERMINAL",
        _identity(record),
        record=record,
        exit_proof=proof,
        now=UTC_NOW,
    )


def test_lane_busy_mints_exit_but_not_terminal_proof():
    record = _record(lease_invocation=OTHER)
    proof = build_host_exit_proof(
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    )
    assert proof["decision"] == "LANE_BUSY"
    assert assert_runtime_report_event_allowed(
        "EXIT",
        _identity(),
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
            _identity(),
            record=record,
            exit_proof=proof,
            now=UTC_NOW,
        )


def test_yielded_record_mints_host_exit_proof():
    base = _record()
    yielded = replace(
        base,
        lease=None,
        transaction=TransactionState(
            id="tx-yield",
            kind="YIELD",
            status="RECONCILED",
            expected_fingerprint="d" * 64,
            invocation_identity=INV,
        ),
    )
    proof = build_host_exit_proof(
        yielded,
        invocation_identity=INV,
        now=UTC_NOW,
    )
    assert proof["decision"] == "YIELDED"
    assert proof["may_return"] is True


def test_stale_host_exit_proof_fails_after_record_generation_changes():
    record = _record(done=True)
    proof = build_host_exit_proof(
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    )
    changed = replace(record, generation=record.generation + 1)
    with pytest.raises(InvocationExitError, match="generation mismatch"):
        validate_host_exit_proof(
            proof,
            record=changed,
            invocation_identity=INV,
            now=UTC_NOW,
        )


def test_progress_checkpoint_status_never_require_or_create_return_authority():
    identity = _identity()
    for event in ("PROGRESS", "CHECKPOINT", "STATUS"):
        assert assert_runtime_report_event_allowed(event, identity)


def test_exit_and_terminal_fail_closed_without_current_proof():
    record = _record(done=True)
    for event in ("EXIT", "TERMINAL"):
        with pytest.raises(RuntimeReportIdentityError, match="host-exit proof"):
            assert_runtime_report_event_allowed(
                event,
                _identity(record),
                record=record,
                exit_proof=None,
                now=UTC_NOW,
            )


def test_interactive_end_requires_structural_host_exit_proof():
    record = _record(done=True)
    proof = build_host_exit_proof(
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    )
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
    proof = build_host_exit_proof(
        record,
        invocation_identity=INV,
        now=UTC_NOW,
    )
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
        "schema": "WHD_FLOW_V2_HOST_EXIT_PROOF_V1",
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
            record=record,
            invocation_identity=INV,
            now=UTC_NOW,
        )
