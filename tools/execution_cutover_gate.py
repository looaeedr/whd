"""Fail-closed WHD Flow v2 cutover-readiness assessment.

The gate is read-only.  It never retires legacy storage, changes a scheduler,
selects work, or mutates ExecutionRecord state.  It only proves whether the
current record/shadow/cache set is safe enough for a later writer cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_claim_guard import GuardTransactionDecision, GuardTransactionState
from tools.execution_ready_index import (
    ExecutionReadyIndex,
    ReadyIndexError,
    build_ready_index,
    validate_ready_index,
)
from tools.execution_record import ExecutionRecord, execution_record_fingerprint
from tools.execution_record_shadow import ShadowComparison
from tools.execution_work_slot_view import WorkSlotViewError, project_work_slots


@dataclass(frozen=True)
class CutoverReadiness:
    status: str
    reasons: tuple[str, ...]
    active_issues: tuple[int, ...]
    shadowed_issues: tuple[int, ...]
    ready_source_digest: str | None


def assess_cutover_readiness(
    records: Iterable[ExecutionRecord],
    *,
    shadow_by_issue: Mapping[int, ShadowComparison],
    legacy_guard_by_issue: Mapping[int, GuardTransactionDecision],
    ready_index: ExecutionReadyIndex | None = None,
) -> CutoverReadiness:
    """Assess whether legacy writers could be cut over in a later transaction."""

    materialized = tuple(records)
    reasons: list[str] = []
    by_issue: dict[int, ExecutionRecord] = {}
    for record in materialized:
        if not isinstance(record, ExecutionRecord):
            reasons.append("invalid non-ExecutionRecord input")
            continue
        if record.issue in by_issue:
            reasons.append(f"duplicate canonical issue record: {record.issue}")
            continue
        by_issue[record.issue] = record

    active = tuple(sorted((r for r in by_issue.values() if r.state != "DONE"), key=lambda r: r.issue))
    active_issues = tuple(record.issue for record in active)

    if not isinstance(shadow_by_issue, Mapping):
        reasons.append("shadow_by_issue must be a mapping")
        shadow_by_issue = {}
    if not isinstance(legacy_guard_by_issue, Mapping):
        reasons.append("legacy_guard_by_issue must be a mapping")
        legacy_guard_by_issue = {}

    shadowed: list[int] = []
    for record in active:
        # Record-local cutover invariants are independent of shadow availability.
        # Report them all so V2_MISSING cannot hide another migration blocker.
        if record.transaction is not None and record.transaction.status != "RECONCILED":
            reasons.append(
                f"issue {record.issue}: non-reconciled transaction "
                f"{record.transaction.id} status={record.transaction.status}"
            )
        if record.next_action is None:
            reasons.append(
                f"issue {record.issue}: active cutover requires structured next_action"
            )
        else:
            try:
                validate_execution_action(record.next_action)
            except ActionContractError as exc:
                reasons.append(
                    f"issue {record.issue}: active cutover requires executable structured next_action: {exc}"
                )

        legacy_guard = legacy_guard_by_issue.get(record.issue)
        if legacy_guard is None:
            reasons.append(f"issue {record.issue}: missing legacy Guard transaction assessment")
        elif not isinstance(legacy_guard, GuardTransactionDecision):
            reasons.append(f"issue {record.issue}: invalid legacy Guard transaction assessment")
        elif legacy_guard.state not in {GuardTransactionState.NONE, GuardTransactionState.CONSUMED}:
            runs = ",".join(str(run) for run in legacy_guard.guard_run_ids) or "NONE"
            reasons.append(
                f"issue {record.issue}: unresolved legacy Guard transaction "
                f"state={legacy_guard.state.value} runs={runs}"
            )

        shadow = shadow_by_issue.get(record.issue)
        if shadow is None:
            reasons.append(f"issue {record.issue}: missing shadow comparison")
            continue
        shadowed.append(record.issue)
        if not isinstance(shadow, ShadowComparison):
            reasons.append(f"issue {record.issue}: invalid shadow comparison")
            continue
        if shadow.status != "MATCH":
            reasons.append(f"issue {record.issue}: shadow {shadow.status}")
            continue
        current_fp = execution_record_fingerprint(record)
        if shadow.v2_fingerprint != current_fp:
            reasons.append(
                f"issue {record.issue}: shadow fingerprint drift "
                f"expected={current_fp} observed={shadow.v2_fingerprint}"
            )

    # Work-slot occupancy remains a projection; ambiguity blocks cutover.
    try:
        project_work_slots(materialized)
    except WorkSlotViewError as exc:
        reasons.append(str(exc))

    # One durable scheduler lane may own at most one active canonical record.
    lanes: dict[str, list[int]] = {}
    for record in active:
        if record.owner_kind == "SCHEDULER" and record.lane_id:
            lanes.setdefault(record.lane_id, []).append(record.issue)
    for lane_id, issues in sorted(lanes.items()):
        if len(issues) > 1:
            reasons.append(
                "multiple active records for scheduler lane "
                f"{lane_id}: {','.join(str(issue) for issue in sorted(issues))}"
            )

    ready_source_digest: str | None = None
    try:
        rebuilt = build_ready_index(materialized)
        ready_source_digest = rebuilt.source_digest
        if ready_index is not None and not validate_ready_index(ready_index, materialized):
            reasons.append("ready-index is stale relative to canonical execution records")
    except ReadyIndexError as exc:
        reasons.append(f"ready-index rebuild failed: {exc}")

    # Stable de-duplication keeps repeated structural failures readable.
    deduped = tuple(dict.fromkeys(reasons))
    return CutoverReadiness(
        status="READY" if not deduped else "NOT_READY",
        reasons=deduped,
        active_issues=active_issues,
        shadowed_issues=tuple(sorted(shadowed)),
        ready_source_digest=ready_source_digest,
    )
