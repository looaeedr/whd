from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 540
WORK_BRANCH = "feature/issue540-stale-takeover-20260923"
BASE_SHA = "a8be8a41dc56ed1af9eee50bc6177e10b5fc0a04"
CLAIM_HEAD = "a" * 40
LIVE_HEAD = "b" * 40


def _module():
    return importlib.import_module("tools.stale_claim_takeover")


def _claim(**overrides):
    payload = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": "chatgpt",
        "executor_source": "chatgpt_interactive",
        "work_branch": WORK_BRANCH,
        "claimed_at": "2026-09-23T05:00:00+08:00",
        "base_sha": BASE_SHA,
        "head_sha": CLAIM_HEAD,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-23T06:00:00+08:00",
        "remote_qa": None,
        "next_action": "continue exact task",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _evaluate(*, now, claim=None, live_head=CLAIM_HEAD, live_commit_at=None, remote=None, threshold=600):
    module = _module()
    if live_commit_at is None:
        live_commit_at = now - timedelta(hours=1)
    return module.evaluate_stale_claim_takeover(
        claim or _claim(),
        now=now,
        live_head_sha=live_head,
        live_head_committed_at=live_commit_at,
        remote_run=remote,
        stale_after_seconds=threshold,
    )


def test_599_seconds_is_not_takeover_eligible():
    now = datetime(2026, 9, 23, 6, 9, 59, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T06:00:00Z")
    result = _evaluate(now=now, claim=claim)
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.stale_seconds == 599


def test_exactly_600_seconds_without_active_run_is_executor_stuck():
    now = datetime(2026, 9, 23, 6, 10, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T06:00:00Z")
    result = _evaluate(now=now, claim=claim)
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.stale_seconds == 600
    assert result.previous_executor_source == "chatgpt_interactive"


def test_active_exact_remote_run_blocks_takeover_even_when_old():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    remote = {
        "found": True,
        "run_id": 12345,
        "head_sha": CLAIM_HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-23T05:00:00Z",
    }
    claim = _claim(
        last_update="2026-09-23T05:00:00Z",
        remote_qa={"run_id": 12345, "head_sha": CLAIM_HEAD},
    )
    result = _evaluate(now=now, claim=claim, remote=remote)
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_recent_branch_commit_blocks_takeover():
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T05:00:00Z")
    result = _evaluate(
        now=now,
        claim=claim,
        live_head=LIVE_HEAD,
        live_commit_at=datetime(2026, 9, 23, 6, 15, 0, tzinfo=UTC),
    )
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.observed_live_head_sha == LIVE_HEAD
    assert result.stale_seconds == 300


def test_old_advanced_branch_can_be_taken_over_at_observed_live_head():
    now = datetime(2026, 9, 23, 6, 20, 0, tzinfo=UTC)
    claim = _claim(last_update="2026-09-23T05:00:00Z")
    result = _evaluate(
        now=now,
        claim=claim,
        live_head=LIVE_HEAD,
        live_commit_at=datetime(2026, 9, 23, 6, 9, 0, tzinfo=UTC),
    )
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.observed_live_head_sha == LIVE_HEAD
    assert result.stale_seconds == 660


def test_scheduler_owned_claim_does_not_require_takeover():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    result = _evaluate(
        now=now,
        claim=_claim(
            executor_source="scheduler",
            last_update="2026-09-23T05:00:00Z",
        ),
    )
    assert result.classification.value == "ALREADY_SCHEDULER"
    assert result.actionable is False


def test_inactive_claim_is_terminal_not_takeover():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    result = _evaluate(
        now=now,
        claim=_claim(phase="RELEASED", last_update="2026-09-23T05:00:00Z"),
    )
    assert result.classification.value == "TERMINAL"
    assert result.actionable is False


def test_malformed_progress_timestamp_fails_closed():
    now = datetime(2026, 9, 23, 7, 0, 0, tzinfo=UTC)
    with pytest.raises(Exception, match="last_update|timestamp|ISO"):
        _evaluate(now=now, claim=_claim(last_update="not-a-time"))


def test_execution_claim_guard_accepts_claim_takeover_as_single_guarded_action(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    assert "claim-takeover" in guard.ALLOWED_ACTIONS

    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker="chatgpt",
        branch=WORK_BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE_SHA,
        expected_head_sha=CLAIM_HEAD,
    )
    assert claim.issue == ISSUE
    assert claim.work_branch == WORK_BRANCH
