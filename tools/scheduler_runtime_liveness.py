"""Parse and select owner-authored scheduler runtime-liveness comments.

This module is intentionally narrow. It does not decide takeover authority; it
only turns the latest matching GitHub Issue comment into the
WHD_SCHEDULER_RUNTIME_LIVENESS_V1 JSON consumed by stale_claim_takeover.py.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

MARKER = "WHD_SCHEDULER_RUNTIME_LIVENESS_V1"
OWNER_LOGIN = "looaeedr"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REQUIRED = {
    "issue",
    "scheduler_lane",
    "invocation_identity",
    "claim_blob_sha",
    "branch",
    "head_sha",
    "executor_source",
    "emitted_at",
    "expires_at",
}
_OPTIONAL = {"active_run_id", "active_run_head_sha"}


class RuntimeLivenessCommentError(RuntimeError):
    """Raised when a relevant liveness comment is malformed."""


def _utc(label: str, value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeLivenessCommentError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeLivenessCommentError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeLivenessCommentError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _positive_int(label: str, value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeLivenessCommentError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeLivenessCommentError(
            f"{label} must be a positive integer"
        ) from exc
    if number <= 0:
        raise RuntimeLivenessCommentError(f"{label} must be a positive integer")
    return number


def _flatten_comments(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        comments = value.get("comments")
        if isinstance(comments, list):
            yield from _flatten_comments(comments)
        else:
            yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _flatten_comments(item)


def parse_runtime_liveness_comment(
    comment: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(comment, Mapping):
        raise RuntimeLivenessCommentError("comment must be a mapping")
    user = comment.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != OWNER_LOGIN:
        raise RuntimeLivenessCommentError(
            "runtime liveness comment must be authored by repository owner"
        )
    body = comment.get("body")
    if not isinstance(body, str):
        raise RuntimeLivenessCommentError("runtime liveness comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != MARKER:
        raise RuntimeLivenessCommentError("runtime liveness comment marker mismatch")

    singles: dict[str, str] = {}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise RuntimeLivenessCommentError(
                "runtime liveness comment contains malformed line"
            )
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in _REQUIRED | _OPTIONAL or key in singles:
            raise RuntimeLivenessCommentError(
                "runtime liveness comment contains unsupported/duplicate key"
            )
        singles[key] = value
    if not _REQUIRED.issubset(singles):
        missing = sorted(_REQUIRED - set(singles))
        raise RuntimeLivenessCommentError(
            "runtime liveness comment is missing required keys: " + ",".join(missing)
        )

    issue = _positive_int("runtime liveness issue", singles["issue"])
    lane = singles["scheduler_lane"]
    invocation = singles["invocation_identity"]
    if not _ID_RE.fullmatch(lane) or not lane.startswith("scheduler."):
        raise RuntimeLivenessCommentError("runtime liveness scheduler_lane is invalid")
    if not _ID_RE.fullmatch(invocation):
        raise RuntimeLivenessCommentError(
            "runtime liveness invocation_identity is invalid"
        )
    for key in ("claim_blob_sha", "head_sha"):
        if not _SHA_RE.fullmatch(singles[key]):
            raise RuntimeLivenessCommentError(f"runtime liveness {key} is invalid")
    branch = singles["branch"]
    if (
        not branch
        or branch.startswith("/")
        or branch.endswith("/")
        or ".." in branch
        or "//" in branch
    ):
        raise RuntimeLivenessCommentError("runtime liveness branch is invalid")
    if singles["executor_source"] != "scheduler":
        raise RuntimeLivenessCommentError(
            "runtime liveness executor_source must be scheduler"
        )

    emitted = _utc("runtime liveness emitted_at", singles["emitted_at"])
    expires = _utc("runtime liveness expires_at", singles["expires_at"])
    if expires <= emitted:
        raise RuntimeLivenessCommentError(
            "runtime liveness expires_at must be after emitted_at"
        )

    run_id = singles.get("active_run_id")
    run_head = singles.get("active_run_head_sha")
    if (run_id is None) != (run_head is None):
        raise RuntimeLivenessCommentError(
            "runtime liveness active run id/head must be present together"
        )
    parsed_run_id = None
    if run_id is not None:
        parsed_run_id = _positive_int("runtime liveness active_run_id", run_id)
        if not _SHA_RE.fullmatch(run_head or ""):
            raise RuntimeLivenessCommentError(
                "runtime liveness active_run_head_sha is invalid"
            )

    comment_id = _positive_int("runtime liveness source comment id", comment.get("id"))
    created_at = _utc(
        "runtime liveness source comment created_at", comment.get("created_at")
    )
    return {
        "schema": MARKER,
        "issue": issue,
        "scheduler_lane": lane,
        "invocation_identity": invocation,
        "claim_blob_sha": singles["claim_blob_sha"],
        "branch": branch,
        "head_sha": singles["head_sha"],
        "executor_source": "scheduler",
        "emitted_at": singles["emitted_at"],
        "expires_at": singles["expires_at"],
        "active_run_id": parsed_run_id,
        "active_run_head_sha": run_head,
        "source_comment_id": comment_id,
        "source_comment_created_at": created_at.isoformat().replace("+00:00", "Z"),
    }


def select_runtime_liveness_comment(
    comments: object,
    *,
    issue: int,
    scheduler_lane: str,
) -> dict[str, object] | None:
    expected_issue = _positive_int("issue", issue)
    if not _ID_RE.fullmatch(scheduler_lane) or not scheduler_lane.startswith(
        "scheduler."
    ):
        raise RuntimeLivenessCommentError("scheduler_lane is invalid")

    matches: list[tuple[datetime, int, dict[str, object]]] = []
    issue_token = f"issue={expected_issue}"
    lane_token = f"scheduler_lane={scheduler_lane}"
    for comment in _flatten_comments(comments):
        body = comment.get("body")
        user = comment.get("user")
        if (
            not isinstance(body, str)
            or not body.startswith(MARKER)
            or not isinstance(user, Mapping)
            or str(user.get("login") or "") != OWNER_LOGIN
        ):
            continue
        try:
            payload = parse_runtime_liveness_comment(comment)
        except RuntimeLivenessCommentError:
            if issue_token in body and lane_token in body:
                raise
            continue
        if (
            payload["issue"] == expected_issue
            and payload["scheduler_lane"] == scheduler_lane
        ):
            created = _utc(
                "runtime liveness source comment created_at",
                payload["source_comment_created_at"],
            )
            matches.append((created, int(payload["source_comment_id"]), payload))

    if not matches:
        return None
    return max(matches, key=lambda item: (item[0], item[1]))[2]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select latest owner-authored WHD scheduler liveness comment"
    )
    parser.add_argument("--comments-json", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--scheduler-lane", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        comments = json.loads(args.comments_json.read_text(encoding="utf-8"))
        selected = select_runtime_liveness_comment(
            comments,
            issue=args.issue,
            scheduler_lane=args.scheduler_lane,
        )
    except (OSError, json.JSONDecodeError, RuntimeLivenessCommentError) as exc:
        print(f"SCHEDULER_RUNTIME_LIVENESS_ERROR: {exc}")
        return 2
    if selected is None:
        print(
            "SCHEDULER_RUNTIME_LIVENESS_MISSING "
            f"issue={args.issue} scheduler_lane={args.scheduler_lane}"
        )
        return 3
    args.out.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "SCHEDULER_RUNTIME_LIVENESS_SELECTED "
        f"issue={args.issue} scheduler_lane={args.scheduler_lane} "
        f"comment_id={selected['source_comment_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
