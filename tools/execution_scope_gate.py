"""Canonical execution-scope boundary for WHD.

This module does not own dispatch, continuity, claim, takeover, or closure state.
It only answers whether a continuation/recovery action is authorized by the
current execution mode.
"""

from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import Final


SCHEMA: Final[str] = "WHD_EXECUTION_SCOPE_GATE_V1"


class ExecutionScopeError(RuntimeError):
    """Raised when mode/action input is malformed or unsupported."""


class ExecutionMode(str, Enum):
    UPDATE_ONLY = "UPDATE_ONLY"
    EXECUTE_TICKET = "EXECUTE_TICKET"
    EXECUTE_CHAIN = "EXECUTE_CHAIN"
    SCHEDULER_LANE = "SCHEDULER_LANE"


class ExecutionAction(str, Enum):
    UPDATE_TARGET = "UPDATE_TARGET"
    VALIDATE_UPDATE = "VALIDATE_UPDATE"
    READBACK_UPDATE = "READBACK_UPDATE"
    SAME_SCOPE_NEXT_ACTION = "SAME_SCOPE_NEXT_ACTION"
    START_SUCCESSOR = "START_SUCCESSOR"
    DYNAMIC_DISCOVERY = "DYNAMIC_DISCOVERY"
    RECOVERY = "RECOVERY"
    TAKEOVER = "TAKEOVER"


def _mode(value: str | ExecutionMode) -> ExecutionMode:
    if isinstance(value, ExecutionMode):
        return value
    try:
        return ExecutionMode(str(value))
    except ValueError as exc:
        raise ExecutionScopeError(f"unknown execution mode: {value}") from exc


def _action(value: str | ExecutionAction) -> ExecutionAction:
    if isinstance(value, ExecutionAction):
        return value
    try:
        return ExecutionAction(str(value))
    except ValueError as exc:
        raise ExecutionScopeError(f"unknown execution action: {value}") from exc


def _decision(
    mode: ExecutionMode,
    action: ExecutionAction,
    allowed: bool,
    reason: str,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "mode": mode.value,
        "action": action.value,
        "allowed": allowed,
        "reason": reason,
    }


def evaluate_execution_scope(
    *,
    mode: str | ExecutionMode,
    action: str | ExecutionAction,
    same_scope: bool,
    fresh_recovery_evidence: bool,
    explicit_user_takeover: bool,
) -> dict[str, object]:
    """Return a deterministic allow/deny decision for one continuation action."""

    parsed_mode = _mode(mode)
    parsed_action = _action(action)

    if not isinstance(same_scope, bool):
        raise ExecutionScopeError("same_scope must be boolean")
    if not isinstance(fresh_recovery_evidence, bool):
        raise ExecutionScopeError("fresh_recovery_evidence must be boolean")
    if not isinstance(explicit_user_takeover, bool):
        raise ExecutionScopeError("explicit_user_takeover must be boolean")

    if parsed_action in {
        ExecutionAction.UPDATE_TARGET,
        ExecutionAction.VALIDATE_UPDATE,
        ExecutionAction.READBACK_UPDATE,
        ExecutionAction.SAME_SCOPE_NEXT_ACTION,
    }:
        if not same_scope:
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "ACTION_OUTSIDE_AUTHORIZED_SCOPE",
            )
        return _decision(parsed_mode, parsed_action, True, "AUTHORIZED_SAME_SCOPE")

    if parsed_action is ExecutionAction.START_SUCCESSOR:
        if parsed_mode in {
            ExecutionMode.EXECUTE_CHAIN,
            ExecutionMode.SCHEDULER_LANE,
        }:
            return _decision(parsed_mode, parsed_action, True, "SUCCESSOR_AUTHORIZED")
        return _decision(
            parsed_mode,
            parsed_action,
            False,
            "SUCCESSOR_NOT_AUTHORIZED_BY_EXECUTION_MODE",
        )

    if parsed_action is ExecutionAction.DYNAMIC_DISCOVERY:
        if parsed_mode is ExecutionMode.SCHEDULER_LANE:
            return _decision(
                parsed_mode,
                parsed_action,
                True,
                "SCHEDULER_DYNAMIC_DISCOVERY_AUTHORIZED",
            )
        return _decision(
            parsed_mode,
            parsed_action,
            False,
            "DYNAMIC_DISCOVERY_REQUIRES_SCHEDULER_LANE",
        )

    if parsed_action is ExecutionAction.RECOVERY:
        if not same_scope:
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "RECOVERY_OUTSIDE_AUTHORIZED_SCOPE",
            )
        if not fresh_recovery_evidence:
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "RECOVERY_REQUIRES_FRESH_MACHINE_EVIDENCE",
            )
        return _decision(
            parsed_mode,
            parsed_action,
            True,
            "RECOVERY_AUTHORIZED_BY_FRESH_MACHINE_EVIDENCE",
        )

    if parsed_action is ExecutionAction.TAKEOVER:
        if not same_scope:
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "TAKEOVER_OUTSIDE_AUTHORIZED_SCOPE",
            )
        if not fresh_recovery_evidence:
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "TAKEOVER_REQUIRES_FRESH_MACHINE_EVIDENCE",
            )
        if (
            parsed_mode is not ExecutionMode.SCHEDULER_LANE
            and not explicit_user_takeover
        ):
            return _decision(
                parsed_mode,
                parsed_action,
                False,
                "TAKEOVER_REQUIRES_SCHEDULER_OR_EXPLICIT_USER_DIRECTION",
            )
        return _decision(parsed_mode, parsed_action, True, "TAKEOVER_AUTHORIZED")

    raise ExecutionScopeError(f"unhandled execution action: {parsed_action.value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WHD execution-scope authorization gate"
    )
    parser.add_argument("--mode", required=True, choices=[m.value for m in ExecutionMode])
    parser.add_argument(
        "--action", required=True, choices=[a.value for a in ExecutionAction]
    )
    parser.add_argument(
        "--same-scope",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--fresh-recovery-evidence",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--explicit-user-takeover",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    decision = evaluate_execution_scope(
        mode=args.mode,
        action=args.action,
        same_scope=args.same_scope,
        fresh_recovery_evidence=args.fresh_recovery_evidence,
        explicit_user_takeover=args.explicit_user_takeover,
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0 if bool(decision["allowed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
