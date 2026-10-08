"""GitHub Issue comment-based ownership and intervention clock (Issue #1412).

GitHub server-created timestamps are the ONLY age input for intervention.
This module is a pure validator/formatter: acquiring or transferring ownership
still requires the existing trusted Flow v2 CAS transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from tools.execution_record import ExecutionRecord

COMMENT_MARKER = "WHD_ISSUE_OWNER_PROGRESS_V1"
INTERVENTION_SECONDS = 600
ACTIVE_EVENTS = frozenset({"ACQUIRED", "PROGRESS", "TAKEOVER"})
FINAL_EVENTS = frozenset({"RELEASED", "DONE"})
ALL_EVENTS = ACTIVE_EVENTS | FINAL_EVENTS
REQUIRED_KEYS = frozenset({
    "issue", "generation", "owner_kind", "owner_id", "work_branch", "head_sha",
    "lane_id", "slot_id", "event", "done", "work", "blocker", "next",
})


@dataclass(frozen=True)
class CommentIntervention:
    eligible: bool
    reason: str
    age_seconds: float | None = None
    comment_id: int | None = None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _line_value(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("progress fields must be text")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("progress fields must be nonblank")
    return cleaned


def build_owner_progress_comment(
    *, issue: int, generation: int, owner_kind: str, owner_id: str,
    work_branch: str, head_sha: str, event: str, done: str,
    work: str, next_step: str, blocker: str = "無",
    lane_id: str | None = None, slot_id: str | None = None,
) -> str:
    """Build an agent/runner comment for Issue API POST; does NOT claim ownership."""
    if event not in ALL_EVENTS:
        raise ValueError("invalid progress event")
    if issue <= 0 or generation <= 0 or len(head_sha) != 40:
        raise ValueError("invalid owning Issue or work HEAD identity")
    values = {
        "issue": str(issue), "generation": str(generation),
        "owner_kind": _line_value(owner_kind), "owner_id": _line_value(owner_id),
        "work_branch": _line_value(work_branch), "head_sha": head_sha,
        "lane_id": _line_value(lane_id or "NONE"), "slot_id": _line_value(slot_id or "NONE"),
        "event": event, "done": _line_value(done),
        "work": _line_value(work), "blocker": _line_value(blocker),
        "next": _line_value(next_step),
    }
    return "\n".join([COMMENT_MARKER, *(f"{k}={v}" for k, v in values.items())])


def _parse_active_comment(body: object) -> dict[str, str] | None:
    if not isinstance(body, str):
        return None
    lines = body.strip().splitlines()
    if not lines or lines[0].strip() != COMMENT_MARKER:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        key, sep, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not sep or key not in REQUIRED_KEYS or not value or key in fields:
            return None
        fields[key] = value
    if set(fields) != REQUIRED_KEYS or fields["event"] not in ACTIVE_EVENTS:
        return None
    try:
        if int(fields["issue"]) <= 0 or int(fields["generation"]) <= 0:
            return None
    except ValueError:
        return None
    if len(fields["head_sha"]) != 40:
        return None
    try:
        int(fields["head_sha"], 16)
    except ValueError:
        return None
    for key in ("work", "next"):
        if fields[key].casefold() in {"heartbeat", "ping", "still alive", "無", "none"}:
            return None
    return fields


def evaluate_issue_comment_intervention(
    record: ExecutionRecord,
    comments: Iterable[Mapping[str, object]],
    *, now: datetime, trusted_authors: Iterable[str],
) -> CommentIntervention:
    """For a foreign owner, only a fresh verified Issue comment can authorize age.

    Absence, ambiguity, future timestamps, wrong owner/generation/HEAD and
    comments from untrusted GitHub logins all fail closed.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    trusted = set(trusted_authors)
    if not trusted:
        return CommentIntervention(False, "NO_TRUSTED_ISSUE_COMMENT_AUTHOR")
    newest: tuple[datetime, int | None] | None = None
    for item in comments:
        if not isinstance(item, Mapping):
            continue
        user = item.get("user")
        login = user.get("login") if isinstance(user, Mapping) else None
        if login not in trusted:
            continue
        fields = _parse_active_comment(item.get("body"))
        if fields is None:
            continue
        if (
            fields["issue"] != str(record.issue)
            or fields["generation"] != str(record.generation)
            or fields["owner_kind"] != record.owner_kind
            or fields["owner_id"] != record.owner_id
            or fields["work_branch"] != record.work_branch
            or fields["head_sha"] != record.head_sha
            or fields["lane_id"] != (record.lane_id or "NONE")
            or fields["slot_id"] != (record.slot_id or "NONE")
        ):
            continue
        created = _timestamp(item.get("created_at"))
        if created is None:
            continue
        if newest is None or created > newest[0]:
            raw_id = item.get("id")
            newest = (created, raw_id if isinstance(raw_id, int) else None)
    if newest is None:
        return CommentIntervention(False, "VALID_ISSUE_OWNER_COMMENT_MISSING")
    age = (now.astimezone(timezone.utc) - newest[0]).total_seconds()
    if age < 0:
        return CommentIntervention(False, "ISSUE_COMMENT_FUTURE_TIMESTAMP", age, newest[1])
    if age <= INTERVENTION_SECONDS:
        return CommentIntervention(False, "ISSUE_COMMENT_PROTECTED_600S", age, newest[1])
    return CommentIntervention(True, "ISSUE_COMMENT_STALE_OVER_600S", age, newest[1])
