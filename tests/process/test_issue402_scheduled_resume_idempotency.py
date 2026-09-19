from __future__ import annotations

from pathlib import Path

import pytest

from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    save_checkpoint,
)
from tools.scheduled_resume_bridge import (
    ScheduledResumeAction,
    claim_scheduled_wake,
    dispatch_scheduled_resume,
)


ISSUE = "#402"
BRANCH = "continuity/issue402-scheduled-resume-idempotency-20260920"
HEAD = "b" * 40


def _write(path: Path, *, next_action="do one thing", state=ContinuityState.RUNNING):
    cp = Checkpoint(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=state,
        next_action=None if state in {ContinuityState.TERMINAL_SUCCESS, ContinuityState.TERMINAL_FAILURE} else next_action,
    )
    save_checkpoint(path, cp)


def _dispatch(path: Path):
    return dispatch_scheduled_resume(
        path,
        expected_issue=ISSUE,
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    )


def test_same_checkpoint_produces_same_fingerprint_and_wake_key(tmp_path):
    path = tmp_path / "checkpoint.json"
    _write(path)
    first = _dispatch(path)
    second = _dispatch(path)
    assert first.checkpoint_fingerprint == second.checkpoint_fingerprint
    assert first.wake_key == second.wake_key
    assert first.action is ScheduledResumeAction.EXECUTE_NEXT_ACTION


def test_atomic_claim_allows_only_one_mutating_owner_for_same_wake(tmp_path):
    path = tmp_path / "checkpoint.json"
    lease_dir = tmp_path / "leases"
    _write(path)
    dispatch = _dispatch(path)

    first = claim_scheduled_wake(lease_dir, dispatch)
    second = claim_scheduled_wake(lease_dir, dispatch)

    assert first.claimed is True
    assert second.claimed is False
    assert first.wake_key == second.wake_key == dispatch.wake_key
    assert first.receipt_path == second.receipt_path
    assert first.receipt_path.is_file()


def test_checkpoint_mutation_gets_new_wake_key_and_new_claim(tmp_path):
    path = tmp_path / "checkpoint.json"
    lease_dir = tmp_path / "leases"
    _write(path, next_action="first action")
    first = _dispatch(path)
    assert claim_scheduled_wake(lease_dir, first).claimed is True

    _write(path, next_action="second action")
    second = _dispatch(path)
    assert second.checkpoint_fingerprint != first.checkpoint_fingerprint
    assert second.wake_key != first.wake_key
    assert claim_scheduled_wake(lease_dir, second).claimed is True


def test_owner_drift_still_fails_before_claim(tmp_path):
    path = tmp_path / "checkpoint.json"
    _write(path)
    with pytest.raises(CheckpointError, match="checkpoint owner mismatch"):
        dispatch_scheduled_resume(
            path,
            expected_issue="#WRONG",
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )


def test_terminal_repeat_is_closing_handoff_and_deterministic(tmp_path):
    path = tmp_path / "checkpoint.json"
    _write(path, state=ContinuityState.TERMINAL_SUCCESS)
    first = _dispatch(path)
    second = _dispatch(path)
    assert first.action is ScheduledResumeAction.CLOSING_HANDOFF
    assert second.action is ScheduledResumeAction.CLOSING_HANDOFF
    assert first.wake_key == second.wake_key
