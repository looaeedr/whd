from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    ScheduledResumeAction,
    TurnExitBlocked,
    assert_turn_exitable,
    load_checkpoint,
    save_checkpoint,
    scheduled_resume_action,
)


def _chain_api():
    state = getattr(continuity, "ChainContinuationState", None)
    assert isinstance(state, type), (
        "R-CHAIN-EXIT: continuity controller cannot represent Master-chain continuation"
    )
    return state


def _terminal_child(**overrides):
    ChainContinuationState = _chain_api()
    values = dict(
        issue="#467",
        branch="workorder/issue464-joint-placement-marking-v1.3-20260921",
        head_sha="90a44fe459da2b78140987d89a995af6255a5934",
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        master_issue="#464",
        chain_state=ChainContinuationState.NEXT_CHILD_EXECUTABLE,
        next_issue="#468",
        chain_next_action=(
            "claim #468 from accepted parent "
            "90a44fe459da2b78140987d89a995af6255a5934"
        ),
    )
    values.update(overrides)
    return Checkpoint(**values)


def test_r_chain_exit_child_terminal_does_not_make_master_chain_turn_exitable():
    checkpoint = _terminal_child()

    with pytest.raises(TurnExitBlocked, match=r"#468|claim #468"):
        assert_turn_exitable(checkpoint)


def test_terminal_child_with_executable_next_child_routes_scheduler_to_execute_next_action():
    checkpoint = _terminal_child()

    assert scheduled_resume_action(checkpoint) is ScheduledResumeAction.EXECUTE_NEXT_ACTION


def test_terminal_child_chain_handoff_roundtrips_durably(tmp_path: Path):
    path = tmp_path / "child-terminal.json"
    checkpoint = _terminal_child()

    save_checkpoint(path, checkpoint)
    loaded = load_checkpoint(path)

    assert loaded.master_issue == "#464"
    assert loaded.next_issue == "#468"
    assert loaded.chain_next_action.startswith("claim #468")
    assert loaded.chain_state.value == "NEXT_CHILD_EXECUTABLE"


def test_master_chain_complete_terminal_child_can_exit_turn():
    ChainContinuationState = _chain_api()
    checkpoint = _terminal_child(
        chain_state=ChainContinuationState.CHAIN_COMPLETE,
        next_issue=None,
        chain_next_action=None,
    )

    assert_turn_exitable(checkpoint)


def test_genuine_external_chain_blocker_can_exit_turn_but_must_carry_reason():
    ChainContinuationState = _chain_api()
    checkpoint = _terminal_child(
        chain_state=ChainContinuationState.NEXT_CHILD_BLOCKED,
        next_issue="#466",
        chain_next_action=None,
        chain_reason="waiting for owning product authority to choose OPEN-1 disposition",
    )

    assert_turn_exitable(checkpoint)


def test_chain_child_missing_structured_handoff_fails_closed():
    ChainContinuationState = _chain_api()

    with pytest.raises(CheckpointError, match=r"chain|next_issue|chain_next_action"):
        Checkpoint(
            issue="#467",
            branch="workorder/issue464-joint-placement-marking-v1.3-20260921",
            head_sha="90a44fe459da2b78140987d89a995af6255a5934",
            state=ContinuityState.TERMINAL_SUCCESS,
            next_action=None,
            master_issue="#464",
            chain_state=ChainContinuationState.NEXT_CHILD_EXECUTABLE,
            next_issue=None,
            chain_next_action=None,
        )


def test_user_explicit_stop_allows_turn_exit_without_claiming_next_child():
    ChainContinuationState = _chain_api()
    checkpoint = _terminal_child(
        chain_state=ChainContinuationState.USER_STOPPED,
        next_issue="#468",
        chain_next_action=None,
        chain_reason="user explicitly stopped the authorized Master chain",
    )

    assert_turn_exitable(checkpoint)
