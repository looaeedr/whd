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
END_RESULT_MARKER = "WHD_SCHEDULER_RUNTIME_END_RESULT_V1"
OWNER_LOGIN = "looaeedr"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REQUIRED = {"issue","scheduler_lane","invocation_identity","claim_blob_sha","branch","head_sha","executor_source","emitted_at","expires_at"}
_OPTIONAL = {"active_run_id","active_run_head_sha"}
_END_LEGACY_REQUIRED = {"issue","scheduler_lane","invocation_identity","claim_blob_sha","branch","head_sha","executor_source","ended_at","turn_exit_run_id"}
_END_RECEIPT_REQUIRED = {"issue","scheduler_lane","invocation_identity","claim_blob_sha","branch","head_sha","executor_source","ended_at","request_comment_id","result_comment_id","checkpoint_fingerprint","turn_exit_run_id","ready_work_census_fingerprint"}


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
    """Parse owner-authored END in either legacy or current receipt-bound shape."""
    if not isinstance(comment, Mapping):
        raise RuntimeLivenessCommentError("comment must be a mapping")
    user = comment.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != OWNER_LOGIN:
        raise RuntimeLivenessCommentError("runtime END must be authored by repository owner")
    body = comment.get("body")
    if not isinstance(body, str):
        raise RuntimeLivenessCommentError("runtime END body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != END_MARKER:
        raise RuntimeLivenessCommentError("runtime END marker mismatch")
    singles: dict[str, str] = {}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise RuntimeLivenessCommentError("runtime END contains malformed line")
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if key in singles:
            raise RuntimeLivenessCommentError("runtime END contains duplicate key")
        singles[key] = value
    keys = set(singles)
    comment_id = _positive_int("runtime source comment id", comment.get("id"))
    created_at = _utc("runtime source comment created_at", comment.get("created_at"))

    if keys == _END_LEGACY_REQUIRED:
        issue, lane, invocation, branch = _validate_common_identity(
            singles, label="runtime END"
        )
        return {
            "schema": END_MARKER, "mode": "LEGACY", "issue": issue,
            "scheduler_lane": lane, "invocation_identity": invocation,
            "claim_blob_sha": singles["claim_blob_sha"], "branch": branch,
            "head_sha": singles["head_sha"], "executor_source": "scheduler",
            "ended_at": singles["ended_at"],
            "turn_exit_run_id": _positive_int(
                "runtime END turn_exit_run_id", singles["turn_exit_run_id"]
            ),
            "source_comment_id": comment_id,
            "source_comment_created_at": created_at.isoformat().replace("+00:00","Z"),
            "_ended_dt": _utc("runtime END ended_at", singles["ended_at"]),
            "_created_dt": created_at,
        }

    if keys == _END_RECEIPT_REQUIRED:
        issue = _positive_int("runtime END issue", singles["issue"])
        lane = singles["scheduler_lane"]
        invocation = singles["invocation_identity"]
        if not _ID_RE.fullmatch(lane) or not lane.startswith("scheduler."):
            raise RuntimeLivenessCommentError("runtime END scheduler_lane is invalid")
        if not _ID_RE.fullmatch(invocation):
            raise RuntimeLivenessCommentError("runtime END invocation_identity is invalid")
        for key in ("claim_blob_sha", "head_sha"):
            if not _SHA_RE.fullmatch(singles[key]):
                raise RuntimeLivenessCommentError(f"runtime END {key} is invalid")
        branch = singles["branch"]
        if not branch or branch.startswith("/") or branch.endswith("/") or ".." in branch or "//" in branch:
            raise RuntimeLivenessCommentError("runtime END branch is invalid")
        if singles["executor_source"] != "scheduler":
            raise RuntimeLivenessCommentError("runtime END executor_source must be scheduler")
        for key in ("checkpoint_fingerprint", "ready_work_census_fingerprint"):
            if not re.fullmatch(r"[0-9a-f]{64}", singles[key]):
                raise RuntimeLivenessCommentError(f"runtime END {key} is invalid")
        return {
            "schema": END_MARKER, "mode": "RECEIPT_BOUND_PENDING_VALIDATION",
            "issue": issue, "scheduler_lane": lane,
            "invocation_identity": invocation,
            "claim_blob_sha": singles["claim_blob_sha"], "branch": branch,
            "head_sha": singles["head_sha"], "executor_source": "scheduler",
            "ended_at": singles["ended_at"],
            "request_comment_id": _positive_int("runtime END request_comment_id", singles["request_comment_id"]),
            "result_comment_id": _positive_int("runtime END result_comment_id", singles["result_comment_id"]),
            "checkpoint_fingerprint": singles["checkpoint_fingerprint"],
            "turn_exit_run_id": _positive_int("runtime END turn_exit_run_id", singles["turn_exit_run_id"]),
            "ready_work_census_fingerprint": singles["ready_work_census_fingerprint"],
            "source_comment_id": comment_id,
            "source_comment_created_at": created_at.isoformat().replace("+00:00","Z"),
            "_ended_dt": _utc("runtime END ended_at", singles["ended_at"]),
            "_created_dt": created_at,
        }

    raise RuntimeLivenessCommentError(
        "runtime END keys do not match legacy or current receipt-bound schema"
    )


def parse_runtime_end_result_comment(comment: Mapping[str, object]) -> dict[str, object]:
    """Parse bot-authored trusted END validator GREEN receipt."""
    if not isinstance(comment, Mapping):
        raise RuntimeLivenessCommentError("END result comment must be a mapping")
    user = comment.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != "github-actions[bot]":
        raise RuntimeLivenessCommentError("END result must be bot-authored")
    body = comment.get("body")
    if not isinstance(body, str) or not body.startswith(END_RESULT_MARKER):
        raise RuntimeLivenessCommentError("END result marker mismatch")
    match = re.search(r"~~~json\s*(\{.*?\})\s*~~~", body, re.S)
    if not match:
        raise RuntimeLivenessCommentError("END result JSON missing")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RuntimeLivenessCommentError("END result JSON invalid") from exc
    if payload.get("schema") != END_RESULT_MARKER:
        raise RuntimeLivenessCommentError("END result schema mismatch")
    if payload.get("result") != "GREEN" or payload.get("reason") != "EXACT_TURN_EXIT_RECEIPT_BOUND":
        raise RuntimeLivenessCommentError("END result is not trusted GREEN")
    required = _END_RECEIPT_REQUIRED | {"validation_run_id"}
    missing = sorted(key for key in required if key not in payload)
    if missing:
        raise RuntimeLivenessCommentError("END result missing keys: " + ",".join(missing))
    issue = _positive_int("END result issue", payload["issue"])
    lane = str(payload["scheduler_lane"])
    invocation = str(payload["invocation_identity"])
    if not _ID_RE.fullmatch(lane) or not lane.startswith("scheduler."):
        raise RuntimeLivenessCommentError("END result scheduler_lane is invalid")
    if not _ID_RE.fullmatch(invocation):
        raise RuntimeLivenessCommentError("END result invocation_identity is invalid")
    for key in ("claim_blob_sha", "head_sha"):
        if not _SHA_RE.fullmatch(str(payload[key])):
            raise RuntimeLivenessCommentError(f"END result {key} is invalid")
    if payload.get("executor_source") != "scheduler":
        raise RuntimeLivenessCommentError("END result executor_source must be scheduler")
    for key in ("checkpoint_fingerprint", "ready_work_census_fingerprint"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(payload[key])):
            raise RuntimeLivenessCommentError(f"END result {key} is invalid")
    created_at = _utc("END result source comment created_at", comment.get("created_at"))
    ended_at = _utc("END result ended_at", payload["ended_at"])
    return {
        **payload,
        "mode": "VALIDATED_RECEIPT_BOUND",
        "issue": issue,
        "scheduler_lane": lane,
        "invocation_identity": invocation,
        "source_comment_id": _positive_int("END result source comment id", comment.get("id")),
        "source_comment_created_at": created_at.isoformat().replace("+00:00","Z"),
        "_ended_dt": ended_at,
        "_created_dt": created_at,
    }


def select_runtime_liveness_comment(comments: object, *, issue: int, scheduler_lane: str) -> dict[str, object] | None:
    expected_issue = _positive_int("issue", issue)
    if not _ID_RE.fullmatch(scheduler_lane) or not scheduler_lane.startswith("scheduler."):
        raise RuntimeLivenessCommentError("scheduler_lane is invalid")
    flat_comments = list(_flatten_comments(comments))
    heartbeats, ends = [], []
    issue_token, lane_token = f"issue={expected_issue}", f"scheduler_lane={scheduler_lane}"
    for comment in flat_comments:
        body, user = comment.get("body"), comment.get("user")
        if not isinstance(body, str) or not isinstance(user, Mapping):
            continue
        marker = body.split("\n",1)[0].strip()
        try:
            if marker == MARKER and str(user.get("login") or "") == OWNER_LOGIN:
                payload = parse_runtime_liveness_comment(comment)
            elif marker == END_MARKER and str(user.get("login") or "") == OWNER_LOGIN:
                payload = parse_runtime_end_comment(comment)
                if payload.get("mode") != "LEGACY":
                    # Current END is only authoritative after trusted validator GREEN.
                    continue
            elif marker == END_RESULT_MARKER and str(user.get("login") or "") == "github-actions[bot]":
                payload = parse_runtime_end_result_comment(comment)
            else:
                continue
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
            if str(end.get(key) or "") != str(selected.get(key) or ""):
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
            "ended_at":str(end["ended_at"]),
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
