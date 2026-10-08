"""Bounded, read-only Flow v2 model context; never a mutation authority.

The canonical record and trusted GitHub transactions are unchanged. This
projection is a model input, not another state store, lease or QA gate.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from tools.execution_record import ExecutionRecord, execution_record_fingerprint
from tools.issue_comment_progress import evaluate_issue_comment_intervention

SCHEMA = "WHD_FLOW_V2_COMPACT_CONTEXT_V1"


def build_compact_execution_context(
    record: ExecutionRecord,
    *,
    now: datetime | None = None,
    issue_comments: Iterable[Mapping[str, object]] | None = None,
    trusted_comment_authors: Iterable[str] = (),
) -> dict[str, object]:
    """Project one exact record; preserve provenance and fail-closed uncertainty.

    An absent comment feed stays UNKNOWN, never stale or takeover-eligible.
    A reported timeout is not a HANDOFF/ACQUIRE authorization; CAS still applies.
    This function performs no I/O and does not persist or mutate the record.
    """
    if not isinstance(record, ExecutionRecord):
        raise TypeError("record must be a canonical ExecutionRecord")
    action = record.next_action
    qa = record.qa
    lease = record.lease
    active_run = record.active_run
    comment_clock: dict[str, object] = {
        "status": "UNKNOWN_NOT_FETCHED", "intervention_candidate": False,
    }
    if issue_comments is not None:
        if now is None:
            raise ValueError("now required when issue comments are supplied")
        verdict = evaluate_issue_comment_intervention(
            record, issue_comments, now=now,
            trusted_authors=trusted_comment_authors,
        )
        comment_clock = {
            "status": verdict.reason,
            "intervention_candidate": verdict.eligible,
            "comment_id": verdict.comment_id,
            "age_seconds": verdict.age_seconds,
        }
    return {
        "schema": SCHEMA,
        "authority": "READ_ONLY_NON_AUTHORITY",
        "provenance": {
            "source": "coord/execution-v2",
            "record_fingerprint": execution_record_fingerprint(record),
            "record_generation": record.generation,
            "issue_and_pr_readback": "NOT_INCLUDED_MUST_FRESH_READ_BEFORE_EFFECT",
        },
        "issue": record.issue,
        "state": record.state,
        "semantic_state": record.semantic_state,
        "execution_intent": record.execution_intent,
        "owner": {
            "kind": record.owner_kind,
            "id": record.owner_id,
            "lane_id": record.lane_id,
            "slot_id": record.slot_id,
        },
        "branch": {
            "work": record.work_branch,
            "head_sha": record.head_sha,
            "target": record.target_branch,
            "target_sha": record.target_sha,
        },
        "next_action": (
            {"kind": action.kind, "args": dict(action.args), "display": action.display}
            if action else None
        ),
        "lease": {
            "present": lease is not None,
            "expires_at": lease.expires_at if lease else None,
            "invocation_identity": lease.invocation_identity if lease else None,
        },
        "qa": {
            "last_accepted_run": qa.last_accepted_run,
            "accepted_head_sha": qa.accepted_head_sha,
            "accepted_for_current_head": (
                qa.last_accepted_run is not None
                and qa.accepted_head_sha == record.head_sha
            ),
            "active_run_id": active_run.id if active_run else None,
        },
        "blocker": (
            {"kind": record.blocker.kind, "evidence": record.blocker.evidence,
             "recheck_after": record.blocker.recheck_after}
            if record.blocker else None
        ),
        "closure": {
            "issue_closed": record.closure.issue_closed,
            "merged_sha": record.closure.merged_sha,
        },
        "comment_clock": comment_clock,
        "effect_policy": "REQUIRE_FRESH_CANONICAL_READBACK_AND_NATIVE_CAS",
    }
