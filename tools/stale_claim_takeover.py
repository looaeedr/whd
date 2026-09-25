"""Executable stale execution-claim takeover policy for WHD schedulers.

The evaluator is pure: it never mutates GitHub, claims, branches, or runs. It turns
fresh durable observations into one fail-closed takeover decision. A scheduler may
request a guarded claim takeover only when this module returns EXECUTOR_STUCK.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_STALE_AFTER_SECONDS = 600
DEFAULT_ORPHAN_GRACE_SECONDS = 90
MAX_RUNTIME_LIVENESS_SECONDS = 300
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_WORKER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_ACTIVE_PHASES = frozenset(
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
_INACTIVE_PHASES = frozenset(
    {"RELEASED", "CLOSED", "TERMINAL_SUCCESS", "TERMINAL_FAILURE"}
)
_ACTIVE_REMOTE_STATUSES = frozenset(
    {"queued", "in_progress", "waiting", "requested", "pending"}
)
_DELEGATION_KEYS = {
    "proof_issue": "proof",
    "blocking_repair_issue": "blocking-repair",
    "helper_issue": "helper",
    "dependency_issue": "dependency",
}
_ALLOWED_DELEGATED_RELATIONSHIPS = frozenset(
    {"proof", "blocking-repair", "helper", "dependency", "repair"}
)
_HELPER_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_RESERVATION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_HELPER_RESERVATION_STATES = frozenset({"RESERVING", "ACTIVE", "TERMINAL"})


class StaleTakeoverError(RuntimeError):
    """Raised when fresh takeover evidence is incomplete or malformed."""


class TakeoverClassification(str, Enum):
    RUN_LIVE = "RUN_LIVE"
    ACTIVE_DELEGATED_WORK = "ACTIVE_DELEGATED_WORK"
    WAIT_ON_FOREIGN_RUNTIME = "WAIT_ON_FOREIGN_RUNTIME"
    EXECUTOR_STUCK = "EXECUTOR_STUCK"
    ORPHANED_SCHEDULER_OWNER = "ORPHANED_SCHEDULER_OWNER"
    ALREADY_SCHEDULER = "ALREADY_SCHEDULER"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class StaleTakeoverEvaluation:
    classification: TakeoverClassification
    actionable: bool
    stale_seconds: int
    latest_progress_at: datetime
    previous_worker: str
    requesting_worker: str | None
    requesting_executor_source: str | None
    user_authority_comment_id: int | None
    previous_executor_source: str
    observed_live_head_sha: str
    reason: str
    stale_after_seconds: int
    claim_head_sha: str
    claim_last_update: datetime
    claim_phase: str
    orphan_grace_seconds: int
    claim_blob_sha: str | None
    runtime_liveness_status: str
    runtime_invocation_identity: str | None
    runtime_liveness_emitted_at: datetime | None
    runtime_liveness_expires_at: datetime | None
    active_delegated_issue: int | None
    active_delegated_helper_key: str | None
    active_delegated_relationship: str | None
    active_delegated_latest_progress_at: datetime | None

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema"] = "WHD_STALE_CLAIM_TAKEOVER_V1"
        payload["classification"] = self.classification.value
        payload["latest_progress_at"] = _iso_utc(self.latest_progress_at)
        payload["claim_last_update"] = _iso_utc(self.claim_last_update)
        if self.runtime_liveness_emitted_at is not None:
            payload["runtime_liveness_emitted_at"] = _iso_utc(
                self.runtime_liveness_emitted_at
            )
        if self.runtime_liveness_expires_at is not None:
            payload["runtime_liveness_expires_at"] = _iso_utc(
                self.runtime_liveness_expires_at
            )
        if self.active_delegated_latest_progress_at is not None:
            payload["active_delegated_latest_progress_at"] = _iso_utc(
                self.active_delegated_latest_progress_at
            )
        return payload


def _iso_utc(value: datetime) -> str:
    return (
        _as_utc("timestamp", value)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _as_utc(label: str, value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise StaleTakeoverError(f"{label} must be an ISO-8601 timestamp") from exc
    else:
        raise StaleTakeoverError(f"{label} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StaleTakeoverError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _require_sha(label: str, value: object) -> str:
    text = str(value or "").strip()
    if not _SHA_RE.fullmatch(text):
        raise StaleTakeoverError(f"{label} must be a 40-char lowercase SHA")
    return text


def _positive_int(label: str, value: object) -> int:
    if isinstance(value, bool):
        raise StaleTakeoverError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise StaleTakeoverError(f"{label} must be a positive integer") from exc
    if number <= 0:
        raise StaleTakeoverError(f"{label} must be a positive integer")
    return number


def _user_directed_authority_comment_id(
    payload: Mapping[str, object] | None,
    *,
    claim_issue: int,
    previous_worker: str,
    requesting_worker: str,
    now: datetime,
) -> int:
    if not isinstance(payload, Mapping):
        raise StaleTakeoverError(
            "interactive requesting_worker requires owner-authored user authority evidence"
        )
    comment_id = _positive_int("user authority comment id", payload.get("id"))
    user = payload.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != "looaeedr":
        raise StaleTakeoverError("user authority comment must be authored by repository owner")
    body = payload.get("body")
    if not isinstance(body, str):
        raise StaleTakeoverError("user authority comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_USER_DIRECTED_TAKEOVER_V1":
        raise StaleTakeoverError("user authority comment marker mismatch")
    singles: dict[str, str] = {}
    allowed = {"issue", "requesting_worker", "previous_worker", "executor_source"}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise StaleTakeoverError("user authority comment contains malformed line")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in allowed or key in singles:
            raise StaleTakeoverError("user authority comment contains unsupported/duplicate key")
        singles[key] = value
    if set(singles) != allowed:
        raise StaleTakeoverError("user authority comment is missing required keys")
    if _positive_int("user authority issue", singles["issue"]) != claim_issue:
        raise StaleTakeoverError("user authority issue mismatch")
    if singles["requesting_worker"] != requesting_worker:
        raise StaleTakeoverError("user authority requesting_worker mismatch")
    if singles["previous_worker"] != previous_worker:
        raise StaleTakeoverError("user authority previous_worker mismatch")
    if singles["executor_source"] != "chat":
        raise StaleTakeoverError("user authority executor_source must be chat")
    created_at = _as_utc("user authority created_at", payload.get("created_at"))
    if created_at > now:
        raise StaleTakeoverError("user authority timestamp is in the future")
    if int((now - created_at).total_seconds()) > 3600:
        raise StaleTakeoverError("user authority comment is older than 3600 seconds")
    return comment_id



@dataclass(frozen=True)
class _DelegatedWorkObservation:
    parent_issue: int
    child_issue: int
    relationship: str
    helper_key: str
    issue_state: str
    claim_phase: str | None
    child_worker: str | None
    claim_blob_sha: str | None
    live_head_sha: str | None
    latest_progress_at: datetime | None
    active: bool


@dataclass(frozen=True)
class HelperReservationDecision:
    """Pure candidate/result for one parent-claim helper reservation CAS."""

    outcome: str
    parent_claim: dict[str, object]
    reservation: dict[str, object]
    expected_parent_claim_blob_sha: str | None = None


def _require_reservation_worker(value: object) -> str:
    text = str(value or "").strip()
    if not _WORKER_RE.fullmatch(text):
        raise StaleTakeoverError(
            "helper reservation reserved_by identity is missing or malformed"
        )
    return text


def _require_reservation_token(value: object) -> str:
    text = str(value or "").strip()
    if not _RESERVATION_TOKEN_RE.fullmatch(text):
        raise StaleTakeoverError("helper reservation token is missing or malformed")
    return text


def _helper_reservations(
    parent_claim: Mapping[str, object],
    *,
    helper_key: str | None = None,
) -> tuple[dict[str, object], ...]:
    raw = parent_claim.get("delegated_work")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise StaleTakeoverError("claim delegated_work must be a list")

    wanted = None if helper_key is None else _require_helper_key(helper_key)
    result: list[dict[str, object]] = []
    active_keys: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise StaleTakeoverError(
                f"claim delegated_work[{index}] must be an object"
            )
        state_raw = item.get("state")
        if state_raw is None:
            continue
        state = str(state_raw).strip().upper()
        if state not in _HELPER_RESERVATION_STATES:
            raise StaleTakeoverError(
                f"claim delegated_work[{index}] helper reservation state is invalid"
            )
        relationship = str(item.get("relationship") or "").strip()
        if relationship not in {"helper", "repair", "blocking-repair"}:
            raise StaleTakeoverError(
                f"claim delegated_work[{index}] reservation relationship is invalid"
            )
        key = _require_helper_key(item.get("helper_key"))
        owner = _require_reservation_worker(item.get("reserved_by"))
        token = _require_reservation_token(item.get("reservation_token"))
        reserved_at = _as_utc(
            f"claim delegated_work[{index}].reserved_at",
            item.get("reserved_at"),
        )

        child_issue = item.get("child_issue")
        child_blob = item.get("child_claim_blob_sha")
        if state == "RESERVING":
            if child_issue is not None or child_blob is not None:
                raise StaleTakeoverError(
                    "RESERVING helper reservation cannot already bind child durable identity"
                )
        else:
            child_issue = _positive_int(
                f"claim delegated_work[{index}].child_issue",
                child_issue,
            )
            child_blob = _require_sha(
                f"claim delegated_work[{index}].child_claim_blob_sha",
                child_blob,
            )

        if state in {"RESERVING", "ACTIVE"}:
            if key in active_keys:
                raise StaleTakeoverError(
                    f"AMBIGUOUS_HELPER_RESERVATION helper_key={key}"
                )
            active_keys.add(key)

        normalized = dict(item)
        normalized.update(
            {
                "relationship": relationship,
                "helper_key": key,
                "state": state,
                "reserved_by": owner,
                "reservation_token": token,
                "reserved_at": _iso_utc(reserved_at),
                "child_issue": child_issue,
                "child_claim_blob_sha": child_blob,
            }
        )
        if wanted is None or key == wanted:
            result.append(normalized)
    return tuple(result)


def _find_live_helper_reservation(
    parent_claim: Mapping[str, object],
    helper_key: str,
) -> dict[str, object] | None:
    entries = [
        item
        for item in _helper_reservations(parent_claim, helper_key=helper_key)
        if item["state"] in {"RESERVING", "ACTIVE"}
    ]
    if len(entries) > 1:
        raise StaleTakeoverError(
            f"AMBIGUOUS_HELPER_RESERVATION helper_key={helper_key}"
        )
    return entries[0] if entries else None


def _legacy_same_key_helper_exists(
    parent_claim: Mapping[str, object],
    helper_key: str,
) -> bool:
    raw = parent_claim.get("delegated_work")
    if not isinstance(raw, list):
        return False
    for item in raw:
        if not isinstance(item, Mapping) or item.get("state") is not None:
            continue
        try:
            key = _require_helper_key(item.get("helper_key"))
        except StaleTakeoverError:
            continue
        if key == helper_key and item.get("child_issue") is not None:
            return True
    return False


def reserve_helper_creation(
    parent_claim: Mapping[str, object],
    *,
    parent_claim_blob_sha: str,
    expected_parent_claim_blob_sha: str,
    helper_key: str,
    reserved_by: str,
    reservation_token: str,
    now: datetime,
) -> HelperReservationDecision:
    """Build one RESERVING parent-claim CAS candidate."""

    current_blob = _require_sha("parent_claim_blob_sha", parent_claim_blob_sha)
    expected_blob = _require_sha(
        "expected_parent_claim_blob_sha", expected_parent_claim_blob_sha
    )
    if current_blob != expected_blob:
        raise StaleTakeoverError(
            "HELPER_RESERVATION_CAS_CONFLICT "
            f"expected_parent_claim_blob_sha={expected_blob} "
            f"current_parent_claim_blob_sha={current_blob}"
        )

    key = _require_helper_key(helper_key)
    owner = _require_reservation_worker(reserved_by)
    token = _require_reservation_token(reservation_token)
    reserved_at = _as_utc("reservation now", now)

    existing = _find_live_helper_reservation(parent_claim, key)
    if existing is not None:
        outcome = (
            "ACTIVE_HELPER_ALREADY_RESERVED"
            if existing["state"] == "RESERVING"
            else "ACTIVE_HELPER_DUPLICATE"
        )
        return HelperReservationDecision(
            outcome=outcome,
            parent_claim=deepcopy(dict(parent_claim)),
            reservation=deepcopy(existing),
            expected_parent_claim_blob_sha=current_blob,
        )
    if _legacy_same_key_helper_exists(parent_claim, key):
        return HelperReservationDecision(
            outcome="ACTIVE_HELPER_DUPLICATE",
            parent_claim=deepcopy(dict(parent_claim)),
            reservation={
                "relationship": "helper",
                "helper_key": key,
                "state": "ACTIVE",
            },
            expected_parent_claim_blob_sha=current_blob,
        )

    candidate = deepcopy(dict(parent_claim))
    delegated = candidate.get("delegated_work")
    if delegated is None:
        delegated = []
        candidate["delegated_work"] = delegated
    if not isinstance(delegated, list):
        raise StaleTakeoverError("claim delegated_work must be a list")

    reservation = {
        "relationship": "helper",
        "helper_key": key,
        "state": "RESERVING",
        "reserved_by": owner,
        "reservation_token": token,
        "reserved_at": _iso_utc(reserved_at),
        "child_issue": None,
        "child_claim_blob_sha": None,
    }
    delegated.append(reservation)
    return HelperReservationDecision(
        outcome="RESERVED",
        parent_claim=candidate,
        reservation=deepcopy(reservation),
        expected_parent_claim_blob_sha=current_blob,
    )


def _assert_helper_reservation_authority(
    reservation: Mapping[str, object],
    *,
    reserved_by: str | None,
    reservation_token: str | None,
) -> None:
    if reserved_by is None or reservation_token is None:
        raise StaleTakeoverError("HELPER_RESERVATION_AUTHORITY_MISMATCH")
    try:
        owner = _require_reservation_worker(reserved_by)
        token = _require_reservation_token(reservation_token)
    except StaleTakeoverError as exc:
        raise StaleTakeoverError(
            "HELPER_RESERVATION_AUTHORITY_MISMATCH"
        ) from exc
    if (
        owner != str(reservation.get("reserved_by") or "")
        or token != str(reservation.get("reservation_token") or "")
    ):
        raise StaleTakeoverError("HELPER_RESERVATION_AUTHORITY_MISMATCH")


def activate_helper_reservation(
    parent_claim: Mapping[str, object],
    *,
    helper_key: str,
    reserved_by: str,
    reservation_token: str,
    child_issue: int,
    child_claim_blob_sha: str,
) -> HelperReservationDecision:
    key = _require_helper_key(helper_key)
    existing = _find_live_helper_reservation(parent_claim, key)
    if existing is None or existing["state"] != "RESERVING":
        raise StaleTakeoverError(
            f"HELPER_RESERVATION_NOT_RESERVING helper_key={key}"
        )
    _assert_helper_reservation_authority(
        existing,
        reserved_by=reserved_by,
        reservation_token=reservation_token,
    )
    child = _positive_int("helper child_issue", child_issue)
    child_blob = _require_sha("helper child_claim_blob_sha", child_claim_blob_sha)

    candidate = deepcopy(dict(parent_claim))
    for item in candidate.get("delegated_work", []):
        if (
            isinstance(item, dict)
            and item.get("helper_key") == key
            and str(item.get("state") or "").upper() == "RESERVING"
            and item.get("reservation_token") == existing["reservation_token"]
        ):
            item["state"] = "ACTIVE"
            item["child_issue"] = child
            item["child_claim_blob_sha"] = child_blob
            return HelperReservationDecision(
                outcome="ACTIVE",
                parent_claim=candidate,
                reservation=deepcopy(item),
            )
    raise StaleTakeoverError("helper reservation changed during activation")


def terminalize_helper_reservation(
    parent_claim: Mapping[str, object],
    *,
    helper_key: str,
    reserved_by: str,
    reservation_token: str,
    child_terminal_proof: Mapping[str, object] | None,
) -> HelperReservationDecision:
    key = _require_helper_key(helper_key)
    existing = _find_live_helper_reservation(parent_claim, key)
    if existing is None or existing["state"] != "ACTIVE":
        raise StaleTakeoverError(
            f"HELPER_RESERVATION_NOT_ACTIVE helper_key={key}"
        )
    _assert_helper_reservation_authority(
        existing,
        reserved_by=reserved_by,
        reservation_token=reservation_token,
    )
    required_true = (
        "issue_closed_completed",
        "claim_released",
        "next_action_null",
        "no_active_run",
        "checkpoint_closed",
    )
    if (
        not isinstance(child_terminal_proof, Mapping)
        or any(child_terminal_proof.get(name) is not True for name in required_true)
    ):
        raise StaleTakeoverError(
            "HELPER_RESERVATION_TERMINAL_REQUIRES_COMPLETE_CHILD_TERMINAL_PROOF"
        )

    candidate = deepcopy(dict(parent_claim))
    for item in candidate.get("delegated_work", []):
        if (
            isinstance(item, dict)
            and item.get("helper_key") == key
            and str(item.get("state") or "").upper() == "ACTIVE"
            and item.get("reservation_token") == existing["reservation_token"]
        ):
            item["state"] = "TERMINAL"
            return HelperReservationDecision(
                outcome="TERMINAL",
                parent_claim=candidate,
                reservation=deepcopy(item),
            )
    raise StaleTakeoverError("helper reservation changed during terminalization")


def reset_helper_reservation(
    parent_claim: Mapping[str, object],
    *,
    helper_key: str,
    reserved_by: str,
    reservation_token: str,
    durable_child_proof: Mapping[str, object] | None,
) -> HelperReservationDecision:
    key = _require_helper_key(helper_key)
    existing = _find_live_helper_reservation(parent_claim, key)
    if existing is None or existing["state"] != "RESERVING":
        raise StaleTakeoverError(
            f"HELPER_RESERVATION_NOT_RESERVING helper_key={key}"
        )
    _assert_helper_reservation_authority(
        existing,
        reserved_by=reserved_by,
        reservation_token=reservation_token,
    )
    required_false = (
        "child_issue_exists",
        "child_claim_exists",
        "helper_durable_mutation_exists",
    )
    if (
        not isinstance(durable_child_proof, Mapping)
        or any(durable_child_proof.get(name) is not False for name in required_false)
    ):
        raise StaleTakeoverError(
            "HELPER_RESERVATION_RESET_REQUIRES_NO_DURABLE_CHILD_PROOF"
        )

    candidate = deepcopy(dict(parent_claim))
    delegated = candidate.get("delegated_work")
    if not isinstance(delegated, list):
        raise StaleTakeoverError("claim delegated_work must be a list")
    candidate["delegated_work"] = [
        item
        for item in delegated
        if not (
            isinstance(item, Mapping)
            and item.get("helper_key") == key
            and str(item.get("state") or "").upper() == "RESERVING"
            and item.get("reservation_token") == existing["reservation_token"]
        )
    ]
    return HelperReservationDecision(
        outcome="RESET",
        parent_claim=candidate,
        reservation=deepcopy(existing),
    )


def _require_helper_key(value: object) -> str:
    text = str(value or "").strip()
    if not _HELPER_KEY_RE.fullmatch(text):
        raise StaleTakeoverError("delegated helper_key is missing or malformed")
    return text


def _declared_delegations(claim: Mapping[str, object]) -> dict[int, dict[str, object]]:
    parent_issue = _positive_int("claim issue", claim.get("issue"))
    result: dict[int, dict[str, object]] = {}
    canonical = claim.get("delegated_work")
    if canonical is not None:
        if not isinstance(canonical, list):
            raise StaleTakeoverError("claim delegated_work must be a list")
        for index, item in enumerate(canonical):
            if not isinstance(item, Mapping):
                raise StaleTakeoverError(f"claim delegated_work[{index}] must be an object")
            reservation_state = str(item.get("state") or "").strip().upper()
            if reservation_state:
                if reservation_state not in _HELPER_RESERVATION_STATES:
                    raise StaleTakeoverError(
                        f"claim delegated_work[{index}] helper reservation state is invalid"
                    )
                if reservation_state == "RESERVING":
                    if (
                        item.get("child_issue") is not None
                        or item.get("child_claim_blob_sha") is not None
                    ):
                        raise StaleTakeoverError(
                            "RESERVING helper reservation cannot bind child durable identity"
                        )
                    continue
            child_issue = _positive_int(
                f"claim delegated_work[{index}].child_issue", item.get("child_issue")
            )
            if child_issue == parent_issue:
                raise StaleTakeoverError("delegated child issue must differ from parent")
            relationship = str(item.get("relationship") or "").strip()
            if relationship not in _ALLOWED_DELEGATED_RELATIONSHIPS:
                raise StaleTakeoverError(
                    f"claim delegated_work[{index}] relationship is invalid"
                )
            helper_key = _require_helper_key(item.get("helper_key"))
            if child_issue in result:
                raise StaleTakeoverError(
                    f"duplicate delegated child issue declaration: {child_issue}"
                )
            result[child_issue] = {
                "relationship": relationship,
                "helper_key": helper_key,
                "canonical": True,
            }

    def scan(node: object) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if key in _DELEGATION_KEYS and value is not None:
                    child_issue = _positive_int(f"claim {key}", value)
                    if child_issue == parent_issue:
                        raise StaleTakeoverError(
                            "delegated child issue must differ from parent"
                        )
                    if child_issue not in result:
                        relationship = _DELEGATION_KEYS[key]
                        result[child_issue] = {
                            "relationship": relationship,
                            "helper_key": f"legacy:{relationship}:{child_issue}",
                            "canonical": False,
                        }
                if isinstance(value, (Mapping, list)):
                    scan(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (Mapping, list)):
                    scan(item)

    scan(claim)
    return result


def _normalize_delegated_work(
    claim: Mapping[str, object],
    delegated_work: Sequence[Mapping[str, object]] | None,
    *,
    now: datetime,
) -> tuple[_DelegatedWorkObservation, ...]:
    parent_issue = _positive_int("claim issue", claim.get("issue"))
    observations: list[_DelegatedWorkObservation] = []
    seen_children: set[int] = set()
    seen_helper_keys: set[str] = set()
    for index, raw in enumerate(delegated_work or ()):
        if not isinstance(raw, Mapping):
            raise StaleTakeoverError(f"delegated work evidence[{index}] must be an object")
        if raw.get("schema") != "WHD_DELEGATED_WORK_V1":
            raise StaleTakeoverError(f"delegated work evidence[{index}] schema mismatch")
        observed_parent = _positive_int(
            f"delegated work evidence[{index}] parent_issue", raw.get("parent_issue")
        )
        if observed_parent != parent_issue:
            raise StaleTakeoverError("delegated work parent issue mismatch")
        child_issue = _positive_int(
            f"delegated work evidence[{index}] child_issue", raw.get("child_issue")
        )
        if child_issue == parent_issue:
            raise StaleTakeoverError("delegated child issue must differ from parent")
        if child_issue in seen_children:
            raise StaleTakeoverError(
                f"duplicate delegated work evidence for child issue {child_issue}"
            )
        seen_children.add(child_issue)
        relationship = str(raw.get("relationship") or "").strip()
        if relationship not in _ALLOWED_DELEGATED_RELATIONSHIPS:
            raise StaleTakeoverError(
                f"delegated work evidence[{index}] relationship is invalid"
            )
        helper_key = _require_helper_key(raw.get("helper_key"))
        if helper_key in seen_helper_keys:
            raise StaleTakeoverError(
                f"duplicate delegated helper_key evidence: {helper_key}"
            )
        seen_helper_keys.add(helper_key)
        issue_state = str(raw.get("issue_state") or "").strip().lower()
        if issue_state not in {"open", "closed"}:
            raise StaleTakeoverError(
                f"delegated work evidence[{index}] issue_state must be open|closed"
            )
        issue_updated_at = None
        if raw.get("issue_updated_at") is not None:
            issue_updated_at = _as_utc(
                f"delegated work evidence[{index}] issue_updated_at",
                raw.get("issue_updated_at"),
            )
            if issue_updated_at > now:
                raise StaleTakeoverError("delegated issue updated_at is in the future")
        child_claim = raw.get("claim")
        if child_claim is None:
            if issue_state != "closed":
                raise StaleTakeoverError(
                    f"open delegated child issue {child_issue} requires a fresh claim"
                )
            observations.append(
                _DelegatedWorkObservation(
                    parent_issue, child_issue, relationship, helper_key, issue_state,
                    None, None, None, None, issue_updated_at, False
                )
            )
            continue
        if not isinstance(child_claim, Mapping):
            raise StaleTakeoverError(
                f"delegated work evidence[{index}] claim must be an object"
            )
        if _positive_int(
            f"delegated child claim[{index}] issue", child_claim.get("issue")
        ) != child_issue:
            raise StaleTakeoverError("delegated child claim issue mismatch")
        child_worker = str(child_claim.get("worker") or "").strip()
        if not _WORKER_RE.fullmatch(child_worker):
            raise StaleTakeoverError(
                "delegated child claim worker identity is missing or malformed"
            )
        claim_phase = str(child_claim.get("phase") or "").strip().upper()
        if claim_phase not in _ACTIVE_PHASES and claim_phase not in _INACTIVE_PHASES:
            raise StaleTakeoverError(f"unknown delegated child claim phase={claim_phase}")
        claim_blob_sha = _require_sha(
            f"delegated work evidence[{index}] claim_blob_sha", raw.get("claim_blob_sha")
        )
        child_head = _require_sha(
            f"delegated child claim[{index}] head_sha", child_claim.get("head_sha")
        )
        child_last_update = _as_utc(
            f"delegated child claim[{index}] last_update", child_claim.get("last_update")
        )
        if child_last_update > now:
            raise StaleTakeoverError("delegated child claim last_update is in the future")
        latest_points = [child_last_update]
        if issue_updated_at is not None:
            latest_points.append(issue_updated_at)
        if issue_state == "open":
            if claim_phase not in _ACTIVE_PHASES:
                raise StaleTakeoverError(
                    f"open delegated child issue {child_issue} has inactive claim phase={claim_phase}"
                )
            live_head = _require_sha(
                f"delegated work evidence[{index}] live_head_sha", raw.get("live_head_sha")
            )
            if live_head != child_head:
                raise StaleTakeoverError(
                    f"delegated child issue {child_issue} claim/live head mismatch"
                )
            live_commit_at = _as_utc(
                f"delegated work evidence[{index}] live_head_committed_at",
                raw.get("live_head_committed_at"),
            )
            if live_commit_at > now:
                raise StaleTakeoverError(
                    "delegated child live commit timestamp is in the future"
                )
            latest_points.append(live_commit_at)
            observations.append(
                _DelegatedWorkObservation(
                    parent_issue, child_issue, relationship, helper_key, issue_state,
                    claim_phase, child_worker, claim_blob_sha, live_head,
                    max(latest_points), True
                )
            )
        else:
            if claim_phase not in _INACTIVE_PHASES:
                raise StaleTakeoverError(
                    f"closed delegated child issue {child_issue} still has active claim phase={claim_phase}"
                )
            observations.append(
                _DelegatedWorkObservation(
                    parent_issue, child_issue, relationship, helper_key, issue_state,
                    claim_phase, child_worker, claim_blob_sha, child_head,
                    max(latest_points), False
                )
            )

    declared = _declared_delegations(claim)
    by_issue = {item.child_issue: item for item in observations}
    for child_issue, declaration in declared.items():
        observed = by_issue.get(child_issue)
        if observed is None:
            raise StaleTakeoverError(
                f"delegated work evidence required for child issue {child_issue}"
            )
        if declaration.get("canonical") is True and (
            observed.relationship != declaration["relationship"]
            or observed.helper_key != declaration["helper_key"]
        ):
            raise StaleTakeoverError(
                f"delegated child issue {child_issue} canonical relationship/helper_key mismatch"
            )
        if (
            declaration.get("canonical") is not True
            and observed.relationship != declaration["relationship"]
        ):
            raise StaleTakeoverError(
                f"delegated child issue {child_issue} relationship mismatch"
            )
    return tuple(observations)


def assert_helper_creation_allowed(
    parent_claim: Mapping[str, object],
    *,
    helper_key: str,
    delegated_work: Sequence[Mapping[str, object]] | None,
    now: datetime,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    reservation_owner: str | None = None,
    reservation_token: str | None = None,
) -> None:
    _positive_int("stale_after_seconds", stale_after_seconds)
    now_utc = _as_utc("now", now)
    candidate_key = _require_helper_key(helper_key)

    reservation = _find_live_helper_reservation(parent_claim, candidate_key)
    if reservation is not None:
        _assert_helper_reservation_authority(
            reservation,
            reserved_by=reservation_owner,
            reservation_token=reservation_token,
        )
        if reservation["state"] == "ACTIVE":
            raise StaleTakeoverError(
                "ACTIVE_HELPER_DUPLICATE "
                f"helper_key={candidate_key} child_issue={reservation['child_issue']}"
            )

    observations = _normalize_delegated_work(
        parent_claim, delegated_work, now=now_utc
    )
    for item in observations:
        if item.active and item.helper_key == candidate_key:
            raise StaleTakeoverError(
                "ACTIVE_HELPER_DUPLICATE "
                f"helper_key={candidate_key} child_issue={item.child_issue}"
            )

    if reservation is None:
        raise StaleTakeoverError(
            f"HELPER_RESERVATION_REQUIRED helper_key={candidate_key}"
        )


def _github_api_json(path: str, *, allow_not_found: bool = False) -> object | None:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if repository != "looaeedr/whd":
        raise StaleTakeoverError(
            "fresh delegated-work discovery requires GITHUB_REPOSITORY=looaeedr/whd"
        )
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/{path.lstrip('/')}",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if allow_not_found and exc.code == 404:
            return None
        raise StaleTakeoverError(
            f"delegated-work GitHub API read failed status={exc.code}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise StaleTakeoverError(f"delegated-work GitHub API read failed: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StaleTakeoverError(
            "delegated-work GitHub API returned invalid JSON"
        ) from exc


def _github_claim_for_issue(issue: int) -> tuple[dict[str, object] | None, str | None]:
    path = urllib.parse.quote(f".dispatch/claims/issue-{issue}.json", safe="/")
    query = urllib.parse.urlencode({"ref": "coord/dispatch-claims"})
    payload = _github_api_json(f"contents/{path}?{query}", allow_not_found=True)
    if payload is None:
        return None, None
    if not isinstance(payload, Mapping):
        raise StaleTakeoverError(
            f"delegated child issue {issue} claim contents response is invalid"
        )
    blob_sha = _require_sha(
        f"delegated child issue {issue} claim blob SHA", payload.get("sha")
    )
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        raise StaleTakeoverError(
            f"delegated child issue {issue} claim content is missing"
        )
    try:
        child_claim = json.loads(base64.b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StaleTakeoverError(
            f"delegated child issue {issue} claim content is invalid"
        ) from exc
    if not isinstance(child_claim, dict):
        raise StaleTakeoverError(
            f"delegated child issue {issue} claim root must be an object"
        )
    return child_claim, blob_sha


def _discover_github_delegated_work(
    claim: Mapping[str, object],
) -> list[dict[str, object]]:
    declarations = _declared_delegations(claim)
    observations: list[dict[str, object]] = []
    for child_issue, declaration in sorted(declarations.items()):
        issue_payload = _github_api_json(f"issues/{child_issue}")
        if not isinstance(issue_payload, Mapping):
            raise StaleTakeoverError(
                f"delegated child issue {child_issue} response is invalid"
            )
        issue_state = str(issue_payload.get("state") or "").strip().lower()
        child_claim, blob_sha = _github_claim_for_issue(child_issue)
        observation = {
            "schema": "WHD_DELEGATED_WORK_V1",
            "parent_issue": _positive_int("claim issue", claim.get("issue")),
            "child_issue": child_issue,
            "relationship": declaration["relationship"],
            "helper_key": declaration["helper_key"],
            "issue_state": issue_state,
            "issue_updated_at": issue_payload.get("updated_at"),
            "claim": child_claim,
            "claim_blob_sha": blob_sha,
        }
        if child_claim is not None:
            phase = str(child_claim.get("phase") or "").strip().upper()
            if issue_state == "open" or phase in _ACTIVE_PHASES:
                branch = str(child_claim.get("work_branch") or "").strip()
                if not branch:
                    raise StaleTakeoverError(
                        f"delegated child issue {child_issue} work_branch is missing"
                    )
                branch_payload = _github_api_json(
                    "branches/" + urllib.parse.quote(branch, safe="")
                )
                if not isinstance(branch_payload, Mapping):
                    raise StaleTakeoverError(
                        f"delegated child issue {child_issue} branch response is invalid"
                    )
                commit_ref = branch_payload.get("commit")
                if not isinstance(commit_ref, Mapping):
                    raise StaleTakeoverError(
                        f"delegated child issue {child_issue} branch commit is missing"
                    )
                live_head = _require_sha(
                    f"delegated child issue {child_issue} live head",
                    commit_ref.get("sha"),
                )
                commit_payload = _github_api_json(f"commits/{live_head}")
                if not isinstance(commit_payload, Mapping):
                    raise StaleTakeoverError(
                        f"delegated child issue {child_issue} commit response is invalid"
                    )
                commit_meta = commit_payload.get("commit")
                if not isinstance(commit_meta, Mapping):
                    raise StaleTakeoverError(
                        f"delegated child issue {child_issue} commit metadata is missing"
                    )
                committer = commit_meta.get("committer")
                author = commit_meta.get("author")
                committed_at = (
                    committer.get("date") if isinstance(committer, Mapping) else None
                )
                if committed_at is None and isinstance(author, Mapping):
                    committed_at = author.get("date")
                observation["live_head_sha"] = live_head
                observation["live_head_committed_at"] = committed_at
        observations.append(observation)
    return observations



def _remote_progress(
    claim: Mapping[str, object],
    remote_run: Mapping[str, object] | None,
) -> tuple[bool, datetime | None, str]:
    remote_qa = claim.get("remote_qa")
    expected_run_id: int | None = None
    expected_run_head = _require_sha("claim head_sha", claim.get("head_sha"))
    if isinstance(remote_qa, Mapping) and remote_qa.get("run_id") is not None:
        expected_run_id = _positive_int("claim remote_qa.run_id", remote_qa.get("run_id"))
        remote_head = remote_qa.get("head_sha") or remote_qa.get("tested_target_sha")
        if remote_head is not None:
            expected_run_head = _require_sha("claim remote_qa head", remote_head)
        if remote_run is None:
            raise StaleTakeoverError(
                "fresh remote_run observation is required when claim remote_qa has run_id"
            )

    if remote_run is None:
        return False, None, "no exact remote run is claimed"

    observed_run_id = _positive_int("remote_run.run_id", remote_run.get("run_id"))
    if expected_run_id is not None and observed_run_id != expected_run_id:
        raise StaleTakeoverError(
            f"remote run identity mismatch expected={expected_run_id} observed={observed_run_id}"
        )

    found = remote_run.get("found", True)
    if not isinstance(found, bool):
        raise StaleTakeoverError("remote_run.found must be boolean")
    if not found:
        return False, None, f"exact remote run {observed_run_id} is missing"

    observed_run_head = _require_sha("remote_run.head_sha", remote_run.get("head_sha"))
    if observed_run_head != expected_run_head:
        raise StaleTakeoverError(
            f"remote run head mismatch expected={expected_run_head} observed={observed_run_head}"
        )

    status = str(remote_run.get("status") or "").strip().lower()
    conclusion = str(remote_run.get("conclusion") or "").strip().lower() or None
    updated_at = _as_utc("remote_run.updated_at", remote_run.get("updated_at"))

    is_active = status in _ACTIVE_REMOTE_STATUSES and conclusion is None
    if is_active:
        return True, updated_at, (
            f"exact remote run {observed_run_id} is active status={status}"
        )
    return False, updated_at, (
        f"exact remote run {observed_run_id} is not active "
        f"status={status or 'unknown'} conclusion={conclusion or 'none'}"
    )


def _scheduler_runtime_liveness(
    runtime_liveness: Mapping[str, object] | None,
    *,
    claim: Mapping[str, object],
    claim_blob_sha: str | None,
    previous_worker: str,
    live_head_sha: str,
    now: datetime,
    remote_run: Mapping[str, object] | None,
) -> tuple[str, str | None, datetime | None, datetime | None]:
    """Validate scheduler invocation liveness bound to the exact claim identity."""

    if claim_blob_sha is None:
        if runtime_liveness is not None:
            raise StaleTakeoverError(
                "runtime liveness evidence requires exact claim blob SHA"
            )
        return "NOT_APPLICABLE", None, None, None

    blob_sha = _require_sha("claim_blob_sha", claim_blob_sha)
    if runtime_liveness is None:
        return "MISSING", None, None, None
    if not isinstance(runtime_liveness, Mapping):
        raise StaleTakeoverError("runtime liveness heartbeat must be a mapping")
    if runtime_liveness.get("schema") != "WHD_SCHEDULER_RUNTIME_LIVENESS_V1":
        raise StaleTakeoverError("runtime liveness heartbeat schema mismatch")

    claim_issue = _positive_int("claim issue", claim.get("issue"))
    if _positive_int("runtime liveness issue", runtime_liveness.get("issue")) != claim_issue:
        raise StaleTakeoverError("runtime liveness heartbeat issue mismatch")

    lane = str(runtime_liveness.get("scheduler_lane") or "").strip()
    if lane != previous_worker:
        raise StaleTakeoverError(
            "runtime liveness heartbeat scheduler lane does not match claim owner"
        )
    invocation = str(runtime_liveness.get("invocation_identity") or "").strip()
    if not _WORKER_RE.fullmatch(invocation):
        raise StaleTakeoverError(
            "runtime liveness heartbeat invocation identity is missing or malformed"
        )

    heartbeat_blob = _require_sha(
        "runtime liveness claim blob SHA", runtime_liveness.get("claim_blob_sha")
    )
    if heartbeat_blob != blob_sha:
        raise StaleTakeoverError("runtime liveness heartbeat claim blob mismatch")

    branch = str(runtime_liveness.get("branch") or "").strip()
    if branch != str(claim.get("work_branch") or "").strip():
        raise StaleTakeoverError("runtime liveness heartbeat branch mismatch")
    heartbeat_head = _require_sha(
        "runtime liveness head SHA", runtime_liveness.get("head_sha")
    )
    if heartbeat_head != live_head_sha:
        raise StaleTakeoverError("runtime liveness heartbeat head mismatch")
    if str(runtime_liveness.get("executor_source") or "").strip() != "scheduler":
        raise StaleTakeoverError(
            "runtime liveness heartbeat executor source must be scheduler"
        )

    emitted_at = _as_utc(
        "runtime liveness emitted_at", runtime_liveness.get("emitted_at")
    )
    expires_at = _as_utc(
        "runtime liveness expires_at", runtime_liveness.get("expires_at")
    )
    if emitted_at > now:
        raise StaleTakeoverError("runtime liveness heartbeat emitted_at is in the future")
    if expires_at <= emitted_at:
        raise StaleTakeoverError(
            "runtime liveness heartbeat expires_at must be after emitted_at"
        )
    ttl_seconds = int((expires_at - emitted_at).total_seconds())
    if ttl_seconds > MAX_RUNTIME_LIVENESS_SECONDS:
        raise StaleTakeoverError(
            "runtime liveness heartbeat TTL exceeds fail-closed maximum"
        )

    active_run_id = runtime_liveness.get("active_run_id")
    active_run_head = runtime_liveness.get("active_run_head_sha")
    if (active_run_id is None) != (active_run_head is None):
        raise StaleTakeoverError(
            "runtime liveness heartbeat active run id/head must be present together"
        )
    if active_run_id is not None:
        heartbeat_run_id = _positive_int(
            "runtime liveness active_run_id", active_run_id
        )
        heartbeat_run_head = _require_sha(
            "runtime liveness active_run_head_sha", active_run_head
        )
        if remote_run is not None and remote_run.get("found", True):
            if _positive_int("remote_run.run_id", remote_run.get("run_id")) != heartbeat_run_id:
                raise StaleTakeoverError(
                    "runtime liveness heartbeat active run id mismatch"
                )
            if _require_sha("remote_run.head_sha", remote_run.get("head_sha")) != heartbeat_run_head:
                raise StaleTakeoverError(
                    "runtime liveness heartbeat active run head mismatch"
                )

    status = "ACTIVE" if now < expires_at else "EXPIRED"
    return status, invocation, emitted_at, expires_at

def evaluate_stale_claim_takeover(
    claim: Mapping[str, object],
    *,
    now: datetime,
    live_head_sha: str,
    live_head_committed_at: datetime | str,
    remote_run: Mapping[str, object] | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    requesting_worker: str | None = None,
    requesting_executor_source: str | None = None,
    user_authority: Mapping[str, object] | None = None,
    claim_blob_sha: str | None = None,
    runtime_liveness: Mapping[str, object] | None = None,
    orphan_grace_seconds: int = DEFAULT_ORPHAN_GRACE_SECONDS,
    delegated_work: Sequence[Mapping[str, object]] | None = None,
) -> StaleTakeoverEvaluation:
    """Classify whether one authorized requester may take over an active WHD claim."""

    if not isinstance(claim, Mapping):
        raise StaleTakeoverError("claim must be a mapping")
    now_utc = _as_utc("now", now)
    live_head = _require_sha("live_head_sha", live_head_sha)
    live_commit_at = _as_utc("live_head_committed_at", live_head_committed_at)
    threshold = _positive_int("stale_after_seconds", stale_after_seconds)
    orphan_grace = _positive_int("orphan_grace_seconds", orphan_grace_seconds)

    phase = str(claim.get("phase") or "").strip().upper()
    if not phase:
        raise StaleTakeoverError("claim phase is required")
    if phase not in _ACTIVE_PHASES and phase not in _INACTIVE_PHASES:
        raise StaleTakeoverError(f"unknown claim phase={phase}")

    claim_head = _require_sha("claim head_sha", claim.get("head_sha"))
    last_update = _as_utc("claim last_update", claim.get("last_update"))
    previous_source = str(claim.get("executor_source") or "unknown").strip() or "unknown"
    previous_worker = str(claim.get("worker") or "").strip()
    if not _WORKER_RE.fullmatch(previous_worker):
        raise StaleTakeoverError("claim worker identity is missing or malformed")

    requester: str | None = None
    requester_source: str | None = None
    authority_comment_id: int | None = None
    if requesting_worker is not None:
        requester = str(requesting_worker).strip()
        if not _WORKER_RE.fullmatch(requester):
            raise StaleTakeoverError("requesting_worker identity is malformed")
        source = str(requesting_executor_source or "").strip().lower()
        if requester.startswith("scheduler."):
            if source not in {"", "scheduler"}:
                raise StaleTakeoverError("scheduler requesting_worker requires scheduler source")
            requester_source = "scheduler"
            if user_authority is not None:
                raise StaleTakeoverError("scheduler takeover must not carry user authority evidence")
        else:
            if source != "chat":
                raise StaleTakeoverError(
                    "interactive requesting_worker requires requesting_executor_source=chat"
                )
            authority_comment_id = _user_directed_authority_comment_id(
                user_authority,
                claim_issue=_positive_int("claim issue", claim.get("issue")),
                previous_worker=previous_worker,
                requesting_worker=requester,
                now=now_utc,
            )
            requester_source = "chat"
    elif requesting_executor_source is not None or user_authority is not None:
        raise StaleTakeoverError(
            "requesting executor source/user authority require requesting_worker"
        )

    remote_active, remote_updated_at, remote_reason = _remote_progress(claim, remote_run)
    delegated_observations = _normalize_delegated_work(
        claim, delegated_work, now=now_utc
    )
    active_delegated = next(
        (item for item in delegated_observations if item.active), None
    )

    runtime_status = "NOT_APPLICABLE"
    runtime_invocation: str | None = None
    runtime_emitted_at: datetime | None = None
    runtime_expires_at: datetime | None = None
    normalized_claim_blob: str | None = None
    if claim_blob_sha is not None:
        normalized_claim_blob = _require_sha("claim_blob_sha", claim_blob_sha)

    if (
        previous_source == "scheduler"
        and requester is not None
        and requester != previous_worker
    ):
        (
            runtime_status,
            runtime_invocation,
            runtime_emitted_at,
            runtime_expires_at,
        ) = _scheduler_runtime_liveness(
            runtime_liveness,
            claim=claim,
            claim_blob_sha=normalized_claim_blob,
            previous_worker=previous_worker,
            live_head_sha=live_head,
            now=now_utc,
            remote_run=remote_run,
        )
    elif runtime_liveness is not None:
        raise StaleTakeoverError(
            "runtime liveness heartbeat is only valid for a foreign scheduler owner"
        )

    progress_points = [last_update, live_commit_at]
    if remote_updated_at is not None:
        progress_points.append(remote_updated_at)
    latest_progress = max(progress_points)

    if latest_progress > now_utc:
        raise StaleTakeoverError(
            "latest durable progress timestamp is in the future relative to now"
        )
    stale_seconds = int((now_utc - latest_progress).total_seconds())

    def result(
        classification: TakeoverClassification,
        actionable: bool,
        reason: str,
    ) -> StaleTakeoverEvaluation:
        return StaleTakeoverEvaluation(
            classification=classification,
            actionable=actionable,
            stale_seconds=stale_seconds,
            latest_progress_at=latest_progress,
            previous_worker=previous_worker,
            requesting_worker=requester,
            requesting_executor_source=requester_source,
            user_authority_comment_id=authority_comment_id,
            previous_executor_source=previous_source,
            observed_live_head_sha=live_head,
            reason=reason,
            stale_after_seconds=threshold,
            claim_head_sha=claim_head,
            claim_last_update=last_update,
            claim_phase=phase,
            orphan_grace_seconds=orphan_grace,
            claim_blob_sha=normalized_claim_blob,
            runtime_liveness_status=runtime_status,
            runtime_invocation_identity=runtime_invocation,
            runtime_liveness_emitted_at=runtime_emitted_at,
            runtime_liveness_expires_at=runtime_expires_at,
            active_delegated_issue=(
                None if active_delegated is None else active_delegated.child_issue
            ),
            active_delegated_helper_key=(
                None if active_delegated is None else active_delegated.helper_key
            ),
            active_delegated_relationship=(
                None if active_delegated is None else active_delegated.relationship
            ),
            active_delegated_latest_progress_at=(
                None if active_delegated is None else active_delegated.latest_progress_at
            ),
        )

    if phase in _INACTIVE_PHASES:
        return result(
            TakeoverClassification.TERMINAL,
            False,
            f"claim phase={phase} is terminal/inactive",
        )

    if previous_source == "scheduler":
        if requester is None:
            return result(
                TakeoverClassification.ALREADY_SCHEDULER,
                False,
                "scheduler-owned claim requires requesting_worker to distinguish lane identity",
            )
        if requester == previous_worker:
            return result(
                TakeoverClassification.ALREADY_SCHEDULER,
                False,
                "claim is already owned by the requesting worker",
            )

    if remote_active:
        return result(
            TakeoverClassification.RUN_LIVE,
            False,
            remote_reason,
        )

    if active_delegated is not None:
        return result(
            TakeoverClassification.ACTIVE_DELEGATED_WORK,
            False,
            (
                "parent has active delegated work "
                f"child_issue={active_delegated.child_issue} "
                f"relationship={active_delegated.relationship} "
                f"helper_key={active_delegated.helper_key}; "
                "evaluate/resume the delegated leaf instead of taking over the parent"
            ),
        )

    if previous_source == "scheduler" and requester != previous_worker:
        if runtime_status == "ACTIVE":
            return result(
                TakeoverClassification.WAIT_ON_FOREIGN_RUNTIME,
                False,
                (
                    "foreign scheduler invocation has a valid runtime heartbeat; "
                    f"{remote_reason}"
                ),
            )

        if stale_seconds >= threshold:
            return result(
                TakeoverClassification.EXECUTOR_STUCK,
                True,
                (
                    f"no active exact run and no durable progress for {stale_seconds}s "
                    f"(threshold={threshold}s); {remote_reason}"
                ),
            )

        if (
            normalized_claim_blob is not None
            and runtime_status in {"MISSING", "EXPIRED"}
            and stale_seconds >= orphan_grace
        ):
            return result(
                TakeoverClassification.ORPHANED_SCHEDULER_OWNER,
                True,
                (
                    f"foreign scheduler runtime liveness={runtime_status.lower()} "
                    f"after grace={orphan_grace}s while durable progress age="
                    f"{stale_seconds}s remains below stale threshold={threshold}s; "
                    f"{remote_reason}"
                ),
            )

    if stale_seconds >= threshold:
        return result(
            TakeoverClassification.EXECUTOR_STUCK,
            True,
            (
                f"no active exact run and no durable progress for {stale_seconds}s "
                f"(threshold={threshold}s); {remote_reason}"
            ),
        )

    return result(
        TakeoverClassification.WAIT_ON_FOREIGN_RUNTIME,
        False,
        (
            f"durable progress age={stale_seconds}s is below threshold={threshold}s; "
            f"{remote_reason}"
        ),
    )
def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StaleTakeoverError(f"{label} file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise StaleTakeoverError(f"{label} JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise StaleTakeoverError(f"{label} JSON root must be an object")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate whether a WHD scheduler may take over a stale execution claim"
    )
    parser.add_argument("--claim", required=True, type=Path)
    parser.add_argument("--live-head-sha", required=True)
    parser.add_argument("--live-head-committed-at", required=True)
    parser.add_argument("--remote-run-json", type=Path)
    parser.add_argument("--runtime-liveness-json", type=Path)
    parser.add_argument(
        "--delegated-work-json", action="append", type=Path, default=[]
    )
    parser.add_argument("--candidate-helper-key")
    parser.add_argument("--claim-blob-sha")
    parser.add_argument(
        "--orphan-grace-seconds",
        type=int,
        default=DEFAULT_ORPHAN_GRACE_SECONDS,
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=DEFAULT_STALE_AFTER_SECONDS,
    )
    parser.add_argument("--now")
    parser.add_argument("--requesting-worker")
    parser.add_argument("--requesting-executor-source")
    parser.add_argument("--user-authority-json", type=Path)
    parser.add_argument("--require-actionable", action="store_true")
    parser.add_argument("--decision-out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        claim = _load_json_object(args.claim, label="claim")
        remote = (
            None
            if args.remote_run_json is None
            else _load_json_object(args.remote_run_json, label="remote run")
        )
        user_authority = (
            None
            if args.user_authority_json is None
            else _load_json_object(args.user_authority_json, label="user authority")
        )
        runtime_liveness = (
            None
            if args.runtime_liveness_json is None
            else _load_json_object(
                args.runtime_liveness_json, label="runtime liveness heartbeat"
            )
        )
        now = datetime.now(timezone.utc) if args.now is None else _as_utc("now", args.now)
        if args.delegated_work_json:
            delegated_work = [
                _load_json_object(path, label="delegated work")
                for path in args.delegated_work_json
            ]
        elif _declared_delegations(claim):
            delegated_work = _discover_github_delegated_work(claim)
        else:
            delegated_work = []
        if args.candidate_helper_key is not None:
            assert_helper_creation_allowed(
                claim,
                helper_key=args.candidate_helper_key,
                delegated_work=delegated_work,
                now=now,
                stale_after_seconds=args.stale_after_seconds,
            )
            print(
                "HELPER_CREATION_GUARD_GREEN "
                f"helper_key={args.candidate_helper_key}"
            )
        result = evaluate_stale_claim_takeover(
            claim,
            now=now,
            live_head_sha=args.live_head_sha,
            live_head_committed_at=args.live_head_committed_at,
            remote_run=remote,
            stale_after_seconds=args.stale_after_seconds,
            requesting_worker=args.requesting_worker,
            requesting_executor_source=args.requesting_executor_source,
            user_authority=user_authority,
            claim_blob_sha=args.claim_blob_sha,
            runtime_liveness=runtime_liveness,
            orphan_grace_seconds=args.orphan_grace_seconds,
            delegated_work=delegated_work,
        )
    except StaleTakeoverError as exc:
        print(f"STALE_CLAIM_TAKEOVER_ERROR: {exc}")
        return 2

    payload_data = result.to_payload()
    payload = json.dumps(payload_data, ensure_ascii=False, sort_keys=True)
    if args.decision_out is not None:
        args.decision_out.write_text(
            json.dumps(payload_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"STALE_CLAIM_TAKEOVER_DECISION {payload}")
    if result.actionable:
        print(
            "STALE_CLAIM_TAKEOVER_GREEN "
            f"classification={result.classification.value} "
            f"stale_seconds={result.stale_seconds} "
            f"observed_live_head_sha={result.observed_live_head_sha}"
        )
        return 0

    print(
        "STALE_CLAIM_TAKEOVER_BLOCKED "
        f"classification={result.classification.value} "
        f"stale_seconds={result.stale_seconds}"
    )
    return 3 if args.require_actionable else 0


if __name__ == "__main__":
    raise SystemExit(main())
