"""GitHub issue-body transport for the canonical WHD continuity checkpoint."""

from __future__ import annotations

import json

from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    checkpoint_from_payload,
    checkpoint_to_payload,
)


CHECKPOINT_BEGIN = "<!-- WHD_CONTINUITY_CHECKPOINT_BEGIN -->"
CHECKPOINT_END = "<!-- WHD_CONTINUITY_CHECKPOINT_END -->"
SCHEDULED_RESUME_ELIGIBLE_MARKER = "<!-- WHD_SCHEDULED_RESUME_ELIGIBLE -->"


def _strip_checkpoint_block(body: str) -> str:
    text = str(body or "")
    start = text.find(CHECKPOINT_BEGIN)
    if start < 0:
        return text.rstrip()
    end = text.find(CHECKPOINT_END, start + len(CHECKPOINT_BEGIN))
    if end < 0:
        raise CheckpointError("continuity checkpoint block is malformed")
    end += len(CHECKPOINT_END)
    return (text[:start] + text[end:]).strip()


def parse_issue_checkpoint(body: str) -> Checkpoint | None:
    text = str(body or "")
    start = text.find(CHECKPOINT_BEGIN)
    if start < 0:
        return None
    end = text.find(CHECKPOINT_END, start + len(CHECKPOINT_BEGIN))
    if end < 0:
        raise CheckpointError("continuity checkpoint block is malformed")
    raw = text[start + len(CHECKPOINT_BEGIN):end].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckpointError("continuity checkpoint JSON is invalid") from exc
    return checkpoint_from_payload(payload)


def render_issue_checkpoint(body: str, checkpoint: Checkpoint) -> str:
    base = _strip_checkpoint_block(body)
    block = (
        f"{CHECKPOINT_BEGIN}\n"
        + json.dumps(
            checkpoint_to_payload(checkpoint),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + f"\n{CHECKPOINT_END}"
    )
    return f"{base}\n\n{block}\n" if base else f"{block}\n"


def is_scheduled_resume_eligible(body: str) -> bool:
    return SCHEDULED_RESUME_ELIGIBLE_MARKER in str(body or "")


def set_scheduled_resume_eligible(body: str, enabled: bool) -> str:
    text = str(body or "")
    if enabled:
        if is_scheduled_resume_eligible(text):
            return text
        base = text.rstrip()
        return (
            f"{base}\n\n{SCHEDULED_RESUME_ELIGIBLE_MARKER}\n"
            if base
            else f"{SCHEDULED_RESUME_ELIGIBLE_MARKER}\n"
        )
    cleaned = text.replace(SCHEDULED_RESUME_ELIGIBLE_MARKER, "")
    lines = [line.rstrip() for line in cleaned.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return ("\n".join(lines) + "\n") if lines else ""
