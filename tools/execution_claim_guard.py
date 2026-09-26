"""Fail-closed execution-claim ownership guard for WHD development actions.

This module does not acquire, mutate, or release claims. It validates an already
acquired shared coordination claim immediately before a branch/write/QA/takeover action so a
second worker cannot treat comments, branch names, stale chat state, or a stale claim
snapshot as ownership.
"""

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_ACTIONS = frozenset(
    {
        "branch-create",
        "claim-takeover",
        "write",
        "commit",
        "qa-dispatch",
        "workflow-dispatch",
        "pr-write",
    }
)
ACTIVE_PHASES = frozenset(
    {
        "CLAIMED",
        "RED",
        "IMPLEMENTING",
        "GREEN",
        "REMOTE_QA",
        "RECOVERING",
        "CLEANUP",
        "DRIFT_AUDIT",
        "CLOSING",
    }
)
INACTIVE_PHASES = frozenset(
    {
        "RELEASED",
        "CLOSED",
        "TERMINAL_SUCCESS",
        "TERMINAL_FAILURE",
    }
)
FILE_MUTATION_ACTIONS = frozenset({"write", "commit"})


class ExecutionClaimError(RuntimeError):
    """Raised when execution ownership cannot be proven exactly."""


class GuardTransactionState(str, Enum):
    """Canonical lifecycle for one Remote Guard transaction."""

    NONE = "NONE"
    PENDING = "PENDING"
    MUTATION_DONE_RECONCILE_ONLY = "MUTATION_DONE_RECONCILE_ONLY"
    EXPIRED_UNCONSUMED = "EXPIRED_UNCONSUMED"
    CONSUMED = "CONSUMED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class GuardTransactionDecision:
    state: GuardTransactionState
    receipt: dict[str, object] | None = None
    guard_run_ids: tuple[int, ...] = ()
    required_next_action: str | None = None
    reason: str | None = None


