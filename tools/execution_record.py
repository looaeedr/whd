"""Canonical per-Issue execution-state projection for WHD control-plane records.

Legacy claim and checkpoint JSON remain durable transports during migration.  This
module is the single semantic projection seam: callers consume one validated
ExecutionRecord instead of independently interpreting the two legacy payloads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping


class ExecutionRecordError(ValueError):
    """Raised when legacy durable payloads cannot describe one execution record."""


def _text(value: object, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    result = str(value or "").strip()
    if not result:
        if optional:
            return None
        raise ExecutionRecordError(f"{field} must be nonblank")
    return result


def _issue(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ExecutionRecordError(f"{field} must be a positive issue number")
    try:
        result = int(str(value).lstrip("#"))
    except (TypeError, ValueError) as exc:
        raise ExecutionRecordError(f"{field} must be a positive issue number") from exc
    if result <= 0:
        raise ExecutionRecordError(f"{field} must be a positive issue number")
    return result


def _optional_issue(value: object, field: str) -> int | None:
    if value in (None, ""):
        return None
    return _issue(value, field)


def _optional_run(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExecutionRecordError("active_run must be a positive integer")
    return value


@dataclass(frozen=True)
class ExecutionRecord:
    issue: int
    owner: str
    branch: str
    head_sha: str
    target_branch: str
    target_sha: str
    semantic_state: str
    next_action: str | None
    active_run: int | None
    closure_state: str
    chain_state: str
    parent_issue: int | None
    slot_id: str | None


def execution_record_from_legacy(
    claim: Mapping[str, object],
    checkpoint: Mapping[str, object],
) -> ExecutionRecord:
    """Project one legacy claim/checkpoint pair into a fail-closed semantic record."""

    if not isinstance(claim, Mapping) or not isinstance(checkpoint, Mapping):
        raise ExecutionRecordError("legacy claim and checkpoint must be mappings")

    claim_issue = _issue(claim.get("issue"), "claim issue")
    checkpoint_issue = _issue(checkpoint.get("issue"), "checkpoint issue")
    if claim_issue != checkpoint_issue:
        raise ExecutionRecordError(
            f"issue identity mismatch: claim={claim_issue} checkpoint={checkpoint_issue}"
        )

    claim_branch = _text(claim.get("work_branch"), "claim branch")
    checkpoint_branch = _text(checkpoint.get("branch"), "checkpoint branch")
    if claim_branch != checkpoint_branch:
        raise ExecutionRecordError(
            f"branch identity mismatch: claim={claim_branch!r} checkpoint={checkpoint_branch!r}"
        )

    claim_head = _text(claim.get("head_sha"), "claim head")
    checkpoint_head = _text(checkpoint.get("head_sha"), "checkpoint head")
    if claim_head != checkpoint_head:
        raise ExecutionRecordError(
            f"head identity mismatch: claim={claim_head!r} checkpoint={checkpoint_head!r}"
        )

    claim_next = _text(claim.get("next_action"), "claim next_action", optional=True)
    checkpoint_next = _text(
        checkpoint.get("next_action"), "checkpoint next_action", optional=True
    )
    if claim_next != checkpoint_next:
        raise ExecutionRecordError(
            "next_action semantic mismatch: "
            f"claim={claim_next!r} checkpoint={checkpoint_next!r}"
        )

    claim_parent = _optional_issue(claim.get("master_issue"), "claim parent issue")
    checkpoint_parent = _optional_issue(
        checkpoint.get("master_issue"), "checkpoint parent issue"
    )
    if claim_parent is not None and checkpoint_parent is not None and claim_parent != checkpoint_parent:
        raise ExecutionRecordError(
            "parent issue mismatch: "
            f"claim={claim_parent} checkpoint={checkpoint_parent}"
        )
    parent_issue = claim_parent if claim_parent is not None else checkpoint_parent

    return ExecutionRecord(
        issue=claim_issue,
        owner=_text(claim.get("worker"), "claim owner"),
        branch=claim_branch,
        head_sha=claim_head,
        target_branch=_text(claim.get("production_target"), "target branch"),
        target_sha=_text(claim.get("production_sha"), "target sha"),
        semantic_state=_text(checkpoint.get("state"), "checkpoint semantic state"),
        next_action=checkpoint_next,
        active_run=_optional_run(checkpoint.get("run_id")),
        closure_state=_text(
            checkpoint.get("closure_state", "CLOSED"), "checkpoint closure state"
        ),
        chain_state=_text(
            checkpoint.get("chain_state", "NONE"), "checkpoint chain state"
        ),
        parent_issue=parent_issue,
        slot_id=_text(claim.get("slot_id"), "slot_id", optional=True),
    )


def execution_record_to_payload(record: ExecutionRecord) -> dict[str, object]:
    if not isinstance(record, ExecutionRecord):
        raise ExecutionRecordError("record must be an ExecutionRecord")
    return {"version": 1, **asdict(record)}


def execution_record_fingerprint(record: ExecutionRecord) -> str:
    canonical = json.dumps(
        execution_record_to_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
