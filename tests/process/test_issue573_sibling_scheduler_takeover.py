from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
CURRENT_LANE = "scheduler.6ab13f881c34819180cee63f5dd9446b"
SIBLING_LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
CLAIM_HEAD = "a" * 40


def _module():
    return importlib.import_module("tools.stale_claim_takeover")


def _claim(*, worker: str, last_update: str, remote_qa=None):
    return {
        "issue": 533,
        "issue_url": "https://github.com/looaeedr/whd/issues/533",
        "worker": worker,
        "executor_source": "scheduler",
        "work_branch": "work/issue520-phase6-bridge-residual-reduction-20260923",
        "claimed_at": "2026-09-23T13:00:00Z",
        "base_sha": "b" * 40,
        "head_sha": CLAIM_HEAD,
        "phase": "CLEANUP",
        "last_update": last_update,
        "remote_qa": remote_qa,
        "next_action": "continue",
        "blocker": None,
    }


def _evaluate(*, claim, now, remote_run=None):
    return _module().evaluate_stale_claim_takeover(
        claim,
        now=now,
        live_head_sha=CLAIM_HEAD,
        live_head_committed_at="2026-09-23T15:00:00Z",
        remote_run=remote_run,
        stale_after_seconds=600,
        requesting_worker=CURRENT_LANE,
    )


def test_same_scheduler_lane_never_stale_takeovers_itself():
    result = _evaluate(
        claim=_claim(worker=CURRENT_LANE, last_update="2026-09-23T15:00:00Z"),
        now=datetime(2026, 9, 23, 18, 0, tzinfo=UTC),
    )
    assert result.classification.value == "ALREADY_SCHEDULER"
    assert result.actionable is False


def test_stale_foreign_sibling_scheduler_is_actionable():
    result = _evaluate(
        claim=_claim(worker=SIBLING_LANE, last_update="2026-09-23T15:00:00Z"),
        now=datetime(2026, 9, 23, 18, 0, tzinfo=UTC),
    )
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.previous_worker == SIBLING_LANE
    assert result.requesting_worker == CURRENT_LANE


def test_active_foreign_sibling_scheduler_run_blocks_takeover():
    remote = {
        "found": True,
        "run_id": 12345,
        "head_sha": CLAIM_HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-23T17:59:00Z",
    }
    result = _evaluate(
        claim=_claim(
            worker=SIBLING_LANE,
            last_update="2026-09-23T15:00:00Z",
            remote_qa={"run_id": 12345, "head_sha": CLAIM_HEAD},
        ),
        now=datetime(2026, 9, 23, 18, 0, tzinfo=UTC),
        remote_run=remote,
    )
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_recent_foreign_sibling_scheduler_progress_blocks_takeover():
    result = _evaluate(
        claim=_claim(worker=SIBLING_LANE, last_update="2026-09-23T17:55:00Z"),
        now=datetime(2026, 9, 23, 18, 0, tzinfo=UTC),
    )
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False


def test_scheduler_claim_without_requesting_lane_stays_fail_closed():
    module = _module()
    result = module.evaluate_stale_claim_takeover(
        _claim(worker=SIBLING_LANE, last_update="2026-09-23T15:00:00Z"),
        now=datetime(2026, 9, 23, 18, 0, tzinfo=UTC),
        live_head_sha=CLAIM_HEAD,
        live_head_committed_at="2026-09-23T15:00:00Z",
        stale_after_seconds=600,
    )
    assert result.classification.value == "ALREADY_SCHEDULER"
    assert result.actionable is False


def test_trusted_remote_guard_schema_binds_takeover_worker():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/whd-remote-execution-guard.yml").read_text(
        encoding="utf-8"
    )
    assert '"takeover_worker"' in workflow
    assert "claim-takeover requires takeover_worker" in workflow
    assert '--requesting-worker "$RG_TAKEOVER_WORKER"' in workflow
    assert '"takeover_worker": request.get("takeover_worker")' in workflow
