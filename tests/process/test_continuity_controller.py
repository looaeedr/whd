import json
from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    FinalizationBlocked,
    assert_finalizable,
    load_checkpoint,
    save_checkpoint,
    transition_checkpoint,
)


def _running(**overrides):
    values = dict(
        issue="#216",
        branch="fix/continuous-execution-runtime-guard-20260914",
        head_sha="abc123",
        state=ContinuityState.RUNNING,
        next_action="run focused QA",
    )
    values.update(overrides)
    return Checkpoint(**values)


def _turn_exit_api():
    guard = getattr(continuity, "assert_turn_exitable", None)
    blocked_error = getattr(continuity, "TurnExitBlocked", None)
    assert callable(guard), "continuity controller is missing assert_turn_exitable()"
    assert isinstance(blocked_error, type), "continuity controller is missing TurnExitBlocked"
    return guard, blocked_error


def test_every_nonterminal_checkpoint_requires_next_action():
    for state in (
        ContinuityState.RUNNING,
        ContinuityState.WAITING_REMOTE,
        ContinuityState.RECOVERING,
        ContinuityState.BLOCKED,
    ):
        kwargs = dict(
            issue="#216",
            branch="fix/runtime-guard",
            head_sha="abc123",
            state=state,
            next_action="",
        )
        if state is ContinuityState.WAITING_REMOTE:
            kwargs["run_id"] = 123
        with pytest.raises(CheckpointError, match="next_action"):
            Checkpoint(**kwargs)


def test_waiting_remote_requires_exact_run_and_head_identity():
    with pytest.raises(CheckpointError, match="run_id"):
        _running(
            state=ContinuityState.WAITING_REMOTE,
            next_action="poll same run",
            run_id=None,
        )

    with pytest.raises(CheckpointError, match="head_sha"):
        _running(
            state=ContinuityState.WAITING_REMOTE,
            next_action="poll same run",
            run_id=123,
            head_sha="",
        )


def test_runtime_cut_reload_preserves_resume_identity_cursor_and_evidence(tmp_path: Path):
    path = tmp_path / "continuity.json"
    original = _running(
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll run 34790000000",
        run_id=34790000000,
        job_id=103900000000,
        log_cursor="byte:8192",
        evidence=("RED observed", "branch-first locked"),
    )

    save_checkpoint(path, original)
    resumed = load_checkpoint(path)

    assert resumed == original
    assert resumed.run_id == 34790000000
    assert resumed.job_id == 103900000000
    assert resumed.head_sha == "abc123"
    assert resumed.log_cursor == "byte:8192"
    assert resumed.next_action == "poll run 34790000000"
    assert resumed.evidence == ("RED observed", "branch-first locked")


