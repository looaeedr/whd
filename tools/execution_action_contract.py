"""Canonical executable next-action vocabulary for WHD Flow v2."""


from __future__ import annotations


import re
from typing import Mapping


from tools.execution_record import ActionSpec, BLOCKER_KINDS


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
CONTROL_ONLY_COMPLETION_MODE = "CONTROL_ONLY"
ACTION_TRANSACTION_KIND = {
    "ACQUIRE": "ACQUIRE",
    "START_BRANCH": "START_BRANCH",
    "APPLY_COMMIT": "APPLY_COMMIT",
    "START_QA": "START_QA",
    "ACCEPT_QA": "ACCEPT_QA",
    "MERGE": "MERGE",
    "SYNC_TARGET": "SYNC_TARGET",
    "HANDOFF": "HANDOFF",
    "FINALIZE": "FINALIZE",
    "YIELD": "YIELD",
    "RECONCILE": "RECONCILE",
    "RESERVE_PATHS": "RESERVE_PATHS",
    "RELEASE_PATHS": "RELEASE_PATHS",
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
        "SYNC_TARGET",
        "HANDOFF",
        "FINALIZE",
        "YIELD",
        "RECONCILE",
        "RESERVE_PATHS",
        "RELEASE_PATHS",
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


    if action.kind == "ACQUIRE":
        bound = args.get("post_acquire")
        if bound is not None:
            if not isinstance(bound, Mapping):
                raise ActionContractError("ACQUIRE post_acquire must be an action object")
            bound_args = bound.get("args", {})
            if not isinstance(bound_args, Mapping):
                raise ActionContractError("ACQUIRE post_acquire.args must be an object")
            nested = ActionSpec(
                kind=_text(bound, "kind"),
                args={str(k): v for k, v in bound_args.items()},
                display=str(bound.get("display") or "").strip(),
            )
            if nested.kind == "ACQUIRE":
                raise ActionContractError("ACQUIRE post_acquire cannot recursively ACQUIRE")
            validate_execution_action(nested)
    elif action.kind == "APPLY_COMMIT":
        _sha(args, "candidate_commit_sha")
    elif action.kind == "START_QA":
        _text(args, "workflow")
    elif action.kind in {"POLL_QA", "ACCEPT_QA"}:
        _positive_int(args, "run_id")
        _sha(args, "head_sha")
    elif action.kind == "MERGE":
        _positive_int(args, "pr_number")
        if "head_sha" in args:
            _sha(args, "head_sha")
        if "target_branch" in args:
            _text(args, "target_branch")
        if "expected_target_sha" in args:
            _sha(args, "expected_target_sha")
        if "revalidation_workflow" in args:
            _text(args, "revalidation_workflow")
    elif action.kind == "SYNC_TARGET":
        _sha(args, "target_sha")
        _positive_int(args, "pr_number")
        _text(args, "target_branch")
        _text(args, "qa_workflow")
    elif action.kind == "HANDOFF":
        _text(args, "to_owner_kind")
        _text(args, "to_owner_id")
    elif action.kind == "RECONCILE":
        _text(args, "reason")
    elif action.kind == "RESERVE_PATHS":
        _text(args, "target_branch")
        _sha(args, "base_sha")
        write_paths = args.get("write_paths", [])
        delete_paths = args.get("delete_paths", [])
        if not isinstance(write_paths, list) or not isinstance(delete_paths, list):
            raise ActionContractError("RESERVE_PATHS write_paths/delete_paths must be arrays")
        if not write_paths and not delete_paths:
            raise ActionContractError("RESERVE_PATHS requires at least one path")
        if any(not str(path).strip() for path in [*write_paths, *delete_paths]):
            raise ActionContractError("RESERVE_PATHS paths must be nonblank")
    elif action.kind == "RELEASE_PATHS":
        _text(args, "reason")
    elif action.kind == "FINALIZE":
        completion_mode = args.get("completion_mode")
        if completion_mode is not None and str(completion_mode).strip().upper() != CONTROL_ONLY_COMPLETION_MODE:
            raise ActionContractError(
                f"FINALIZE completion_mode must be {CONTROL_ONLY_COMPLETION_MODE} when supplied"
            )
    elif action.kind == "WAIT_EXTERNAL":
        blocker = _text(args, "blocker_kind")
        if blocker not in BLOCKER_KINDS:
            raise ActionContractError(
                f"blocker_kind must be one of {sorted(BLOCKER_KINDS)}"
            )
    # START_BRANCH / YIELD use identity already bound in the
    # ExecutionRecord/transaction plan and need no extra action args.
    return True