def _guard_tx_timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionClaimError(f"invalid Guard transaction {label} timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionClaimError(
            f"Guard transaction {label} timestamp must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc)


def _guard_tx_run_id(receipt: Mapping[str, object]) -> int:
    value = receipt.get("run_id")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExecutionClaimError("invalid Guard transaction run_id")
    return value


def _guard_tx_files(payload: Mapping[str, object]) -> tuple[str, ...]:
    value = payload.get("changed_files", ())
    if not isinstance(value, (list, tuple)):
        raise ExecutionClaimError("invalid Guard transaction changed_files")
    return _normalize_changed_files(str(item) for item in value)


def _guard_tx_readback_for(
    receipt: Mapping[str, object],
    durable_readbacks: Iterable[Mapping[str, object]],
) -> Mapping[str, object] | None:
    run_id = _guard_tx_run_id(receipt)
    matches = [
        item
        for item in durable_readbacks
        if item.get("guard_run_id") == run_id
        and str(item.get("action") or "") == str(receipt.get("action") or "")
    ]
    if len(matches) > 1:
        raise ExecutionClaimError(
            "ambiguous Guard transaction durable readback: multiple matches"
        )
    return matches[0] if matches else None


def _guard_tx_readback_proves_mutation(
    receipt: Mapping[str, object],
    readback: Mapping[str, object],
    *,
    live_branch_head_sha: str,
) -> bool:
    if readback.get("mutation_applied") is not True:
        return False
    if _guard_tx_files(readback) != _guard_tx_files(receipt):
        return False

    action = str(receipt.get("action") or "")
    if action == "commit":
        if str(readback.get("parent_sha") or "") != str(receipt.get("head_sha") or ""):
            return False
        if str(readback.get("post_head_sha") or "") != live_branch_head_sha:
            return False
        committed_at = _guard_tx_timestamp(readback.get("committed_at"), "commit")
        issued_at = _guard_tx_timestamp(receipt.get("issued_at"), "issued_at")
        expires_at = _guard_tx_timestamp(receipt.get("expires_at"), "expires_at")
        return issued_at <= committed_at <= expires_at
    if action == "write":
        return readback.get("target_changed") is True
    if action == "branch-create":
        return (
            readback.get("branch_exists") is True
            and str(readback.get("branch_head_sha") or "")
            == str(receipt.get("head_sha") or "")
        )
    if action == "claim-takeover":
        return readback.get("claim_cas_applied") is True
    if action in {"qa-dispatch", "workflow-dispatch"}:
        return (
            readback.get("run_created") is True
            and str(readback.get("run_head_sha") or "")
            == str(receipt.get("tested_target_sha") or "")
        )
    if action == "pr-write":
        return readback.get("pr_readback") is True
    return False



def durable_branch_create_readbacks_from_live_branch(
    receipts: Iterable[Mapping[str, object]],
    *,
    live_branch_head_sha: str,
) -> list[dict[str, object]]:
    """Project exact live branch state into durable readback for branch-create GREEN.

    A branch-create mutation is fully proven by the remote branch existing at the
    exact guarded HEAD. Unlike commit/write actions, there is no additional
    coordination mutation to reconcile before the receipt can be considered
    consumed.
    """

    live_head = str(live_branch_head_sha or "").strip()
    if not live_head:
        return []

    readbacks: list[dict[str, object]] = []
    for receipt in receipts:
        if receipt.get("schema") != "WHD_REMOTE_GUARD_RECEIPT_V1":
            continue
        if receipt.get("result") != "GREEN":
            continue
        if str(receipt.get("action") or "") != "branch-create":
            continue
        if str(receipt.get("head_sha") or "") != live_head:
            continue
        if str(receipt.get("tested_target_sha") or "") != live_head:
            continue
        readbacks.append(
            {
                "guard_run_id": _guard_tx_run_id(receipt),
                "action": "branch-create",
                "mutation_applied": True,
                "reconciled": True,
                "branch_exists": True,
                "branch_head_sha": live_head,
                "changed_files": list(_guard_tx_files(receipt)),
            }
        )
    return readbacks

def _guard_tx_equivalence_key(
    receipt: Mapping[str, object],
) -> tuple[object, ...]:
    """Return the mutation identity shared by truly equivalent GREEN receipts."""

    takeover_evidence = receipt.get("takeover_evidence")
    try:
        takeover_identity = json.dumps(
            takeover_evidence,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ExecutionClaimError(
            "invalid Guard transaction takeover_evidence"
        ) from exc

    return (
        receipt.get("issue"),
        str(receipt.get("worker") or ""),
        str(receipt.get("executor_source") or ""),
        str(receipt.get("action") or ""),
        str(receipt.get("branch") or ""),
        str(receipt.get("base_sha") or ""),
        str(receipt.get("head_sha") or ""),
        str(receipt.get("claim_blob_sha") or ""),
        str(receipt.get("guard_authority_sha") or ""),
        str(receipt.get("tested_target_sha") or ""),
        _guard_tx_files(receipt),
        str(receipt.get("takeover_worker") or ""),
        takeover_identity,
    )


def _guard_tx_identity_matches(
    receipt: Mapping[str, object],
    *,
    current_issue: int,
    current_worker: str,
    current_executor_source: str,
    current_branch: str,
    current_claim_head_sha: str,
    current_claim_blob_sha: str,
    expected_changed_files: Iterable[str] | None,
) -> bool:
    fixed = (
        receipt.get("issue") == current_issue,
        str(receipt.get("worker") or "") == current_worker,
        str(receipt.get("executor_source") or "") == current_executor_source,
        str(receipt.get("branch") or "") == current_branch,
        str(receipt.get("claim_blob_sha") or "") == current_claim_blob_sha,
        str(receipt.get("head_sha") or "") == current_claim_head_sha,
        str(receipt.get("tested_target_sha") or "") == current_claim_head_sha,
    )
    if not all(fixed):
        return False
    if expected_changed_files is not None:
        expected = _normalize_changed_files(expected_changed_files)
        if _guard_tx_files(receipt) != expected:
            return False
    return True


def classify_guard_transaction(
    *,
    receipts: Iterable[Mapping[str, object]],
    current_issue: int,
    current_worker: str,
    current_executor_source: str,
    current_branch: str,
    current_claim_head_sha: str,
    live_branch_head_sha: str,
    current_claim_blob_sha: str,
    now: datetime,
    durable_readbacks: Iterable[Mapping[str, object]] = (),
    expected_changed_files: Iterable[str] | None = None,
) -> GuardTransactionDecision:
    """Classify one exact Remote Guard mutation, deduping equivalent GREEN receipts."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ExecutionClaimError("Guard transaction current time must be timezone-aware")
    current_utc = now.astimezone(timezone.utc)
    green = [
        item
        for item in receipts
        if item.get("schema") == "WHD_REMOTE_GUARD_RECEIPT_V1"
        and item.get("result") == "GREEN"
    ]
    if not green:
        return GuardTransactionDecision(GuardTransactionState.NONE)

    members: list[
        tuple[Mapping[str, object], int, datetime, datetime, tuple[object, ...]]
    ] = []
    ambiguous_runs: list[int] = []
    for receipt in green:
        try:
            run_id = _guard_tx_run_id(receipt)
            issued_at = _guard_tx_timestamp(receipt.get("issued_at"), "issued_at")
            expires_at = _guard_tx_timestamp(receipt.get("expires_at"), "expires_at")
            if expires_at < issued_at:
                raise ExecutionClaimError("Guard transaction validity window is inverted")
            members.append(
                (
                    receipt,
                    run_id,
                    issued_at,
                    expires_at,
                    _guard_tx_equivalence_key(receipt),
                )
            )
        except ExecutionClaimError:
            try:
                ambiguous_runs.append(_guard_tx_run_id(receipt))
            except ExecutionClaimError:
                pass

    if ambiguous_runs or len(members) != len(green):
        run_ids = tuple(
            sorted(
                set(
                    ambiguous_runs
                    + [run_id for _, run_id, _, _, _ in members]
                )
            )
        )
        return GuardTransactionDecision(
            GuardTransactionState.AMBIGUOUS,
            guard_run_ids=run_ids,
            required_next_action="FAIL_CLOSED",
            reason="Guard receipt is malformed or cannot be paired exactly",
        )

    identity_keys = {identity for _, _, _, _, identity in members}
    run_ids = tuple(sorted(run_id for _, run_id, _, _, _ in members))
    if len(identity_keys) != 1:
        return GuardTransactionDecision(
            GuardTransactionState.AMBIGUOUS,
            guard_run_ids=run_ids,
            required_next_action="FAIL_CLOSED",
            reason="multiple GREEN Guard transactions have conflicting mutation identity",
        )

    canonical_all = min(members, key=lambda item: (item[2], item[1]))
    canonical_receipt = canonical_all[0]
    if not _guard_tx_identity_matches(
        canonical_receipt,
        current_issue=current_issue,
        current_worker=current_worker,
        current_executor_source=current_executor_source,
        current_branch=current_branch,
        current_claim_head_sha=current_claim_head_sha,
        current_claim_blob_sha=current_claim_blob_sha,
        expected_changed_files=expected_changed_files,
    ):
        return GuardTransactionDecision(
            GuardTransactionState.AMBIGUOUS,
            guard_run_ids=run_ids,
            required_next_action="FAIL_CLOSED",
            reason="Guard receipt/current ownership identity cannot be paired exactly",
        )

    readbacks = tuple(durable_readbacks)
    proven: list[
        tuple[Mapping[str, object], Mapping[str, object], datetime, int]
    ] = []
    try:
        for receipt, run_id, issued_at, _, _ in members:
            readback = _guard_tx_readback_for(receipt, readbacks)
            if readback is not None and _guard_tx_readback_proves_mutation(
                receipt,
                readback,
                live_branch_head_sha=live_branch_head_sha,
            ):
                proven.append((receipt, readback, issued_at, run_id))
    except ExecutionClaimError:
        return GuardTransactionDecision(
            GuardTransactionState.AMBIGUOUS,
            guard_run_ids=run_ids,
            required_next_action="FAIL_CLOSED",
            reason="Guard transaction durable readback is ambiguous",
        )

    if proven:
        representative = min(proven, key=lambda item: (item[2], item[3]))
        if any(readback.get("reconciled") is True for _, readback, _, _ in proven):
            return GuardTransactionDecision(
                GuardTransactionState.CONSUMED,
                receipt=dict(representative[0]),
                guard_run_ids=run_ids,
                reason=(
                    "equivalent GREEN group has action-specific durable readback "
                    "+ reconciliation complete"
                ),
            )
        return GuardTransactionDecision(
            GuardTransactionState.MUTATION_DONE_RECONCILE_ONLY,
            receipt=dict(representative[0]),
            guard_run_ids=run_ids,
            required_next_action="RECONCILE_ONLY",
            reason=(
                "equivalent GREEN group has durable mutation proof while "
                "coordination metadata is stale"
            ),
        )

    if live_branch_head_sha != current_claim_head_sha:
        return GuardTransactionDecision(
            GuardTransactionState.AMBIGUOUS,
            guard_run_ids=run_ids,
            required_next_action="FAIL_CLOSED",
            reason=(
                "live branch HEAD drifted without action-specific durable mutation proof"
            ),
        )

    live_members = [
        item for item in members if current_utc < item[3]
    ]
    if live_members:
        canonical_live = min(live_members, key=lambda item: (item[2], item[1]))
        return GuardTransactionDecision(
            GuardTransactionState.PENDING,
            receipt=dict(canonical_live[0]),
            guard_run_ids=run_ids,
            required_next_action="CONSUME_GUARD_TRANSACTION",
            reason=(
                "equivalent GREEN receipts collapse to one pending mutation; "
                "only the earliest-issued currently-live receipt is consumable"
            ),
        )

    return GuardTransactionDecision(
        GuardTransactionState.EXPIRED_UNCONSUMED,
        receipt=dict(canonical_receipt),
        guard_run_ids=run_ids,
        required_next_action="FRESH_RECONCILE_THEN_FRESH_GUARD",
        reason="all equivalent GREEN receipts expired without durable mutation proof",
    )


def _guard_tx_evidence(decision: GuardTransactionDecision) -> str:
    receipt = decision.receipt or {}
    return (
        f"issue={receipt.get('issue')} worker={receipt.get('worker')} "
        f"guard_run_id={receipt.get('run_id')} action={receipt.get('action')} "
        f"branch={receipt.get('branch')} head={receipt.get('head_sha')} "
        f"changed_files={receipt.get('changed_files')} "
        f"issued_at={receipt.get('issued_at')} expires_at={receipt.get('expires_at')} "
        f"required_next_action={decision.required_next_action}"
    )


def assert_pending_guard_transaction_clear(
    decision: GuardTransactionDecision,
    *,
    operation: str,
) -> None:
    """Block control-flow progress until the current Guard transaction is resolved."""

    state = decision.state
    if state is GuardTransactionState.PENDING:
        raise ExecutionClaimError(
            "PENDING_GUARD_TRANSACTION_NOT_CONSUMED: "
            f"operation={operation} {_guard_tx_evidence(decision)}"
        )
    if state is GuardTransactionState.MUTATION_DONE_RECONCILE_ONLY:
        raise ExecutionClaimError(
            "DURABLE_MUTATION_ALREADY_HAPPENED: "
            f"operation={operation} required_next_action=RECONCILE_ONLY"
        )
    if state is GuardTransactionState.EXPIRED_UNCONSUMED:
        raise ExecutionClaimError(
            "EXPIRED_UNCONSUMED_GUARD: "
            f"operation={operation} {_guard_tx_evidence(decision)}"
        )
    if state is GuardTransactionState.AMBIGUOUS:
        raise ExecutionClaimError(
            "AMBIGUOUS_GUARD_TRANSACTION: "
            f"operation={operation} guard_run_ids={decision.guard_run_ids}"
        )


def assert_guard_receipt_consumable(
    decision: GuardTransactionDecision,
    *,
    guard_run_id: int,
) -> Mapping[str, object]:
    """Allow a single-use consume only for the one exact current PENDING receipt."""

    if decision.state is GuardTransactionState.PENDING:
        receipt = decision.receipt or {}
        if receipt.get("run_id") != guard_run_id:
            raise ExecutionClaimError(
                "GUARD_RECEIPT_IDENTITY_MISMATCH: requested receipt is not the exact pending transaction"
            )
        return receipt
    if decision.state is GuardTransactionState.EXPIRED_UNCONSUMED:
        raise ExecutionClaimError(
            "EXPIRED_UNCONSUMED: expired GREEN receipt is permanently unconsumable"
        )
    if decision.state is GuardTransactionState.CONSUMED:
        raise ExecutionClaimError("CONSUMED_REPLAY_BLOCKED: Guard receipt replay rejected")
    if decision.state is GuardTransactionState.MUTATION_DONE_RECONCILE_ONLY:
        raise ExecutionClaimError(
            "DURABLE_MUTATION_ALREADY_HAPPENED: Guard receipt replay rejected; reconcile only"
        )
    if decision.state is GuardTransactionState.AMBIGUOUS:
        raise ExecutionClaimError("AMBIGUOUS_GUARD_TRANSACTION: fail closed")
    raise ExecutionClaimError("NO_PENDING_GUARD_TRANSACTION: nothing is consumable")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ExecutionClaimError(f"ambiguous execution claim: duplicate JSON key {key!r}")
        payload[key] = value
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionClaimError(f"missing required claim field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise ExecutionClaimError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


def _require_sha(payload: dict[str, object], key: str) -> str:
    return _validate_sha(_require_text(payload, key), f"claim field {key}")


def _normalize_changed_files(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for index, raw in enumerate(values):
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/"):
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: expected repository-relative path"
            )
        if ".." in PurePosixPath(value).parts:
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: path traversal is not allowed"
            )
        if value not in result:
            result.append(value)
    return tuple(result)


def _is_skill_contract_path(path: str) -> bool:
    return path.startswith(".agents/skills/") and path.endswith("/SKILL.md")


def _assert_skill_authoring_preflight(
    changed_files: tuple[str, ...],
    evidence_paths: Iterable[str],
) -> None:
    skill_targets = tuple(path for path in changed_files if _is_skill_contract_path(path))
    if not skill_targets:
        return

    evidence = tuple(str(path).strip() for path in evidence_paths if str(path).strip())
    if not evidence:
        raise ExecutionClaimError(
            "Skill write preflight missing: .agents/skills/**/SKILL.md mutation requires "
            "canonical Phase6 Preflight evidence including 寫技能"
        )

    try:
        from tools.phase6_skill_preflight import (
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )
    except ModuleNotFoundError:
        from phase6_skill_preflight import (  # type: ignore[no-redef]
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )

    required_skills = required_skills_for(task="", changed_files=changed_files)
    required_references = required_references_for(task="", changed_files=changed_files)
    if "寫技能" not in required_skills:
        raise ExecutionClaimError(
            "Skill write preflight registry defect: 寫技能 is not required for Skill mutation"
        )

    completed_skills = completed_skills_from_evidence(evidence)
    completed_references = completed_references_from_evidence(
        evidence, required_references
    )
    missing_skills = [item for item in required_skills if item not in completed_skills]
    missing_references = [
        item for item in required_references if item not in completed_references
    ]
    if missing_skills or missing_references:
        raise ExecutionClaimError(
            "Skill write preflight incomplete: "
            f"missing_skills={missing_skills!r} "
            f"missing_references={missing_references!r}; "
            "寫技能 and all canonical required references must be completed before mutation"
        )


def _load_takeover_evidence(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"claim-takeover evidence not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"claim-takeover evidence invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionClaimError("claim-takeover evidence root must be an object")
    return payload


def _timestamp_epoch(label: str, value: object) -> float:
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionClaimError(f"claim-takeover {label} timestamp invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionClaimError(f"claim-takeover {label} timestamp must be timezone-aware")
    return parsed.timestamp()


def _assert_user_directed_takeover_authority(
    path: Path | None,
    *,
    issue: int,
    previous_worker: str,
    requesting_worker: str,
    expected_comment_id: int,
) -> None:
    if path is None:
        raise ExecutionClaimError(
            "interactive claim-takeover requires owner-authored user authority evidence"
        )
    payload = _load_takeover_evidence(path)
    comment_id = payload.get("id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        raise ExecutionClaimError("user authority comment id is invalid")
    if comment_id != expected_comment_id:
        raise ExecutionClaimError("user authority comment id mismatch")
    user = payload.get("user")
    if not isinstance(user, dict) or str(user.get("login") or "") != "looaeedr":
        raise ExecutionClaimError("user authority comment must be authored by repository owner")
    body = payload.get("body")
    if not isinstance(body, str):
        raise ExecutionClaimError("user authority comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_USER_DIRECTED_TAKEOVER_V1":
        raise ExecutionClaimError("user authority comment marker mismatch")
    singles: dict[str, str] = {}
    allowed = {"issue", "requesting_worker", "previous_worker", "executor_source"}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise ExecutionClaimError("user authority comment contains malformed line")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in allowed or key in singles:
            raise ExecutionClaimError(
                "user authority comment contains unsupported/duplicate key"
            )
        singles[key] = value
    if set(singles) != allowed:
        raise ExecutionClaimError("user authority comment is missing required keys")
    if singles["issue"] != str(issue):
        raise ExecutionClaimError("user authority issue mismatch")
    if singles["requesting_worker"] != requesting_worker:
        raise ExecutionClaimError("user authority requesting_worker mismatch")
    if singles["previous_worker"] != previous_worker:
        raise ExecutionClaimError("user authority previous_worker mismatch")
    if singles["executor_source"] != "chat":
        raise ExecutionClaimError("user authority executor_source must be chat")


def _assert_takeover_evidence(
    evidence_path: Path | None,
    *,
    claim_path: Path,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    expected_live_head_sha: str,
    user_authority_evidence: Path | None = None,
) -> None:
    if evidence_path is None:
        raise ExecutionClaimError("claim-takeover requires machine stale takeover evidence")
    evidence = _load_takeover_evidence(evidence_path)
    if evidence.get("schema") != "WHD_STALE_CLAIM_TAKEOVER_V1":
        raise ExecutionClaimError("claim-takeover evidence schema mismatch")
    classification = str(evidence.get("classification") or "")
    if classification not in {"EXECUTOR_STUCK", "ORPHANED_SCHEDULER_OWNER"}:
        raise ExecutionClaimError(
            "claim-takeover evidence is not actionable stale/orphaned scheduler evidence"
        )
    if evidence.get("actionable") is not True:
        raise ExecutionClaimError("claim-takeover evidence is not actionable")
    stale_seconds = evidence.get("stale_seconds")
    threshold = evidence.get("stale_after_seconds")
    if isinstance(stale_seconds, bool) or not isinstance(stale_seconds, int):
        raise ExecutionClaimError("claim-takeover stale seconds are invalid")
    if threshold != 600:
        raise ExecutionClaimError("claim-takeover stale threshold must be exactly 600 seconds")
    if classification == "EXECUTOR_STUCK":
        if stale_seconds < 600:
            raise ExecutionClaimError("claim-takeover stale evidence is below 600 seconds")
    else:
        grace = evidence.get("orphan_grace_seconds")
        if grace != 90:
            raise ExecutionClaimError(
                "orphaned scheduler takeover grace must be exactly 90 seconds"
            )
        if stale_seconds < grace or stale_seconds >= 600:
            raise ExecutionClaimError(
                "orphaned scheduler takeover evidence is outside the 90..599 second window"
            )
        if evidence.get("runtime_liveness_status") not in {"MISSING", "EXPIRED"}:
            raise ExecutionClaimError(
                "orphaned scheduler takeover requires missing/expired runtime liveness"
            )
        evidence_blob = _validate_sha(
            str(evidence.get("claim_blob_sha") or ""),
            "orphaned scheduler claim blob SHA",
        )
        actual_blob = _git_blob_sha(claim_path)
        if evidence_blob != actual_blob:
            raise ExecutionClaimError(
                "orphaned scheduler takeover claim blob evidence mismatch"
            )
    observed = _validate_sha(
        str(evidence.get("observed_live_head_sha") or ""),
        "takeover observed live head SHA",
    )
    if observed != expected_live_head_sha:
        raise ExecutionClaimError(
            f"claim-takeover observed live head mismatch expected={expected_live_head_sha} evidence={observed}"
        )
    evidence_claim_head = _validate_sha(
        str(evidence.get("claim_head_sha") or ""),
        "takeover evidence claim head SHA",
    )
    if evidence_claim_head != claim.head_sha:
        raise ExecutionClaimError(
            f"claim-takeover evidence claim head mismatch expected={claim.head_sha} evidence={evidence_claim_head}"
        )
    expected_source = str(raw_claim.get("executor_source") or "unknown").strip() or "unknown"
    if classification == "ORPHANED_SCHEDULER_OWNER" and expected_source != "scheduler":
        raise ExecutionClaimError(
            "orphaned scheduler takeover requires scheduler previous executor source"
        )
    if str(evidence.get("previous_executor_source") or "") != expected_source:
        raise ExecutionClaimError("claim-takeover previous executor source mismatch")

    evidence_previous_worker = str(evidence.get("previous_worker") or "").strip()
    evidence_requesting_worker = str(evidence.get("requesting_worker") or "").strip()
    evidence_requesting_source = str(
        evidence.get("requesting_executor_source") or ""
    ).strip()
    if evidence_previous_worker != claim.worker:
        raise ExecutionClaimError(
            "claim-takeover requires evidence bound to the previous worker"
        )
    if not evidence_requesting_worker or evidence_requesting_worker == claim.worker:
        raise ExecutionClaimError(
            "claim-takeover requires a distinct requesting worker"
        )
    if evidence_requesting_worker.startswith("scheduler."):
        if evidence_requesting_source != "scheduler":
            raise ExecutionClaimError(
                "scheduler requesting worker requires scheduler executor source"
            )
        if evidence.get("user_authority_comment_id") is not None:
            raise ExecutionClaimError(
                "scheduler claim-takeover must not carry user authority evidence"
            )
    else:
        if evidence_requesting_source != "chat":
            raise ExecutionClaimError(
                "interactive claim-takeover requires chat executor source"
            )
        authority_id = evidence.get("user_authority_comment_id")
        if (
            isinstance(authority_id, bool)
            or not isinstance(authority_id, int)
            or authority_id <= 0
        ):
            raise ExecutionClaimError(
                "interactive claim-takeover requires user authority comment id"
            )
        _assert_user_directed_takeover_authority(
            user_authority_evidence,
            issue=claim.issue,
            previous_worker=claim.worker,
            requesting_worker=evidence_requesting_worker,
            expected_comment_id=authority_id,
        )
    if str(evidence.get("claim_phase") or "").upper() != claim.phase:
        raise ExecutionClaimError("claim-takeover evidence claim phase mismatch")
    claim_last_update = raw_claim.get("last_update")
    if claim_last_update is None:
        raise ExecutionClaimError("claim-takeover claim last_update missing")
    if _timestamp_epoch("claim last_update", claim_last_update) != _timestamp_epoch(
        "evidence claim_last_update", evidence.get("claim_last_update")
    ):
        raise ExecutionClaimError("claim-takeover evidence claim last_update mismatch")



def _git_blob_sha(path: Path) -> str:
    data = Path(path).read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def _github_api_json(path: str) -> object:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if repository != "looaeedr/whd":
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation requires GITHUB_REPOSITORY=looaeedr/whd"
        )
    if not token:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation requires authenticated GitHub API access"
        )
    url = f"https://api.github.com/repos/{repository}/{path.lstrip('/')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation GitHub API read failed: {exc}"
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation GitHub API returned invalid JSON"
        ) from exc


def _github_issue_comments(issue: int) -> list[dict[str, object]]:
    comments: list[dict[str, object]] = []
    for page in range(1, 21):
        payload = _github_api_json(f"issues/{issue}/comments?per_page=100&page={page}")
        if not isinstance(payload, list):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation issue-comments response is not a list"
            )
        page_items = [item for item in payload if isinstance(item, dict)]
        comments.extend(page_items)
        if len(payload) < 100:
            return comments
    raise ExecutionClaimError(
        "post-commit claim-head reconciliation exceeded issue-comment pagination limit"
    )


def _github_commit(sha: str) -> dict[str, object]:
    payload = _github_api_json(f"commits/{sha}")
    if not isinstance(payload, dict):
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation commit response is not an object"
        )
    return payload


def _github_issue(issue: int) -> dict[str, object]:
    payload = _github_api_json(f"issues/{issue}")
    if not isinstance(payload, dict):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery issue response is not an object"
        )
    return payload


def _parse_remote_guard_request_comment(
    comment: dict[str, object],
) -> dict[str, object] | None:
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") != "looaeedr":
        return None
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_REMOTE_GUARD_REQUEST_V1":
        return None
    singles: dict[str, str] = {}
    changed_files: list[str] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            return None
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "changed_file":
            changed_files.append(value)
        elif key in singles:
            return None
        else:
            singles[key] = value
    payload: dict[str, object] = dict(singles)
    payload["changed_files"] = changed_files
    payload["comment_id"] = comment.get("id")
    return payload


def _parse_remote_guard_receipt_comment(
    comment: dict[str, object],
) -> dict[str, object] | None:
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
        return None
    body = comment.get("body")
    if not isinstance(body, str) or not body.startswith("WHD_REMOTE_GUARD_RESULT_V1"):
        return None
    match = re.search(r"~~~json\s*(\{.*?\})\s*~~~", body, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def exact_remote_guard_receipts_from_comments(
    comments: Iterable[Mapping[str, object]],
    *,
    issue: int,
    worker: str,
    executor_source: str,
    branch: str,
    base_sha: str,
    head_sha: str,
    claim_blob_sha: str,
) -> tuple[dict[str, object], ...]:
    """Select only GREEN receipts bound to the current exact ownership identity."""

    selected: list[dict[str, object]] = []
    for raw in comments:
        comment = dict(raw)
        receipt = _parse_remote_guard_receipt_comment(comment)
        if receipt is None or receipt.get("result") != "GREEN":
            continue
        fixed = (
            receipt.get("issue") == issue,
            str(receipt.get("worker") or "") == worker,
            str(receipt.get("executor_source") or "") == executor_source,
            str(receipt.get("branch") or "") == branch,
            str(receipt.get("base_sha") or "") == base_sha,
            str(receipt.get("head_sha") or "") == head_sha,
            str(receipt.get("tested_target_sha") or "") == head_sha,
            str(receipt.get("claim_blob_sha") or "") == claim_blob_sha,
        )
        if all(fixed):
            selected.append(dict(receipt))
    return tuple(selected)


def assert_remote_guard_request_permitted(
    decision: GuardTransactionDecision,
    *,
    reconciliation_request: bool = False,
) -> None:
    """Fail closed before minting a second Guard against unresolved current state."""

    if decision.state is GuardTransactionState.PENDING:
        raise ExecutionClaimError(
            "REMOTE_GUARD_REJECTED: PENDING_GUARD_TRANSACTION "
            + _guard_tx_evidence(decision)
        )
    if decision.state is GuardTransactionState.AMBIGUOUS:
        raise ExecutionClaimError(
            "REMOTE_GUARD_REJECTED: AMBIGUOUS_GUARD_TRANSACTION "
            f"guard_run_ids={decision.guard_run_ids}"
        )
    if decision.state is GuardTransactionState.MUTATION_DONE_RECONCILE_ONLY:
        if reconciliation_request:
            return
        raise ExecutionClaimError(
            "REMOTE_GUARD_REJECTED: DURABLE_MUTATION_ALREADY_HAPPENED "
            "required_next_action=RECONCILE_ONLY"
        )
    # EXPIRED_UNCONSUMED is permanently unconsumable, but after this workflow has
    # fresh-read the exact current identity it may mint the one fresh recovery Guard.
    if decision.state in {
        GuardTransactionState.NONE,
        GuardTransactionState.CONSUMED,
        GuardTransactionState.EXPIRED_UNCONSUMED,
    }:
        return
    raise ExecutionClaimError(
        f"REMOTE_GUARD_REJECTED: unsupported transaction state {decision.state.value}"
    )


def _reconcile_timestamp_epoch(label: str, value: object) -> float:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation {label} timestamp invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation {label} timestamp must be timezone-aware"
        )
    return parsed.timestamp()


def _load_raw_claim_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"cannot re-read execution claim: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionClaimError("execution claim root must be object")
    return payload


def _load_legacy_postcommit_recovery(path: Path | None) -> dict[str, object]:
    if path is None:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery evidence is required"
        )
    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(
            f"legacy postcommit reconciliation recovery evidence invalid: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery evidence root must be object"
        )
    return payload


def _assert_legacy_postcommit_reconcile_authority(
    path: Path | None,
    *,
    issue: int,
    worker: str,
    executor_source: str,
    branch: str,
    claim_head_sha: str,
    live_head_sha: str,
    current_claim_blob: str,
    prior_guard_run_id: int,
    prior_request_comment_id: int,
    commit_file_set: tuple[str, ...],
) -> None:
    payload = _load_legacy_postcommit_recovery(path)
    comment_id = payload.get("id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery comment id is invalid"
        )
    user = payload.get("user")
    if not isinstance(user, dict) or str(user.get("login") or "") != "looaeedr":
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery must be owner-authored"
        )
    body = payload.get("body")
    if not isinstance(body, str):
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery comment body is missing"
        )
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_LEGACY_POSTCOMMIT_RECONCILE_V1":
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery marker mismatch"
        )

    required = {
        "issue",
        "worker",
        "executor_source",
        "branch",
        "claim_blob_sha",
        "claim_head_sha",
        "live_head_sha",
        "prior_guard_run_id",
        "prior_request_comment_id",
        "recovery_reason",
    }
    fields: dict[str, str] = {}
    changed_files: list[str] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise ExecutionClaimError(
                "legacy postcommit reconciliation recovery contains malformed line"
            )
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if key == "changed_file":
            if not value:
                raise ExecutionClaimError(
                    "legacy postcommit reconciliation recovery changed_file is blank"
                )
            changed_files.append(value)
            continue
        if key not in required or key in fields or not value:
            raise ExecutionClaimError(
                "legacy postcommit reconciliation recovery contains unsupported/duplicate key"
            )
        fields[key] = value

    if set(fields) != required or not changed_files:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery is missing required identity"
        )
    if len(changed_files) != len(set(changed_files)):
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery changed_file is ambiguous"
        )
    if fields["issue"] != str(issue):
        raise ExecutionClaimError("legacy postcommit reconciliation recovery issue mismatch")
    if fields["worker"] != worker:
        raise ExecutionClaimError("legacy postcommit reconciliation recovery worker mismatch")
    if fields["executor_source"] != executor_source:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery executor_source mismatch"
        )
    if fields["branch"] != branch:
        raise ExecutionClaimError("legacy postcommit reconciliation recovery branch mismatch")
    if _validate_sha(fields["claim_blob_sha"], "legacy recovery claim blob SHA") != current_claim_blob:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery claim blob mismatch"
        )
    if _validate_sha(fields["claim_head_sha"], "legacy recovery claim HEAD") != claim_head_sha:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery claim head mismatch"
        )
    if _validate_sha(fields["live_head_sha"], "legacy recovery live HEAD") != live_head_sha:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery live head mismatch"
        )
    try:
        recovery_run_id = int(fields["prior_guard_run_id"])
        recovery_request_id = int(fields["prior_request_comment_id"])
    except ValueError as exc:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery prior identity is invalid"
        ) from exc
    if recovery_run_id != prior_guard_run_id or recovery_run_id <= 0:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery prior guard run mismatch"
        )
    if recovery_request_id != prior_request_comment_id or recovery_request_id <= 0:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery prior request mismatch"
        )
    if fields["recovery_reason"] != "LEGACY_RECEIPT_WINDOW_EXPIRED_AFTER_MUTATION":
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery reason mismatch"
        )
    if tuple(sorted(changed_files)) != commit_file_set:
        raise ExecutionClaimError(
            "legacy postcommit reconciliation recovery changed-file mismatch"
        )


def _assert_post_commit_claim_head_reconciliation(
    path: Path,
    *,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    issue: int,
    worker: str,
    branch: str,
    expected_live_head_sha: str,
    changed_files: tuple[str, ...],
    legacy_reconcile_recovery: Path | None = None,
) -> None:
    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    expected_checkpoint_path = f".dispatch/checkpoints/issue-{issue}.json"
    allowed_scopes = {
        (expected_claim_path,),
        (expected_claim_path, expected_checkpoint_path),
        (expected_checkpoint_path, expected_claim_path),
    }
    if changed_files not in allowed_scopes:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation may write only the exact shared "
            "claim path or exact claim+checkpoint pair"
        )

    commit = _github_commit(expected_live_head_sha)
    if str(commit.get("sha") or "") != expected_live_head_sha:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation live commit SHA mismatch"
        )
    parents = commit.get("parents")
    if not isinstance(parents, list):
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation commit parent evidence is malformed"
        )

    merge_production_parent: str | None = None
    is_direct_child = (
        len(parents) == 1
        and isinstance(parents[0], dict)
        and str(parents[0].get("sha") or "") == claim.head_sha
    )
    if not is_direct_child:
        production_target = str(raw_claim.get("production_target") or "").strip()
        if not production_target:
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation merge sync requires production_target"
            )
        if (
            len(parents) != 2
            or not isinstance(parents[0], dict)
            or not isinstance(parents[1], dict)
        ):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation merge sync requires exactly two parents"
            )

        parent_shas = [str(parent.get("sha") or "") for parent in parents]
        claim_parent_indexes = [
            index for index, sha in enumerate(parent_shas) if sha == claim.head_sha
        ]
        if len(claim_parent_indexes) != 1:
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation merge sync requires exactly one "
                "parent to match claim HEAD"
            )

        merge_production_parent = parent_shas[1 - claim_parent_indexes[0]]
        if not _SHA_RE.fullmatch(merge_production_parent):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production parent SHA is malformed"
            )

        encoded_target = urllib.parse.quote(production_target, safe="")
        production = _github_api_json(f"branches/{encoded_target}")
        if not isinstance(production, dict):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production branch response is malformed"
            )
        production_commit = production.get("commit")
        production_head = (
            str(production_commit.get("sha") or "")
            if isinstance(production_commit, dict)
            else ""
        )
        if not _SHA_RE.fullmatch(production_head):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production target HEAD is malformed"
            )
        if production_head != merge_production_parent:
            comparison = _github_api_json(
                f"compare/{merge_production_parent}...{production_head}"
            )
            merge_base = (
                comparison.get("merge_base_commit")
                if isinstance(comparison, dict)
                else None
            )
            if (
                not isinstance(comparison, dict)
                or str(comparison.get("status") or "") not in {"ahead", "identical"}
                or not isinstance(merge_base, dict)
                or str(merge_base.get("sha") or "") != merge_production_parent
            ):
                raise ExecutionClaimError(
                    "post-commit claim-head reconciliation production parent is not "
                    "the exact target HEAD used for sync or an ancestor of current production"
                )

    if merge_production_parent is None:
        files = commit.get("files")
        file_evidence_label = "commit changed-file"
    else:
        work_delta = _github_api_json(
            f"compare/{merge_production_parent}...{expected_live_head_sha}"
        )
        merge_base = (
            work_delta.get("merge_base_commit")
            if isinstance(work_delta, dict)
            else None
        )
        if (
            not isinstance(work_delta, dict)
            or str(work_delta.get("status") or "") not in {"ahead", "identical"}
            or not isinstance(merge_base, dict)
            or str(merge_base.get("sha") or "") != merge_production_parent
        ):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation work-delta comparison is not "
                "rooted at the production parent"
            )
        files = work_delta.get("files")
        file_evidence_label = "work-delta"

    if not isinstance(files, list) or not files:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation {file_evidence_label} evidence missing"
        )
    commit_files: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise ExecutionClaimError(
                f"post-commit claim-head reconciliation {file_evidence_label} evidence malformed"
            )
        filename = str(item["filename"])
        if filename in commit_files:
            raise ExecutionClaimError(
                f"post-commit claim-head reconciliation {file_evidence_label} evidence is ambiguous"
            )
        commit_files.append(filename)
    commit_file_set = tuple(sorted(commit_files))

    metadata = commit.get("commit")
    committer = metadata.get("committer") if isinstance(metadata, dict) else None
    committed_at = committer.get("date") if isinstance(committer, dict) else None
    commit_epoch = _reconcile_timestamp_epoch("commit", committed_at)

    comments = _github_issue_comments(issue)
    requests_by_id: dict[int, dict[str, object]] = {}
    for comment in comments:
        request = _parse_remote_guard_request_comment(comment)
        comment_id = request.get("comment_id") if request else None
        if request is not None and isinstance(comment_id, int):
            requests_by_id[comment_id] = request

    current_claim_blob = _git_blob_sha(path)
    raw_source = str(raw_claim.get("executor_source") or "").strip()
    expected_executor_source = "scheduler" if raw_source == "scheduler" else "chat"
    expired_legacy_candidates: list[tuple[int, int]] = []

    for comment in comments:
        receipt = _parse_remote_guard_receipt_comment(comment)
        if receipt is None:
            continue
        if receipt.get("schema") != "WHD_REMOTE_GUARD_RECEIPT_V1":
            continue
        if receipt.get("result") != "GREEN" or receipt.get("reason") != "EXECUTION_CLAIM_GUARD_GREEN":
            continue
        if receipt.get("action") not in {"write", "commit"}:
            continue
        if receipt.get("issue") != issue:
            continue
        if str(receipt.get("worker") or "") != worker:
            continue
        if str(receipt.get("executor_source") or "") != expected_executor_source:
            continue
        if str(receipt.get("branch") or "") != branch:
            continue
        if str(receipt.get("base_sha") or "") != claim.base_sha:
            continue
        if str(receipt.get("head_sha") or "") != claim.head_sha:
            continue
        if str(receipt.get("tested_target_sha") or "") != claim.head_sha:
            continue
        if str(receipt.get("claim_blob_sha") or "") != current_claim_blob:
            continue
        if (
            merge_production_parent is not None
            and str(receipt.get("guard_authority_sha") or "")
            != merge_production_parent
        ):
            continue

        receipt_files = receipt.get("changed_files")
        if not isinstance(receipt_files, list):
            continue
        receipt_file_set = tuple(sorted(str(item) for item in receipt_files))
        if len(receipt_file_set) != len(set(receipt_file_set)):
            continue
        if not set(commit_file_set).issubset(receipt_file_set):
            continue

        request_comment_id = receipt.get("request_comment_id")
        if isinstance(request_comment_id, bool) or not isinstance(request_comment_id, int):
            continue
        request = requests_by_id.get(request_comment_id)
        if request is None:
            continue
        fixed_keys = (
            "issue",
            "worker",
            "executor_source",
            "action",
            "branch",
            "base_sha",
            "head_sha",
            "claim_blob_sha",
            "guard_authority_sha",
            "tested_target_sha",
        )
        if any(str(request.get(key) or "") != str(receipt.get(key) or "") for key in fixed_keys):
            continue
        request_files = request.get("changed_files")
        if not isinstance(request_files, list):
            continue
        request_file_set = tuple(sorted(str(item) for item in request_files))
        if request_file_set != receipt_file_set:
            continue

        issued_epoch = _reconcile_timestamp_epoch("receipt issued_at", receipt.get("issued_at"))
        expires_epoch = _reconcile_timestamp_epoch("receipt expires_at", receipt.get("expires_at"))
        if issued_epoch <= commit_epoch <= expires_epoch:
            return

        run_id = receipt.get("run_id")
        if (
            is_direct_child
            and merge_production_parent is None
            and issued_epoch <= expires_epoch < commit_epoch
            and receipt_file_set == commit_file_set
            and not isinstance(run_id, bool)
            and isinstance(run_id, int)
            and run_id > 0
        ):
            expired_legacy_candidates.append((run_id, request_comment_id))

    if legacy_reconcile_recovery is not None:
        if not is_direct_child or merge_production_parent is not None:
            raise ExecutionClaimError(
                "legacy postcommit reconciliation recovery is restricted to a single direct-child commit"
            )
        if len(expired_legacy_candidates) != 1:
            raise ExecutionClaimError(
                "legacy postcommit reconciliation recovery requires exactly one matching expired prior GREEN receipt"
            )
        prior_guard_run_id, prior_request_comment_id = expired_legacy_candidates[0]
        _assert_legacy_postcommit_reconcile_authority(
            legacy_reconcile_recovery,
            issue=issue,
            worker=worker,
            executor_source=expected_executor_source,
            branch=branch,
            claim_head_sha=claim.head_sha,
            live_head_sha=expected_live_head_sha,
            current_claim_blob=current_claim_blob,
            prior_guard_run_id=prior_guard_run_id,
            prior_request_comment_id=prior_request_comment_id,
            commit_file_set=commit_file_set,
        )
        return

    raise ExecutionClaimError(
        "post-commit claim-head reconciliation lacks a matching prior GREEN mutation receipt "
        "bound to the current claim blob, direct child commit, changed-file set, and receipt window"
    )



def _assert_reopened_released_claim_reactivation(
    path: Path,
    *,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    issue: int,
    worker: str,
    branch: str,
    changed_files: tuple[str, ...],
) -> None:
    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    if changed_files != (expected_claim_path,):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery may write only the exact shared claim path"
        )
    if claim.phase != "RELEASED":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires phase=RELEASED"
        )
    if str(raw_claim.get("executor_source") or "").strip() != "scheduler":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery is restricted to scheduler-owned claims"
        )
    if not worker.startswith("scheduler."):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires a unique scheduler lane identity"
        )
    if branch != claim.work_branch:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery cannot use a delegated branch"
        )

    live_issue = _github_issue(issue)
    if str(live_issue.get("state") or "").lower() != "open":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires the owning Issue to be open"
        )
    if str(live_issue.get("state_reason") or "").lower() != "reopened":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires state_reason=reopened"
        )

    pointer: dict[str, str] | None = None
    for comment in _github_issue_comments(issue):
        user = comment.get("user")
        body = comment.get("body")
        if not isinstance(user, dict) or user.get("login") != "looaeedr":
            continue
        if not isinstance(body, str):
            continue
        lines = body.replace("\r\n", "\n").split("\n")
        if not lines or lines[0].strip() != "WHD_PROCESS_RECOVERY_POINTER_V1":
            continue
        fields: dict[str, str] = {}
        malformed = False
        for raw in lines[1:]:
            if not raw.strip():
                continue
            if "=" not in raw:
                malformed = True
                break
            key, value = raw.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key or not value or key in fields:
                malformed = True
                break
            fields[key] = value
        if malformed:
            continue
        if fields.get("process_state") != "REOPENED_INVALID_FINALIZATION_EVIDENCE":
            continue
        if fields.get("resume_condition") != "TRUSTED_REMOTE_FINALIZATION_EXECUTOR_INTEGRATED":
            continue
        if fields.get("resume_action") != "RUN_MACHINE_FINALIZATION_PROOF_THEN_CLOSE_READBACK_RELEASE":
            continue
        pointer = fields

    if pointer is None:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery lacks owner-authored WHD_PROCESS_RECOVERY_POINTER_V1"
        )

    try:
        blocking_issue = int(pointer["blocking_repair_issue"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery pointer has invalid blocking_repair_issue"
        ) from exc
    if blocking_issue <= 0 or blocking_issue == issue:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery pointer blocking issue is invalid"
        )

    repair = _github_issue(blocking_issue)
    repair_body = str(repair.get("body") or "")
    if f"#{issue}" not in repair_body:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery blocking issue is not bound to the owning Issue"
        )
    lowered = repair_body.lower()
    if "trusted" not in lowered or "finalization" not in lowered:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery blocking issue does not describe trusted finalization repair"
        )

    workflow = _github_api_json(
        "contents/.github/workflows/whd-remote-finalization.yml?ref=main"
    )
    if not isinstance(workflow, dict) or workflow.get("type") != "file":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires trusted finalization workflow on main"
        )
    workflow_sha = str(workflow.get("sha") or "")
    if not _SHA_RE.fullmatch(workflow_sha):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery trusted workflow identity is malformed"
        )


def _normalize_delegated(payload: dict[str, object]) -> tuple[str, ...]:
    raw = payload.get("delegated_branches", [])
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ExecutionClaimError("malformed delegated_branches: expected list")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ExecutionClaimError(
                f"malformed delegated_branches[{index}]: expected nonblank branch"
            )
        result.append(item.strip())
    if len(set(result)) != len(result):
        raise ExecutionClaimError("malformed delegated_branches: duplicate branch")
    return tuple(result)


@dataclass(frozen=True)
class ExecutionClaim:
    issue: int
    issue_url: str
    worker: str
    work_branch: str
    claimed_at: str
    base_sha: str
    head_sha: str
    phase: str
    delegated_branches: tuple[str, ...] = ()


def load_execution_claim(
    path: Path,
    *,
    allow_released_recovery: bool = False,
    allow_unknown_phase_recovery: bool = False,
) -> ExecutionClaim:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"execution claim not found: {path}") from exc
    except ExecutionClaimError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"malformed execution claim {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ExecutionClaimError("malformed execution claim: root must be an object")

    issue = payload.get("issue")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("missing required claim field: issue")

    issue_url = _require_text(payload, "issue_url")
    worker = _require_text(payload, "worker")
    work_branch = _require_text(payload, "work_branch")
    claimed_at = _require_text(payload, "claimed_at")
    base_sha = _require_sha(payload, "base_sha")
    head_sha = _require_sha(payload, "head_sha")
    phase = _require_text(payload, "phase").upper()
    delegated = _normalize_delegated(payload)

    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if issue_url != expected_url:
        raise ExecutionClaimError(
            f"claim issue_url mismatch: expected {expected_url!r}, got {issue_url!r}"
        )
    if phase in INACTIVE_PHASES:
        if not (allow_released_recovery and phase == "RELEASED"):
            raise ExecutionClaimError(f"execution claim is inactive: phase={phase}")
    elif phase not in ACTIVE_PHASES:
        if not allow_unknown_phase_recovery:
            raise ExecutionClaimError(
                f"ambiguous execution claim state: unknown phase={phase}"
            )

    return ExecutionClaim(
        issue=issue,
        issue_url=issue_url,
        worker=worker,
        work_branch=work_branch,
        claimed_at=claimed_at,
        base_sha=base_sha,
        head_sha=head_sha,
        phase=phase,
        delegated_branches=delegated,
    )



def _load_active_claim_checkpoint(path: Path):
    try:
        from tools.continuity_controller import CheckpointError, load_checkpoint
    except ModuleNotFoundError:
        from continuity_controller import CheckpointError, load_checkpoint  # type: ignore[no-redef]

    try:
        return load_checkpoint(Path(path))
    except CheckpointError as exc:
        raise ExecutionClaimError(
            f"ACTIVE_CLAIM_REQUIRES_CHECKPOINT: {exc}"
        ) from exc


def _assert_claim_checkpoint_identity(
    claim: "ExecutionClaim",
    checkpoint_path: Path,
):
    """Validate exact issue/branch/head binding between one active claim and checkpoint."""

    if claim.phase not in ACTIVE_PHASES:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: "
            f"claim is not active: phase={claim.phase}"
        )

    checkpoint = _load_active_claim_checkpoint(checkpoint_path)
    if str(checkpoint.issue) != str(claim.issue):
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: checkpoint issue mismatch "
            f"expected={claim.issue} actual={checkpoint.issue}"
        )
    if checkpoint.branch != claim.work_branch:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: checkpoint branch mismatch "
            f"expected={claim.work_branch!r} actual={checkpoint.branch!r}"
        )
    if checkpoint.head_sha != claim.head_sha:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: checkpoint head mismatch "
            f"expected={claim.head_sha} actual={checkpoint.head_sha}"
        )
    return checkpoint


def assert_active_claim_requires_checkpoint(
    claim: "ExecutionClaim",
    checkpoint_path: Path,
):
    """Validate the exact non-terminal checkpoint paired with one active claim."""

    checkpoint = _assert_claim_checkpoint_identity(claim, checkpoint_path)
    state_value = getattr(checkpoint.state, "value", str(checkpoint.state))
    if state_value in {"TERMINAL_SUCCESS", "TERMINAL_FAILURE"}:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: active claim cannot use "
            f"terminal checkpoint state={state_value}"
        )
    return checkpoint


def assert_execution_claim_checkpoint_prewrite(
    claim: "ExecutionClaim",
    checkpoint_path: Path,
    *,
    action: str,
    changed_files: Iterable[str],
):
    """Validate checkpoint compatibility for one guarded prewrite action.

    Normal repository actions still require a non-terminal checkpoint. The only
    terminal-checkpoint exception is an exact canonical closure coordination write:
    checkpoint-only or the atomic claim+checkpoint pair while closure is pending.
    """

    checkpoint = _assert_claim_checkpoint_identity(claim, checkpoint_path)
    state_value = getattr(checkpoint.state, "value", str(checkpoint.state))
    if state_value not in {"TERMINAL_SUCCESS", "TERMINAL_FAILURE"}:
        return checkpoint

    normalized = _normalize_changed_files(changed_files)
    claim_path = f".dispatch/claims/issue-{claim.issue}.json"
    checkpoint_repo_path = f".dispatch/checkpoints/issue-{claim.issue}.json"
    allowed_scopes = {
        (checkpoint_repo_path,),
        (claim_path, checkpoint_repo_path),
        (checkpoint_repo_path, claim_path),
    }
    closure_state = getattr(
        checkpoint.closure_state,
        "value",
        str(checkpoint.closure_state),
    )
    pending_closure_states = {
        "FINALIZATION_PENDING",
        "ISSUE_CLOSE_PENDING",
        "RELEASE_HANDOFF_PENDING",
    }
    if (
        action != "write"
        or normalized not in allowed_scopes
        or closure_state not in pending_closure_states
    ):
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: terminal checkpoint permits only "
            "an exact canonical closure coordination write"
        )
    return checkpoint


def assert_legacy_checkpoint_repair_transaction(
    prior_claim_path: Path,
    candidate_claim_path: Path,
    candidate_checkpoint_path: Path,
    *,
    prior_checkpoint_exists: bool,
    changed_files: Iterable[str],
):
    """Validate the one narrow legacy claim-without-checkpoint bootstrap.

    The claim is immutable in this repair.  Only the missing checkpoint is
    bootstrapped; any claim/head/owner/phase continuity update must use the
    normal evidence-bound reconciliation path afterwards.
    """

    if prior_checkpoint_exists:
        raise ExecutionClaimError(
            "LEGACY_CHECKPOINT_REPAIR: prior checkpoint must be missing"
        )

    prior_path = Path(prior_claim_path)
    candidate_path = Path(candidate_claim_path)
    try:
        prior_bytes = prior_path.read_bytes()
        candidate_bytes = candidate_path.read_bytes()
    except OSError as exc:
        raise ExecutionClaimError(
            f"LEGACY_CHECKPOINT_REPAIR: prior claim must exist: {exc}"
        ) from exc

    if prior_bytes != candidate_bytes:
        raise ExecutionClaimError(
            "LEGACY_CHECKPOINT_REPAIR: candidate claim must remain unchanged"
        )

    claim = load_execution_claim(candidate_path)
    normalized = _normalize_changed_files(changed_files)
    claim_path = f".dispatch/claims/issue-{claim.issue}.json"
    checkpoint_repo_path = f".dispatch/checkpoints/issue-{claim.issue}.json"
    if len(normalized) != 2 or set(normalized) != {
        claim_path,
        checkpoint_repo_path,
    }:
        raise ExecutionClaimError(
            "LEGACY_CHECKPOINT_REPAIR: must atomically write the exact "
            "claim+checkpoint pair"
        )

    return assert_active_claim_requires_checkpoint(
        claim,
        Path(candidate_checkpoint_path),
    )


def assert_active_claim_activation_transaction(
    claim: "ExecutionClaim",
    checkpoint_path: Path,
    *,
    transition: str,
    changed_files: Iterable[str],
):
    """Validate one active-claim activation/re-activation transaction."""

    transition = str(transition).strip()
    allowed = {"fresh-create", "successor-create", "takeover", "reactivate", "legacy-checkpoint-repair"}
    if transition not in allowed:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: unsupported activation transition "
            f"{transition!r}"
        )

    checkpoint = assert_active_claim_requires_checkpoint(claim, checkpoint_path)
    normalized = _normalize_changed_files(changed_files)
    claim_path = f".dispatch/claims/issue-{claim.issue}.json"
    checkpoint_repo_path = f".dispatch/checkpoints/issue-{claim.issue}.json"

    if transition in {"fresh-create", "successor-create", "legacy-checkpoint-repair"}:
        if len(normalized) != 2 or set(normalized) != {
            claim_path,
            checkpoint_repo_path,
        }:
            raise ExecutionClaimError(
                "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: fresh/successor/legacy repair "
                "must atomically use the exact claim+checkpoint pair"
            )
    elif claim_path not in normalized:
        raise ExecutionClaimError(
            "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: takeover/reactivation must "
            "include the exact claim path and actively validate the checkpoint"
        )

    return checkpoint

def assert_execution_claim(
    path: Path,
    *,
    issue: int,
    worker: str,
    branch: str,
    action: str,
    expected_base_sha: str,
    expected_head_sha: str,
    changed_files: Iterable[str] = (),
    preflight_evidence: Iterable[str] = (),
    takeover_evidence: Path | None = None,
    user_authority_evidence: Path | None = None,
    legacy_reconcile_recovery: Path | None = None,
) -> ExecutionClaim:
    """Return the validated current claim or raise before one repository action."""
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("issue must be a positive integer")
    worker = str(worker).strip()
    branch = str(branch).strip()
    action = str(action).strip()
    expected_base_sha = _validate_sha(expected_base_sha, "expected base SHA")
    expected_head_sha = _validate_sha(expected_head_sha, "expected head SHA")
    if not worker:
        raise ExecutionClaimError("worker must be nonblank")
    if not branch:
        raise ExecutionClaimError("branch must be nonblank")
    if action not in ALLOWED_ACTIONS:
        raise ExecutionClaimError(
            f"unsupported guarded action {action!r}; allowed={sorted(ALLOWED_ACTIONS)!r}"
        )

    normalized_changed_files = _normalize_changed_files(changed_files)
    if action in FILE_MUTATION_ACTIONS and not normalized_changed_files:
        raise ExecutionClaimError(
            f"changed-file identity is required for guarded action {action!r}"
        )

    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    expected_checkpoint_path = f".dispatch/checkpoints/issue-{issue}.json"
    exact_claim_write = (
        action == "write" and normalized_changed_files == (expected_claim_path,)
    )
    post_commit_reconcile_scopes = {
        (expected_claim_path,),
        (expected_claim_path, expected_checkpoint_path),
        (expected_checkpoint_path, expected_claim_path),
    }
    claim = load_execution_claim(
        path,
        allow_released_recovery=exact_claim_write,
        allow_unknown_phase_recovery=exact_claim_write,
    )
    if claim.issue != issue:
        raise ExecutionClaimError(
            f"issue mismatch: requested #{issue}, claim owns #{claim.issue}"
        )
    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if claim.issue_url != expected_url:
        raise ExecutionClaimError(
            f"issue URL mismatch: expected {expected_url!r}, got {claim.issue_url!r}"
        )
    if claim.worker != worker:
        raise ExecutionClaimError(
            f"worker is not claim owner: requested={worker!r}, owner={claim.worker!r}"
        )
    if claim.base_sha != expected_base_sha:
        raise ExecutionClaimError(
            f"base SHA mismatch: expected={expected_base_sha}, claim={claim.base_sha}"
        )
    allowed_branches = {claim.work_branch, *claim.delegated_branches}
    if branch not in allowed_branches:
        raise ExecutionClaimError(
            f"branch is not authorized by execution claim: {branch!r}; "
            f"owner_branch={claim.work_branch!r}; delegated={claim.delegated_branches!r}"
        )

    raw_claim: dict[str, object] | None = None
    if claim.phase == "RELEASED":
        raw_claim = _load_raw_claim_payload(path)
        _assert_reopened_released_claim_reactivation(
            path,
            claim=claim,
            raw_claim=raw_claim,
            issue=issue,
            worker=worker,
            branch=branch,
            changed_files=normalized_changed_files,
        )

    if action != "claim-takeover" and claim.head_sha != expected_head_sha:
        if action == "write" and normalized_changed_files in post_commit_reconcile_scopes:
            raw_claim = _load_raw_claim_payload(path)
            _assert_post_commit_claim_head_reconciliation(
                path,
                claim=claim,
                raw_claim=raw_claim,
                issue=issue,
                worker=worker,
                branch=branch,
                expected_live_head_sha=expected_head_sha,
                changed_files=normalized_changed_files,
                legacy_reconcile_recovery=legacy_reconcile_recovery,
            )
        else:
            raise ExecutionClaimError(
                f"stale claim head SHA: expected={expected_head_sha}, claim={claim.head_sha}"
            )

    if action == "claim-takeover":
        raw_claim = raw_claim or _load_raw_claim_payload(path)
        _assert_takeover_evidence(
            takeover_evidence,
            claim_path=path,
            claim=claim,
            raw_claim=raw_claim,
            expected_live_head_sha=expected_head_sha,
            user_authority_evidence=user_authority_evidence,
        )

    if action in FILE_MUTATION_ACTIONS:
        _assert_skill_authoring_preflight(
            normalized_changed_files,
            preflight_evidence,
        )
    return claim


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed unless the caller owns the current shared WHD execution claim"
    )
    parser.add_argument("--claim", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--base-sha", required=True, dest="expected_base_sha")
    parser.add_argument("--head-sha", required=True, dest="expected_head_sha")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="repository-relative file mutated by write/commit; repeat for multiple files",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="exact continuity checkpoint required by ACTIVE_CLAIM_REQUIRES_CHECKPOINT",
    )
    parser.add_argument(
        "--preflight-evidence",
        action="append",
        default=[],
        help="Phase6 Preflight evidence file; required when a changed file is a Skill SKILL.md",
    )
    parser.add_argument(
        "--takeover-evidence",
        type=Path,
        help="machine evidence emitted by tools/stale_claim_takeover.py; required for claim-takeover",
    )
    parser.add_argument(
        "--user-authority-evidence",
        type=Path,
        help="owner-authored WHD_USER_DIRECTED_TAKEOVER_V1 GitHub issue-comment JSON; required for interactive takeover",
    )
    parser.add_argument(
        "--legacy-reconcile-recovery",
        type=Path,
        help="owner-authored WHD_LEGACY_POSTCOMMIT_RECONCILE_V1 issue-comment JSON; narrow legacy out-of-window reconciliation only",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        claim = assert_execution_claim(
            args.claim,
            issue=args.issue,
            worker=args.worker,
            branch=args.branch,
            action=args.action,
            expected_base_sha=args.expected_base_sha,
            expected_head_sha=args.expected_head_sha,
            changed_files=args.changed_file,
            preflight_evidence=args.preflight_evidence,
            takeover_evidence=args.takeover_evidence,
            user_authority_evidence=args.user_authority_evidence,
            legacy_reconcile_recovery=args.legacy_reconcile_recovery,
        )

        normalized_changed_files = _normalize_changed_files(args.changed_file)
        if claim.head_sha != args.expected_head_sha and args.action == "write":
            expected_pair = {
                f".dispatch/claims/issue-{args.issue}.json",
                f".dispatch/checkpoints/issue-{args.issue}.json",
            }
            if (
                len(normalized_changed_files) != 2
                or set(normalized_changed_files) != expected_pair
            ):
                raise ExecutionClaimError(
                    "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: post-commit reconciliation "
                    "must atomically update the exact claim+checkpoint pair"
                )

        if args.checkpoint is None:
            raise ExecutionClaimError(
                "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: --checkpoint is required "
                "for every trusted prewrite action"
            )
        assert_execution_claim_checkpoint_prewrite(
            claim,
            args.checkpoint,
            action=args.action,
            changed_files=normalized_changed_files,
        )
    except ExecutionClaimError as exc:
        print(f"EXECUTION_CLAIM_GUARD_ERROR: {exc}")
        return 2
    print(
        "EXECUTION_CLAIM_GUARD_GREEN "
        f"issue={claim.issue} worker={claim.worker} branch={args.branch} action={args.action} "
        f"base_sha={claim.base_sha} head_sha={claim.head_sha} phase={claim.phase}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
