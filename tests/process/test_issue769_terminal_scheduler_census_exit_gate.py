from __future__ import annotations

import pytest

from tools.continuity_controller import (
    Checkpoint,
    ContinuityState,
    TurnExitBlocked,
    assert_turn_exitable,
)


def test_terminal_closed_scheduler_requires_ready_work_census_proof() -> None:
    checkpoint = Checkpoint(
        issue="769",
        branch="governance/issue769-terminal-scheduler-census-hard-gate-20260927",
        head_sha="a" * 40,
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
    )
    claim = {
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "invocation_identity": "scheduler.invocation.issue769",
        "phase": "RELEASED",
    }

    with pytest.raises(TurnExitBlocked, match="READY_WORK_CENSUS"):
        assert_turn_exitable(checkpoint, claim_state=claim)
