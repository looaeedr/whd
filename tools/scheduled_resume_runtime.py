"""Scheduled Resume runtime policy.

This module interprets one already-owned continuity checkpoint after the shared
GitHub lease has been acquired. It does not discover work and does not own the
scheduler. It only applies the state-specific policy frozen by #399/#403.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    transition_checkpoint,
)


DEFAULT_REMOTE_STALE_AFTER = timedelta(hours=2)
DEFAULT_BLOCKED_NOTIFY_THRESHOLD = 3
DEFAULT_BLOCKED_NOTIFY_BACKOFF = timedelta(hours=6)
_ACTIVE_REMOTE_STATUSES = frozenset(
    {"queued", "in_progress", "waiting", "requested", "pending"}
)


class ScheduledWakeDisposition(str, Enum):
    EXECUTE_NEXT_ACTION = "EXECUTE_NEXT_ACTION"
    CONTINUE_RECOVERY = "CONTINUE_RECOVERY"
    NO_OP = "NO_OP"
    NOTIFY_BLOCKER = "NOTIFY_BLOCKER"
    CLOSING_HANDOFF = "CLOSING_HANDOFF"


@dataclass(frozen=True)
class RemoteRunObservation:
    found: bool
    run_id: int
    head_sha: str
    status: str | None
    conclusion: str | None
    updated_at: datetime | None

    def __post_init__(self) -> None:
        if isinstance(self.run_id, bool) or not isinstance(self.run_id, int) or self.run_id <= 0:
            raise CheckpointError("remote observation run_id must be positive")
        head_sha = str(self.head_sha).strip()
        if not head_sha:
            raise CheckpointError("remote observation head_sha must be nonblank")
        object.__setattr__(self, "head_sha", head_sha)
        if self.updated_at is not None:
            if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
                raise CheckpointError("remote updated_at must be timezone-aware")
            object.__setattr__(
                self,
                "updated_at",
                self.updated_at.astimezone(timezone.utc),
            )


@dataclass(frozen=True)
class ScheduledWakeEvaluation:
    checkpoint: Checkpoint
    disposition: ScheduledWakeDisposition
    next_action: str | None = None
    notification: str | None = None
    reason: str = ""


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise CheckpointError("scheduled wake time must be timezone-aware")
    return now.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return (
        _normalize_now(value)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckpointError("blocked_last_notified_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CheckpointError("blocked_last_notified_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _recover_waiting_remote(checkpoint: Checkpoint, *, reason: str) -> ScheduledWakeEvaluation:
    next_action = (
        f"recover WAITING_REMOTE run {checkpoint.run_id}: {reason}; "
        "inspect exact evidence and continue from the durable checkpoint"
    )
    recovered = transition_checkpoint(
        checkpoint,
        state=ContinuityState.RECOVERING,
        next_action=next_action,
        evidence=(f"scheduled-resume WAITING_REMOTE recovery: {reason}",),
    )
    return ScheduledWakeEvaluation(
        checkpoint=recovered,
        disposition=ScheduledWakeDisposition.CONTINUE_RECOVERY,
        next_action=next_action,
        reason=reason,
    )


def _evaluate_waiting_remote(
    checkpoint: Checkpoint,
    *,
    now: datetime,
    remote: RemoteRunObservation | None,
    stale_after: timedelta,
) -> ScheduledWakeEvaluation:
    if remote is None:
        raise CheckpointError("WAITING_REMOTE scheduled wake requires fresh remote observation")

    if remote.run_id != checkpoint.run_id:
        return _recover_waiting_remote(
            checkpoint,
            reason=(
                f"run identity mismatch expected={checkpoint.run_id} "
                f"observed={remote.run_id}"
            ),
        )
    if not remote.found:
        return _recover_waiting_remote(
            checkpoint,
            reason=f"run {checkpoint.run_id} missing",
        )
    if remote.head_sha != checkpoint.head_sha:
        return _recover_waiting_remote(
            checkpoint,
            reason=(
                f"head mismatch expected={checkpoint.head_sha} "
                f"observed={remote.head_sha}"
            ),
        )

    status = (remote.status or "").strip().lower()
    conclusion = (remote.conclusion or "").strip().lower() or None
    if status == "completed" or conclusion is not None:
        return _recover_waiting_remote(
            checkpoint,
            reason=(
                f"run {checkpoint.run_id} terminal "
                f"status={status or 'unknown'} conclusion={conclusion or 'none'}"
            ),
        )

    if status not in _ACTIVE_REMOTE_STATUSES:
        return _recover_waiting_remote(
            checkpoint,
            reason=f"run {checkpoint.run_id} unexpected status={status or 'missing'}",
        )
    if remote.updated_at is None:
        return _recover_waiting_remote(
            checkpoint,
            reason=f"run {checkpoint.run_id} missing updated_at",
        )

    age = now - remote.updated_at
    if age > stale_after:
        return _recover_waiting_remote(
            checkpoint,
            reason=(
                f"run {checkpoint.run_id} stale for {int(age.total_seconds())}s "
                f"(threshold={int(stale_after.total_seconds())}s)"
            ),
        )

    return ScheduledWakeEvaluation(
        checkpoint=checkpoint,
        disposition=ScheduledWakeDisposition.NO_OP,
        reason=(
            f"run {checkpoint.run_id} still active and non-stale "
            f"(age={int(age.total_seconds())}s)"
        ),
    )


def _evaluate_blocked(
    checkpoint: Checkpoint,
    *,
    now: datetime,
    notify_threshold: int,
    notify_backoff: timedelta,
) -> ScheduledWakeEvaluation:
    if notify_threshold <= 0:
        raise CheckpointError("blocked notify threshold must be positive")
    if notify_backoff.total_seconds() <= 0:
        raise CheckpointError("blocked notify backoff must be positive")

    next_count = checkpoint.blocked_count + 1
    last_notified = (
        None
        if checkpoint.blocked_last_notified_at is None
        else _parse_utc(checkpoint.blocked_last_notified_at)
    )

    should_notify = next_count >= notify_threshold and (
        last_notified is None or now - last_notified >= notify_backoff
    )
    next_last_notified = _iso_utc(now) if should_notify else checkpoint.blocked_last_notified_at
    updated = transition_checkpoint(
        checkpoint,
        state=ContinuityState.BLOCKED,
        next_action=checkpoint.next_action,
        blocked_count=next_count,
        blocked_last_notified_at=next_last_notified,
    )

    if should_notify:
        return ScheduledWakeEvaluation(
            checkpoint=updated,
            disposition=ScheduledWakeDisposition.NOTIFY_BLOCKER,
            notification=checkpoint.next_action,
            reason="genuine blocker reached notification threshold/backoff",
        )
    return ScheduledWakeEvaluation(
        checkpoint=updated,
        disposition=ScheduledWakeDisposition.NO_OP,
        reason="genuine blocker retained silently below notification/backoff gate",
    )


def evaluate_scheduled_wake(
    checkpoint: Checkpoint,
    *,
    now: datetime,
    remote: RemoteRunObservation | None = None,
    remote_stale_after: timedelta = DEFAULT_REMOTE_STALE_AFTER,
    blocked_notify_threshold: int = DEFAULT_BLOCKED_NOTIFY_THRESHOLD,
    blocked_notify_backoff: timedelta = DEFAULT_BLOCKED_NOTIFY_BACKOFF,
) -> ScheduledWakeEvaluation:
    """Evaluate one scheduled wake after exact-owner/lease validation."""

    now = _normalize_now(now)
    if remote_stale_after.total_seconds() <= 0:
        raise CheckpointError("remote stale threshold must be positive")

    if checkpoint.state is ContinuityState.RUNNING:
        return ScheduledWakeEvaluation(
            checkpoint=checkpoint,
            disposition=ScheduledWakeDisposition.EXECUTE_NEXT_ACTION,
            next_action=checkpoint.next_action,
            reason="resume exact durable next_action after runtime cut",
        )
    if checkpoint.state is ContinuityState.WAITING_REMOTE:
        return _evaluate_waiting_remote(
            checkpoint,
            now=now,
            remote=remote,
            stale_after=remote_stale_after,
        )
    if checkpoint.state is ContinuityState.RECOVERING:
        return ScheduledWakeEvaluation(
            checkpoint=checkpoint,
            disposition=ScheduledWakeDisposition.CONTINUE_RECOVERY,
            next_action=checkpoint.next_action,
            reason="continue exact durable recovery action",
        )
    if checkpoint.state is ContinuityState.BLOCKED:
        return _evaluate_blocked(
            checkpoint,
            now=now,
            notify_threshold=blocked_notify_threshold,
            notify_backoff=blocked_notify_backoff,
        )
    if checkpoint.state in {
        ContinuityState.TERMINAL_SUCCESS,
        ContinuityState.TERMINAL_FAILURE,
    }:
        return ScheduledWakeEvaluation(
            checkpoint=checkpoint,
            disposition=ScheduledWakeDisposition.CLOSING_HANDOFF,
            reason="terminal checkpoint requires issue-closure-gate handoff before deactivation",
        )
    raise CheckpointError(f"unsupported continuity state: {checkpoint.state!r}")
