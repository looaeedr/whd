from __future__ import annotations

from pathlib import Path

import pytest

import tools.continuity_controller as continuity


BRANCH = "work/issue691-turn-exit-scheduler-end-20260926"
HEAD = "6" * 40
FINGERPRINT = "f" * 64


def _checkpoint() -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue="691",
        branch=BRANCH,
        head_sha=HEAD,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=continuity.ClosureState.CLOSED,
    )


def _claim() -> dict[str, object]:
    return {
        "phase": "RELEASED",
        "authority_progress": {
            "state": "SUBSTANTIVE_ACTION_COMPLETED",
            "acquired_via": "claim-takeover",
            "first_substantive_action": "focused-red",
        },
    }


def _turn_exit_receipt() -> dict[str, object]:
    return {
        "schema": "WHD_REMOTE_TURN_EXIT_RESULT_V1",
        "request_comment_id": 101,
        "issue": 691,
        "worker": "scheduler.example",
        "invocation_identity": "invocation-abc",
        "claim_blob_sha": "a" * 40,
        "checkpoint_blob_sha": "b" * 40,
        "checkpoint_fingerprint": FINGERPRINT,
        "branch": BRANCH,
        "head_sha": HEAD,
        "closure_state": "CLOSED",
        "pending_guard_state": "CONSUMED",
        "durable_mutation_state": "CONSUMED",
        "delegated_work_state": "NONE",
        "active_remote_run": False,
        "result": "TURN_EXIT_PERMITTED",
        "reason": "TURN_EXIT_PERMITTED",
        "scheduler_end_allowed": True,
        "required_end_marker": "WHD_SCHEDULER_RUNTIME_END_V1",
        "issued_at": "2026-09-26T14:00:00Z",
        "run_id": 303,
    }


def _scheduler_end() -> dict[str, object]:
    return {
        "schema": "WHD_SCHEDULER_RUNTIME_END_V1",
        "issue": 691,
        "scheduler_lane": "scheduler.example",
        "invocation_identity": "invocation-abc",
        "request_comment_id": 101,
        "result_comment_id": 202,
        "checkpoint_fingerprint": FINGERPRINT,
        "turn_exit_run_id": 303,
    }


def test_red_stop_08_local_gate_uses_same_live_durable_invariants_as_remote() -> None:
    local_gate = getattr(
        continuity,
        "evaluate_local_turn_exit_from_durable_state",
        None,
    )
    assert callable(local_gate), (
        "RED-STOP-08: local/interactive live durable turn-exit gate is missing"
    )

    kwargs = dict(
        issue_state="closed",
        issue_state_reason="completed",
        claim_state=_claim(),
        transaction_state="CONSUMED",
        live_branch_head_sha=HEAD,
        active_remote_run=False,
        delegated_work_state="NONE",
        expected_issue="691",
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    )
    local = local_gate(_checkpoint(), **kwargs)
    remote = continuity.evaluate_remote_turn_exit_from_durable_state(
        _checkpoint(),
        **kwargs,
    )
    assert local == remote == "TURN_EXIT_PERMITTED"


def test_red_stop_12_scheduler_end_binds_exact_permitted_turn_exit_receipt() -> None:
    verify = getattr(continuity, "assert_scheduler_end_receipt", None)
    assert callable(verify), (
        "RED-STOP-12: scheduler END exact turn-exit receipt verifier is missing"
    )
    verify(
        _scheduler_end(),
        turn_exit_receipt=_turn_exit_receipt(),
        result_comment_id=202,
    )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("result_comment_id", 999, "result comment"),
        ("checkpoint_fingerprint", "e" * 64, "fingerprint"),
        ("invocation_identity", "other-invocation", "invocation"),
    ],
)
def test_red_stop_13_scheduler_end_rejects_stale_or_wrong_receipt_identity(
    field: str,
    value: object,
    match: str,
) -> None:
    verify = getattr(continuity, "assert_scheduler_end_receipt", None)
    assert callable(verify), (
        "RED-STOP-13: scheduler END exact receipt verifier is missing"
    )
    end = _scheduler_end()
    end[field] = value
    with pytest.raises(continuity.TurnExitBlocked, match=match):
        verify(
            end,
            turn_exit_receipt=_turn_exit_receipt(),
            result_comment_id=202,
        )


def test_trusted_workflow_validates_scheduler_end_comment() -> None:
    text = Path(".github/workflows/whd-turn-exit-gate.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        "scheduler-end:",
        "WHD_SCHEDULER_RUNTIME_END_V1",
        "assert_scheduler_end_receipt",
        "request_comment_id",
        "result_comment_id",
        "checkpoint_fingerprint",
        "turn_exit_run_id",
        "WHD_SCHEDULER_RUNTIME_END_RESULT_V1",
    ):
        assert token in text
