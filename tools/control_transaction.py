"""Pure WHD Flow v2 atomic control-transaction semantics.

This module deliberately owns only deterministic execution-record transitions.
It does not call GitHub, Drive, Actions, or any other side-effecting transport.
A trusted executor can use ``prepare_transaction`` to bind an exact record and
``execute_transaction`` after performing/reading back one deterministic effect.

There is no persisted "GREEN but not yet consumed" authorization state. A
successful transition records only the reconciled transaction result.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Mapping

from tools.execution_invocation_exit import classify_invocation_exit
from tools.execution_record import (
    ActionSpec,
    BlockerState,
    ChainState,
    ClosureState,
    ExecutionRecord,
    LeaseState,
    QAState,
    RunState,
    TransactionState,
    execution_record_fingerprint,
)


TARGET_ADVANCE_PROOF_SCHEMA = "WHD_FLOW_V2_TARGET_ADVANCE_PROOF_V1"


TRANSACTION_KINDS = frozenset(
    {
        "ACQUIRE",
        "START_BRANCH",
        "APPLY_COMMIT",
        "START_QA",
        "ACCEPT_QA",
        "FAIL_QA",
        "BLOCK",
        "MERGE",
        "SYNC_TARGET",
        "HANDOFF",
        "FINALIZE",
        "RECONCILE",
        "YIELD",
    }
)


class ControlTransactionError(RuntimeError):
    """Base class for invalid atomic control transactions."""


class ControlTransactionConflict(ControlTransactionError):
    """Raised when optimistic-concurrency identity no longer matches."""


class ControlTransactionReplay(ControlTransactionError):
    """Raised when a reconciled transaction is submitted again."""


@dataclass(frozen=True)
class ControlTransactionPlan:
    transaction_id: str
    kind: str
    issue: int
    expected_generation: int
    expected_fingerprint: str
    expected_work_branch: str
    expected_head_sha: str
    expected_target_sha: str
    invocation_identity: str | None = None


def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip()
    if not text:
        if optional:
            return None
        raise ControlTransactionError(f"{name} must be nonblank")
    return text


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ControlTransactionError(f"{name} must be an object")
    return value


def _action(value: object, name: str = "next_action", *, optional: bool = False) -> ActionSpec | None:
    if value is None and optional:
        return None
    if isinstance(value, ActionSpec):
        return value
    payload = _mapping(value, name)
    args = payload.get("args", {})
    if not isinstance(args, Mapping):
        raise ControlTransactionError(f"{name}.args must be an object")
    return ActionSpec(
        kind=_text(payload.get("kind"), f"{name}.kind"),
        args={str(k): v for k, v in args.items()},
        display=str(payload.get("display") or "").strip(),
    )


def _lease(value: object, *, optional: bool = False) -> LeaseState | None:
    if value is None and optional:
        return None
    if isinstance(value, LeaseState):
        return value
    payload = _mapping(value, "lease")
    return LeaseState(
        token=_text(payload.get("token"), "lease.token"),
        invocation_identity=_text(
            payload.get("invocation_identity"), "lease.invocation_identity"
        ),
        expires_at=_text(payload.get("expires_at"), "lease.expires_at"),
    )


def _updated_at(effect: Mapping[str, object]) -> str:
    return _text(effect.get("updated_at"), "effect.updated_at")


def _aware_timestamp(value: object, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlTransactionError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ControlTransactionError(f"{name} must be timezone-aware")
    return parsed


def _reconciled_transaction(plan: ControlTransactionPlan) -> TransactionState:
    return TransactionState(
        id=plan.transaction_id,
        kind=plan.kind,
        status="RECONCILED",
        expected_fingerprint=plan.expected_fingerprint,
        invocation_identity=plan.invocation_identity,
    )


def prepare_transaction(
    record: ExecutionRecord,
    *,
    kind: str,
    transaction_id: str,
    invocation_identity: str | None = None,
) -> ControlTransactionPlan:
    """Bind one transaction to the exact current execution-record identity."""
    if not isinstance(record, ExecutionRecord):
        raise ControlTransactionError("record must be an ExecutionRecord")
    tx_kind = _text(kind, "transaction kind")
    if tx_kind not in TRANSACTION_KINDS:
        raise ControlTransactionError(
            f"transaction kind must be one of {sorted(TRANSACTION_KINDS)}"
        )
    tx_id = _text(transaction_id, "transaction_id")
    invocation = _text(invocation_identity, "invocation_identity", optional=True)
    return ControlTransactionPlan(
        transaction_id=tx_id,
        kind=tx_kind,
        issue=record.issue,
        expected_generation=record.generation,
        expected_fingerprint=execution_record_fingerprint(record),
        expected_work_branch=record.work_branch,
        expected_head_sha=record.head_sha,
        expected_target_sha=record.target_sha,
        invocation_identity=invocation,
    )


def _assert_plan_matches(record: ExecutionRecord, plan: ControlTransactionPlan) -> None:
    if record.transaction is not None and record.transaction.id == plan.transaction_id:
        if record.transaction.status == "RECONCILED":
            raise ControlTransactionReplay(
                f"transaction {plan.transaction_id} already applied and reconciled"
            )
    if record.issue != plan.issue:
        raise ControlTransactionConflict(
            f"issue drift: expected {plan.issue}, observed {record.issue}"
        )
    if record.generation != plan.expected_generation:
        raise ControlTransactionConflict(
            "generation drift: "
            f"expected {plan.expected_generation}, observed {record.generation}"
        )
    current_fingerprint = execution_record_fingerprint(record)
    if current_fingerprint != plan.expected_fingerprint:
        raise ControlTransactionConflict(
            "fingerprint drift: "
            f"expected {plan.expected_fingerprint}, observed {current_fingerprint}"
        )
    if record.work_branch != plan.expected_work_branch:
        raise ControlTransactionConflict(
            f"branch drift: expected {plan.expected_work_branch}, observed {record.work_branch}"
        )
    if record.head_sha != plan.expected_head_sha:
        raise ControlTransactionConflict(
            f"head drift: expected {plan.expected_head_sha}, observed {record.head_sha}"
        )
    if record.target_sha != plan.expected_target_sha:
        raise ControlTransactionConflict(
            f"target drift: expected {plan.expected_target_sha}, observed {record.target_sha}"
        )


def _base_update(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
    **changes: object,
) -> ExecutionRecord:
    return replace(
        record,
        generation=record.generation + 1,
        transaction=_reconciled_transaction(plan),
        updated_at=_updated_at(effect),
        **changes,
    )


def _execute_acquire(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state == "DONE":
        raise ControlTransactionError("ACQUIRE cannot mutate DONE record")

    lease = _lease(effect.get("lease"))
    observed_at = _aware_timestamp(effect.get("observed_at"), "observed_at")
    lease_expires = _aware_timestamp(lease.expires_at, "lease.expires_at")
    if lease_expires <= observed_at:
        raise ControlTransactionError("ACQUIRE new lease must expire after observed_at")
    if plan.invocation_identity is not None and lease.invocation_identity != plan.invocation_identity:
        raise ControlTransactionError("ACQUIRE lease invocation must match transaction invocation")

    owner_kind = _text(effect.get("owner_kind"), "owner_kind")
    owner_id = _text(effect.get("owner_id"), "owner_id")
    lane_id = _text(effect.get("lane_id"), "lane_id", optional=True)
    slot_id = _text(effect.get("slot_id"), "slot_id", optional=True)
    next_action = _action(effect.get("next_action"))

    if record.state == "READY":
        return _base_update(
            record,
            plan,
            effect,
            owner_kind=owner_kind,
            owner_id=owner_id,
            lane_id=lane_id,
            slot_id=slot_id,
            lease=lease,
            state="ACTIVE",
            semantic_state=str(effect.get("semantic_state") or "CLAIMED"),
            next_action=next_action,
            blocker=None,
        )

    # Non-terminal resume is lease renewal only. Ownership, lane, slot, state,
    # blocker/run identity and exact continuation meaning cannot change here.
    if (owner_kind, owner_id, lane_id, slot_id) != (
        record.owner_kind, record.owner_id, record.lane_id, record.slot_id
    ):
        raise ControlTransactionError("ACQUIRE resume requires same owner/lane/slot")
    if next_action != record.next_action:
        raise ControlTransactionError("ACQUIRE resume cannot rewrite next_action")
    requested_semantic = str(effect.get("semantic_state") or record.semantic_state).strip()
    if requested_semantic != record.semantic_state:
        raise ControlTransactionError("ACQUIRE resume cannot rewrite semantic_state")
    if record.lease is not None:
        prior_expires = _aware_timestamp(record.lease.expires_at, "existing lease.expires_at")
        if prior_expires > observed_at:
            raise ControlTransactionConflict("ACQUIRE cannot replace a live lease")

    return _base_update(record, plan, effect, lease=lease)


def _execute_start_branch(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state != "ACTIVE":
        raise ControlTransactionError("START_BRANCH requires ACTIVE state")
    work_branch = _text(effect.get("work_branch"), "work_branch")
    head_sha = _text(effect.get("head_sha"), "head_sha")
    next_action = _action(effect.get("next_action"))
    return _base_update(
        record,
        plan,
        effect,
        work_branch=work_branch,
        head_sha=head_sha,
        semantic_state=str(effect.get("semantic_state") or "IMPLEMENTING"),
        next_action=next_action,
    )


def _execute_apply_commit(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state not in {"ACTIVE", "INTEGRATING"}:
        raise ControlTransactionError("APPLY_COMMIT requires ACTIVE or INTEGRATING state")
    head_sha = _text(effect.get("head_sha"), "head_sha")
    if head_sha == record.head_sha:
        raise ControlTransactionError("APPLY_COMMIT must advance head_sha")
    next_action = _action(effect.get("next_action"))
    semantic_state = str(effect.get("semantic_state") or record.semantic_state)
    return _base_update(
        record,
        plan,
        effect,
        head_sha=head_sha,
        semantic_state=semantic_state,
        next_action=next_action,
        active_run=None,
        blocker=None,
    )


def _execute_sync_target(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    """Reconcile a trusted target->work branch sync.

    If the work head advanced, accepted QA is intentionally invalidated by the
    head mismatch and the next action must be START_QA.  If the work head was
    already current, QA may remain accepted and execution may return to MERGE.
    """
    if record.state != "INTEGRATING":
        raise ControlTransactionError("SYNC_TARGET requires INTEGRATING state")
    if record.qa.accepted_head_sha != record.head_sha or record.qa.last_accepted_run is None:
        raise ControlTransactionError("SYNC_TARGET requires accepted QA for current head")

    head_sha = _text(effect.get("head_sha"), "head_sha")
    target_sha = _text(effect.get("target_sha"), "target_sha")
    next_action = _action(effect.get("next_action"))

    if head_sha == record.head_sha:
        if target_sha == record.target_sha:
            raise ControlTransactionError("SYNC_TARGET must advance head or target identity")
        if next_action.kind != "MERGE":
            raise ControlTransactionError("SYNC_TARGET no-op head reconciliation must return to MERGE")
        semantic_state = str(effect.get("semantic_state") or "TARGET_RECONCILED")
    else:
        if next_action.kind != "START_QA":
            raise ControlTransactionError("SYNC_TARGET head advance must require START_QA")
        semantic_state = str(effect.get("semantic_state") or "QA_INVALIDATED_BY_TARGET_SYNC")

    return _base_update(
        record,
        plan,
        effect,
        head_sha=head_sha,
        target_sha=target_sha,
        semantic_state=semantic_state,
        active_run=None,
        next_action=next_action,
        blocker=None,
    )


def _execute_start_qa(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state not in {"ACTIVE", "VERIFYING", "INTEGRATING"}:
        raise ControlTransactionError(
            "START_QA requires ACTIVE/VERIFYING/INTEGRATING state"
        )
    if record.active_run is not None:
        raise ControlTransactionError("START_QA rejected: active_run already exists")
    run_id = effect.get("run_id")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise ControlTransactionError("run_id must be a positive integer")
    run_head = _text(effect.get("run_head_sha"), "run_head_sha")
    if run_head != record.head_sha:
        raise ControlTransactionError("START_QA run_head_sha must match current record head")
    run = RunState(
        id=run_id,
        head_sha=run_head,
        purpose=_text(effect.get("purpose"), "purpose"),
        status=_text(effect.get("run_status"), "run_status", optional=True),
    )
    next_action = _action(effect.get("next_action"))
    return _base_update(
        record,
        plan,
        effect,
        state="VERIFYING",
        semantic_state=str(effect.get("semantic_state") or "REMOTE_QA"),
        active_run=run,
        next_action=next_action,
        blocker=None,
    )


def _execute_accept_qa(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state != "VERIFYING" or record.active_run is None:
        raise ControlTransactionError("ACCEPT_QA requires one active_run in VERIFYING state")
    run_id = effect.get("run_id")
    if run_id != record.active_run.id:
        raise ControlTransactionError("ACCEPT_QA run_id does not match active_run")
    run_head = _text(effect.get("run_head_sha"), "run_head_sha")
    if run_head != record.active_run.head_sha or run_head != record.head_sha:
        raise ControlTransactionError("ACCEPT_QA run_head_sha must match active_run/current head")
    if str(effect.get("conclusion") or "").strip().lower() != "success":
        raise ControlTransactionError("ACCEPT_QA requires conclusion=success")
    next_state = _text(effect.get("next_state"), "next_state")
    if next_state not in {"ACTIVE", "INTEGRATING"}:
        raise ControlTransactionError("ACCEPT_QA next_state must be ACTIVE or INTEGRATING")
    next_action = _action(effect.get("next_action"))
    qa = QAState(last_accepted_run=record.active_run.id, accepted_head_sha=record.head_sha)
    return _base_update(
        record,
        plan,
        effect,
        state=next_state,
        semantic_state=str(effect.get("semantic_state") or "GREEN"),
        active_run=None,
        qa=qa,
        next_action=next_action,
        blocker=None,
    )


_QA_FAILURE_CONCLUSIONS = frozenset({
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
})


def _execute_fail_qa(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    """Consume one exact terminal failed QA run and return to repair work."""
    if record.state != "VERIFYING" or record.active_run is None:
        raise ControlTransactionError("FAIL_QA requires one active_run in VERIFYING state")
    run_id = effect.get("run_id")
    if run_id != record.active_run.id:
        raise ControlTransactionError("FAIL_QA run_id does not match active_run")
    run_head = _text(effect.get("run_head_sha"), "run_head_sha")
    if run_head != record.active_run.head_sha or run_head != record.head_sha:
        raise ControlTransactionError("FAIL_QA run_head_sha must match active_run/current head")
    conclusion = str(effect.get("conclusion") or "").strip().lower()
    if conclusion not in _QA_FAILURE_CONCLUSIONS:
        raise ControlTransactionError(
            "FAIL_QA requires a terminal non-success conclusion"
        )
    next_action = _action(effect.get("next_action"))
    return _base_update(
        record,
        plan,
        effect,
        state="ACTIVE",
        semantic_state=str(effect.get("semantic_state") or "QA_FAILED_REPAIR"),
        active_run=None,
        next_action=next_action,
        blocker=None,
    )


def _execute_merge(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state != "INTEGRATING":
        raise ControlTransactionError("MERGE requires INTEGRATING state")
    if record.qa.accepted_head_sha != record.head_sha or record.qa.last_accepted_run is None:
        raise ControlTransactionError("MERGE requires accepted_head equal to current head")
    merged_sha = _text(effect.get("merged_sha"), "merged_sha")
    target_sha = _text(effect.get("target_sha"), "target_sha")
    if merged_sha != target_sha:
        raise ControlTransactionError("MERGE target_sha must equal fresh merged_sha readback")
    next_action = _action(effect.get("next_action"))
    closure = ClosureState(
        merged_sha=merged_sha,
        issue_closed=False,
        released_at=None,
    )
    return _base_update(
        record,
        plan,
        effect,
        target_sha=target_sha,
        state="INTEGRATING",
        semantic_state=str(effect.get("semantic_state") or "MERGED"),
        closure=closure,
        next_action=next_action,
        blocker=None,
    )


def _execute_handoff(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state == "DONE":
        raise ControlTransactionError("HANDOFF cannot mutate DONE record")

    # Handoff is routing-only. Slot/work identity and exact continuation meaning
    # stay on the same canonical record; changing them would create a hidden
    # second scheduling/ownership transition inside HANDOFF.
    if "slot_id" in effect:
        requested_slot = _text(effect.get("slot_id"), "slot_id", optional=True)
        if requested_slot != record.slot_id:
            raise ControlTransactionError(
                f"HANDOFF cannot change slot_id: {record.slot_id!r} -> {requested_slot!r}"
            )
    if "next_action" in effect:
        requested_action = _action(effect.get("next_action"), optional=True)
        if requested_action != record.next_action:
            raise ControlTransactionError("HANDOFF cannot rewrite next_action")
    if "semantic_state" in effect:
        requested_semantic_state = _text(effect.get("semantic_state"), "semantic_state")
        if requested_semantic_state != record.semantic_state:
            raise ControlTransactionError("HANDOFF cannot rewrite semantic_state")

    lease = _lease(effect.get("lease"), optional=True)
    return _base_update(
        record,
        plan,
        effect,
        owner_kind=_text(effect.get("owner_kind"), "owner_kind"),
        owner_id=_text(effect.get("owner_id"), "owner_id"),
        lane_id=_text(effect.get("lane_id"), "lane_id", optional=True),
        slot_id=record.slot_id,
        lease=lease,
        next_action=record.next_action,
        semantic_state=record.semantic_state,
    )


def _finalize_target_sha(
    record: ExecutionRecord,
    effect: Mapping[str, object],
) -> str:
    """Accept the merge SHA as a stable anchor while allowing a proven descendant target."""
    anchor = _text(record.closure.merged_sha, "closure.merged_sha")
    observed_target = _text(
        effect.get("observed_target_sha"),
        "observed_target_sha",
        optional=True,
    ) or record.target_sha

    if observed_target == anchor:
        return observed_target

    proof = effect.get("target_advance_proof")
    if not isinstance(proof, Mapping):
        raise ControlTransactionError(
            "FINALIZE target advanced beyond merge anchor without trusted descendant proof"
        )
    if proof.get("schema") != TARGET_ADVANCE_PROOF_SCHEMA:
        raise ControlTransactionError("FINALIZE target advance proof schema mismatch")
    if str(proof.get("target_branch") or "").strip() != record.target_branch:
        raise ControlTransactionError("FINALIZE target advance proof branch mismatch")
    if str(proof.get("anchor_sha") or "").strip() != anchor:
        raise ControlTransactionError("FINALIZE target advance proof anchor mismatch")
    if str(proof.get("observed_target_sha") or "").strip() != observed_target:
        raise ControlTransactionError("FINALIZE target advance proof target mismatch")
    if proof.get("anchor_is_ancestor") is not True:
        raise ControlTransactionError("FINALIZE target advance proof must prove anchor ancestry")
    if proof.get("fresh_readback") is not True:
        raise ControlTransactionError("FINALIZE target advance proof requires fresh readback")
    if str(proof.get("trusted_source") or "").strip() != "control_transaction_production_executor":
        raise ControlTransactionError("FINALIZE target advance proof has untrusted source")
    return observed_target


def _execute_finalize(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state != "INTEGRATING":
        raise ControlTransactionError("FINALIZE requires INTEGRATING state")
    if record.qa.last_accepted_run is None or record.qa.accepted_head_sha != record.head_sha:
        raise ControlTransactionError("FINALIZE requires accepted QA for current head")
    if not record.closure.merged_sha:
        raise ControlTransactionError("FINALIZE requires fresh merged target readback or a merged anchor")
    final_target_sha = _finalize_target_sha(record, effect)
    if effect.get("issue_closed") is not True:
        raise ControlTransactionError("FINALIZE requires issue_closed=true readback")
    if str(effect.get("issue_state") or "").strip().lower() != "closed":
        raise ControlTransactionError("FINALIZE requires issue_state=closed readback")
    if str(effect.get("issue_state_reason") or "").strip().lower() != "completed":
        raise ControlTransactionError("FINALIZE requires issue_state_reason=completed readback")
    released_at = _text(effect.get("released_at"), "released_at")
    closure = ClosureState(
        merged_sha=record.closure.merged_sha,
        issue_closed=True,
        released_at=released_at,
    )
    chain = record.chain
    if "next_issue" in effect or "chain_next_action" in effect:
        next_issue = effect.get("next_issue")
        if next_issue is not None and (isinstance(next_issue, bool) or not isinstance(next_issue, int) or next_issue <= 0):
            raise ControlTransactionError("next_issue must be a positive integer")
        chain = ChainState(
            parent_issue=record.chain.parent_issue,
            next_issue=next_issue,
            next_action=_action(effect.get("chain_next_action"), "chain_next_action", optional=True),
        )
    return _base_update(
        record,
        plan,
        effect,
        state="DONE",
        semantic_state=str(effect.get("semantic_state") or "TERMINAL_SUCCESS"),
        next_action=None,
        lease=None,
        active_run=None,
        blocker=None,
        closure=closure,
        chain=chain,
        target_sha=final_target_sha,
    )


def _execute_block(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state == "DONE":
        raise ControlTransactionError("BLOCK cannot mutate DONE record")
    if record.active_run is not None:
        raise ControlTransactionError("BLOCK requires active_run to be cleared first")

    blocker_kind = _text(effect.get("blocker_kind"), "blocker_kind")
    blocker_evidence = _text(effect.get("blocker_evidence"), "blocker_evidence")
    recheck_after = _text(effect.get("recheck_after"), "recheck_after", optional=True)
    blocker = BlockerState(
        kind=blocker_kind,
        evidence=blocker_evidence,
        recheck_after=recheck_after,
    )
    next_action = _action(effect.get("next_action"))
    if next_action.kind != "WAIT_EXTERNAL":
        raise ControlTransactionError("BLOCK next_action must be WAIT_EXTERNAL")
    action_blocker_kind = str(next_action.args.get("blocker_kind") or "").strip()
    if action_blocker_kind != blocker.kind:
        raise ControlTransactionError("BLOCK next_action blocker_kind must match blocker")

    return _base_update(
        record,
        plan,
        effect,
        state="BLOCKED",
        semantic_state=str(effect.get("semantic_state") or "BLOCKED"),
        blocker=blocker,
        next_action=next_action,
    )


def _execute_reconcile(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state == "DONE":
        raise ControlTransactionError("RECONCILE cannot mutate DONE record")

    observed_branch = _text(
        effect.get("observed_work_branch"), "observed_work_branch"
    )
    if observed_branch != record.work_branch:
        raise ControlTransactionError("RECONCILE cannot change work_branch identity")

    observed_head = _text(effect.get("observed_head_sha"), "observed_head_sha")
    observed_target = _text(effect.get("observed_target_sha"), "observed_target_sha")
    next_action = _action(effect.get("next_action"))

    if record.active_run is not None and observed_head != record.head_sha:
        raise ControlTransactionError(
            "RECONCILE cannot move head while active_run is bound to the current head"
        )

    if "owner_kind" in effect and _text(effect.get("owner_kind"), "owner_kind") != record.owner_kind:
        raise ControlTransactionError("RECONCILE cannot change owner_kind")
    if "owner_id" in effect and _text(effect.get("owner_id"), "owner_id") != record.owner_id:
        raise ControlTransactionError("RECONCILE cannot change owner_id")
    if "lane_id" in effect and _text(effect.get("lane_id"), "lane_id", optional=True) != record.lane_id:
        raise ControlTransactionError("RECONCILE cannot change lane_id")
    if "slot_id" in effect and _text(effect.get("slot_id"), "slot_id", optional=True) != record.slot_id:
        raise ControlTransactionError("RECONCILE cannot change slot_id")

    requested_state = str(effect.get("state") or record.state).strip()
    clear_blocker = effect.get("clear_blocker") is True
    blocker = record.blocker
    if requested_state != record.state:
        if not (record.state == "BLOCKED" and requested_state == "ACTIVE" and clear_blocker):
            raise ControlTransactionError("RECONCILE primary-state change is only allowed for BLOCKED -> ACTIVE with clear_blocker=true")
        blocker = None
    elif clear_blocker:
        raise ControlTransactionError("RECONCILE clear_blocker requires BLOCKED -> ACTIVE transition")
    requested_semantic = str(effect.get("semantic_state") or record.semantic_state).strip()

    return _base_update(
        record,
        plan,
        effect,
        head_sha=observed_head,
        target_sha=observed_target,
        state=requested_state,
        blocker=blocker,
        semantic_state=requested_semantic,
        next_action=next_action,
    )


def _execute_yield(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    if record.state == "DONE":
        raise ControlTransactionError("YIELD is only for non-terminal work")
    if record.lease is None:
        raise ControlTransactionError("YIELD requires an active invocation lease")
    if plan.invocation_identity is None:
        raise ControlTransactionError("YIELD requires transaction invocation_identity")
    if record.lease.invocation_identity != plan.invocation_identity:
        raise ControlTransactionError("YIELD lease invocation does not match transaction invocation")
    if "next_action" in effect:
        requested_action = _action(effect.get("next_action"), optional=True)
        if requested_action != record.next_action:
            raise ControlTransactionError("YIELD cannot rewrite next_action")
    if "semantic_state" in effect:
        requested_semantic = _text(effect.get("semantic_state"), "semantic_state")
        if requested_semantic != record.semantic_state:
            raise ControlTransactionError("YIELD cannot rewrite semantic_state")

    exit_decision = classify_invocation_exit(
        record,
        invocation_identity=plan.invocation_identity,
        now=_text(effect.get("updated_at"), "effect.updated_at"),
        host_boundary=True,
    )
    if not exit_decision.requires_yield:
        raise ControlTransactionError(
            "YIELD rejected by invocation-exit gate: "
            f"{exit_decision.decision}"
        )
    return _base_update(
        record,
        plan,
        effect,
        lease=None,
        next_action=record.next_action,
        semantic_state=record.semantic_state,
    )


_EXECUTORS = {
    "ACQUIRE": _execute_acquire,
    "START_BRANCH": _execute_start_branch,
    "APPLY_COMMIT": _execute_apply_commit,
    "START_QA": _execute_start_qa,
    "ACCEPT_QA": _execute_accept_qa,
    "FAIL_QA": _execute_fail_qa,
    "BLOCK": _execute_block,
    "MERGE": _execute_merge,
    "SYNC_TARGET": _execute_sync_target,
    "HANDOFF": _execute_handoff,
    "FINALIZE": _execute_finalize,
    "RECONCILE": _execute_reconcile,
    "YIELD": _execute_yield,
}


def execute_transaction(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    *,
    effect: Mapping[str, object],
) -> ExecutionRecord:
    """Apply one fully read-back effect to the exact record bound by ``plan``.

    This is deliberately a one-step semantic transition: there is no durable
    AUTHORIZED/GREEN record that can later be consumed by a different runtime.
    """
    if not isinstance(record, ExecutionRecord):
        raise ControlTransactionError("record must be an ExecutionRecord")
    if not isinstance(plan, ControlTransactionPlan):
        raise ControlTransactionError("plan must be a ControlTransactionPlan")
    if not isinstance(effect, Mapping):
        raise ControlTransactionError("effect must be an object")
    if plan.kind not in _EXECUTORS:
        raise ControlTransactionError(f"unsupported transaction kind: {plan.kind}")
    _assert_plan_matches(record, plan)
    return _EXECUTORS[plan.kind](record, plan, effect)
