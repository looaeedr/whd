from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TO_TICKETS = ROOT / ".agents" / "skills" / "engineering" / "拆解任務工單" / "SKILL.md"


def _guard():
    spec = importlib.util.find_spec("tools.ticket_breakdown_guard")
    assert spec is not None, (
        "RED-STOP-14: machine ticket-breakdown validator is missing"
    )
    return importlib.import_module("tools.ticket_breakdown_guard")


def _ticket(*, closure_owner: str | None) -> str:
    lines = [
        "# T: example",
        "",
        "**What to build:** executable behavior.",
        "**Approved RED IDs:** RED-STOP-14",
        "**Requirement Authority:** #685",
        "**AI Library References:** exact/path.md",
        "**AI Library Writeback:** None — no durable knowledge change.",
        "**Blocked by:** None",
    ]
    if closure_owner is not None:
        lines.append(f"**Issue Closure owner:** {closure_owner}")
    lines += [
        "**Status:** ready-for-agent",
        "",
        "- [ ] executable acceptance",
    ]
    return "\n".join(lines) + "\n"


def test_red_stop_14_rejects_ticket_without_issue_closure_owner() -> None:
    guard = _guard()
    with pytest.raises(guard.TicketBreakdownError, match="Issue Closure owner"):
        guard.validate_ticket_body(_ticket(closure_owner=None))


def test_red_stop_14_rejects_ambiguous_issue_closure_owner() -> None:
    guard = _guard()
    with pytest.raises(guard.TicketBreakdownError, match="Issue Closure owner"):
        guard.validate_ticket_body(_ticket(closure_owner="everyone / T7"))


def test_red_stop_14_accepts_exact_github_issue_closure_owner() -> None:
    guard = _guard()
    result = guard.validate_ticket_body(_ticket(closure_owner="#693"))
    assert result.issue_closure_owner == "#693"


def test_red_stop_14_ticket_template_projects_issue_closure_owner() -> None:
    text = TO_TICKETS.read_text(encoding="utf-8")
    assert "**Issue Closure owner:**" in text, (
        "RED-STOP-14: generic Ticket Template does not project the mandatory closure owner"
    )
