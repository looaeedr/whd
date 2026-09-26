from __future__ import annotations

import pytest

import tools.continuity_controller as continuity


BRANCH = "work/issue690-closure-drift-classification-20260926"


def _terminal_pending(
    closure_state: object = None,
) -> continuity.Checkpoint:
    state = closure_state or continuity.ClosureState.FINALIZATION_PENDING
    next_action = (
        None
        if state is continuity.ClosureState.CLOSED
        else "finish canonical closure transaction"
    )
    return continuity.Checkpoint(
        issue="690",
        branch=BRANCH,
        head_sha="1" * 40,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=state,
        closure_next_action=next_action,
    )


def _api():
    classification = getattr(continuity, "ClosureDriftClassification", None)
    repair_action = getattr(continuity, "ClosureDriftRepairAction", None)
    classify = getattr(continuity, "classify_closure_drift", None)
    plan_repair = getattr(continuity, "plan_closure_drift_repair", None)
    assert isinstance(
        classification, type
    ), "RED-STOP-10: ClosureDriftClassification is missing"
    assert isinstance(
        repair_action, type
    ), "RED-STOP-10: ClosureDriftRepairAction is missing"
    assert callable(classify), "RED-STOP-10: classify_closure_drift is missing"
    assert callable(plan_repair), "RED-STOP-10: plan_closure_drift_repair is missing"
    return classification, repair_action, classify, plan_repair


def test_red_stop_10_issue_closed_before_finalization_has_explicit_machine_classification() -> None:
    classification, repair_action, classify, _plan = _api()
    assessment = classify(
        _terminal_pending(),
        issue_state="closed",
        issue_state_reason="completed",
        claim_state={"phase": "GREEN"},
    )
    assert assessment.classification is classification.ISSUE_CLOSED_BEFORE_FINALIZATION
    assert assessment.repair_action is repair_action.REOPEN_ISSUE_AND_RESUME_FINALIZATION


def test_red_stop_10_repair_plan_is_deterministic_and_cannot_silently_release() -> None:
    classification, repair_action, classify, plan_repair = _api()
    checkpoint = _terminal_pending()
    assessment = classify(
        checkpoint,
        issue_state="closed",
        issue_state_reason="completed",
        claim_state={"phase": "GREEN"},
    )
    assert assessment.classification is classification.ISSUE_CLOSED_BEFORE_FINALIZATION
    plan = plan_repair(checkpoint, assessment=assessment)
    assert plan.action is repair_action.REOPEN_ISSUE_AND_RESUME_FINALIZATION
    assert plan.required_issue_state == "open"
    assert plan.target_closure_state is continuity.ClosureState.FINALIZATION_PENDING
    assert plan.target_claim_phase != "RELEASED"
    assert plan.terminal_complete is False


def test_reg_stop_01_normal_release_handoff_pending_close_readback_is_consistent() -> None:
    classification, _repair_action, classify, _plan = _api()
    assessment = classify(
        _terminal_pending(continuity.ClosureState.RELEASE_HANDOFF_PENDING),
        issue_state="closed",
        issue_state_reason="completed",
        claim_state={"phase": "GREEN"},
    )
    assert assessment.classification is classification.CONSISTENT


def test_reg_stop_02_closed_checkpoint_requires_released_claim_for_consistency() -> None:
    classification, _repair_action, classify, _plan = _api()
    assessment = classify(
        _terminal_pending(continuity.ClosureState.CLOSED),
        issue_state="closed",
        issue_state_reason="completed",
        claim_state={"phase": "GREEN"},
    )
    assert assessment.classification is not classification.CONSISTENT

    released = classify(
        _terminal_pending(continuity.ClosureState.CLOSED),
        issue_state="closed",
        issue_state_reason="completed",
        claim_state={"phase": "RELEASED"},
    )
    assert released.classification is classification.CONSISTENT
