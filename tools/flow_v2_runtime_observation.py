"""Flow v2 runtime-observation adapter.

This module is NOT a liveness authority.  It reuses the existing machine
owners in tools.scheduler_runtime_liveness and tools.interactive_runtime_liveness
and projects their validated evidence, plus trusted transaction progress, into
coord/monitor-v2.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from tools.execution_record import ExecutionRecord, execution_record_fingerprint
from tools import interactive_runtime_liveness as interactive_liveness
from tools import scheduler_runtime_liveness as scheduler_liveness

SCHEMA = "WHD_RUNTIME_OBSERVATION_V2"
AUTHORITY = "NON_AUTHORITY"
EVENTS = {"WAKE", "HEARTBEAT", "PROGRESS", "EXIT"}
LIVENESS_STATES = {"LIVE", "EXPIRED", "ENDED", "UNKNOWN"}
HEARTBEAT_TTL_SECONDS = 300

LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"

_SOURCE_BY_OWNER = {
    LANE_A: ("scheduler-a", "排程A", None),
    LANE_B: ("scheduler-b", "排程B", None),
    "chatgpt.flowv2.work0": ("work-0", "工作0", "/工作0"),
    "chatgpt.flowv2.work1": ("work-1", "工作1", "/工作1"),
    "chatgpt.flowv2.work2": ("work-2", "工作2", "/工作2"),
    "chatgpt.flowv2.work3": ("work-3", "工作3", "/工作3"),
}


class RuntimeObservationError(ValueError):
    pass


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeObservationError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _identity_for_record(
    record: ExecutionRecord, *, runtime_owner: str | None = None
) -> tuple[str, str, str | None]:
    owner = runtime_owner or record.owner_id or record.lane_id
    if owner not in _SOURCE_BY_OWNER:
        raise RuntimeObservationError(f"unsupported runtime owner for observation: {owner!r}")
    return _SOURCE_BY_OWNER[owner]


def derive_liveness_state(observation: Mapping[str, object] | None, *, now: datetime | None = None) -> str:
    if not observation:
        return "UNKNOWN"
    if observation.get("exit_at") or observation.get("exit_state") or observation.get("event") == "EXIT":
        return "ENDED"
    expires = observation.get("heartbeat_expires_at")
    if not expires:
        return "UNKNOWN"
    current = now or datetime.now(timezone.utc)
    return "LIVE" if _utc(str(expires)) > current else "EXPIRED"


def _base(
    *,
    previous: Mapping[str, object] | None,
    source: str,
    handler: str,
    entrypoint: str | None,
    event: str,
    issue: int | None,
    slot_id: str | None,
    claim_worker: str | None,
    invocation_identity: str | None,
    conversation_identity: str | None,
    branch: str | None,
    head_sha: str | None,
    action: str | None,
    record_fingerprint: str | None,
    observed_at: datetime,
) -> dict[str, object]:
    if event not in EVENTS:
        raise RuntimeObservationError(f"unsupported runtime event: {event}")
    prev = dict(previous or {})
    return {
        "schema": SCHEMA,
        "version": 2,
        "authority": AUTHORITY,
        "source": source,
        "handler": handler,
        "entrypoint": entrypoint,
        "event": event,
        "runtime_state": "WORKING" if event != "EXIT" else str(prev.get("exit_state") or "ENDED"),
        "issue": issue,
        "slot_id": slot_id,
        "claim_worker": claim_worker,
        "owner_id": claim_worker,
        "invocation_identity": invocation_identity,
        "conversation_identity": conversation_identity,
        "branch": branch,
        "head_sha": head_sha,
        "action": action,
        "record_fingerprint": record_fingerprint,
        "last_wake_at": prev.get("last_wake_at"),
        "last_heartbeat_at": prev.get("last_heartbeat_at"),
        "heartbeat_expires_at": prev.get("heartbeat_expires_at"),
        "last_progress_at": prev.get("last_progress_at"),
        "exit_at": prev.get("exit_at"),
        "exit_state": prev.get("exit_state"),
        "liveness_state": str(prev.get("liveness_state") or "UNKNOWN"),
        "observed_at": _iso(observed_at),
    }


def project_transaction_progress(
    *,
    record: ExecutionRecord,
    invocation_identity: str,
    action: str,
    previous: Mapping[str, object] | None = None,
    conversation_identity: str = "UNAVAILABLE",
    runtime_owner: str | None = None,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Project trusted durable progress without pretending it was a HEARTBEAT event.

    A PROGRESS event proves the invocation was alive at that instant, so it may
    refresh the heartbeat timestamp/TTL.  It remains event=PROGRESS.
    """
    now = observed_at or datetime.now(timezone.utc)
    source, handler, entrypoint = _identity_for_record(record, runtime_owner=runtime_owner)
    out = _base(
        previous=previous,
        source=source,
        handler=handler,
        entrypoint=entrypoint,
        event="PROGRESS",
        issue=record.issue,
        slot_id=record.slot_id,
        claim_worker=(record.owner_id if record.owner_id not in {None, "NONE"} else runtime_owner),
        invocation_identity=invocation_identity,
        conversation_identity=(conversation_identity if record.owner_kind == "INTERACTIVE" else None),
        branch=record.work_branch,
        head_sha=record.head_sha,
        action=action,
        record_fingerprint=execution_record_fingerprint(record),
        observed_at=now,
    )
    out["last_progress_at"] = _iso(now)
    out["last_heartbeat_at"] = _iso(now)
    out["heartbeat_expires_at"] = _iso(now + timedelta(seconds=HEARTBEAT_TTL_SECONDS))
    out["liveness_state"] = "LIVE"
    out["exit_at"] = None
    out["exit_state"] = None
    return out


