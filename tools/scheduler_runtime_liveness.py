"""Parse owner-authored scheduler runtime heartbeat + matching END comments."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

MARKER = "WHD_SCHEDULER_RUNTIME_LIVENESS_V1"
END_MARKER = "WHD_SCHEDULER_RUNTIME_END_V1"
OWNER_LOGIN = "looaeedr"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REQUIRED = {"issue","scheduler_lane","invocation_identity","claim_blob_sha","branch","head_sha","executor_source","emitted_at","expires_at"}
_OPTIONAL = {"active_run_id","active_run_head_sha"}
_END_REQUIRED = {"issue","scheduler_lane","invocation_identity","claim_blob_sha","branch","head_sha","executor_source","ended_at","turn_exit_run_id"}


class RuntimeLivenessCommentError(RuntimeError):
    """Raised when a relevant heartbeat or END comment is malformed."""


def _utc(label: str, value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeLivenessCommentError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeLivenessCommentError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeLivenessCommentError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _positive_int(label: str, value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeLivenessCommentError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeLivenessCommentError(f"{label} must be a positive integer") from exc
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


def _parse_kv_body(comment, *, marker, required, optional=None):
    user = comment.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != OWNER_LOGIN:
        raise RuntimeLivenessCommentError("runtime comment must be authored by repository owner")
    body = comment.get("body")
    if not isinstance(body, str):
        raise RuntimeLivenessCommentError("runtime comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != marker:
        raise RuntimeLivenessCommentError("runtime comment marker mismatch")
    allowed = required | (optional or set())
    singles = {}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise RuntimeLivenessCommentError("runtime comment contains malformed line")
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in allowed or key in singles:
            raise RuntimeLivenessCommentError("runtime comment contains unsupported/duplicate key")
        singles[key] = value
    if not required.issubset(singles):
        raise RuntimeLivenessCommentError("runtime comment is missing required keys: " + ",".join(sorted(required-set(singles))))
    return singles, _positive_int("runtime source comment id", comment.get("id")), _utc("runtime source comment created_at", comment.get("created_at"))


def _validate_common_identity(singles, *, label):
    issue = _positive_int(f"{label} issue", singles["issue"])
    lane = singles["scheduler_lane"]
    invocation = singles["invocation_identity"]
    if not _ID_RE.fullmatch(lane) or not lane.startswith("scheduler."):
        raise RuntimeLivenessCommentError(f"{label} scheduler_lane is invalid")
    if not _ID_RE.fullmatch(invocation):
        raise RuntimeLivenessCommentError(f"{label} invocation_identity is invalid")
    for key in ("claim_blob_sha","head_sha"):
        if not _SHA_RE.fullmatch(singles[key]):
            raise RuntimeLivenessCommentError(f"{label} {key} is invalid")
    branch = singles["branch"]
    if not branch or branch.startswith("/") or branch.endswith("/") or ".." in branch or "//" in branch:
        raise RuntimeLivenessCommentError(f"{label} branch is invalid")
    if singles["executor_source"] != "scheduler":
        raise RuntimeLivenessCommentError(f"{label} executor_source must be scheduler")
    return issue, lane, invocation, branch


def parse_runtime_liveness_comment(comment: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(comment, Mapping):
        raise RuntimeLivenessCommentError("comment must be a mapping")
    singles, comment_id, created_at = _parse_kv_body(comment, marker=MARKER, required=_REQUIRED, optional=_OPTIONAL)
    issue, lane, invocation, branch = _validate_common_identity(singles, label="runtime liveness")
    emitted = _utc("runtime liveness emitted_at", singles["emitted_at"])
    expires = _utc("runtime liveness expires_at", singles["expires_at"])
    if expires <= emitted:
        raise RuntimeLivenessCommentError("runtime liveness expires_at must be after emitted_at")
    run_id, run_head = singles.get("active_run_id"), singles.get("active_run_head_sha")
    if (run_id is None) != (run_head is None):
        raise RuntimeLivenessCommentError("runtime liveness active run id/head must be present together")
    parsed_run_id = None
    if run_id is not None:
        parsed_run_id = _positive_int("runtime liveness active_run_id", run_id)
        if not _SHA_RE.fullmatch(run_head or ""):
            raise RuntimeLivenessCommentError("runtime liveness active_run_head_sha is invalid")
    return {
        "schema": MARKER, "issue": issue, "scheduler_lane": lane,
        "invocation_identity": invocation, "claim_blob_sha": singles["claim_blob_sha"],
        "branch": branch, "head_sha": singles["head_sha"], "executor_source": "scheduler",
        "emitted_at": singles["emitted_at"], "expires_at": singles["expires_at"],
        "active_run_id": parsed_run_id, "active_run_head_sha": run_head,
        "runtime_status": "ACTIVE", "end_source_comment_id": None,
        "ended_at": None, "turn_exit_run_id": None,
        "source_comment_id": comment_id,
        "source_comment_created_at": created_at.isoformat().replace("+00:00","Z"),
    }


def parse_runtime_end_comment(comment: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(comment, Mapping):
        raise RuntimeLivenessCommentError("comment must be a mapping")
    singles, comment_id, created_at = _parse_kv_body(comment, marker=END_MARKER, required=_END_REQUIRED)
    issue, lane, invocation, branch = _validate_common_identity(singles, label="runtime END")
    return {
        "schema": END_MARKER, "issue": issue, "scheduler_lane": lane,
        "invocation_identity": invocation, "claim_blob_sha": singles["claim_blob_sha"],
        "branch": branch, "head_sha": singles["head_sha"], "executor_source": "scheduler",
        "ended_at": singles["ended_at"],
        "turn_exit_run_id": _positive_int("runtime END turn_exit_run_id", singles["turn_exit_run_id"]),
        "source_comment_id": comment_id,
        "source_comment_created_at": created_at.isoformat().replace("+00:00","Z"),
        "_ended_dt": _utc("runtime END ended_at", singles["ended_at"]),
        "_created_dt": created_at,
    }


def select_runtime_liveness_comment(comments: object, *, issue: int, scheduler_lane: str) -> dict[str, object] | None:
    expected_issue = _positive_int("issue", issue)
    if not _ID_RE.fullmatch(scheduler_lane) or not scheduler_lane.startswith("scheduler."):
        raise RuntimeLivenessCommentError("scheduler_lane is invalid")
    heartbeats, ends = [], []
    issue_token, lane_token = f"issue={expected_issue}", f"scheduler_lane={scheduler_lane}"
    for comment in _flatten_comments(comments):
        body, user = comment.get("body"), comment.get("user")
        if not isinstance(body, str) or not isinstance(user, Mapping) or str(user.get("login") or "") != OWNER_LOGIN:
            continue
        marker = body.split("\n",1)[0].strip()
        if marker not in {MARKER, END_MARKER}:
            continue
        try:
            payload = parse_runtime_liveness_comment(comment) if marker == MARKER else parse_runtime_end_comment(comment)
        except RuntimeLivenessCommentError:
            if issue_token in body and lane_token in body:
                raise
            continue
        if payload["issue"] != expected_issue or payload["scheduler_lane"] != scheduler_lane:
            continue
        if marker == MARKER:
            created = _utc("runtime liveness source comment created_at", payload["source_comment_created_at"])
            heartbeats.append((created, int(payload["source_comment_id"]), payload))
        else:
            ends.append(payload)
    if not heartbeats:
        return None
    selected = max(heartbeats, key=lambda item:(item[0],item[1]))[2]
    selected_created = _utc("runtime liveness source comment created_at", selected["source_comment_created_at"])
    selected_emitted = _utc("runtime liveness emitted_at", selected["emitted_at"])
    matching = []
    for end in ends:
        if end["invocation_identity"] != selected["invocation_identity"]:
            continue
        for key in ("claim_blob_sha","branch","head_sha","executor_source"):
            if end[key] != selected[key]:
                raise RuntimeLivenessCommentError(f"runtime END {key} does not match selected heartbeat")
        if end["_ended_dt"] < selected_emitted or end["_created_dt"] < selected_created:
            raise RuntimeLivenessCommentError("runtime END predates selected heartbeat invocation")
        matching.append(end)
    if matching:
        end = max(matching, key=lambda item:(item["_created_dt"],int(item["source_comment_id"])))
        selected = dict(selected)
        selected.update({
            "runtime_status":"ENDED",
            "end_source_comment_id":int(end["source_comment_id"]),
            "ended_at":end["ended_at"],
            "turn_exit_run_id":int(end["turn_exit_run_id"]),
        })
    return selected


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select latest owner-authored WHD scheduler heartbeat and matching END")
    parser.add_argument("--comments-json", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--scheduler-lane", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        comments = json.loads(args.comments_json.read_text(encoding="utf-8"))
        selected = select_runtime_liveness_comment(comments, issue=args.issue, scheduler_lane=args.scheduler_lane)
    except (OSError, json.JSONDecodeError, RuntimeLivenessCommentError) as exc:
        print(f"SCHEDULER_RUNTIME_LIVENESS_ERROR: {exc}")
        return 2
    if selected is None:
        print(f"SCHEDULER_RUNTIME_LIVENESS_MISSING issue={args.issue} scheduler_lane={args.scheduler_lane}")
        return 3
    args.out.write_text(json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SCHEDULER_RUNTIME_LIVENESS_SELECTED " f"issue={args.issue} scheduler_lane={args.scheduler_lane} " f"comment_id={selected['source_comment_id']} runtime_status={selected['runtime_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
