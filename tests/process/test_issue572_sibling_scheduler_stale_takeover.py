from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 572
WORKER = "scheduler.foreign-sibling"
BRANCH = "work/issue572-sibling-stale"
BASE = "a" * 40
CLAIM_HEAD = "b" * 40
LIVE_HEAD = "c" * 40


def _takeover():
    return importlib.import_module("tools.stale_claim_takeover")


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _claim(**overrides):
    payload = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": WORKER,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T00:00:00+08:00",
        "base_sha": BASE,
        "head_sha": CLAIM_HEAD,
        "phase": "CLEANUP",
        "last_update": "2026-09-23T16:00:00Z",
        "remote_qa": None,
        "next_action": "continue cleanup",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _evaluate(*, now, claim=None, live_commit_at=None, remote=None):
    if live_commit_at is None:
        live_commit_at = now - timedelta(hours=1)
    return _takeover().evaluate_stale_claim_takeover(
        claim or _claim(),
        now=now,
        live_head_sha=LIVE_HEAD,
        live_head_committed_at=live_commit_at,
        remote_run=remote,
        stale_after_seconds=600,
    )


def test_stale_foreign_scheduler_claim_is_actionable() -> None:
    now = datetime(2026, 9, 23, 18, 0, 0, tzinfo=UTC)
    result = _evaluate(now=now)

    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.previous_executor_source == "scheduler"
    assert result.claim_head_sha == CLAIM_HEAD
    assert result.observed_live_head_sha == LIVE_HEAD


def test_active_exact_run_still_blocks_foreign_scheduler_takeover() -> None:
    now = datetime(2026, 9, 23, 18, 0, 0, tzinfo=UTC)
    remote = {
        "found": True,
        "run_id": 572001,
        "head_sha": CLAIM_HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-23T17:00:00Z",
    }
    claim = _claim(remote_qa={"run_id": 572001, "head_sha": CLAIM_HEAD})

    result = _evaluate(now=now, claim=claim, remote=remote)

    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_recent_durable_progress_still_blocks_foreign_scheduler_takeover() -> None:
    now = datetime(2026, 9, 23, 18, 0, 0, tzinfo=UTC)
    result = _evaluate(
        now=now,
        live_commit_at=datetime(2026, 9, 23, 17, 55, 0, tzinfo=UTC),
    )

    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.stale_seconds == 300


def test_terminal_scheduler_claim_is_not_takeover_actionable() -> None:
    now = datetime(2026, 9, 23, 18, 0, 0, tzinfo=UTC)
    result = _evaluate(now=now, claim=_claim(phase="RELEASED"))

    assert result.classification.value == "TERMINAL"
    assert result.actionable is False


def test_execution_guard_accepts_bound_scheduler_source_takeover_evidence(
    tmp_path: Path,
) -> None:
    guard = _guard()
    payload = _claim()
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    evidence = {
        "schema": "WHD_STALE_CLAIM_TAKEOVER_V1",
        "classification": "EXECUTOR_STUCK",
        "actionable": True,
        "stale_seconds": 3600,
        "stale_after_seconds": 600,
        "previous_executor_source": "scheduler",
        "observed_live_head_sha": LIVE_HEAD,
        "claim_head_sha": CLAIM_HEAD,
        "claim_last_update": payload["last_update"],
        "claim_phase": payload["phase"],
        "latest_progress_at": "2026-09-23T17:00:00Z",
    }
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence) + "\n", encoding="utf-8")

    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE,
        expected_head_sha=LIVE_HEAD,
        takeover_evidence=evidence_path,
    )

    assert claim.head_sha == CLAIM_HEAD
    assert claim.worker == WORKER
