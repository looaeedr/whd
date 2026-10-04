# -*- coding: utf-8 -*-
"""Validate scheduler-owned push requests for remote Phase6 Preflight."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Mapping

PUSH_SCHEMA = "WHD_REMOTE_PHASE6_PREFLIGHT_PUSH_REQUEST_V1"
NORMALIZED_SCHEMA = "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1"

REQUEST_BRANCH_LANES = {
    "coord/preflight-requests-a": "scheduler.6ab13fa557fc8191935c671214b865e2",
    "coord/preflight-requests-b": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
}


class Phase6PushRequestError(ValueError):
    pass


def _nonblank(value: object, label: str, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise Phase6PushRequestError(f"{label} must be nonblank")
    if len(text) > max_len:
        raise Phase6PushRequestError(f"{label} too long")
    return text


def _branch(value: object) -> str:
    text = _nonblank(value, "branch", max_len=200)
    if (
        not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", text)
        or text.startswith("/")
        or text.endswith("/")
        or ".." in text
        or "//" in text
        or "@{" in text
    ):
        raise Phase6PushRequestError("invalid branch")
    return text


def _sha(value: object) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise Phase6PushRequestError("head_sha must be a Git SHA")
    return text


def _changed_files(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise Phase6PushRequestError("changed_files must be an array")
    result: list[str] = []
    for raw_value in value:
        raw = str(raw_value or "")
        path = PurePosixPath(raw)
        if (
            not raw
            or path.is_absolute()
            or ".." in path.parts
            or raw.startswith("./")
            or "\\" in raw
        ):
            raise Phase6PushRequestError(f"invalid changed_file: {raw!r}")
        result.append(path.as_posix())
    if len(result) > 100:
        raise Phase6PushRequestError("too many changed_file entries")
    if len(result) != len(set(result)):
        raise Phase6PushRequestError("duplicate changed_file entries")
    return result


def normalize_push_request(
    payload: object,
    *,
    request_branch: str,
) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise Phase6PushRequestError("push request must be an object")
    item = {str(k): v for k, v in payload.items()}
    if item.get("schema") != PUSH_SCHEMA:
        raise Phase6PushRequestError("invalid push preflight schema")

    expected_lane = REQUEST_BRANCH_LANES.get(request_branch)
    if expected_lane is None:
        raise Phase6PushRequestError(f"unsupported preflight request branch: {request_branch}")

    lane_id = _nonblank(item.get("lane_id"), "lane_id", max_len=128)
    worker = _nonblank(item.get("worker"), "worker", max_len=128)
    if lane_id != expected_lane or worker != expected_lane:
        raise Phase6PushRequestError(
            f"preflight request lane mismatch: branch {request_branch} requires {expected_lane}"
        )
    if item.get("executor_source") != "scheduler":
        raise Phase6PushRequestError("push preflight executor_source must be scheduler")

    issue = item.get("issue")
    if isinstance(issue, bool):
        raise Phase6PushRequestError("issue must be positive")
    try:
        issue_number = int(issue)
    except (TypeError, ValueError) as exc:
        raise Phase6PushRequestError("issue must be positive") from exc
    if issue_number <= 0:
        raise Phase6PushRequestError("issue must be positive")

    request_id = _nonblank(item.get("request_id"), "request_id", max_len=160)
    invocation = _nonblank(item.get("invocation_identity"), "invocation_identity", max_len=256)
    task = _nonblank(item.get("task"), "task", max_len=4000)
    normalized = {
        "schema": NORMALIZED_SCHEMA,
        "request_source": "push",
        "request_id": request_id,
        "issue": issue_number,
        "worker": worker,
        "lane_id": lane_id,
        "invocation_identity": invocation,
        "executor_source": "scheduler",
        "branch": _branch(item.get("branch")),
        "head_sha": _sha(item.get("head_sha")),
        "task": task,
        "changed_files": _changed_files(item.get("changed_files")),
    }
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate scheduler Phase6 push request")
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--request-branch", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = json.loads(args.request_file.read_text(encoding="utf-8"))
    normalized = normalize_push_request(payload, request_branch=args.request_branch)
    args.output.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
