"""Machine builder for scheduler host entrypoint observations.

This is NON_AUTHORITY observability.  It makes host WAKE/HEARTBEAT/PROGRESS/EXIT
state deterministic even when there is no current ExecutionRecord, so a normal
NO_EXECUTABLE_WORK cycle does not remain stuck at the seed projection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

SCHEMA = "WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1"
AUTHORITY = "NON_AUTHORITY"
EVENTS = {"WAKE", "HEARTBEAT", "PROGRESS", "EXIT"}
HEARTBEAT_TTL_SECONDS = 300


class SchedulerEntrypointObservationError(ValueError):
    pass


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchedulerEntrypointObservationError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchedulerEntrypointObservationError("observed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _required(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise SchedulerEntrypointObservationError(f"{field} must be nonblank")
    return result


def build_entrypoint_observation(
    *,
    previous: Mapping[str, object] | None,
    entrypoint: str,
    task_id: str,
    lane_id: str,
    invocation_identity: str,
    event: str,
    observed_at: str,
    exit_state: str | None = None,
    heartbeat_ttl_seconds: int = HEARTBEAT_TTL_SECONDS,
) -> dict[str, object]:
    event = _required(event, "event").upper()
    if event not in EVENTS:
        raise SchedulerEntrypointObservationError(f"unsupported event: {event}")
    if heartbeat_ttl_seconds <= 0:
        raise SchedulerEntrypointObservationError("heartbeat_ttl_seconds must be positive")

    entrypoint = _required(entrypoint, "entrypoint")
    task_id = _required(task_id, "task_id")
    lane_id = _required(lane_id, "lane_id")
    invocation_identity = _required(invocation_identity, "invocation_identity")
    now = _utc(observed_at)
    prev = dict(previous or {})

    if prev and prev.get("schema") not in {None, SCHEMA}:
        raise SchedulerEntrypointObservationError("previous observation schema mismatch")
    for field, current in (("entrypoint", entrypoint), ("lane_id", lane_id)):
        prior = prev.get(field)
        if prior not in {None, current}:
            raise SchedulerEntrypointObservationError(f"previous {field} identity mismatch")
    prior_task_id = prev.get("task_id")
    if prior_task_id not in {None, task_id} and event != "WAKE":
        raise SchedulerEntrypointObservationError("previous task_id identity mismatch")

    out: dict[str, object] = {
        "schema": SCHEMA,
        "version": 1,
        "authority": AUTHORITY,
        "entrypoint": entrypoint,
        "task_id": task_id,
        "lane_id": lane_id,
        "invocation_identity": invocation_identity,
        "event": event,
        "last_wake_at": prev.get("last_wake_at"),
        "last_heartbeat_at": prev.get("last_heartbeat_at"),
        "heartbeat_expires_at": prev.get("heartbeat_expires_at"),
        "last_progress_at": prev.get("last_progress_at"),
        "exit_at": prev.get("exit_at"),
        "exit_state": prev.get("exit_state"),
        "observed_at": _iso(now),
    }

    if event == "WAKE":
        out["last_wake_at"] = _iso(now)
        out["last_heartbeat_at"] = None
        out["heartbeat_expires_at"] = None
        out["last_progress_at"] = None
        out["exit_at"] = None
        out["exit_state"] = None
    elif event in {"HEARTBEAT", "PROGRESS"}:
        if prev.get("invocation_identity") not in {None, invocation_identity}:
            raise SchedulerEntrypointObservationError("heartbeat/progress invocation identity mismatch")
        out["last_heartbeat_at"] = _iso(now)
        out["heartbeat_expires_at"] = _iso(now + timedelta(seconds=heartbeat_ttl_seconds))
        if event == "PROGRESS":
            out["last_progress_at"] = _iso(now)
        out["exit_at"] = None
        out["exit_state"] = None
    else:
        if prev.get("invocation_identity") not in {None, invocation_identity}:
            raise SchedulerEntrypointObservationError("exit invocation identity mismatch")
        state = _required(exit_state, "exit_state")
        out["exit_at"] = _iso(now)
        out["exit_state"] = state

    return out
