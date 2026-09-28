"""Read-only shadow comparison between legacy WHD state and ExecutionRecord V2.

This module is intentionally side-effect free. It is the M4 cutover seam: scheduler
or work-slot callers can compare the legacy semantic projection with a native V2
record before any writer is switched over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from tools.execution_record import (
    ExecutionRecord,
    execution_record_fingerprint,
    execution_record_from_legacy,
    execution_record_from_payload,
    execution_record_to_payload,
)


@dataclass(frozen=True)
class ShadowDifference:
    field: str
    legacy: object
    v2: object


@dataclass(frozen=True)
class ShadowComparison:
    status: str
    legacy_fingerprint: str
    v2_fingerprint: str | None
    differences: tuple[ShadowDifference, ...]
    bootstrap_payload: dict[str, object] | None = None


def _action_display(record_action: object) -> object:
    if record_action is None:
        return None
    return getattr(record_action, "display", None)


def _projection(record: ExecutionRecord) -> dict[str, object]:
    active_run = record.active_run
    return {
        "issue": record.issue,
        "execution_intent": record.execution_intent,
        "owner_kind": record.owner_kind,
        "owner_id": record.owner_id,
        "lane_id": record.lane_id,
        "slot_id": record.slot_id,
        "source_branch": record.source_branch,
        "source_sha": record.source_sha,
        "work_branch": record.work_branch,
        "head_sha": record.head_sha,
        "target_branch": record.target_branch,
        "target_sha": record.target_sha,
        "state": record.state,
        "semantic_state": record.semantic_state,
        "next_action.display": _action_display(record.next_action),
        "active_run.id": active_run.id if active_run else None,
        "active_run.head_sha": active_run.head_sha if active_run else None,
        "qa.last_accepted_run": record.qa.last_accepted_run,
        "qa.accepted_head_sha": record.qa.accepted_head_sha,
        "closure.merged_sha": record.closure.merged_sha,
        "closure.issue_closed": record.closure.issue_closed,
        "closure.released_at": record.closure.released_at,
        "chain.parent_issue": record.chain.parent_issue,
        "chain.next_issue": record.chain.next_issue,
        "chain.next_action.display": _action_display(record.chain.next_action),
    }


def shadow_compare_legacy_to_v2(
    claim: Mapping[str, object],
    checkpoint: Mapping[str, object],
    native_v2: Mapping[str, object] | ExecutionRecord | None,
) -> ShadowComparison:
    """Compare legacy and V2 state without writing or changing scheduler authority."""
    legacy = execution_record_from_legacy(claim, checkpoint)
    legacy_fingerprint = execution_record_fingerprint(legacy)

    if native_v2 is None:
        return ShadowComparison(
            status="V2_MISSING",
            legacy_fingerprint=legacy_fingerprint,
            v2_fingerprint=None,
            differences=(),
            bootstrap_payload=execution_record_to_payload(legacy),
        )

    v2 = native_v2 if isinstance(native_v2, ExecutionRecord) else execution_record_from_payload(native_v2)
    legacy_view = _projection(legacy)
    v2_view = _projection(v2)
    differences = tuple(
        ShadowDifference(field=field, legacy=legacy_view[field], v2=v2_view[field])
        for field in legacy_view
        if legacy_view[field] != v2_view[field]
    )
    return ShadowComparison(
        status="MATCH" if not differences else "MISMATCH",
        legacy_fingerprint=legacy_fingerprint,
        v2_fingerprint=execution_record_fingerprint(v2),
        differences=differences,
        bootstrap_payload=None,
    )
