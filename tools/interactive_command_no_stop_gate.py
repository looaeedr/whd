"""Deterministic next-action gate for explicit WHD user instructions.

The caller must supply observed facts. This helper never grants permissions,
manufactures source evidence, or substitutes a status report for work.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence
import re

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

# One user instruction may combine several existing WHD command methods.
# Keep these in one ordered route, not separate competing work orders.
_COMMAND_SKILLS = {
    "/功能": ("新增功能",),
    "/debug": ("diagnosing-bugs", "tdd"),
    "/派工": ("派工", "issue-closure-gate"),
    "/接手": ("root-local-first", "執行開發任務"),
}
_COMMAND_PATTERN = re.compile(r"(?<![A-Za-z0-9_])/(?:功能|debug|派工|接手)(?![A-Za-z0-9_])", re.IGNORECASE)

def ordered_command_skills(task: str) -> tuple[str, ...]:
    """Explicit commands share one sequence; only /接手 selects RC skills."""
    present = {match.group(0).casefold() for match in _COMMAND_PATTERN.finditer(task)}
    ordered: list[str] = []
    for command in ("/功能", "/debug", "/派工", "/接手"):
        if command in present:
            for skill in _COMMAND_SKILLS[command]:
                if skill not in ordered:
                    ordered.append(skill)
    return tuple(ordered)

@dataclass(frozen=True)
class ActionExecution:
    """Observed result, not an assertion that an Issue or CI is complete."""
    completed_action: str | None
    attempted: tuple[str, ...]
    blocked: tuple[str, ...]

def execute_authorized_step(
    observation: WorkObservation,
    handlers: Mapping[str, Callable[[], object]],
) -> ActionExecution:
    """Actually invoke one authorized action; try independent authorized work after a refusal.

    No command string, skill or policy grants tool privileges. A denied operation
    cannot be retried through a different, unapproved transport. The caller must
    only register handlers for actions it is independently authorized to run.
    """
    attempted: list[str] = []
    blocked: list[str] = []
    for action in observation.authorized_actions:
        if action not in handlers:
            continue
        attempted.append(action)
        try:
            handlers[action]()
        except (PermissionError, OSError):
            blocked.append(action)
            continue
        return ActionExecution(action, tuple(attempted), tuple(blocked))
    return ActionExecution(None, tuple(attempted), tuple(blocked))
