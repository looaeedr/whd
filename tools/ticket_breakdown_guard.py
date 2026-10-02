"""Machine validation for WHD approved ticket-breakdown closure ownership."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


class TicketBreakdownError(ValueError):
    """Raised when a proposed/published ticket has ambiguous closure ownership."""


@dataclass(frozen=True)
class TicketBreakdownContract:
    issue_closure_owner: str


_OWNER_FIELD_RE = re.compile(
    r"(?m)^\*\*Issue Closure owner:\*\*\s*(?P<owner>.*?)\s*$"
)
_OWNER_ID_RE = re.compile(r"^(?:T[1-9]\d*|#[1-9]\d*)$")


def validate_ticket_body(body: str) -> TicketBreakdownContract:
    """Validate the single canonical closure-owner field in one ticket body."""

    if not isinstance(body, str) or not body.strip():
        raise TicketBreakdownError("ticket body must be nonblank")

    matches = list(_OWNER_FIELD_RE.finditer(body))
    if len(matches) != 1:
        raise TicketBreakdownError(
            "Issue Closure owner must appear exactly once in every ticket"
        )

    owner = matches[0].group("owner").strip()
    if not _OWNER_ID_RE.fullmatch(owner):
        raise TicketBreakdownError(
            "Issue Closure owner must be one exact T<N> draft owner or #<N> "
            "published GitHub Issue; ambiguous/shared owners are forbidden"
        )
    return TicketBreakdownContract(issue_closure_owner=owner)


def validate_breakdown_closure_ownership(
    tickets: Mapping[str, str],
) -> dict[str, TicketBreakdownContract]:
    """Validate closure-owner topology for a proposed multi-ticket breakdown."""

    if not isinstance(tickets, Mapping) or not tickets:
        raise TicketBreakdownError("breakdown must contain at least one ticket")

    normalized: dict[str, str] = {}
    for raw_id, body in tickets.items():
        ticket_id = str(raw_id).strip()
        if not re.fullmatch(r"T[1-9]\d*", ticket_id):
            raise TicketBreakdownError(
                f"invalid draft ticket identity {raw_id!r}; expected T<N>"
            )
        if ticket_id in normalized:
            raise TicketBreakdownError(f"duplicate ticket identity {ticket_id}")
        normalized[ticket_id] = body

    validated = {
        ticket_id: validate_ticket_body(body)
        for ticket_id, body in normalized.items()
    }
    for ticket_id, contract in validated.items():
        owner = contract.issue_closure_owner
        if owner.startswith("T") and owner not in normalized:
            raise TicketBreakdownError(
                f"Issue Closure owner {owner} referenced by {ticket_id} "
                "does not exist in the proposed breakdown"
            )
    return validated
