"""Canonical executable next-action vocabulary for WHD Flow v2."""

from __future__ import annotations

import re
from typing import Mapping

from tools.execution_record import ActionSpec, BLOCKER_KINDS

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
ACTION_TRANSACTION_KIND = {
    "ACQUIRE": "ACQUIRE",
    "START_BRANCH": "START_BRANCH",
    "APPLY_COMMIT": "APPLY_COMMIT",
    "START_QA": "START_QA",
    "ACCEPT_QA": "ACCEPT_QA",
    "MERGE": "MERGE",
    "HANDOFF": "HANDOFF",
    "FINALIZE": "FINALIZE",
    "YIELD": "YIELD",
    "RECONCILE": "RECONCILE",
}
OBSERVATION_ACTION_KINDS = frozenset({"POLL_QA", "WAIT_EXTERNAL"})

EXECUTABLE_ACTION_KINDS = frozenset(
    {
        "ACQUIRE",
        "START_BRANCH",
        "APPLY_COMMIT",
        "START_QA",
        "POLL_QA",
        "ACCEPT_QA",
        "MERGE",
        "HANDOFF",
        "FINALIZE",
        "YIELD",
        "RECONCILE",
        "WAIT_EXTERNAL",
    }
)


class ActionContractError(ValueError):
    """Raised when a next action is not machine-executable."""


def _text(args: Mapping[str, object], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ActionContractError(f"{key} must be nonblank")
    return value


def _sha(args: Mapping[str, object], key: str) -> str:
    value = _text(args, key)
    if not _SHA_RE.fullmatch(value):
        raise ActionContractError(f"{key} must be a 40-character git SHA")
    return value.lower()


def _positive_int(args: Mapping[str, object], key: str) -> int:
    value = args.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ActionContractError(f"{key} must be a positive integer")
    return value


def validate_execution_action(action: ActionSpec) -> bool:
    """Validate one finite, machine-executable next action.

    This validator intentionally does not interpret ``display`` prose.  All
    machine-relevant identity must be present in ``kind`` and ``args``.
    """
    if not isinstance(action, ActionSpec):
        raise ActionContractError("action must be an ActionSpec")
    if action.kind not in EXECUTABLE_ACTION_KINDS:
        raise ActionContractError(f"unknown/non-executable action kind {action.kind!r}")
    args = action.args
    if not isinstance(args, Mapping):
        raise ActionContractError("action args must be an object")

    if action.kind == "APPLY_COMMIT":
        _sha(args, "candidate_commit_sha")
    elif action.kind == "START_QA":
        _text(args, "workflow")
    elif action.kind in {"POLL_QA", "ACCEPT_QA"}:
        _positive_int(args, "run_id")
        _sha(args, "head_sha")
    elif action.kind == "MERGE":
        _positive_int(args, "pr_number")
    elif action.kind == "HANDOFF":
        _text(args, "to_owner_kind")
        _text(args, "to_owner_id")
    elif action.kind == "RECONCILE":
        _text(args, "reason")
    elif action.kind == "WAIT_EXTERNAL":
        blocker = _text(args, "blocker_kind")
        if blocker not in BLOCKER_KINDS:
            raise ActionContractError(
                f"blocker_kind must be one of {sorted(BLOCKER_KINDS)}"
            )
    # ACQUIRE / START_BRANCH / FINALIZE / YIELD use identity already bound in
    # the ExecutionRecord/transaction plan and need no extra action args.
    return True
