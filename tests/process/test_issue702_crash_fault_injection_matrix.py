from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.claim_activation_recovery import (
    ClaimActivationReadbackState,
    classify_claim_activation_readback,
)
from tools.scheduler_state_reconciliation import (
    SchedulerStateMutationIntent,
    SchedulerStateObservation,
    SchedulerStateReconciliationState,
    classify_scheduler_state_reconciliation,
)


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "governance" / "issue702_crash_fault_injection_matrix.json"

BOUNDARIES = (
    "prepare",
    "authorize",
    "post-effect",
    "readback",
    "pre-reconcile",
    "post-reconcile",
)

SURFACES = {
    "guard",
    "dispatch",
    "development-task",
    "scheduler-simulation",
    "scheduler-authoring",
    "forced-takeover",
    "scheduled-resume",
    "recurring-scheduler",
    "work-slot",
    "scheduler-end",
    "issue-closure",
    "helper-lifecycle",
    "claim-activation",
    "poweroff",
}


def _operation(state: continuity.OperationState) -> continuity.OperationTransaction:
    return continuity.OperationTransaction(
        operation_id="issue702-fault-op",
        operation_type="repository-write",
        state=state,
        target=".dispatch/claims/issue-702.json",
        payload_hash="a" * 64,
        recovery_action="reconcile issue702-fault-op from exact durable readback",
    )


def _running_checkpoint(state: continuity.OperationState) -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue="702",
        branch="work/issue702-crash-fault-combined-acceptance-20260927",
        head_sha="b" * 40,
        state=continuity.ContinuityState.RUNNING,
        next_action="ordinary checkpoint next action",
        operation=_operation(state),
    )


def _terminal_checkpoint(state: continuity.OperationState) -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue="702",
        branch="work/issue702-crash-fault-combined-acceptance-20260927",
        head_sha="b" * 40,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        evidence=("combined acceptance complete",),
        closure_state=continuity.ClosureState.CLOSED,
        operation=_operation(state),
    )


def _load_matrix() -> dict:
    assert MATRIX.exists(), (
        "RED-STOP-22: amendment-wide crash-after-side-effect fault-injection "
        "matrix artifact is missing"
    )
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_red_stop_22_matrix_declares_every_boundary_and_entry_surface():
    payload = _load_matrix()
    assert payload["schema"] == "WHD_CRASH_FAULT_INJECTION_MATRIX_V1"
    assert tuple(payload["boundaries"]) == BOUNDARIES

    rows = payload["surfaces"]
    assert {row["surface"] for row in rows} == SURFACES
    for row in rows:
        assert set(row["boundaries"]) == set(BOUNDARIES), row["surface"]
        path = ROOT / row["path"]
        assert path.exists(), (row["surface"], row["path"])
        text = path.read_text(encoding="utf-8")
        for marker in row["markers"]:
            assert marker in text, (row["surface"], marker)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (continuity.OperationState.PREPARED, continuity.ScheduledResumeAction.CONTINUE_RECOVERY),
        (continuity.OperationState.AUTHORIZED, continuity.ScheduledResumeAction.CONTINUE_RECOVERY),
        (continuity.OperationState.EFFECT_OBSERVED, continuity.ScheduledResumeAction.CONTINUE_RECOVERY),
        (continuity.OperationState.AMBIGUOUS, continuity.ScheduledResumeAction.CONTINUE_RECOVERY),
        (continuity.OperationState.RECONCILED, continuity.ScheduledResumeAction.EXECUTE_NEXT_ACTION),
    ],
)
def test_fault_injection_reentry_never_blindly_replays_unresolved_operation(state, expected):
    checkpoint = _running_checkpoint(state)
    assert continuity.scheduled_resume_action(checkpoint) is expected


@pytest.mark.parametrize(
    "state",
    [
        continuity.OperationState.PREPARED,
        continuity.OperationState.AUTHORIZED,
        continuity.OperationState.EFFECT_OBSERVED,
        continuity.OperationState.AMBIGUOUS,
    ],
)
def test_fault_injection_unresolved_operation_blocks_turn_exit(state):
    with pytest.raises(continuity.TurnExitBlocked, match="UNRESOLVED_OPERATION"):
        continuity.assert_turn_exitable(_terminal_checkpoint(state))


