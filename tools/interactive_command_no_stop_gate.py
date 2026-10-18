"""Deterministic next-action gate for explicit WHD user instructions.

The caller must supply observed facts. This helper never grants permissions,
manufactures source evidence, or substitutes a status report for work.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True)
class WorkObservation:
    authorized_actions: Sequence[str] = ()
    ci_status: str = ""
    ci_conclusion: str = ""
    pr_open: bool = False
    localx_merged: bool = False
    issue_closed: bool = False
    next_issue_started: bool = False
    operation_rejected: bool = False
    rejected_actions: Sequence[str] = ()
    next_issue_checked: bool = False

def next_action(observation: WorkObservation) -> str:
    """Return an executable next action, never a predeclared stop procedure.

    User-supplied authorized actions are attempted in their given priority.
    Permission rejection to one operation never authorizes an unapproved route.
    """
    denied = set(observation.rejected_actions)
    for action in observation.authorized_actions:
        if action not in denied:
            return action
    if observation.ci_status in {"requested", "queued", "waiting", "pending", "in_progress"}:
        return "CONTINUE_POLL"
    if observation.ci_status == "completed" and observation.ci_conclusion in {
        "failure", "cancelled", "timed_out", "action_required",
        "startup_failure", "stale",
    }:
        return "REPAIR_AND_RETEST"
    if observation.ci_status == "completed" and observation.ci_conclusion != "success":
        return "RECONCILE_ONLY"
    if observation.ci_status == "completed" and not observation.localx_merged:
        return "LOCALX_INTEGRATION_PENDING" if observation.pr_open else "RECONCILE_ONLY"
    if (observation.localx_merged and not observation.next_issue_checked
            and not observation.next_issue_started):
        return "DISCOVER_NEXT_ISSUE"
    if observation.localx_merged and not observation.issue_closed:
        return "CONTINUE_FINALIZATION"
    if observation.localx_merged and observation.issue_closed:
        return "CONTINUE_NEXT_ISSUE" if observation.next_issue_started else "DISCOVER_NEXT_ISSUE"
    return "READ_CURRENT_SOURCE_AND_CONTINUE"
