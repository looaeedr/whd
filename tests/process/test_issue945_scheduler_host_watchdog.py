from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.scheduler_host_watchdog import (
    ENTRYPOINTS,
    HOST_SNAPSHOT_SCHEMA,
    ENTRYPOINT_SCHEMA,
    STATUS_HOST_AUTO_PAUSE,
    STATUS_HOST_ENTRY_FAILURE,
    STATUS_HOST_STATE_UNKNOWN,
    STATUS_OK_LIVE,
    STATUS_RUNTIME_LIVENESS_FAILURE,
    classify_entrypoint,
    evaluate,
)


def _spec(key: str):
    return next(x for x in ENTRYPOINTS if x.key == key)


def _entry(*, wake: str, heartbeat: str | None = None, expires: str | None = None, exit_at: str | None = None):
    return {
        "schema": ENTRYPOINT_SCHEMA,
        "entrypoint": "00",
        "last_wake_at": wake,
        "last_heartbeat_at": heartbeat,
        "heartbeat_expires_at": expires,
        "exit_at": exit_at,
        "exit_state": "DONE" if exit_at else None,
        "event": "EXIT" if exit_at else ("HEARTBEAT" if heartbeat else "WAKE"),
    }


def _host(*, observed_at: str, task_id: str, enabled: bool, last_run_time: str | None):
    return {
        "schema": HOST_SNAPSHOT_SCHEMA,
        "authority": "NON_AUTHORITY",
        "observed_at": observed_at,
        "tasks": {
            task_id: {
                "enabled": enabled,
                "last_run_time": last_run_time,
            }
        },
    }


def test_missing_wake_after_120_seconds_is_host_entry_failure_when_host_enabled():
    now = datetime(2026, 9, 28, 15, 2, 1, tzinfo=timezone.utc)  # 23:02:01 Taipei
    spec = _spec("a00")
    host = _host(
        observed_at="2026-09-28T15:02:00Z",
        task_id=spec.automation_id,
        enabled=True,
        last_run_time="2026-09-28T15:00:30Z",
    )
    row = classify_entrypoint(spec, now=now, observation=None, host_snapshot=host)
    assert row["expected_at"] == "2026-09-28T15:00:00Z"
    assert row["status"] == STATUS_HOST_ENTRY_FAILURE
    assert row["reason"] == "HOST_RECORDED_RUN_BUT_DURABLE_WAKE_MISSING"


def test_missing_wake_plus_fresh_disabled_snapshot_upgrades_to_host_auto_pause():
    now = datetime(2026, 9, 28, 15, 2, 1, tzinfo=timezone.utc)
    spec = _spec("a00")
    host = _host(
        observed_at="2026-09-28T15:02:00Z",
        task_id=spec.automation_id,
        enabled=False,
        last_run_time="2026-09-28T15:00:30Z",
    )
    row = classify_entrypoint(spec, now=now, observation=None, host_snapshot=host)
    assert row["status"] == STATUS_HOST_AUTO_PAUSE
    assert row["host_enabled"] is False


def test_stale_host_snapshot_never_guesses_auto_pause():
    now = datetime(2026, 9, 28, 15, 2, 1, tzinfo=timezone.utc)
    spec = _spec("a00")
    host = _host(
        observed_at="2026-09-28T14:00:00Z",
        task_id=spec.automation_id,
        enabled=False,
        last_run_time="2026-09-28T14:00:20Z",
    )
    row = classify_entrypoint(spec, now=now, observation=None, host_snapshot=host)
    assert row["status"] == STATUS_HOST_STATE_UNKNOWN
    assert row["host_state"] == "STALE"


def test_valid_wake_and_heartbeat_is_live():
    now = datetime(2026, 9, 28, 15, 3, 0, tzinfo=timezone.utc)
    spec = _spec("a00")
    obs = _entry(
        wake="2026-09-28T15:00:20Z",
        heartbeat="2026-09-28T15:02:30Z",
        expires="2026-09-28T15:07:30Z",
    )
    row = classify_entrypoint(spec, now=now, observation=obs, host_snapshot=None)
    assert row["status"] == STATUS_OK_LIVE


def test_wake_with_expired_heartbeat_before_exit_is_runtime_liveness_failure():
    now = datetime(2026, 9, 28, 15, 10, 0, tzinfo=timezone.utc)
    spec = _spec("a00")
    obs = _entry(
        wake="2026-09-28T15:00:20Z",
        heartbeat="2026-09-28T15:02:30Z",
        expires="2026-09-28T15:07:30Z",
    )
    row = classify_entrypoint(spec, now=now, observation=obs, host_snapshot=None)
    assert row["status"] == STATUS_RUNTIME_LIVENESS_FAILURE
    assert row["reason"] == "HEARTBEAT_EXPIRED_BEFORE_EXIT"


def test_previous_hour_wake_cannot_satisfy_new_occurrence():
    now = datetime(2026, 9, 28, 15, 2, 1, tzinfo=timezone.utc)
    spec = _spec("a00")
    obs = _entry(wake="2026-09-28T14:00:20Z")
    row = classify_entrypoint(spec, now=now, observation=obs, host_snapshot=None)
    assert row["status"] == STATUS_HOST_STATE_UNKNOWN


def test_evaluate_is_non_authoritative_and_degraded_on_missed_wake():
    now = datetime(2026, 9, 28, 15, 47, 1, tzinfo=timezone.utc)
    rows = {spec.key: None for spec in ENTRYPOINTS}
    result = evaluate(now=now, entrypoint_observations=rows, host_snapshot=None)
    assert result["authority"] == "NON_AUTHORITY"
    assert result["overall_state"] == "DEGRADED"
    statuses = {x["entrypoint_key"]: x["status"] for x in result["entries"]}
    assert statuses["b45"] == STATUS_HOST_STATE_UNKNOWN


def test_watchdog_workflow_has_default_branch_bootstrap_and_exact_schedule():
    workflow = Path(".github/workflows/whd-scheduler-host-watchdog.yml").read_text(
        encoding="utf-8"
    )
    assert "- cron: '2,17,22,42,47 * * * *'" in workflow
    assert "7-57/5" not in workflow
    assert "  push:\n    branches:\n      - main\n    paths:\n      - .github/workflows/whd-scheduler-host-watchdog.yml" in workflow
    assert "  workflow_dispatch:" in workflow
