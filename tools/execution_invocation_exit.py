"""Physical invocation exit classifier for WHD Flow v2.

Task terminal state and physical-runtime return are separate.  This classifier
is side-effect-free: when it returns a YIELD_REQUIRED decision, the caller must
execute an exact YIELD control transaction and then reclassify the resulting
record before returning.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from tools.execution_action_contract import ACTION_TRANSACTION_KIND, OBSERVATION_ACTION_KINDS
from tools.execution_record import (
    ExecutionRecord,
    execution_record_fingerprint,
    execution_record_to_payload,
)


SUBSTANTIVE_TRANSACTION_KINDS = frozenset({
    "START_BRANCH", "APPLY_COMMIT", "START_QA", "ACCEPT_QA", "CONSUME_QA", "MERGE", "HANDOFF", "FINALIZE", "RECONCILE", "BLOCK"
})
REMOTE_ACTIVE_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting", "requested"})
REMOTE_QA_ACTIVE_OBSERVATION_BUDGET = 1
HOST_EXIT_PROOF_SCHEMA = "WHD_FLOW_V2_HOST_EXIT_PROOF_V1"
HOST_EXIT_PROOF_VERSION = 1
HOST_EXIT_PROOF_TTL_SECONDS = 60


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


def assert_remote_qa_active_observation_budget(
    *,
    observation_count: int,
    run_status: str,
) -> bool:
    """Reject same-invocation busy polling of one active remote QA run."""
    if isinstance(observation_count, bool) or not isinstance(observation_count, int):
        raise InvocationExitError("observation_count must be an integer")
    if observation_count <= 0:
        raise InvocationExitError("observation_count must be positive")
    status = _text(run_status, "run_status").lower()
    if status in REMOTE_ACTIVE_STATUSES and observation_count > REMOTE_QA_ACTIVE_OBSERVATION_BUDGET:
        raise InvocationExitError(
            "REMOTE_QA_POLL_BUDGET_EXHAUSTED "
            f"observation_count={observation_count} budget={REMOTE_QA_ACTIVE_OBSERVATION_BUDGET} "
            f"run_status={status}"
        )
    return True


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
    root_sync_receipt: object | None = None,
    lane_delivery_receipt: object | None = None,
) -> bool:
    """Require trusted DONE/closure evidence for ordinary workspace delivery.

    Root sync/recovery is optional maintenance and is non-blocking for terminal
    return. The current workspace workflow has no Current Source
    snapshot/manifest or per-Issue workspace archival completion authority.
    """
    assert_durable_terminal_exit(record)
    from tools.post_integration_durability import classify_post_integration_durability

    result = classify_post_integration_durability(
        execution_record=execution_record_to_payload(record),
        root_sync_receipt=root_sync_receipt,
        lane_delivery_receipt=lane_delivery_receipt,
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

FOREIGN_READ_ONLY_ACTIONS = frozenset({
    "READ_ONLY_DISCOVERY",
    "READ_ONLY_STATUS",
})
TERMINAL_TAIL_FOREIGN_READ_ONLY_ACTIONS = FOREIGN_READ_ONLY_ACTIONS


def _yielded_nonterminal_leaf(record: ExecutionRecord) -> bool:
    """Return whether this leaf durably yielded and has no active writer lease."""
    if record.state == "DONE" or record.lease is not None or terminal_tail_active(record):
        return False
    tx = record.transaction
    return (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.kind == "YIELD"
    )


def _durable_owning_identity_active(record: ExecutionRecord) -> bool:
    return (
        record.state != "DONE"
        and record.owner_kind != "NONE"
        and record.owner_id != "NONE"
        and not _yielded_nonterminal_leaf(record)
    )


def released_stale_reset_residue(
    record: ExecutionRecord,
    *,
    observed_at: str,
) -> bool:
    """Return whether a nonterminal record is only stale RELEASED residue.

    This classification is deliberately side-effect-free and uses only durable
    ExecutionRecord facts.  Work-branch absence remains a trusted GitHub
    readback owned by the RELEASE_PATHS cleanup seam; this helper never grants
    cleanup authority by itself.
    """
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    observed = _aware(observed_at, "observed_at")
    if record.state == "DONE" or terminal_tail_active(record):
        return False
    scope = record.mutation_scope
    if scope is None or scope.reservation_state != "RELEASED":
        return False
    if record.lease is None:
        return False
    if _aware(record.lease.expires_at, "lease.expires_at") >= observed:
        return False
    if record.active_run is not None:
        return False
    if record.qa.last_accepted_run is not None or record.qa.accepted_head_sha is not None:
        return False
    return True


def assert_active_owning_issue_sticky(
    record: ExecutionRecord,
    *,
    requested_issue: int,
    requested_action_kind: str,
) -> bool:
    """Forbid foreign mutations while this durable owning Issue is nonterminal.

    This is the general owning-Issue gate.  The existing terminal-tail gate is
    intentionally stronger and keeps its more specific failure identity.
    """
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    if isinstance(requested_issue, bool) or not isinstance(requested_issue, int) or requested_issue <= 0:
        raise InvocationExitError("requested_issue must be a positive issue number")
    action = _text(requested_action_kind, "requested_action_kind")
    if requested_issue == record.issue or not _durable_owning_identity_active(record):
        return True
    if action in FOREIGN_READ_ONLY_ACTIONS:
        return True
    if terminal_tail_active(record):
        return assert_terminal_tail_owning_issue_sticky(
            record,
            requested_issue=requested_issue,
            requested_action_kind=action,
        )
    raise InvocationExitError(
        "ACTIVE_OWNING_ISSUE_NO_PIVOT "
        f"current_issue={record.issue} foreign_issue={requested_issue} "
        f"requested_action={action}"
    )


def assert_terminal_tail_owning_issue_sticky(
    record: ExecutionRecord,
    *,
    requested_issue: int,
    requested_action_kind: str,
) -> bool:
    """Forbid unrelated Issue work from preempting an active terminal tail.

    Read-only discovery/status is allowed so stale coordination debt can be
    observed and handed off later. Any foreign Flow/control mutation must wait
    until the current owning Issue leaves terminal tail.
    """
    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    if isinstance(requested_issue, bool) or not isinstance(requested_issue, int) or requested_issue <= 0:
        raise InvocationExitError("requested_issue must be a positive issue number")
    action = _text(requested_action_kind, "requested_action_kind")
    if not terminal_tail_active(record) or requested_issue == record.issue:
        return True
    if action in TERMINAL_TAIL_FOREIGN_READ_ONLY_ACTIONS:
        return True
    raise InvocationExitError(
        "TERMINAL_TAIL_NO_PIVOT "
        f"current_issue={record.issue} foreign_issue={requested_issue} "
        f"requested_action={action}"
    )

def build_host_exit_proof(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
    now: str,
    root_sync_receipt: object | None = None,
    lane_delivery_receipt: object | None = None,
    remote_qa_active_observation_count: int = 1,
    alternative_executable_leaf_count: int = 0,
) -> dict[str, object]:
    """Mint a short-lived proof only when the canonical host boundary may return.

    The proof is bound to the exact ExecutionRecord fingerprint and invocation.
    It is not durable authority by itself: every consumer must revalidate it
    against a fresh record and re-run classify_invocation_exit.
    """

    decision = classify_invocation_exit(
        record,
        invocation_identity=invocation_identity,
        now=now,
        host_boundary=True,
        root_sync_receipt=root_sync_receipt,
        lane_delivery_receipt=lane_delivery_receipt,
        remote_qa_active_observation_count=remote_qa_active_observation_count,
        alternative_executable_leaf_count=alternative_executable_leaf_count,
    )
    if not decision.may_return:
        raise InvocationExitError(
            "HOST_EXIT_BLOCKED "
            f"decision={decision.decision} "
            f"next_action={decision.next_action_kind or 'NONE'}"
        )
    if decision.requires_yield:
        raise InvocationExitError(
            "HOST_EXIT_BLOCKED classifier returned may_return with requires_yield"
        )
    classified_at = _aware(now, "now").isoformat().replace("+00:00", "Z")
    return {
        "schema": HOST_EXIT_PROOF_SCHEMA,
        "version": HOST_EXIT_PROOF_VERSION,
        "issue": record.issue,
        "generation": record.generation,
        "invocation_identity": _text(invocation_identity, "invocation_identity"),
        "record_fingerprint": execution_record_fingerprint(record),
        "decision": decision.decision,
        "may_return": True,
        "requires_yield": False,
        "next_action_kind": decision.next_action_kind,
        "active_run_id": decision.active_run_id,
        "classified_at": classified_at,
        "remote_qa_active_observation_count": remote_qa_active_observation_count,
        "alternative_executable_leaf_count": alternative_executable_leaf_count,
    }


def validate_host_exit_proof(
    proof: object,
    record: ExecutionRecord,
    *,
    invocation_identity: str,
    now: str,
    root_sync_receipt: object | None = None,
    lane_delivery_receipt: object | None = None,
) -> dict[str, object]:
    """Fail closed unless proof still authorizes this exact host return."""

    if not isinstance(record, ExecutionRecord):
        raise InvocationExitError("record must be an ExecutionRecord")
    if not isinstance(proof, Mapping):
        raise InvocationExitError("host exit proof must be an object")
    item = {str(key): value for key, value in proof.items()}
    if item.get("schema") != HOST_EXIT_PROOF_SCHEMA:
        raise InvocationExitError("host exit proof schema mismatch")
    if item.get("version") != HOST_EXIT_PROOF_VERSION:
        raise InvocationExitError("host exit proof version mismatch")
    invocation = _text(invocation_identity, "invocation_identity")
    if item.get("invocation_identity") != invocation:
        raise InvocationExitError("host exit proof invocation mismatch")
    if item.get("issue") != record.issue:
        raise InvocationExitError("host exit proof issue mismatch")
    if item.get("generation") != record.generation:
        raise InvocationExitError("host exit proof generation mismatch")
    if item.get("record_fingerprint") != execution_record_fingerprint(record):
        raise InvocationExitError("host exit proof record fingerprint mismatch")
    if item.get("may_return") is not True or item.get("requires_yield") is not False:
        raise InvocationExitError("host exit proof does not authorize return")

    classified_at = _aware(item.get("classified_at"), "host exit proof classified_at")
    now_dt = _aware(now, "now")
    age = (now_dt - classified_at).total_seconds()
    if age < 0:
        raise InvocationExitError("host exit proof is from the future")
    if age > HOST_EXIT_PROOF_TTL_SECONDS:
        raise InvocationExitError("host exit proof expired")

    observation_count = item.get("remote_qa_active_observation_count", 1)
    alternative_count = item.get("alternative_executable_leaf_count", 0)
    if isinstance(observation_count, bool) or not isinstance(observation_count, int):
        raise InvocationExitError("host exit proof remote observation count is invalid")
    if isinstance(alternative_count, bool) or not isinstance(alternative_count, int):
        raise InvocationExitError("host exit proof alternative leaf count is invalid")

    current = classify_invocation_exit(
        record,
        invocation_identity=invocation,
        now=now,
        host_boundary=True,
        root_sync_receipt=root_sync_receipt,
        lane_delivery_receipt=lane_delivery_receipt,
        remote_qa_active_observation_count=observation_count,
        alternative_executable_leaf_count=alternative_count,
    )
    if not current.may_return or current.requires_yield:
        raise InvocationExitError(
            "HOST_EXIT_PROOF_NO_LONGER_RETURNABLE "
            f"decision={current.decision}"
        )
    if item.get("decision") != current.decision:
        raise InvocationExitError("host exit proof decision drift")
    if item.get("next_action_kind") != current.next_action_kind:
        raise InvocationExitError("host exit proof next_action drift")
    if item.get("active_run_id") != current.active_run_id:
        raise InvocationExitError("host exit proof active_run drift")
    return item


def classify_invocation_exit(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
    now: str,
    host_boundary: bool = False,
    root_sync_receipt: object | None = None,
    lane_delivery_receipt: object | None = None,
    remote_qa_active_observation_count: int = 1,
    alternative_executable_leaf_count: int = 0,
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
    if (
        isinstance(alternative_executable_leaf_count, bool)
        or not isinstance(alternative_executable_leaf_count, int)
        or alternative_executable_leaf_count < 0
    ):
        raise InvocationExitError("alternative_executable_leaf_count must be a non-negative integer")

    if record.state == "DONE":
        assert_durable_terminal_exit(record)
        if record.mutation_scope is not None:
            assert_repository_content_cycle_complete(
                record,
                root_sync_receipt=root_sync_receipt,
                lane_delivery_receipt=lane_delivery_receipt,
            )
        return _decision(record, "TASK_TERMINAL", may_return=True, requires_yield=False)

    if record.lease is None:
        tx = record.transaction
        if (
            tx is not None
            and tx.status == "RECONCILED"
            and tx.kind == "YIELD"
            and tx.invocation_identity == invocation
        ):
            if alternative_executable_leaf_count > 0:
                return _decision(
                    record,
                    "CONTINUE_OTHER_EXECUTABLE_LEAF",
                    may_return=False,
                    requires_yield=False,
                )
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
            assert_remote_qa_active_observation_budget(
                observation_count=remote_qa_active_observation_count,
                run_status=run_status,
            )
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
    if (
        host_boundary
        and current_substantive
        and record.next_action is not None
        and record.next_action.kind in ACTION_TRANSACTION_KIND
        and record.next_action.kind != "YIELD"
    ):
        return _decision(record, "CONTINUE_EXECUTION", may_return=False, requires_yield=False)

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