def test_save_is_versioned_json_and_load_rejects_unknown_version(tmp_path: Path):
    path = tmp_path / "continuity.json"
    save_checkpoint(path, _running())

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1

    payload["version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CheckpointError, match="version"):
        load_checkpoint(path)


def test_finalization_is_blocked_for_every_nonterminal_state():
    for state in (
        ContinuityState.RUNNING,
        ContinuityState.WAITING_REMOTE,
        ContinuityState.RECOVERING,
        ContinuityState.BLOCKED,
    ):
        kwargs = {}
        if state is ContinuityState.WAITING_REMOTE:
            kwargs["run_id"] = 123
        checkpoint = _running(state=state, next_action="continue", **kwargs)
        with pytest.raises(FinalizationBlocked, match="non-terminal"):
            assert_finalizable(checkpoint)


def test_terminal_success_and_failure_are_finalizable_and_have_no_next_action():
    for state in (
        ContinuityState.TERMINAL_SUCCESS,
        ContinuityState.TERMINAL_FAILURE,
    ):
        checkpoint = _running(state=state, next_action=None)
        assert_finalizable(checkpoint)

        with pytest.raises(CheckpointError, match="next_action"):
            _running(state=state, next_action="should not exist")


def test_terminal_checkpoint_cannot_transition_back_to_active_state():
    terminal = _running(
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        evidence=("QA GREEN",),
    )
    with pytest.raises(CheckpointError, match="terminal"):
        transition_checkpoint(
            terminal,
            state=ContinuityState.RUNNING,
            next_action="illegal restart",
        )


def test_transition_to_waiting_remote_preserves_existing_evidence_and_sets_owner():
    running = _running(evidence=("branch-first",))
    waiting = transition_checkpoint(
        running,
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll same run",
        run_id=34790000000,
        job_id=103900000000,
        head_sha="def456",
        log_cursor="step:3",
        evidence=("RED fixed",),
    )

    assert waiting.state is ContinuityState.WAITING_REMOTE
    assert waiting.run_id == 34790000000
    assert waiting.job_id == 103900000000
    assert waiting.head_sha == "def456"
    assert waiting.log_cursor == "step:3"
    assert waiting.evidence == ("branch-first", "RED fixed")


def test_new_waiting_remote_lock_requires_explicit_run_id_instead_of_reusing_stale_owner():
    stale = _running(
        run_id=111,
        job_id=222,
        log_cursor="old-run-cursor",
        evidence=("previous remote run terminal",),
    )

    with pytest.raises(CheckpointError, match="explicit run_id"):
        transition_checkpoint(
            stale,
            state=ContinuityState.WAITING_REMOTE,
            next_action="poll newly submitted run",
        )


def test_new_waiting_remote_lock_clears_stale_job_and_cursor_when_not_explicitly_replaced():
    stale = _running(run_id=111, job_id=222, log_cursor="old-run-cursor")

    waiting = transition_checkpoint(
        stale,
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll run 333",
        run_id=333,
        head_sha="new-head",
    )

    assert waiting.run_id == 333
    assert waiting.job_id is None
    assert waiting.log_cursor is None
    assert waiting.head_sha == "new-head"


def test_same_waiting_remote_lock_can_preserve_owner_while_advancing_cursor():
    waiting = _running(
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll same run",
        run_id=333,
        job_id=444,
        log_cursor="step:2",
    )

    advanced = transition_checkpoint(
        waiting,
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll same run",
        log_cursor="step:3",
        evidence=("step 2 complete",),
    )

    assert advanced.run_id == 333
    assert advanced.job_id == 444
    assert advanced.head_sha == waiting.head_sha
    assert advanced.log_cursor == "step:3"
    assert advanced.evidence == ("step 2 complete",)


def test_turn_exit_is_blocked_for_autonomous_nonterminal_states():
    guard, blocked_error = _turn_exit_api()

    for state in (
        ContinuityState.RUNNING,
        ContinuityState.WAITING_REMOTE,
        ContinuityState.RECOVERING,
    ):
        kwargs = {}
        if state is ContinuityState.WAITING_REMOTE:
            kwargs["run_id"] = 123
        checkpoint = _running(state=state, next_action="continue closing work", **kwargs)
        with pytest.raises(blocked_error, match="continue closing work"):
            guard(checkpoint)


def test_blocked_checkpoint_can_exit_turn_but_remains_nonfinalizable():
    guard, _blocked_error = _turn_exit_api()
    checkpoint = _running(
        state=ContinuityState.BLOCKED,
        next_action="wait for missing external authority",
    )

    guard(checkpoint)
    with pytest.raises(FinalizationBlocked, match="non-terminal"):
        assert_finalizable(checkpoint)


def test_terminal_checkpoints_can_exit_turn():
    guard, _blocked_error = _turn_exit_api()

    for state in (
        ContinuityState.TERMINAL_SUCCESS,
        ContinuityState.TERMINAL_FAILURE,
    ):
        guard(_running(state=state, next_action=None))


def test_remote_success_handoff_to_closing_running_blocks_turn_exit():
    guard, blocked_error = _turn_exit_api()
    waiting = _running(
        state=ContinuityState.WAITING_REMOTE,
        next_action="poll run 34980000000",
        run_id=34980000000,
        job_id=104400000000,
        evidence=("remote QA active",),
    )
    closing = transition_checkpoint(
        waiting,
        state=ContinuityState.RUNNING,
        next_action="cleanup temporary QA workflow then drift audit",
        evidence=("remote QA terminal success",),
    )

    assert closing.state is ContinuityState.RUNNING
    assert closing.evidence[-1] == "remote QA terminal success"
    with pytest.raises(blocked_error, match="cleanup temporary QA workflow then drift audit"):
        guard(closing)


def test_assert_turn_exitable_cli_blocks_running_checkpoint(tmp_path: Path, capsys):
    path = tmp_path / "continuity.json"
    save_checkpoint(path, _running(next_action="close issue after cleanup"))

    exit_code = continuity.main(["assert-turn-exitable", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "TURN_EXIT_GUARD_ERROR" in output
    assert "close issue after cleanup" in output


def _closure_state_api():
    closure_state = getattr(continuity, "ClosureState", None)
    assert isinstance(closure_state, type), "continuity controller is missing ClosureState"
    return closure_state


def test_terminal_checkpoint_with_pending_closure_cannot_exit_turn():
    closure_state = _closure_state_api()
    guard, blocked_error = _turn_exit_api()
    checkpoint = _running(
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=closure_state.FINALIZATION_PENDING,
        closure_next_action="run bound finalization proof then close/readback/release",
    )

    with pytest.raises(blocked_error, match="finalization proof"):
        guard(checkpoint)


def test_terminal_checkpoint_can_exit_only_after_closure_is_complete():
    closure_state = _closure_state_api()
    guard, _blocked_error = _turn_exit_api()
    checkpoint = _running(
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=closure_state.CLOSED,
        closure_next_action=None,
    )

    guard(checkpoint)


def test_terminal_transition_enters_closure_transaction_by_default():
    guard, blocked_error = _turn_exit_api()
    terminal = transition_checkpoint(
        _running(),
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
    )

    assert terminal.closure_state is continuity.ClosureState.FINALIZATION_PENDING
    assert "finalization proof" in terminal.closure_next_action
    with pytest.raises(blocked_error, match="FINALIZATION_PENDING"):
        guard(terminal)


def test_legacy_persisted_terminal_without_closure_metadata_recovers_as_pending(tmp_path: Path):
    path = tmp_path / "legacy-terminal.json"
    payload = continuity.checkpoint_to_payload(
        _running(state=ContinuityState.TERMINAL_SUCCESS, next_action=None)
    )
    payload.pop("closure_state")
    payload.pop("closure_next_action")
    path.write_text(json.dumps(payload), encoding="utf-8")

    recovered = load_checkpoint(path)

    assert recovered.closure_state is continuity.ClosureState.FINALIZATION_PENDING
    assert "finalization proof" in recovered.closure_next_action


def test_pending_terminal_requires_issue_close_pending_before_bound_finalization_proof():
    checkpoint = _running(
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=continuity.ClosureState.FINALIZATION_PENDING,
        closure_next_action="advance to ISSUE_CLOSE_PENDING",
    )

    assert_finalizable(checkpoint)
    with pytest.raises(continuity.FinalizationBlocked, match="ISSUE_CLOSE_PENDING"):
        continuity.authorize_finalization(
            checkpoint,
            expected_issue=checkpoint.issue,
            expected_branch=checkpoint.branch,
            expected_head_sha=checkpoint.head_sha,
        )

    checkpoint = continuity.advance_closure(
        checkpoint,
        state=continuity.ClosureState.ISSUE_CLOSE_PENDING,
        next_action="run bound finalization proof",
    )
    proof = continuity.authorize_finalization(
        checkpoint,
        expected_issue=checkpoint.issue,
        expected_branch=checkpoint.branch,
        expected_head_sha=checkpoint.head_sha,
    )
    assert proof.checkpoint_fingerprint


def test_closure_lifecycle_is_monotonic_and_only_closed_terminal_can_exit():
    guard, blocked_error = _turn_exit_api()
    checkpoint = transition_checkpoint(
        _running(),
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
    )
    checkpoint = continuity.advance_closure(
        checkpoint,
        state=continuity.ClosureState.ISSUE_CLOSE_PENDING,
        next_action="close owning Issue and read it back",
        evidence=("bound finalization proof verified",),
    )
    with pytest.raises(blocked_error, match="close owning Issue"):
        guard(checkpoint)

    checkpoint = continuity.advance_closure(
        checkpoint,
        state=continuity.ClosureState.RELEASE_HANDOFF_PENDING,
        next_action=(
            "atomically persist checkpoint CLOSED + claim RELEASED + successor handoff"
        ),
        evidence=("Issue closed/completed readback verified",),
    )
    with pytest.raises(blocked_error, match="claim RELEASED"):
        guard(checkpoint)

    checkpoint = continuity.advance_closure(
        checkpoint,
        state=continuity.ClosureState.CLOSED,
        next_action=None,
        evidence=("atomic release/handoff closure commit read back",),
    )
    guard(checkpoint)

    with pytest.raises(CheckpointError, match="already CLOSED"):
        continuity.advance_closure(
            checkpoint,
            state=continuity.ClosureState.CLOSED,
            next_action=None,
        )


def test_terminal_resume_returns_closure_next_action_before_master_handoff(tmp_path: Path, capsys):
    path = tmp_path / "closing.json"
    checkpoint = transition_checkpoint(
        _running(),
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
    )
    save_checkpoint(path, checkpoint)

    exit_code = continuity.main(["resume", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "finalization proof" in output
