from __future__ import annotations

from dataclasses import replace

import pytest

import tools.continuity_controller as continuity


def _checkpoint() -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue="689",
        branch="work/issue689-takeover-substantive-action-20260926",
        head_sha="1" * 40,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=continuity.ClosureState.CLOSED,
    )


def _api():
    state = getattr(continuity, "AuthorityProgressState", None)
    progress_cls = getattr(continuity, "AuthorityProgress", None)
    consume = getattr(continuity, "record_first_substantive_action", None)
    assert state is not None, "RED-STOP-06: AuthorityProgressState is missing"
    assert progress_cls is not None, "RED-STOP-06: AuthorityProgress is missing"
    assert callable(consume), "RED-STOP-07: substantive-action consumer is missing"
    return state, progress_cls, consume


def test_authority_acquired_pending_state_blocks_turn_exit_deterministically() -> None:
    state, progress_cls, _ = _api()
    progress = progress_cls(
        state=state.AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION,
        acquired_via="claim-takeover",
        first_substantive_action=None,
    )
    with pytest.raises(
        continuity.TurnExitBlocked,
        match="AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION",
    ):
        continuity.assert_turn_exitable(
            _checkpoint(),
            authority_progress=progress,
        )


@pytest.mark.parametrize(
    "acquired_via",
    ["fresh-create", "claim-takeover", "reactivate", "scheduler-takeover"],
)
def test_interactive_and_scheduler_authority_share_same_pending_contract(
    acquired_via: str,
) -> None:
    state, progress_cls, _ = _api()
    progress = progress_cls(
        state=state.AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION,
        acquired_via=acquired_via,
        first_substantive_action=None,
    )
    with pytest.raises(continuity.TurnExitBlocked):
        continuity.assert_turn_exitable(
            _checkpoint(),
            authority_progress=progress,
        )


@pytest.mark.parametrize(
    "non_substantive",
    [
        "branch-create",
        "guard-receipt",
        "heartbeat",
        "progress-report",
        "claim-cas",
    ],
)
def test_non_substantive_events_do_not_consume_pending_state(
    non_substantive: str,
) -> None:
    state, progress_cls, consume = _api()
    progress = progress_cls(
        state=state.AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION,
        acquired_via="claim-takeover",
        first_substantive_action=None,
    )
    with pytest.raises(
        continuity.CheckpointError,
        match="substantive",
    ):
        consume(progress, action=non_substantive)


def test_valid_substantive_action_consumes_pending_state_and_allows_exit() -> None:
    state, progress_cls, consume = _api()
    progress = progress_cls(
        state=state.AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION,
        acquired_via="claim-takeover",
        first_substantive_action=None,
    )
    done = consume(
        progress,
        action="red-test-created-and-executed",
    )
    assert done.state is state.SUBSTANTIVE_ACTION_COMPLETED
    assert done.first_substantive_action == "red-test-created-and-executed"
    continuity.assert_turn_exitable(
        _checkpoint(),
        authority_progress=done,
    )


def test_claim_state_pending_authority_is_enforced_without_parallel_state() -> None:
    with pytest.raises(
        continuity.TurnExitBlocked,
        match="AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION",
    ):
        continuity.assert_turn_exitable(
            _checkpoint(),
            claim_state={
                "phase": "GREEN",
                "authority_progress": {
                    "state": "AUTHORITY_ACQUIRED_PENDING_SUBSTANTIVE_ACTION",
                    "acquired_via": "claim-takeover",
                    "first_substantive_action": None,
                },
            },
        )


def test_claim_state_completed_authority_allows_normal_turn_exit_rules() -> None:
    continuity.assert_turn_exitable(
        _checkpoint(),
        claim_state={
            "phase": "RELEASED",
            "authority_progress": {
                "state": "SUBSTANTIVE_ACTION_COMPLETED",
                "acquired_via": "scheduler-takeover",
                "first_substantive_action": "red-test-created-and-executed",
            },
        },
    )