def project_interactive_liveness(
    parsed: Mapping[str, object],
    *,
    previous: Mapping[str, object] | None = None,
    event: str = "HEARTBEAT",
) -> dict[str, object]:
    """Adapt output from #679 interactive_runtime_liveness; do not re-parse it."""
    if parsed.get("schema") not in {interactive_liveness.MARKER, interactive_liveness.END_MARKER}:
        raise RuntimeObservationError("interactive evidence was not parsed by #679 authority")
    ended = str(parsed.get("runtime_status") or "") == "ENDED" or parsed.get("ended_at")
    chosen_event = "EXIT" if ended else event
    if chosen_event not in {"HEARTBEAT", "EXIT"}:
        raise RuntimeObservationError("interactive liveness adapter only accepts HEARTBEAT/EXIT")
    now = _utc(str(parsed.get("ended_at") or parsed.get("emitted_at")))
    slot_id = str(parsed["slot_id"])
    idx = slot_id.rsplit(".", 1)[-1]
    if idx not in {"0", "1", "2", "3"}:
        raise RuntimeObservationError("interactive slot is outside fixed work slots")
    out = _base(
        previous=previous,
        source=f"work-{idx}",
        handler=f"工作{idx}",
        entrypoint=f"/工作{idx}",
        event=chosen_event,
        issue=int(parsed["issue"]),
        slot_id=slot_id,
        claim_worker=str(parsed["worker"]),
        invocation_identity=str(parsed["invocation_identity"]),
        conversation_identity=str(parsed["conversation_identity"]),
        branch=str(parsed["branch"]),
        head_sha=str(parsed["head_sha"]),
        action=None,
        record_fingerprint=None,
        observed_at=now,
    )
    if chosen_event == "HEARTBEAT":
        out["last_heartbeat_at"] = str(parsed["emitted_at"])
        out["heartbeat_expires_at"] = str(parsed["expires_at"])
        out["liveness_state"] = "LIVE"
    else:
        out["exit_at"] = str(parsed["ended_at"])
        out["exit_state"] = str(parsed.get("end_reason") or "ENDED")
        out["runtime_state"] = out["exit_state"]
        out["liveness_state"] = "ENDED"
    return out


def project_scheduler_liveness(
    parsed: Mapping[str, object],
    *,
    previous: Mapping[str, object] | None = None,
    event: str = "HEARTBEAT",
) -> dict[str, object]:
    """Adapt output from existing scheduler_runtime_liveness authority."""
    if parsed.get("schema") not in {scheduler_liveness.MARKER, scheduler_liveness.END_MARKER}:
        raise RuntimeObservationError("scheduler evidence was not parsed by scheduler authority")
    lane = str(parsed["scheduler_lane"])
    if lane not in {LANE_A, LANE_B}:
        raise RuntimeObservationError("unknown scheduler lane")
    source, handler, entrypoint = _SOURCE_BY_OWNER[lane]
    ended = str(parsed.get("runtime_status") or "") == "ENDED" or parsed.get("ended_at")
    chosen_event = "EXIT" if ended else event
    if chosen_event not in {"HEARTBEAT", "EXIT"}:
        raise RuntimeObservationError("scheduler liveness adapter only accepts HEARTBEAT/EXIT")
    now = _utc(str(parsed.get("ended_at") or parsed.get("emitted_at")))
    out = _base(
        previous=previous,
        source=source,
        handler=handler,
        entrypoint=entrypoint,
        event=chosen_event,
        issue=int(parsed["issue"]),
        slot_id=None,
        claim_worker=lane,
        invocation_identity=str(parsed["invocation_identity"]),
        conversation_identity=None,
        branch=str(parsed["branch"]),
        head_sha=str(parsed["head_sha"]),
        action=None,
        record_fingerprint=None,
        observed_at=now,
    )
    if chosen_event == "HEARTBEAT":
        out["last_heartbeat_at"] = str(parsed["emitted_at"])
        out["heartbeat_expires_at"] = str(parsed["expires_at"])
        out["liveness_state"] = "LIVE"
    else:
        out["exit_at"] = str(parsed["ended_at"])
        out["exit_state"] = "ENDED"
        out["runtime_state"] = "ENDED"
        out["liveness_state"] = "ENDED"
    return out
