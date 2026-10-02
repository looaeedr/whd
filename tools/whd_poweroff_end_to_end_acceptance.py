from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "WHD_HANDOFF_REQUEST_V1"
GATE_SCHEMA = "WHD_POWER_OFF_GATE_V1"
PROJECTION_SCHEMA = "WHD_HA_POWER_OFF_PROJECTION_V1"
ACTUATOR_SCHEMA = "WHD_HA_ACTUATOR_DECISION_V1"
RESUME_SCHEMA = "WHD_SCHEDULER_RESUME_EVIDENCE_V1"
ACCEPTANCE_SCHEMA = "WHD_END_TO_END_ACCEPTANCE_V1"
TRANSPORT = "NODE_RED_EXEC"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _output(
    *,
    result: str,
    reason: str,
    request_id: str | None,
    revision: str | None,
    actuator_allowed: bool,
    gate_receipt: Any,
    projection: Any,
    actuator_decision: Any,
    scheduler_resume: Any,
) -> dict[str, Any]:
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "result": result,
        "reason": reason,
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "actuator_allowed": actuator_allowed,
        "evidence": {
            "gate_receipt": gate_receipt,
            "projection": projection,
            "actuator_decision": actuator_decision,
            "scheduler_resume": scheduler_resume,
        },
        "scheduler_resume": scheduler_resume,
    }


def _reject(
    reason: str,
    *,
    request_id: str | None,
    revision: str | None,
    gate_receipt: Any,
    projection: Any,
    actuator_decision: Any,
    scheduler_resume: Any,
) -> dict[str, Any]:
    return _output(
        result="REJECTED",
        reason=reason,
        request_id=request_id,
        revision=revision,
        actuator_allowed=False,
        gate_receipt=gate_receipt,
        projection=projection,
        actuator_decision=actuator_decision,
        scheduler_resume=scheduler_resume,
    )


def _request_identity(request: Any) -> tuple[str | None, str | None]:
    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        return None, None
    return (
        _text(request.get("poweroff_request_id")) or None,
        _text(request.get("evidence_revision")) or None,
    )


def _resume_is_complete(resume: Any) -> bool:
    if not isinstance(resume, dict) or resume.get("schema") != RESUME_SCHEMA:
        return False
    required = (
        "pre_shutdown_local_head",
        "remote_head",
        "checkpoint",
        "claim_owner_pre",
        "claim_owner_post",
        "scheduler_invocation_identity",
        "exact_next_action",
    )
    if any(not _text(resume.get(key)) for key in required):
        return False
    handoff = resume.get("handoff_receipt")
    if not isinstance(handoff, dict):
        return False
    if handoff.get("schema") != "WHD_WORK_EXECUTOR_HANDOFF_V1":
        return False
    if _text(handoff.get("result")) != "GREEN":
        return False
    return True


