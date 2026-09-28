"""Host-independent scheduler lifecycle watchdog.

This module is NON_AUTHORITY observability.  It derives expected recurring
occurrences for WHD scheduler entrypoints and compares them with durable
entrypoint observations written to coord/monitor-v2.  Optional ChatGPT host
snapshots can refine a missing WAKE to HOST_AUTO_PAUSE, but host state never
grants execution authority.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

SCHEMA = "WHD_SCHEDULER_HOST_WATCHDOG_V1"
HOST_SNAPSHOT_SCHEMA = "WHD_CHATGPT_AUTOMATION_HOST_SNAPSHOT_V1"
ENTRYPOINT_SCHEMA = "WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1"
AUTHORITY = "NON_AUTHORITY"
TAIPEI = ZoneInfo("Asia/Taipei")
GRACE_SECONDS = 120
HEARTBEAT_TTL_SECONDS = 300
HOST_SNAPSHOT_MAX_AGE_SECONDS = 1800

STATUS_OK_LIVE = "OK_LIVE"
STATUS_OK_EXITED = "OK_EXITED"
STATUS_OK_STARTING = "OK_STARTING"
STATUS_NOT_DUE = "NOT_DUE"
STATUS_HOST_ENTRY_FAILURE = "HOST_ENTRY_FAILURE"
STATUS_HOST_AUTO_PAUSE = "HOST_AUTO_PAUSE"
STATUS_HOST_STATE_UNKNOWN = "HOST_STATE_UNKNOWN"
STATUS_RUNTIME_LIVENESS_FAILURE = "RUNTIME_LIVENESS_FAILURE"

HOST_SNAPSHOT_PATH = ".dispatch/monitor/host/chatgpt-automations.json"
WATCHDOG_PATH = ".dispatch/monitor/host/watchdog.json"

@dataclass(frozen=True)
class EntrypointSpec:
    key: str
    entrypoint: str
    minute: int
    automation_id: str
    lane_owner: str
    observation_path: str


LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"

ENTRYPOINTS: tuple[EntrypointSpec, ...] = (
    EntrypointSpec(
        "a00", "00", 0, "6ab13f881c34819180cee63f5dd9446b", LANE_A,
        ".dispatch/monitor/host/entrypoints/a00.json",
    ),
    EntrypointSpec(
        "b15", "B15", 15, "6ab51d9226808191b9ae0c624e28c246", LANE_B,
        ".dispatch/monitor/host/entrypoints/b15.json",
    ),
    EntrypointSpec(
        "a20", "20", 20, "6ab4eaee5e008191a0e7e23303f64cea", LANE_A,
        ".dispatch/monitor/host/entrypoints/a20.json",
    ),
    EntrypointSpec(
        "a40", "40", 40, "6ab13fa557fc8191935c671214b865e2", LANE_A,
        ".dispatch/monitor/host/entrypoints/a40.json",
    ),
    EntrypointSpec(
        "b45", "B45", 45, "6ab51d9ec6708191a578d67065f8979b", LANE_B,
        ".dispatch/monitor/host/entrypoints/b45.json",
    ),
)


def _parse_time(value: object | None) -> datetime | None:
    if value in {None, ""}:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("watchdog timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def latest_expected_occurrence(now: datetime, minute: int) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(TAIPEI)
    candidate = local.replace(minute=minute, second=0, microsecond=0)
    if candidate > local:
        candidate -= timedelta(hours=1)
    return candidate.astimezone(timezone.utc)


def _fresh_host_snapshot(
    snapshot: Mapping[str, object] | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> bool:
    if not isinstance(snapshot, Mapping):
        return False
    if snapshot.get("schema") != HOST_SNAPSHOT_SCHEMA:
        return False
    observed = _parse_time(snapshot.get("observed_at"))
    if observed is None:
        return False
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    return 0 <= age <= max_age_seconds


def _host_task(
    snapshot: Mapping[str, object] | None,
    automation_id: str,
) -> Mapping[str, object] | None:
    if not isinstance(snapshot, Mapping):
        return None
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, Mapping):
        return None
    value = tasks.get(automation_id)
    return value if isinstance(value, Mapping) else None


def _matching_wake(
    observation: Mapping[str, object] | None,
    *,
    expected_at: datetime,
) -> datetime | None:
    if not isinstance(observation, Mapping):
        return None
    if observation.get("schema") != ENTRYPOINT_SCHEMA:
        return None
    wake = _parse_time(observation.get("last_wake_at") or observation.get("wake_at"))
    if wake is None:
        return None
    # A host can deliver a few seconds early; do not let a prior hourly wake
    # satisfy the next expected occurrence.
    if wake < expected_at - timedelta(seconds=30):
        return None
    return wake


def classify_entrypoint(
    spec: EntrypointSpec,
    *,
    now: datetime,
    observation: Mapping[str, object] | None,
    host_snapshot: Mapping[str, object] | None,
    grace_seconds: int = GRACE_SECONDS,
    heartbeat_ttl_seconds: int = HEARTBEAT_TTL_SECONDS,
    host_snapshot_max_age_seconds: int = HOST_SNAPSHOT_MAX_AGE_SECONDS,
) -> dict[str, object]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    expected = latest_expected_occurrence(now, spec.minute)
    due_at = expected + timedelta(seconds=grace_seconds)
    wake = _matching_wake(observation, expected_at=expected)

    base: dict[str, object] = {
        "entrypoint": spec.entrypoint,
        "entrypoint_key": spec.key,
        "automation_id": spec.automation_id,
        "lane_owner": spec.lane_owner,
        "expected_at": _iso(expected),
        "due_at": _iso(due_at),
        "last_wake_at": _iso(wake),
        "status": STATUS_NOT_DUE,
        "reason": "GRACE_WINDOW_OPEN",
        "host_state": "UNKNOWN",
        "host_enabled": None,
        "host_last_run_time": None,
        "host_snapshot_observed_at": None,
    }

    snapshot_fresh = _fresh_host_snapshot(
        host_snapshot, now=now, max_age_seconds=host_snapshot_max_age_seconds
    )
    host_task = _host_task(host_snapshot, spec.automation_id)
    if snapshot_fresh and host_task is not None:
        base["host_state"] = "FRESH"
        base["host_enabled"] = host_task.get("enabled")
        base["host_last_run_time"] = host_task.get("last_run_time")
        base["host_snapshot_observed_at"] = host_snapshot.get("observed_at")
    elif isinstance(host_snapshot, Mapping):
        base["host_state"] = "STALE"
        base["host_snapshot_observed_at"] = host_snapshot.get("observed_at")

    if now < due_at:
        return base

    if wake is None:
        if snapshot_fresh and host_task is not None:
            if host_task.get("enabled") is False:
                base["status"] = STATUS_HOST_AUTO_PAUSE
                base["reason"] = "EXPECTED_WAKE_MISSING_AND_HOST_TASK_DISABLED"
            else:
                base["status"] = STATUS_HOST_ENTRY_FAILURE
                last_run = _parse_time(host_task.get("last_run_time"))
                if last_run is not None and last_run >= expected - timedelta(seconds=30):
                    base["reason"] = "HOST_RECORDED_RUN_BUT_DURABLE_WAKE_MISSING"
                else:
                    base["reason"] = "EXPECTED_WAKE_MISSING_WHILE_HOST_TASK_ENABLED"
        else:
            base["status"] = STATUS_HOST_STATE_UNKNOWN
            base["reason"] = "EXPECTED_WAKE_MISSING_AND_HOST_STATE_UNAVAILABLE_OR_STALE"
        return base

    if not isinstance(observation, Mapping):
        base["status"] = STATUS_RUNTIME_LIVENESS_FAILURE
        base["reason"] = "WAKE_PRESENT_WITHOUT_RUNTIME_OBSERVATION"
        return base

    if observation.get("exit_at") or observation.get("exit_state") or observation.get("event") == "EXIT":
        base["status"] = STATUS_OK_EXITED
        base["reason"] = "DURABLE_EXIT_PRESENT"
        return base

    expires = _parse_time(observation.get("heartbeat_expires_at"))
    if expires is not None:
        if expires > now:
            base["status"] = STATUS_OK_LIVE
            base["reason"] = "HEARTBEAT_VALID"
        else:
            base["status"] = STATUS_RUNTIME_LIVENESS_FAILURE
            base["reason"] = "HEARTBEAT_EXPIRED_BEFORE_EXIT"
        return base

    heartbeat = _parse_time(observation.get("last_heartbeat_at"))
    if heartbeat is not None:
        if heartbeat + timedelta(seconds=heartbeat_ttl_seconds) > now:
            base["status"] = STATUS_OK_LIVE
            base["reason"] = "HEARTBEAT_WITHIN_TTL"
        else:
            base["status"] = STATUS_RUNTIME_LIVENESS_FAILURE
            base["reason"] = "HEARTBEAT_STALE_BEFORE_EXIT"
        return base

    if wake + timedelta(seconds=heartbeat_ttl_seconds) > now:
        base["status"] = STATUS_OK_STARTING
        base["reason"] = "WAKE_PRESENT_HEARTBEAT_WINDOW_OPEN"
    else:
        base["status"] = STATUS_RUNTIME_LIVENESS_FAILURE
        base["reason"] = "WAKE_PRESENT_BUT_HEARTBEAT_NEVER_APPEARED"
    return base


def evaluate(
    *,
    now: datetime,
    entrypoint_observations: Mapping[str, Mapping[str, object] | None],
    host_snapshot: Mapping[str, object] | None,
) -> dict[str, object]:
    rows = [
        classify_entrypoint(
            spec,
            now=now,
            observation=entrypoint_observations.get(spec.key),
            host_snapshot=host_snapshot,
        )
        for spec in ENTRYPOINTS
    ]
    degraded = {
        STATUS_HOST_ENTRY_FAILURE,
        STATUS_HOST_AUTO_PAUSE,
        STATUS_HOST_STATE_UNKNOWN,
        STATUS_RUNTIME_LIVENESS_FAILURE,
    }
    return {
        "schema": SCHEMA,
        "version": 1,
        "authority": AUTHORITY,
        "observed_at": _iso(now),
        "timezone": "Asia/Taipei",
        "grace_seconds": GRACE_SECONDS,
        "heartbeat_ttl_seconds": HEARTBEAT_TTL_SECONDS,
        "host_snapshot_max_age_seconds": HOST_SNAPSHOT_MAX_AGE_SECONDS,
        "overall_state": "DEGRADED" if any(r["status"] in degraded for r in rows) else "HEALTHY",
        "entries": rows,
    }


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def evaluate_monitor_dir(monitor_dir: Path, *, now: datetime) -> dict[str, object]:
    host = _load_json(monitor_dir / HOST_SNAPSHOT_PATH)
    observations: dict[str, dict[str, object] | None] = {}
    for spec in ENTRYPOINTS:
        observations[spec.key] = _load_json(monitor_dir / spec.observation_path)
    return evaluate(now=now, entrypoint_observations=observations, host_snapshot=host)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--now", default=None, help="timezone-aware ISO-8601; defaults to current UTC")
    args = parser.parse_args()

    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    assert now is not None
    result = evaluate_monitor_dir(Path(args.monitor_dir), now=now)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
