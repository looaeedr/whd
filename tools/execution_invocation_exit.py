"""Physical invocation exit classifier for WHD Flow v2.

Task terminal state and physical-runtime return are separate.  This classifier
is side-effect-free: when it returns a YIELD_REQUIRED decision, the caller must
execute an exact YIELD control transaction and then reclassify the resulting
record before returning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tools.execution_action_contract import OBSERVATION_ACTION_KINDS
from tools.execution_record import ExecutionRecord, execution_record_to_payload


SUBSTANTIVE_TRANSACTION_KINDS = frozenset({
    "START_BRANCH", "APPLY_COMMIT", "START_QA", "ACCEPT_QA", "CONSUME_QA", "MERGE", "HANDOFF", "FINALIZE", "RECONCILE", "BLOCK"
})
REMOTE_ACTIVE_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting", "requested"})


class InvocationExitError(ValueError):
    """Raised when invocation-exit inputs are malformed."""


@dataclass(frozen=True)
class InvocationExitDecision:
    decision: str
    may_return: bool
    requires_yield: bool
    issue: int
    next_action_kind: str | None
    active_run_id: int | None


def _text(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise InvocationExitError(f"{field} must be nonblank")
    return result


def _aware(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvocationExitError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvocationExitError(f"{field} must be timezone-aware")
    return parsed


def _decision(record: ExecutionRecord, name: str, *, may_return: bool, requires_yield: bool) -> InvocationExitDecision:
    return InvocationExitDecision(
        decision=name,
        may_return=may_return,
        requires_yield=requires_yield,
        issue=record.issue,
        next_action_kind=record.next_action.kind if record.next_action else None,
        active_run_id=record.active_run.id if record.active_run else None,
    )


def durable_terminal_exit_blockers(record: ExecutionRecord) -> tuple[str, ...]:
    """Return machine reasons that forbid a task-complete/terminal claim.

    Functional success is deliberately irrelevant here. QA GREEN, a merged PR,
    or a user-visible fix may all exist while the durable execution tail is still
    nonterminal. Only the canonical DONE tuple authorizes a completion claim.
    """
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")

    blockers: list[str] = []
    if record.state != "DONE":
        blockers.append("STATE_NOT_DONE")
    if record.next_action is not None:
        blockers.append("NEXT_ACTION_PENDING")
    if record.lease is not None:
        blockers.append("LEASE_NOT_CLEARED")
    if record.active_run is not None:
        blockers.append("ACTIVE_RUN_NOT_CLEARED")
    if record.owner_kind != "NONE" or record.owner_id != "NONE" or record.lane_id is not None:
        blockers.append("OWNER_NOT_CLEARED")
    if not record.closure.issue_closed:
        blockers.append("ISSUE_NOT_CLOSED")
    if record.closure.released_at is None:
        blockers.append("RELEASE_NOT_RECORDED")
    if record.mutation_scope is not None and record.mutation_scope.reservation_state != "RELEASED":
        blockers.append("PATH_RESERVATION_NOT_RELEASED")
    return tuple(blockers)


def assert_durable_terminal_exit(record: ExecutionRecord) -> bool:
    """Fail closed unless record proves the canonical durable terminal tuple."""
    blockers = durable_terminal_exit_blockers(record)
    if blockers:
        raise InvocationExitError(
            "DURABLE_TERMINAL_EXIT_BLOCKED: " + ",".join(blockers)
        )
    return True


def assert_repository_content_cycle_complete(
    record: ExecutionRecord,
    *,
    source_manifest: object,
    workspace_location: str,
) -> bool:
    """Fail closed until execution DONE is followed by durable root cleanup.

    ``assert_durable_terminal_exit`` proves only the Flow v2 execution tuple.
    Repository-content work is not user-visible/physical-cycle complete until
    the exact source export has been written/read back and the issue workspace
    has left ``/work/active``.
    """
    assert_durable_terminal_exit(record)
    from tools.post_integration_durability import classify_post_integration_durability

    result = classify_post_integration_durability(
        execution_record=execution_record_to_payload(record),
        source_manifest=source_manifest,
        workspace_location=workspace_location,
    )
    if result.get("state") != "DURABLE_CLEANUP_COMPLETE":
        next_action = str(result.get("next_action") or "UNKNOWN")
        raise InvocationExitError(f"POST_INTEGRATION_DURABILITY_PENDING:{next_action}")
    return True

def terminal_tail_active(record: ExecutionRecord) -> bool:
    """Return whether the record crossed the no-yield terminal-tail boundary."""
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    if record.next_action is None:
        return False
    if record.next_action.kind == "FINALIZE":
        return True
    return (
        record.next_action.kind == "MERGE"
        and record.qa.last_accepted_run is not None
        and record.qa.accepted_head_sha == record.head_sha
    )

def classify_invocation_exit(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
    now: str,
    host_boundary: bool = False,
) -> InvocationExitDecision:
    """Classify whether this physical invocation may return.

    A non-terminal owner never gains return authority from a progress message.
    YIELD_REQUIRED is not permission to return: the exact YIELD transaction must
    first be durably reconciled, after which this function returns ``YIELDED``.
    """
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    invocation = _text(invocation_identity, "invocation_identity")
    now_dt = _aware(now, "now")

    if record.state == "DONE":
        assert_durable_terminal_exit(record)
        return _decision(record, "TASK_TERMINAL", may_return=True, requires_yield=False)

    if record.lease is None:
        tx = record.transaction
        if (
            tx is not None
            and tx.status == "RECONCILED"
            and tx.kind == "YIELD"
            and tx.invocation_identity == invocation
        ):
            return _decision(record, "YIELDED", may_return=True, requires_yield=False)
        return _decision(record, "ACQUIRE_REQUIRED", may_return=False, requires_yield=False)

    expires_at = _aware(record.lease.expires_at, "lease.expires_at")
    if record.lease.invocation_identity != invocation:
        if expires_at > now_dt:
            return _decision(record, "LANE_BUSY", may_return=True, requires_yield=False)
        return _decision(record, "ACQUIRE_REQUIRED", may_return=False, requires_yield=False)
    if expires_at <= now_dt:
        return _decision(record, "ACQUIRE_REQUIRED", may_return=False, requires_yield=False)

    if record.state == "BLOCKED" and record.blocker is not None:
        return _decision(record, "YIELD_REQUIRED_BLOCKED", may_return=False, requires_yield=True)

    if record.active_run is not None and record.next_action is not None:
        run_status = str(record.active_run.status or "").strip().lower()
        if record.next_action.kind == "POLL_QA" and record.next_action.kind in OBSERVATION_ACTION_KINDS and run_status in REMOTE_ACTIVE_STATUSES:
            return _decision(record, "YIELD_REQUIRED_REMOTE_WAIT", may_return=False, requires_yield=True)

    if terminal_tail_active(record):
        return _decision(
            record,
            "CONTINUE_TERMINAL_TAIL",
            may_return=False,
            requires_yield=False,
        )

    tx = record.transaction
    current_substantive = (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.invocation_identity == invocation
        and tx.kind in SUBSTANTIVE_TRANSACTION_KINDS
    )
    if host_boundary and current_substantive:
        return _decision(record, "YIELD_REQUIRED_HOST_BOUNDARY", may_return=False, requires_yield=True)

    if host_boundary and record.owner_kind == "SCHEDULER":
        return _decision(
            record,
            "SCHEDULER_EXECUTION_NO_PROGRESS",
            may_return=False,
            requires_yield=False,
        )

    return _decision(record, "CONTINUE_EXECUTION", may_return=False, requires_yield=False)
