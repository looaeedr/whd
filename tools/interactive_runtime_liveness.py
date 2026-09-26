"""Parse owner-authored interactive ChatGPT runtime heartbeat + END comments."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Mapping

MARKER = "WHD_INTERACTIVE_RUNTIME_LIVENESS_V1"
END_MARKER = "WHD_INTERACTIVE_RUNTIME_END_V1"
OWNER_LOGIN = "looaeedr"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_HEARTBEAT_REQUIRED = {
    "issue",
    "slot_id",
    "worker",
    "invocation_identity",
    "conversation_identity",
    "claim_blob_sha",
    "branch",
    "head_sha",
    "executor_source",
    "emitted_at",
    "expires_at",
}
_END_REQUIRED = {
    "issue",
    "slot_id",
    "worker",
    "invocation_identity",
    "conversation_identity",
    "claim_blob_sha",
    "branch",
    "head_sha",
    "executor_source",
    "ended_at",
    "reason",
}


class InteractiveRuntimeLivenessError(RuntimeError):
    """Raised when relevant interactive runtime evidence is malformed."""


def _utc(label: str, value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise InteractiveRuntimeLivenessError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise InteractiveRuntimeLivenessError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InteractiveRuntimeLivenessError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _positive_int(label: str, value: object) -> int:
    if isinstance(value, bool):
        raise InteractiveRuntimeLivenessError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise InteractiveRuntimeLivenessError(
            f"{label} must be a positive integer"
        ) from exc
    if number <= 0:
        raise InteractiveRuntimeLivenessError(f"{label} must be a positive integer")
    return number


def _parse(comment: Mapping[str, object], *, marker: str, required: set[str]):
    user = comment.get("user")
    if not isinstance(user, Mapping) or str(user.get("login") or "") != OWNER_LOGIN:
        raise InteractiveRuntimeLivenessError(
            "interactive runtime comment must be authored by repository owner"
        )
    body = comment.get("body")
    if not isinstance(body, str):
        raise InteractiveRuntimeLivenessError("interactive runtime comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != marker:
        raise InteractiveRuntimeLivenessError("interactive runtime marker mismatch")

    fields: dict[str, str] = {}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise InteractiveRuntimeLivenessError(
                "interactive runtime comment contains malformed line"
            )
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in required or key in fields:
            raise InteractiveRuntimeLivenessError(
                "interactive runtime comment contains unsupported/duplicate key"
            )
        fields[key] = value
    if set(fields) != required:
        raise InteractiveRuntimeLivenessError(
            "interactive runtime comment is missing required keys"
        )
    return fields, _positive_int("source comment id", comment.get("id")), _utc(
        "source comment created_at", comment.get("created_at")
    )


def _common(fields: Mapping[str, str], *, label: str):
    issue = _positive_int(f"{label} issue", fields["issue"])
    slot = fields["slot_id"]
    worker = fields["worker"]
    invocation = fields["invocation_identity"]
    conversation = fields["conversation_identity"]
    if not _ID_RE.fullmatch(slot):
        raise InteractiveRuntimeLivenessError(f"{label} slot_id identity is invalid")
    if not _ID_RE.fullmatch(worker) or not worker.startswith("chatgpt."):
        raise InteractiveRuntimeLivenessError(f"{label} worker identity is invalid")
    if not _ID_RE.fullmatch(invocation):
        raise InteractiveRuntimeLivenessError(
            f"{label} invocation identity is invalid"
        )
    if not _ID_RE.fullmatch(conversation) or conversation == "UNAVAILABLE":
        raise InteractiveRuntimeLivenessError(
            f"{label} conversation identity is invalid"
        )
    for key in ("claim_blob_sha", "head_sha"):
        if not _SHA_RE.fullmatch(fields[key]):
            raise InteractiveRuntimeLivenessError(f"{label} {key} is invalid")
    branch = fields["branch"]
    if not branch or branch.startswith("/") or branch.endswith("/") or ".." in branch or "//" in branch:
        raise InteractiveRuntimeLivenessError(f"{label} branch is invalid")
    if fields["executor_source"] != "chat":
        raise InteractiveRuntimeLivenessError(
            f"{label} executor_source must be chat"
        )
    return issue, slot, worker, invocation, conversation, branch


def parse_interactive_runtime_liveness_comment(
    comment: Mapping[str, object],
) -> dict[str, object]:
    fields, cid, created = _parse(
        comment, marker=MARKER, required=_HEARTBEAT_REQUIRED
    )
    issue, slot, worker, invocation, conversation, branch = _common(
        fields, label="interactive runtime liveness"
    )
    emitted = _utc("interactive runtime emitted_at", fields["emitted_at"])
    expires = _utc("interactive runtime expires_at", fields["expires_at"])
    if expires <= emitted:
        raise InteractiveRuntimeLivenessError(
            "interactive runtime expires_at must be after emitted_at"
        )
    return {
        "schema": MARKER,
        "issue": issue,
        "slot_id": slot,
        "worker": worker,
        "invocation_identity": invocation,
        "conversation_identity": conversation,
        "claim_blob_sha": fields["claim_blob_sha"],
        "branch": branch,
        "head_sha": fields["head_sha"],
        "executor_source": "chat",
        "emitted_at": fields["emitted_at"],
        "expires_at": fields["expires_at"],
        "runtime_status": "ACTIVE",
        "ended_at": None,
        "end_reason": None,
        "end_source_comment_id": None,
        "source_comment_id": cid,
        "source_comment_created_at": created.isoformat().replace("+00:00", "Z"),
    }


def parse_interactive_runtime_end_comment(
    comment: Mapping[str, object],
) -> dict[str, object]:
    fields, cid, created = _parse(comment, marker=END_MARKER, required=_END_REQUIRED)
    issue, slot, worker, invocation, conversation, branch = _common(
        fields, label="interactive runtime END"
    )
    ended = _utc("interactive runtime ended_at", fields["ended_at"])
    reason = fields["reason"]
    if not _ID_RE.fullmatch(reason):
        raise InteractiveRuntimeLivenessError("interactive runtime END reason is invalid")
    return {
        "schema": END_MARKER,
        "issue": issue,
        "slot_id": slot,
        "worker": worker,
        "invocation_identity": invocation,
        "conversation_identity": conversation,
        "claim_blob_sha": fields["claim_blob_sha"],
        "branch": branch,
        "head_sha": fields["head_sha"],
        "executor_source": "chat",
        "ended_at": fields["ended_at"],
        "end_reason": reason,
        "source_comment_id": cid,
        "source_comment_created_at": created.isoformat().replace("+00:00", "Z"),
        "_ended_dt": ended,
        "_created_dt": created,
    }


def _flatten(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        comments = value.get("comments")
        if isinstance(comments, list):
            yield from _flatten(comments)
        else:
            yield value
    elif isinstance(value, list):
        for item in value:
            yield from _flatten(item)


def select_interactive_runtime_liveness(
    comments: object,
    *,
    issue: int,
    worker: str,
) -> dict[str, object] | None:
    expected_issue = _positive_int("issue", issue)
    if not _ID_RE.fullmatch(worker) or not worker.startswith("chatgpt."):
        raise InteractiveRuntimeLivenessError("worker identity is invalid")

    heartbeats: list[tuple[datetime, int, dict[str, object]]] = []
    ends: list[dict[str, object]] = []
    issue_token = f"issue={expected_issue}"
    worker_token = f"worker={worker}"

    for comment in _flatten(comments):
        body = comment.get("body")
        user = comment.get("user")
        if (
            not isinstance(body, str)
            or not isinstance(user, Mapping)
            or str(user.get("login") or "") != OWNER_LOGIN
        ):
            continue
        marker = body.split("\n", 1)[0].strip()
        if marker not in {MARKER, END_MARKER}:
            continue
        try:
            payload = (
                parse_interactive_runtime_liveness_comment(comment)
                if marker == MARKER
                else parse_interactive_runtime_end_comment(comment)
            )
        except InteractiveRuntimeLivenessError:
            if issue_token in body and worker_token in body:
                raise
            continue
        if payload["issue"] != expected_issue:
            continue
        if marker == MARKER:
            if payload["worker"] != worker:
                continue
            created = _utc(
                "source comment created_at", payload["source_comment_created_at"]
            )
            heartbeats.append((created, int(payload["source_comment_id"]), payload))
        else:
            # Keep all END records for the issue. After selecting the exact
            # heartbeat owner, compare the END identity envelope fail-closed.
            ends.append(payload)

    if not heartbeats:
        return None

    selected = max(heartbeats, key=lambda item: (item[0], item[1]))[2]
    selected_created = _utc(
        "selected source comment created_at", selected["source_comment_created_at"]
    )
    selected_emitted = _utc("selected emitted_at", selected["emitted_at"])

    matching: list[dict[str, object]] = []
    identity_fields = (
        "slot_id",
        "worker",
        "invocation_identity",
        "conversation_identity",
        "claim_blob_sha",
        "branch",
        "head_sha",
        "executor_source",
    )
    for end in ends:
        if end["issue"] != selected["issue"]:
            continue
        # Any END for this issue that points at the selected heartbeat identity
        # envelope must match it exactly. Do not silently ignore a drifted worker,
        # invocation, conversation, claim, branch, or HEAD as "another runtime".
        overlaps_selected_identity = any(
            end.get(key) == selected.get(key)
            for key in (
                "slot_id",
                "invocation_identity",
                "conversation_identity",
                "claim_blob_sha",
                "branch",
                "head_sha",
            )
        )
        if not overlaps_selected_identity:
            continue
        for key in identity_fields:
            if end[key] != selected[key]:
                raise InteractiveRuntimeLivenessError(
                    f"interactive runtime END {key} does not match selected heartbeat"
                )
        if end["_ended_dt"] < selected_emitted or end["_created_dt"] < selected_created:
            raise InteractiveRuntimeLivenessError(
                "interactive runtime END predates selected heartbeat"
            )
        matching.append(end)

    if matching:
        end = max(
            matching,
            key=lambda item: (item["_created_dt"], int(item["source_comment_id"])),
        )
        selected = dict(selected)
        selected.update(
            {
                "runtime_status": "ENDED",
                "ended_at": end["ended_at"],
                "end_reason": end["end_reason"],
                "end_source_comment_id": int(end["source_comment_id"]),
            }
        )
    return selected
