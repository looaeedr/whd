from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "WHD_POWER_OFF_GATE_SNAPSHOT_V1"
RESULT_SCHEMA = "WHD_POWER_OFF_GATE_V1"
VALIDATION_SCHEMA = "WHD_POWER_OFF_SAFE_VALIDATION_V1"

NONTERMINAL_CHECKPOINT_STATES = {
    "RUNNING",
    "WAITING_REMOTE",
    "RECOVERING",
    "BLOCKED",
}
PASS_GUARD_STATES = {"NONE", "CONSUMED"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _result(
    result: str,
    reason: str,
    *,
    request_id: str | None,
    revision: str | None,
    active_slots: list[str],
    blocking_slots: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "result": result,
        "reason": reason,
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "active_slots": active_slots,
    }
    if blocking_slots is not None:
        payload["blocking_slots"] = blocking_slots
    return payload


def _slot_decision(slot: dict[str, Any]) -> tuple[str, str]:
    dependency_error = _text(slot.get("dependency_error"))
    local_state = _text(slot.get("local_machine_state"))

    if dependency_error:
        return "ERROR", dependency_error
    if local_state == "LOCAL_MACHINE_UNAVAILABLE":
        return "ERROR", "LOCAL_MACHINE_UNREACHABLE"
    if bool(slot.get("local_mutation_in_progress")):
        return "NOT_SAFE", "LOCAL_MUTATION_IN_PROGRESS"
    if local_state == "LOCAL_DIRTY_CONFLICT":
        return "NOT_SAFE", "LOCAL_STATE_CONFLICT"
    if not bool(slot.get("local_worktree_clean", False)):
        return "NOT_SAFE", "LOCAL_DIRTY_NOT_DURABLE"
    if not bool(slot.get("local_head_matches_remote", False)):
        return "NOT_SAFE", "LOCAL_REMOTE_HEAD_MISMATCH"
    try:
        unpushed = int(slot.get("unpushed_commits", 0))
    except (TypeError, ValueError):
        return "ERROR", "SNAPSHOT_INVALID"
    if unpushed > 0:
        return "NOT_SAFE", "LOCAL_UNPUSHED"
    if not bool(slot.get("checkpoint_durable", False)):
        return "NOT_SAFE", "CHECKPOINT_MISSING"

    checkpoint_state = _text(slot.get("checkpoint_state"))
    if checkpoint_state in NONTERMINAL_CHECKPOINT_STATES and not _text(
        slot.get("checkpoint_next_action")
    ):
        return "NOT_SAFE", "CHECKPOINT_NEXT_ACTION_MISSING"
    if not bool(slot.get("checkpoint_head_matches_remote", False)):
        return "NOT_SAFE", "CHECKPOINT_HEAD_MISMATCH"

    guard = _text(slot.get("guard_transaction"))
    if guard == "PENDING":
        return "NOT_SAFE", "PENDING_GUARD_TRANSACTION"
    if guard == "MUTATION_DONE_RECONCILE_ONLY":
        return "NOT_SAFE", "GUARD_RECONCILIATION_REQUIRED"
    if guard == "AMBIGUOUS":
        return "NOT_SAFE", "GUARD_AMBIGUOUS"
    if guard not in PASS_GUARD_STATES:
        return "ERROR", "GUARD_TRANSACTION_UNKNOWN"

    if not bool(slot.get("handoff_verified", False)):
        return "NOT_SAFE", "HANDOFF_NOT_VERIFIED"
    if not bool(slot.get("claim_owner_matches_scheduler", False)):
        return "NOT_SAFE", "CLAIM_OWNER_NOT_SCHEDULER"

    enablement = _text(slot.get("scheduler_enablement"))
    if enablement == "UNVERIFIED":
        return "NOT_SAFE", "SCHEDULER_ENABLEMENT_UNVERIFIED"
    if enablement == "DISABLED":
        return "NOT_SAFE", "SCHEDULER_DISABLED"
    if enablement != "ENABLED":
        return "ERROR", "SCHEDULER_ENABLEMENT_INVALID"

    if not bool(slot.get("local_runtime_end_durable", False)):
        return "NOT_SAFE", "LOCAL_RUNTIME_END_MISSING"

    return "SAFE", "SAFE_TO_POWER_OFF"


def evaluate_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return _result(
            "ERROR",
            "SNAPSHOT_INVALID",
            request_id=None,
            revision=None,
            active_slots=[],
        )

    request_id = _text(snapshot.get("poweroff_request_id")) or None
    revision = _text(snapshot.get("evidence_revision")) or None
    if snapshot.get("schema") != SNAPSHOT_SCHEMA or request_id is None or revision is None:
        return _result(
            "ERROR",
            "SNAPSHOT_INVALID",
            request_id=request_id,
            revision=revision,
            active_slots=[],
        )

    slots = snapshot.get("slots")
    if not isinstance(slots, list):
        return _result(
            "ERROR",
            "SNAPSHOT_INVALID",
            request_id=request_id,
            revision=revision,
            active_slots=[],
        )

    local_slots: list[dict[str, Any]] = []
    active_slots: list[str] = []
    for raw in slots:
        if not isinstance(raw, dict):
            return _result(
                "ERROR",
                "SNAPSHOT_INVALID",
                request_id=request_id,
                revision=revision,
                active_slots=active_slots,
            )
        if not bool(raw.get("local_dependent")):
            continue
        slot_id = _text(raw.get("slot_id"))
        if not slot_id:
            return _result(
                "ERROR",
                "SNAPSHOT_INVALID",
                request_id=request_id,
                revision=revision,
                active_slots=active_slots,
            )
        local_slots.append(raw)
        active_slots.append(slot_id)

    if not local_slots:
        return _result(
            "SAFE",
            "NO_LOCAL_WHD_WORK",
            request_id=request_id,
            revision=revision,
            active_slots=[],
            blocking_slots=[],
        )

    errors: list[tuple[str, str]] = []
    blockers: list[tuple[str, str]] = []
    for slot in local_slots:
        slot_id = _text(slot.get("slot_id"))
        result, reason = _slot_decision(slot)
        if result == "ERROR":
            errors.append((slot_id, reason))
        elif result == "NOT_SAFE":
            blockers.append((slot_id, reason))

    if errors:
        slot_id, reason = errors[0]
        return _result(
            "ERROR",
            reason,
            request_id=request_id,
            revision=revision,
            active_slots=active_slots,
            blocking_slots=[slot for slot, _ in errors + blockers],
        )
    if blockers:
        slot_id, reason = blockers[0]
        return _result(
            "NOT_SAFE",
            reason,
            request_id=request_id,
            revision=revision,
            active_slots=active_slots,
            blocking_slots=[slot for slot, _ in blockers],
        )
    return _result(
        "SAFE",
        "SAFE_TO_POWER_OFF",
        request_id=request_id,
        revision=revision,
        active_slots=active_slots,
        blocking_slots=[],
    )


def validate_safe_receipt(
    receipt: Any,
    *,
    request_id: str,
    evidence_revision: str,
) -> dict[str, Any]:
    result = {
        "schema": VALIDATION_SCHEMA,
        "valid": False,
        "reason": "RECEIPT_INVALID",
    }
    if not isinstance(receipt, dict) or receipt.get("schema") != RESULT_SCHEMA:
        return result
    if receipt.get("result") != "SAFE":
        result["reason"] = "RECEIPT_NOT_SAFE"
        return result
    if _text(receipt.get("poweroff_request_id")) != request_id:
        result["reason"] = "REQUEST_ID_MISMATCH"
        return result
    if _text(receipt.get("evidence_revision")) != evidence_revision:
        result["reason"] = "EVIDENCE_REVISION_MISMATCH"
        return result
    result["valid"] = True
    result["reason"] = "VALID"
    return result


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        snapshot = _load_json(args.snapshot)
    except Exception:
        snapshot = None
    return _emit(evaluate_snapshot(snapshot))


def _cmd_validate_safe(args: argparse.Namespace) -> int:
    try:
        receipt = _load_json(args.receipt)
    except Exception:
        receipt = None
    return _emit(
        validate_safe_receipt(
            receipt,
            request_id=_text(args.request_id),
            evidence_revision=_text(args.evidence_revision),
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WHD workstation power-off safety evaluator")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--snapshot", required=True)
    evaluate.set_defaults(func=_cmd_evaluate)

    validate = sub.add_parser("validate-safe")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--request-id", required=True)
    validate.add_argument("--evidence-revision", required=True)
    validate.set_defaults(func=_cmd_validate_safe)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
