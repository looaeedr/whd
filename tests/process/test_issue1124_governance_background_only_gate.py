from __future__ import annotations

import pytest

from tools.continuity_controller import (
    AuthorityProgress,
    AuthorityProgressState,
    CheckpointError,
    record_first_substantive_action,
)
from tools.root_local_first_gate import (
    assert_outer_primary_action,
    classify_outer_orchestration_event,
    is_background_only_outer_event,
)


def _pending() -> AuthorityProgress:
    return AuthorityProgress(
        state=AuthorityProgressState.AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION,
        acquired_via="USER_EXPLICIT",
    )


@pytest.mark.parametrize(
    "event",
    [
        "ACQUIRE",
        "RESERVE_PATHS",
        "RECONCILE",
        "LEASE_RENEW",
        "START_QA",
        "ACCEPT_QA",
        "FINALIZE",
        "EXPIRED_LEASE",
        "RESERVATION_MISMATCH",
        "GOVERNANCE_DRIFT",
        "TEST_RED",
        "STATUS_QUERY",
        "PROGRESS_QUERY",
    ],
)
def test_control_plane_plumbing_is_background_only(event: str):
    classification = classify_outer_orchestration_event(event)
    assert classification["disposition"] == "BACKGROUND_CONTINUE_PRIMARY_TASK"
    assert classification["outer_visible"] is False
    assert classification["primary_task_switch_allowed"] is False
    assert is_background_only_outer_event(event) is True
    with pytest.raises(ValueError, match="GOVERNANCE_MUST_REMAIN_MACHINE_INTERNAL"):
        assert_outer_primary_action(event)


@pytest.mark.parametrize(
    "phase",
    ["FRESH_READ", "ROOT_MUTATE", "TARGETED_TEST", "EXACT_DIFF", "POST_PUSH_CI", "MERGE_FINALIZE"],
)
def test_outer_layer_accepts_phase_outcomes_only(phase: str):
    result = assert_outer_primary_action(phase)
    assert result["disposition"] == "OUTER_VISIBLE_PHASE"
    assert result["outer_visible"] is True


def test_real_blocker_can_be_reported_without_promoting_transaction_kind():
    blocker = assert_outer_primary_action(
        "REPORT_BLOCKER", escalation_trigger="PATH_CONFLICT"
    )
    assert blocker["disposition"] == "REAL_ESCALATION_BLOCKER"
    assert blocker["escalation_trigger"] == "PATH_CONFLICT"

    with pytest.raises(ValueError, match="GOVERNANCE_MUST_REMAIN_MACHINE_INTERNAL"):
        assert_outer_primary_action(
            "RECONCILE", escalation_trigger="PATH_CONFLICT"
        )


def test_non_escalation_anomaly_cannot_be_used_as_scope_switch_trigger():
    with pytest.raises(ValueError, match="PRIMARY_TASK_SWITCH_FORBIDDEN"):
        classify_outer_orchestration_event(
            "REPORT_BLOCKER", escalation_trigger="EXPIRED_LEASE"
        )


def test_continuity_rejects_background_governance_as_first_substantive_action():
    for event in ("ACQUIRE", "RECONCILE", "START_QA", "EXPIRED_LEASE"):
        with pytest.raises(CheckpointError, match="background/non-substantive"):
            record_first_substantive_action(_pending(), action=event)

    done = record_first_substantive_action(_pending(), action="ROOT_MUTATE")
    assert done.state is AuthorityProgressState.SUBSTANTIVE_ACTION_COMPLETED
    assert done.first_substantive_action == "ROOT_MUTATE"
