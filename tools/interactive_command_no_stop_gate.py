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
    next_issue_eligible: bool = False
    next_issue_authorized: bool = False
    no_eligible_issue_evidence: str = ""

def next_action(observation: WorkObservation) -> str:
    """Return an executable next action, never a predeclared stop procedure.

    User-supplied authorized actions are attempted in their given priority.
    Permission rejection to one operation never authorizes an unapproved route.
    """
    denied = set(observation.rejected_actions)
    for action in observation.authorized_actions:
        if action in {"START_NEXT_ISSUE", "CONTINUE_NEXT_ISSUE"} and not (
            observation.next_issue_checked and observation.next_issue_eligible
            and observation.next_issue_authorized
        ):
            continue
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
    if observation.localx_merged and not observation.next_issue_checked:
        return "DISCOVER_NEXT_ISSUE"
    if observation.localx_merged and not observation.issue_closed:
        return "CONTINUE_FINALIZATION"
    if observation.localx_merged and observation.issue_closed:
        if observation.next_issue_started and not observation.next_issue_eligible:
            return "RECONCILE_ONLY"
        if observation.next_issue_eligible:
            if not observation.next_issue_authorized:
                return "NEXT_ISSUE_AUTHORIZATION_REQUIRED"
            return ("CONTINUE_NEXT_ISSUE" if observation.next_issue_started
                    else "START_NEXT_ISSUE")
        if observation.no_eligible_issue_evidence:
            return "RELEASED"
        return "RECONCILE_ONLY"
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
# Publishing is routed by Registry, not the ordered execution-command route.
# Mask nearby explicit negations of slash commands and high-impact bare aliases
# (dispatch, deletion, publishing, and prompt healthcheck) for discovery only.
_NEGATABLE_COMMAND_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:/(?:功能|debug|派工|接手|推推|提示詞健檢|提視詞健檢|刪除|刪掉|清除|清掉|清空)"
    r"|推推|派工|接手|提示詞健檢|提視詞健檢"
    r"|刪除|刪掉|清除|清掉|清空|移除|清\s*(?:staging|active\s*0)"
    r"|delete|remove|prompt audit|prompt healthcheck)"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
# A negative instruction names a command to forbid it, not to activate it.
# This only filters an explicit nearby negation; it does not infer authority
# from affirmative commands or attempt to classify all natural-language intent.
_NEGATED_COMMAND_PREFIX = re.compile(
    r"(?:不要|不用|不必|無需|禁止|不准|不可以|不可|不能|不應|不想|不打算|不|未|別|不是|do\s+not|don't|not)"
    # Common Chinese adverbs and English action verbs can intervene.
    # Keep this bounded to adjacent words rather than scanning a whole sentence.
    r"(?:\s*(?:再|直接|去|透過|用|執行|啟動|使用|呼叫|跑|run|execute|use)){0,3}"
    r"\s*[`\"'「『(\[]?\s*$",
    re.IGNORECASE,
)


def without_negated_command_mentions(task: str) -> str:
    """Mask negated commands and prompt-healthcheck aliases in Skill discovery.

    Keep all other text and command positions unchanged. This is a Skill
    discovery safeguard, never a substitute for explicit user authorization.
    """
    result = list(task)
    for match in _NEGATABLE_COMMAND_PATTERN.finditer(task):
        prefix = task[max(0, match.start() - 40):match.start()]
        if _NEGATED_COMMAND_PREFIX.search(prefix):
            result[match.start():match.end()] = " " * len(match.group(0))
    return "".join(result)


def ordered_command_skills(task: str) -> tuple[str, ...]:
    """Explicit commands share one sequence; only affirmative /接手 selects RC skills."""
    routable = without_negated_command_mentions(task)
    present = {match.group(0).casefold() for match in _COMMAND_PATTERN.finditer(routable)}
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
    denied = set(observation.rejected_actions)
    for action in observation.authorized_actions:
        if action in denied or (
            action in {"START_NEXT_ISSUE", "CONTINUE_NEXT_ISSUE"}
            and not (observation.next_issue_checked
                     and observation.next_issue_eligible
                     and observation.next_issue_authorized)
        ):
            blocked.append(action)
            continue
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
