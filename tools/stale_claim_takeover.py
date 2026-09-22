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
_ACTIVE_PHASES = frozenset(
    {
        "CLAIMED",
        "RED",
        "IMPLEMENTING",
        "GREEN",
        "REMOTE_QA",
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
    previous_executor_source: str
    observed_live_head_sha: str
    reason: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        payload["latest_progress_at"] = _iso_utc(self.latest_progress_at)
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


def _remote_progress(
    claim: Mapping[str, object],
    remote_run: Mapping[str, object] | None,
) -> tuple[bool, datetime | None, str]:
    remote_qa = claim.get("remote_qa")
    expected_run_id: int | None = None
    if isinstance(remote_qa, Mapping) and remote_qa.get("run_id") is not None:
        expected_run_id = _positive_int("claim remote_qa.run_id", remote_qa.get("run_id"))
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
) -> StaleTakeoverEvaluation:
    """Classify whether a scheduler may take over one active WHD execution claim."""

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

    last_update = _as_utc("claim last_update", claim.get("last_update"))
    previous_source = str(claim.get("executor_source") or "unknown").strip() or "unknown"

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

    if phase in _INACTIVE_PHASES:
        return StaleTakeoverEvaluation(
            classification=TakeoverClassification.TERMINAL,
            actionable=False,
            stale_seconds=stale_seconds,
            latest_progress_at=latest_progress,
            previous_executor_source=previous_source,
            observed_live_head_sha=live_head,
            reason=f"claim phase={phase} is terminal/inactive",
        )

    if previous_source == "scheduler":
        return StaleTakeoverEvaluation(
            classification=TakeoverClassification.ALREADY_SCHEDULER,
            actionable=False,
            stale_seconds=stale_seconds,
            latest_progress_at=latest_progress,
            previous_executor_source=previous_source,
            observed_live_head_sha=live_head,
            reason="claim is already owned by scheduler executor_source",
        )

    if remote_active:
        return StaleTakeoverEvaluation(
            classification=TakeoverClassification.RUN_LIVE,
            actionable=False,
            stale_seconds=stale_seconds,
            latest_progress_at=latest_progress,
            previous_executor_source=previous_source,
            observed_live_head_sha=live_head,
            reason=remote_reason,
        )

    if stale_seconds >= threshold:
        return StaleTakeoverEvaluation(
            classification=TakeoverClassification.EXECUTOR_STUCK,
            actionable=True,
            stale_seconds=stale_seconds,
            latest_progress_at=latest_progress,
            previous_executor_source=previous_source,
            observed_live_head_sha=live_head,
            reason=(
                f"no active exact run and no durable progress for {stale_seconds}s "
                f"(threshold={threshold}s); {remote_reason}"
            ),
        )

    return StaleTakeoverEvaluation(
        classification=TakeoverClassification.WAIT_ON_FOREIGN_RUNTIME,
        actionable=False,
        stale_seconds=stale_seconds,
        latest_progress_at=latest_progress,
        previous_executor_source=previous_source,
        observed_live_head_sha=live_head,
        reason=(
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
    parser.add_argument("--require-actionable", action="store_true")
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
        now = datetime.now(timezone.utc) if args.now is None else _as_utc("now", args.now)
        result = evaluate_stale_claim_takeover(
            claim,
            now=now,
            live_head_sha=args.live_head_sha,
            live_head_committed_at=args.live_head_committed_at,
            remote_run=remote,
            stale_after_seconds=args.stale_after_seconds,
        )
    except StaleTakeoverError as exc:
        print(f"STALE_CLAIM_TAKEOVER_ERROR: {exc}")
        return 2

    payload = json.dumps(result.to_payload(), ensure_ascii=False, sort_keys=True)
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
