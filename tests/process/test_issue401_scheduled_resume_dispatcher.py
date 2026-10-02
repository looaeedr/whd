from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    ScheduledResumeAction,
    save_checkpoint,
    scheduled_resume_action,
)
from tools.scheduled_resume_bridge import dispatch_scheduled_resume, main


def cp(state, *, next_action="do exact thing", run_id=None):
    if state in {ContinuityState.TERMINAL_SUCCESS, ContinuityState.TERMINAL_FAILURE}:
        next_action = None
    if state is ContinuityState.WAITING_REMOTE and run_id is None:
        run_id = 123
    return Checkpoint(
        issue="#401",
        branch="continuity/issue401-scheduled-resume-dispatcher-20260920",
        head_sha="a" * 40,
        state=state,
        next_action=next_action,
        run_id=run_id,
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ContinuityState.RUNNING, ScheduledResumeAction.EXECUTE_NEXT_ACTION),
        (ContinuityState.WAITING_REMOTE, ScheduledResumeAction.POLL_LOCKED_RUN),
        (ContinuityState.RECOVERING, ScheduledResumeAction.CONTINUE_RECOVERY),
        (ContinuityState.BLOCKED, ScheduledResumeAction.REPORT_BLOCKER),
        (ContinuityState.TERMINAL_SUCCESS, ScheduledResumeAction.CLOSING_HANDOFF),
        (ContinuityState.TERMINAL_FAILURE, ScheduledResumeAction.CLOSING_HANDOFF),
    ],
)
def test_canonical_controller_owns_scheduled_resume_mapping(state, expected):
    assert scheduled_resume_action(cp(state)) is expected


def test_bridge_dispatches_exact_owner_and_preserves_next_action(tmp_path):
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, cp(ContinuityState.RUNNING, next_action="run focused GREEN"))
    result = dispatch_scheduled_resume(
        path,
        expected_issue="#401",
        expected_branch="continuity/issue401-scheduled-resume-dispatcher-20260920",
        expected_head_sha="a" * 40,
    )
    assert result.action is ScheduledResumeAction.EXECUTE_NEXT_ACTION
    assert result.next_action == "run focused GREEN"
    assert result.issue == "#401"
    assert result.branch == "continuity/issue401-scheduled-resume-dispatcher-20260920"
    assert result.head_sha == "a" * 40
    assert result.run_id is None


def test_bridge_waiting_remote_preserves_locked_run_identity(tmp_path):
    path = tmp_path / "checkpoint.json"
    save_checkpoint(
        path,
        cp(
            ContinuityState.WAITING_REMOTE,
            next_action="poll same locked run",
            run_id=987654,
        ),
    )
    result = dispatch_scheduled_resume(
        path,
        expected_issue="#401",
        expected_branch="continuity/issue401-scheduled-resume-dispatcher-20260920",
        expected_head_sha="a" * 40,
    )
    assert result.action is ScheduledResumeAction.POLL_LOCKED_RUN
    assert result.run_id == 987654
    assert result.next_action == "poll same locked run"


def test_bridge_owner_mismatch_fails_closed(tmp_path):
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, cp(ContinuityState.RUNNING))
    with pytest.raises(CheckpointError, match="checkpoint owner mismatch"):
        dispatch_scheduled_resume(
            path,
            expected_issue="#WRONG",
            expected_branch="continuity/issue401-scheduled-resume-dispatcher-20260920",
            expected_head_sha="a" * 40,
        )


def test_bridge_cli_outputs_machine_readable_json(tmp_path, capsys):
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, cp(ContinuityState.RECOVERING, next_action="inspect exact failure"))
    rc = main(
        [
            str(path),
            "--issue", "#401",
            "--branch", "continuity/issue401-scheduled-resume-dispatcher-20260920",
            "--head-sha", "a" * 40,
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "CONTINUE_RECOVERY"
    assert payload["next_action"] == "inspect exact failure"
    assert payload["state"] == "RECOVERING"


def test_bridge_does_not_own_a_second_state_machine():
    source = Path("tools/scheduled_resume_bridge.py").read_text(encoding="utf-8")
    assert "transition_checkpoint" not in source
    assert "save_checkpoint" not in source
    assert "class ContinuityState" not in source
    assert "class ScheduledResumeAction" not in source