def test_fault_injection_post_issue_close_readback_reconciles_without_replay():
    operation = continuity.OperationTransaction(
        operation_id="issue702-close",
        operation_type="github-issue-close",
        state=continuity.OperationState.EFFECT_OBSERVED,
        target="https://github.com/looaeedr/whd/issues/702",
        payload_hash="c" * 64,
        recovery_action="read back Issue #702 and reconcile",
    )
    reconciled = continuity.reconcile_issue_close_operation(
        operation,
        issue_state="closed",
        issue_state_reason="completed",
    )
    assert reconciled.operation_id == operation.operation_id
    assert reconciled.state is continuity.OperationState.RECONCILED


def test_fault_injection_claim_activation_distinguishes_not_applied_effect_and_ambiguous():
    parent = "1" * 40
    applied = "2" * 40
    claim_path = ".dispatch/claims/issue-702.json"
    checkpoint_path = ".dispatch/checkpoints/issue-702.json"
    claim_blob = "3" * 40
    checkpoint_blob = "4" * 40

    not_applied = classify_claim_activation_readback(
        coord_parent_sha=parent,
        current_coord_sha=parent,
        current_parent_shas=(),
        current_changed_files=(),
        claim_path=claim_path,
        checkpoint_path=checkpoint_path,
        current_claim_blob_sha="",
        current_checkpoint_blob_sha="",
        candidate_claim_blob_sha=claim_blob,
        candidate_checkpoint_blob_sha=checkpoint_blob,
    )
    assert not_applied.state is ClaimActivationReadbackState.NOT_APPLIED

    effect = classify_claim_activation_readback(
        coord_parent_sha=parent,
        current_coord_sha=applied,
        current_parent_shas=(parent,),
        current_changed_files=(claim_path, checkpoint_path),
        claim_path=claim_path,
        checkpoint_path=checkpoint_path,
        current_claim_blob_sha=claim_blob,
        current_checkpoint_blob_sha=checkpoint_blob,
        candidate_claim_blob_sha=claim_blob,
        candidate_checkpoint_blob_sha=checkpoint_blob,
    )
    assert effect.state is ClaimActivationReadbackState.EFFECT_OBSERVED

    ambiguous = classify_claim_activation_readback(
        coord_parent_sha=parent,
        current_coord_sha=applied,
        current_parent_shas=("9" * 40,),
        current_changed_files=(claim_path, checkpoint_path),
        claim_path=claim_path,
        checkpoint_path=checkpoint_path,
        current_claim_blob_sha=claim_blob,
        current_checkpoint_blob_sha=checkpoint_blob,
        candidate_claim_blob_sha=claim_blob,
        candidate_checkpoint_blob_sha=checkpoint_blob,
    )
    assert ambiguous.state is ClaimActivationReadbackState.AMBIGUOUS


def test_fault_injection_scheduler_enable_distinguishes_pre_post_and_unknown_identity():
    intent = SchedulerStateMutationIntent(
        lane_owner="scheduler.6ab13fa557fc8191935c671214b865e2",
        entrypoint="00",
        automation_id="6ab13f881c34819180cee63f5dd9446b",
        schedule="BEGIN:VEVENT\nRRULE:FREQ=HOURLY;BYMINUTE=0\nEND:VEVENT",
        timing_mode="exact_schedule",
        enabled_before=False,
        enabled_after=True,
    )

    pre = SchedulerStateObservation(
        lane_owner=intent.lane_owner,
        entrypoint=intent.entrypoint,
        automation_id=intent.automation_id,
        schedule=intent.schedule,
        timing_mode=intent.timing_mode,
        enabled=False,
    )
    assert (
        classify_scheduler_state_reconciliation(intent, pre).state
        is SchedulerStateReconciliationState.NOT_APPLIED
    )

    post = SchedulerStateObservation(
        lane_owner=intent.lane_owner,
        entrypoint=intent.entrypoint,
        automation_id=intent.automation_id,
        schedule=intent.schedule,
        timing_mode=intent.timing_mode,
        enabled=True,
    )
    assert (
        classify_scheduler_state_reconciliation(intent, post).state
        is SchedulerStateReconciliationState.EFFECT_OBSERVED
    )

    wrong = SchedulerStateObservation(
        lane_owner=intent.lane_owner,
        entrypoint=intent.entrypoint,
        automation_id="wrong-automation",
        schedule=intent.schedule,
        timing_mode=intent.timing_mode,
        enabled=True,
    )
    assert (
        classify_scheduler_state_reconciliation(intent, wrong).state
        is SchedulerStateReconciliationState.AMBIGUOUS
    )