def verify_end_to_end_acceptance(
    request: Any,
    gate_receipt: Any,
    projection: Any,
    actuator_decision: Any,
    scheduler_resume: Any,
) -> dict[str, Any]:
    """Verify R11 end-to-end evidence without owning any actuator action."""

    request_id, revision = _request_identity(request)
    if request_id is None or revision is None:
        return _reject(
            "REQUEST_INVALID",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    if not isinstance(gate_receipt, dict) or gate_receipt.get("schema") != GATE_SCHEMA:
        return _reject(
            "GATE_RECEIPT_INVALID",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(gate_receipt.get("poweroff_request_id")) != request_id:
        return _reject(
            "GATE_RECEIPT_REQUEST_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(gate_receipt.get("evidence_revision")) != revision:
        return _reject(
            "GATE_RECEIPT_REVISION_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    if (
        not isinstance(projection, dict)
        or projection.get("schema") != PROJECTION_SCHEMA
        or _text(projection.get("transport")) != TRANSPORT
    ):
        return _reject(
            "PROJECTION_INVALID",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(projection.get("poweroff_request_id")) != request_id:
        return _reject(
            "PROJECTION_REQUEST_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(projection.get("evidence_revision")) != revision:
        return _reject(
            "PROJECTION_REVISION_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    if (
        not isinstance(actuator_decision, dict)
        or actuator_decision.get("schema") != ACTUATOR_SCHEMA
        or _text(actuator_decision.get("authority")) != "HA_NODE_RED"
    ):
        return _reject(
            "ACTUATOR_DECISION_INVALID",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(actuator_decision.get("poweroff_request_id")) != request_id:
        return _reject(
            "ACTUATOR_REQUEST_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )
    if _text(actuator_decision.get("evidence_revision")) != revision:
        return _reject(
            "ACTUATOR_REVISION_MISMATCH",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    projection_result = _text(projection.get("result"))
    gate_result = _text(gate_receipt.get("result"))
    decision = _text(actuator_decision.get("decision"))
    invoked = actuator_decision.get("actuator_invoked")
    if not isinstance(invoked, bool) or decision not in {"ALLOW", "BLOCK"}:
        return _reject(
            "ACTUATOR_DECISION_INVALID",
            request_id=request_id,
            revision=revision,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    if projection_result == "SAFE":
        if gate_result != "SAFE":
            return _reject(
                "GATE_PROJECTION_MISMATCH",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        if decision != "ALLOW" or not invoked:
            return _reject(
                "SAFE_REQUIRES_ACTUATOR_ALLOW",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        if not _resume_is_complete(scheduler_resume):
            return _reject(
                "SCHEDULER_RESUME_EVIDENCE_INVALID",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        if _text(scheduler_resume.get("poweroff_request_id")) != request_id:
            return _reject(
                "SCHEDULER_RESUME_REQUEST_MISMATCH",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        handoff = scheduler_resume.get("handoff_receipt")
        if _text(handoff.get("poweroff_request_id")) != request_id:
            return _reject(
                "HANDOFF_RECEIPT_REQUEST_MISMATCH",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        return _output(
            result="ACCEPTED",
            reason="END_TO_END_ACCEPTANCE",
            request_id=request_id,
            revision=revision,
            actuator_allowed=True,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    if projection_result in {"NOT_SAFE", "ERROR"}:
        if gate_result != projection_result:
            return _reject(
                "GATE_PROJECTION_MISMATCH",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        if decision != "BLOCK" or invoked:
            return _reject(
                "ACTUATOR_MUST_NOT_RUN",
                request_id=request_id,
                revision=revision,
                gate_receipt=gate_receipt,
                projection=projection,
                actuator_decision=actuator_decision,
                scheduler_resume=scheduler_resume,
            )
        return _output(
            result="ACCEPTED",
            reason="NEGATIVE_PATH_ACCEPTED",
            request_id=request_id,
            revision=revision,
            actuator_allowed=False,
            gate_receipt=gate_receipt,
            projection=projection,
            actuator_decision=actuator_decision,
            scheduler_resume=scheduler_resume,
        )

    return _reject(
        "PROJECTION_RESULT_INVALID",
        request_id=request_id,
        revision=revision,
        gate_receipt=gate_receipt,
        projection=projection,
        actuator_decision=actuator_decision,
        scheduler_resume=scheduler_resume,
    )


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        request = _load_json(args.request)
    except Exception:
        request = None
    try:
        gate_receipt = _load_json(args.gate_receipt)
    except Exception:
        gate_receipt = None
    try:
        projection = _load_json(args.projection)
    except Exception:
        projection = None
    try:
        actuator_decision = _load_json(args.actuator_decision)
    except Exception:
        actuator_decision = None
    try:
        scheduler_resume = _load_json(args.scheduler_resume)
    except Exception:
        scheduler_resume = None
    return _emit(
        verify_end_to_end_acceptance(
            request,
            gate_receipt,
            projection,
            actuator_decision,
            scheduler_resume,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "R11 evidence-only verifier for WHD -> HA/Node-RED integration. "
            "This verifier does not own an actuator action."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--request", required=True)
    verify.add_argument("--gate-receipt", required=True)
    verify.add_argument("--projection", required=True)
    verify.add_argument("--actuator-decision", required=True)
    verify.add_argument("--scheduler-resume", required=True)
    verify.set_defaults(func=_cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
