from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from workstation_poweroff_gate import validate_safe_receipt

REQUEST_SCHEMA = "WHD_HANDOFF_REQUEST_V1"
PROJECTION_SCHEMA = "WHD_HA_POWER_OFF_PROJECTION_V1"
TRANSPORT = "NODE_RED_EXEC"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _projection(
    *,
    request_id: str | None,
    revision: str | None,
    result: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": PROJECTION_SCHEMA,
        "transport": TRANSPORT,
        "poweroff_request_id": request_id,
        "evidence_revision": revision,
        "result": result,
        "reason": reason,
    }


def _request_identity(request: Any) -> tuple[str | None, str | None]:
    if not isinstance(request, dict):
        return None, None
    return (
        _text(request.get("poweroff_request_id")) or None,
        _text(request.get("evidence_revision")) or None,
    )


def project_gate_receipt(
    request: Any,
    gate_receipt: Any,
    *,
    now_epoch_seconds: float,
) -> dict[str, Any]:
    request_id, revision = _request_identity(request)

    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason="REQUEST_INVALID",
        )
    if request_id is None or revision is None:
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason="REQUEST_INVALID",
        )

    requested_at = request.get("requested_at_epoch_seconds")
    timeout_seconds = request.get("timeout_seconds")
    if (
        isinstance(requested_at, bool)
        or not isinstance(requested_at, (int, float))
        or isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason="REQUEST_INVALID",
        )

    if now_epoch_seconds > float(requested_at) + float(timeout_seconds):
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason="TIMEOUT",
        )

    if not isinstance(gate_receipt, dict):
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason="RECEIPT_INVALID",
        )

    receipt_result = _text(gate_receipt.get("result"))
    receipt_reason = _text(gate_receipt.get("reason")) or "RECEIPT_INVALID"

    if receipt_result == "SAFE":
        validation = validate_safe_receipt(
            gate_receipt,
            request_id=request_id,
            evidence_revision=revision,
        )
        if not bool(validation.get("valid")):
            return _projection(
                request_id=request_id,
                revision=revision,
                result="ERROR",
                reason=_text(validation.get("reason")) or "RECEIPT_INVALID",
            )
        return _projection(
            request_id=request_id,
            revision=revision,
            result="SAFE",
            reason=receipt_reason,
        )

    if receipt_result == "NOT_SAFE":
        return _projection(
            request_id=request_id,
            revision=revision,
            result="NOT_SAFE",
            reason=receipt_reason,
        )

    if receipt_result == "ERROR":
        return _projection(
            request_id=request_id,
            revision=revision,
            result="ERROR",
            reason=receipt_reason,
        )

    return _projection(
        request_id=request_id,
        revision=revision,
        result="ERROR",
        reason="RECEIPT_INVALID",
    )


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def _cmd_project(args: argparse.Namespace) -> int:
    try:
        request = _load_json(args.request)
    except Exception:
        request = None
    try:
        receipt = _load_json(args.gate_receipt)
    except Exception:
        receipt = None
    try:
        now_epoch_seconds = float(args.now_epoch_seconds)
    except (TypeError, ValueError):
        now_epoch_seconds = float("inf")
    return _emit(
        project_gate_receipt(
            request,
            receipt,
            now_epoch_seconds=now_epoch_seconds,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Thin Home Assistant/Node-RED transport projection for WHD power-off "
            "gate receipts. This tool never performs a power-off action."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    project = sub.add_parser("project")
    project.add_argument("--request", required=True)
    project.add_argument("--gate-receipt", required=True)
    project.add_argument("--now-epoch-seconds", required=True)
    project.set_defaults(func=_cmd_project)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
