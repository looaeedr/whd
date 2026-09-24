"""Executable stale execution-claim takeover policy for WHD schedulers.

The evaluator is pure: it never mutates GitHub, claims, branches, or runs. It turns
fresh durable observations into one fail-closed takeover decision. A scheduler may
request a guarded claim takeover only when this module returns EXECUTOR_STUCK.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping

DEFAULT_STALE_AFTER_SECONDS = 600
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


class StaleTakeoverError(RuntimeError):
    """Raised when fresh takeover evidence is incomplete or malformed."""


class TakeoverClassification(str, Enum):
    RUN_LIVE = "RUN_LIVE"
    WAIT_ON_FOREIGN_RUNTIME = "WAIT_ON_FOREIGN_RUNTIME"
    EXECUTOR_STUCK = "EXECUTOR_STUCK"
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

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema"] = "WHD_STALE_CLAIM_TAKEOVER_V1"
        payload["classification"] = self.classification.value
        payload["latest_progress_at"] = _iso_utc(self.latest_progress_at)
        payload["claim_last_update"] = _iso_utc(self.claim_last_update)
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
) -> StaleTakeoverEvaluation:
    """Classify whether one authorized requester may take over an active WHD claim."""

    if not isinstance(claim, Mapping):
        raise StaleTakeoverError("claim must be a mapping")
    now_utc = _as_utc("now", now)
    live_head = _require_sha("live_head_sha", live_head_sha)
    live_commit_at = _as_utc("live_head_committed_at", live_head_committed_at)
    threshold = _positive_int("stale_after_seconds", stale_after_seconds)

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
        now = datetime.now(timezone.utc) if args.now is None else _as_utc("now", args.now)
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
