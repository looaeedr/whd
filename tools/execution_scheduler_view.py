"""Read-only scheduler decision projection for WHD Flow v2.

This module never claims, leases, selects, or mutates work.  It projects the
canonical ExecutionRecord set into the smallest deterministic scheduler wake
decision needed for execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_ready_index import (
    ExecutionReadyIndex,
    ReadyIndexError,
    build_ready_index,
    validate_ready_index,
)
from tools.execution_record import ExecutionRecord, execution_record_fingerprint
from tools.issue_comment_progress import evaluate_issue_comment_intervention
from tools.scheduler_ready_ingress import SchedulerDispatchCandidate


DECISIONS = frozenset({
    "RESUME_CURRENT",
    "LANE_BUSY",
    "TAKEOVER_CANDIDATE",
    "READY_CANDIDATES",
    "INGRESS_REQUIRED",
    "NO_EXECUTABLE_WORK",
})
LEASE_STATUSES = frozenset({
    "NONE",
    "CURRENT_INVOCATION",
    "ACTIVE_OTHER_INVOCATION",
    "EXPIRED",
})


class SchedulerViewError(ValueError):
    """Raised when canonical records cannot produce one safe scheduler view."""


@dataclass(frozen=True)
class SchedulerView:
    decision: str
    lane_id: str
    invocation_identity: str
    current_issue: int | None
    current_record_fingerprint: str | None
    current_state: str | None
    next_action_kind: str | None
    next_action_display: str | None
    lease_status: str | None
    active_run_id: int | None
    ready_issues: tuple[int, ...]
    selected_issue: int | None
    requires_transaction: str | None
    takeover_issues: tuple[int, ...] = ()
    takeover_from_owner_id: str | None = None
    takeover_reason: str | None = None


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SchedulerViewError(f"{field} must be nonblank")
    return text


def _aware_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchedulerViewError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchedulerViewError(f"{field} must be timezone-aware")
    return parsed


def _current_for_lane(records: tuple[ExecutionRecord, ...], lane_id: str) -> ExecutionRecord | None:
    matches: list[ExecutionRecord] = []
    for record in records:
        if not isinstance(record, ExecutionRecord):
            raise SchedulerViewError("all records must be ExecutionRecord instances")
        if record.state == "DONE":
            continue

        points_to_lane = record.lane_id == lane_id or (
            record.owner_kind == "SCHEDULER" and record.owner_id == lane_id
        )
        if points_to_lane:
            if not (
                record.owner_kind == "SCHEDULER"
                and record.owner_id == lane_id
                and record.lane_id == lane_id
            ):
                raise SchedulerViewError(
                    f"owner/lane identity mismatch for issue {record.issue}: "
                    f"owner_kind={record.owner_kind!r} owner_id={record.owner_id!r} "
                    f"lane_id={record.lane_id!r}"
                )
            matches.append(record)

    if len(matches) > 1:
        issues = ",".join(str(record.issue) for record in sorted(matches, key=lambda item: item.issue))
        raise SchedulerViewError(f"multiple same-lane nonterminal records: {issues}")
    return matches[0] if matches else None


def _lease_status(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
    now: datetime,
) -> tuple[str, str | None]:
    if record.lease is None:
        return "NONE", "ACQUIRE"
    if record.lease.invocation_identity == invocation_identity:
        return "CURRENT_INVOCATION", None
    expires_at = _aware_timestamp(record.lease.expires_at, "lease expires_at")
    if expires_at > now:
        return "ACTIVE_OTHER_INVOCATION", None
    return "EXPIRED", "ACQUIRE"


@dataclass(frozen=True)
class _TakeoverCandidate:
    record: ExecutionRecord
    reason: str


def _takeover_candidates(
    records: tuple[ExecutionRecord, ...],
    *,
    lane_id: str,
    issue_comments: Mapping[int, Iterable[Mapping[str, object]]],
    trusted_comment_authors: frozenset[str],
    now: datetime,
) -> tuple[_TakeoverCandidate, ...]:
    """Only verified owning-Issue comments determine the intervention timer.

    Runtime heartbeat, lease, END and family state are NOT time classifiers.
    Flow v2 CAS / single-writer fencing still governs actual ownership transfer.
    """
    candidates: list[_TakeoverCandidate] = []
    for record in records:
        if (
            record.state in {"READY", "DONE", "BLOCKED"}
            or record.execution_intent != "SCHEDULER_LANE"
            or record.owner_id in {"NONE", "UNCLAIMED"}
            or record.lane_id == lane_id
        ):
            continue
        action = record.next_action
        if action is None:
            continue
        try:
            validate_execution_action(action)
        except ActionContractError as exc:
            raise SchedulerViewError(
                f"issue {record.issue} has non-executable next_action: {exc}"
            ) from exc

        verdict = evaluate_issue_comment_intervention(
            record,
            issue_comments.get(record.issue, ()),
            now=now,
            trusted_authors=trusted_comment_authors,
        )
        if not verdict.eligible:
            continue
        candidates.append(
            _TakeoverCandidate(
                record=record,
                reason=verdict.reason,
            )
        )
    candidates.sort(key=lambda item: item.record.issue)
    return tuple(candidates)


def build_takeover_handoff_effect(view: SchedulerView) -> dict[str, object]:
    """Build the only legal routing mutation for a scheduler takeover decision."""
    if view.decision != "TAKEOVER_CANDIDATE" or view.selected_issue is None:
        raise SchedulerViewError("scheduler view is not a takeover candidate")
    return {
        "owner_kind": "SCHEDULER",
        "owner_id": view.lane_id,
        "lane_id": view.lane_id,
    }


def build_scheduler_view(
    records: Iterable[ExecutionRecord],
    *,
    lane_id: str,
    invocation_identity: str,
    now: str,
    ready_index: ExecutionReadyIndex | None = None,
    dispatch_candidates: Iterable[SchedulerDispatchCandidate] = (),
    runtime_observations: Mapping[str, Mapping[str, object] | None] | None = None,
    issue_comments: Mapping[int, Iterable[Mapping[str, object]]] | None = None,
    trusted_comment_authors: Iterable[str] = (),
) -> SchedulerView:
    """Build a deterministic, side-effect-free scheduler wake projection.

    Priority is always same-lane non-terminal continuity.  Only when that is
    absent may READY cache entries be exposed.  READY entries are already
    deterministically ordered by Issue number, so the first entry is selected
    as the exact ACQUIRE candidate.  Selection is routing only and never grants
    execution authority; the trusted ACQUIRE transaction still decides the race.
    """

    lane_id = _required_text(lane_id, "lane_id")
    invocation_identity = _required_text(invocation_identity, "invocation_identity")
    now_dt = _aware_timestamp(_required_text(now, "now"), "now")
    materialized = tuple(records)

    current = _current_for_lane(materialized, lane_id)
    if current is not None:
        status, required_tx = _lease_status(
            current,
            invocation_identity=invocation_identity,
            now=now_dt,
        )
        decision = "LANE_BUSY" if status == "ACTIVE_OTHER_INVOCATION" else "RESUME_CURRENT"
        action = current.next_action
        if action is not None:
            try:
                validate_execution_action(action)
            except ActionContractError as exc:
                raise SchedulerViewError(
                    f"issue {current.issue} has non-executable next_action: {exc}"
                ) from exc
        return SchedulerView(
            decision=decision,
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            current_issue=current.issue,
            current_record_fingerprint=execution_record_fingerprint(current),
            current_state=current.state,
            next_action_kind=action.kind if action else None,
            next_action_display=action.display if action else None,
            lease_status=status,
            active_run_id=current.active_run.id if current.active_run else None,
            ready_issues=(),
            selected_issue=None,
            requires_transaction=required_tx,
        )

    # An absent/unfetched comment feed can NEVER mean an expired worker.
    # runtime_observations remains for observability compatibility only.
    takeover = _takeover_candidates(
        materialized,
        lane_id=lane_id,
        issue_comments=issue_comments or {},
        trusted_comment_authors=frozenset(trusted_comment_authors),
        now=now_dt,
    )
    if takeover:
        selected = takeover[0]
        record = selected.record
        status, _ = _lease_status(
            record,
            invocation_identity=invocation_identity,
            now=now_dt,
        )
        return SchedulerView(
            decision="TAKEOVER_CANDIDATE",
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            current_issue=None,
            current_record_fingerprint=execution_record_fingerprint(record),
            current_state=record.state,
            next_action_kind=record.next_action.kind if record.next_action else None,
            next_action_display=record.next_action.display if record.next_action else None,
            lease_status=status,
            active_run_id=None,
            ready_issues=(),
            selected_issue=record.issue,
            requires_transaction="HANDOFF",
            takeover_issues=tuple(item.record.issue for item in takeover),
            takeover_from_owner_id=record.owner_id,
            takeover_reason=selected.reason,
        )

    if ready_index is None:
        try:
            ready_index = build_ready_index(materialized)
        except ReadyIndexError as exc:
            raise SchedulerViewError(str(exc)) from exc
    else:
        try:
            valid = validate_ready_index(ready_index, materialized)
        except ReadyIndexError as exc:
            raise SchedulerViewError(str(exc)) from exc
        if not valid:
            raise SchedulerViewError("stale ready index does not match canonical execution records")

    ready_issues = tuple(
        entry.issue
        for entry in ready_index.entries
        if entry.execution_intent == "SCHEDULER_LANE"
    )
    if ready_issues:
        return SchedulerView(
            decision="READY_CANDIDATES",
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            current_issue=None,
            current_record_fingerprint=None,
            current_state=None,
            next_action_kind="ACQUIRE",
            next_action_display=f"Acquire Issue #{ready_issues[0]}",
            lease_status=None,
            active_run_id=None,
            ready_issues=ready_issues,
            selected_issue=ready_issues[0],
            requires_transaction="ACQUIRE",
        )

    record_issues = {record.issue for record in materialized}
    eligible_dispatch: list[SchedulerDispatchCandidate] = []
    for candidate in dispatch_candidates:
        if not isinstance(candidate, SchedulerDispatchCandidate):
            raise SchedulerViewError("dispatch_candidates must contain SchedulerDispatchCandidate objects")
        if candidate.issue in record_issues:
            continue
        if candidate.matches_lane(lane_id):
            eligible_dispatch.append(candidate)
    eligible_dispatch.sort(key=lambda item: item.issue)
    if eligible_dispatch:
        selected = eligible_dispatch[0]
        return SchedulerView(
            decision="INGRESS_REQUIRED",
            lane_id=lane_id,
            invocation_identity=invocation_identity,
            current_issue=None,
            current_record_fingerprint=None,
            current_state=None,
            next_action_kind="DISPATCH_READY",
            next_action_display=f"Create READY ingress for Issue #{selected.issue}",
            lease_status=None,
            active_run_id=None,
            ready_issues=(),
            selected_issue=selected.issue,
            requires_transaction="DISPATCH_READY",
        )

    return SchedulerView(
        decision="NO_EXECUTABLE_WORK",
        lane_id=lane_id,
        invocation_identity=invocation_identity,
        current_issue=None,
        current_record_fingerprint=None,
        current_state=None,
        next_action_kind=None,
        next_action_display=None,
        lease_status=None,
        active_run_id=None,
        ready_issues=(),
        selected_issue=None,
        requires_transaction=None,
    )
