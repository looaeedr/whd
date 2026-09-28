"""Terminal-only WHD Flow v2 control-transaction executor seam.

This module composes the pure transaction semantics with the V2 transport
contract.  A request binds a deterministic candidate intent.  A trusted wrapper
performs the external side effect, fresh-reads the result, then passes that
readback as ``effect``.  This seam emits only terminal APPLIED/CONFLICT/FAILED
receipts; it has no GREEN/PENDING authorization state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction import (
    ControlTransactionConflict,
    ControlTransactionError,
    ControlTransactionPlan,
    ControlTransactionReplay,
    execute_transaction,
)
from tools.control_transaction_transport import (
    ControlTransactionTransportRequest,
    TransportError,
    build_terminal_receipt,
    terminal_receipt_to_payload,
    transport_request_from_payload,
    validate_transport_request,
)
from tools.execution_record import (
    ExecutionRecord,
    ExecutionRecordError,
    execution_record_from_payload,
    execution_record_to_payload,
)

SCHEMA = "WHD_CONTROL_TRANSACTION_EXECUTOR_RESULT_V2"


def canonical_json_digest(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TransportError("payload must be canonical-JSON serializable") from exc
    return hashlib.sha256(raw).hexdigest()


def _plan_from_request(request: ControlTransactionTransportRequest) -> ControlTransactionPlan:
    return ControlTransactionPlan(
        transaction_id=request.transaction_id,
        kind=request.kind,
        issue=request.issue,
        expected_generation=request.expected_generation,
        expected_fingerprint=request.expected_record_fingerprint,
        expected_work_branch=request.expected_work_branch,
        expected_head_sha=request.expected_head_sha,
        expected_target_sha=request.expected_target_sha,
        invocation_identity=request.invocation_identity,
    )


def _terminal_result(
    *,
    request: ControlTransactionTransportRequest,
    record: ExecutionRecord,
    result: str,
    reason: str,
    readback_digest: str,
    post_record: ExecutionRecord | None = None,
) -> dict[str, object]:
    observed = post_record or record
    receipt = build_terminal_receipt(
        request=request,
        result=result,
        reason=reason,
        observed_work_branch=observed.work_branch,
        observed_head_sha=observed.head_sha,
        observed_target_sha=observed.target_sha,
        readback_digest=readback_digest,
        post_record=post_record if result == "APPLIED" else None,
    )
    return {
        "schema": SCHEMA,
        "result": result,
        "receipt": terminal_receipt_to_payload(receipt),
        "post_record": execution_record_to_payload(post_record) if post_record else None,
    }


def execute_terminal_request(
    *,
    request_payload: object,
    record_payload: object,
    candidate_payload: object,
    effect_payload: object,
) -> dict[str, object]:
    """Validate, terminalize, and reconcile one exact transaction request."""
    request = transport_request_from_payload(request_payload)
    record = execution_record_from_payload(record_payload)
    readback_digest = canonical_json_digest(effect_payload)

    candidate_digest = canonical_json_digest(candidate_payload)
    if candidate_digest != request.candidate_effect_digest:
        return _terminal_result(
            request=request,
            record=record,
            result="FAILED",
            reason=(
                "candidate intent digest mismatch: "
                f"expected={request.candidate_effect_digest} observed={candidate_digest}"
            ),
            readback_digest=readback_digest,
        )

    try:
        validate_transport_request(request, record)
    except TransportError as exc:
        return _terminal_result(
            request=request,
            record=record,
            result="CONFLICT",
            reason=str(exc),
            readback_digest=readback_digest,
        )

    if not isinstance(effect_payload, Mapping):
        return _terminal_result(
            request=request,
            record=record,
            result="FAILED",
            reason="fresh readback effect must be an object",
            readback_digest=readback_digest,
        )

    try:
        post = execute_transaction(
            record,
            _plan_from_request(request),
            effect=effect_payload,
        )
    except (ControlTransactionConflict, ControlTransactionReplay) as exc:
        return _terminal_result(
            request=request,
            record=record,
            result="CONFLICT",
            reason=str(exc),
            readback_digest=readback_digest,
        )
    except (ControlTransactionError, ExecutionRecordError, ValueError, TypeError) as exc:
        return _terminal_result(
            request=request,
            record=record,
            result="FAILED",
            reason=str(exc),
            readback_digest=readback_digest,
        )

    return _terminal_result(
        request=request,
        record=record,
        result="APPLIED",
        reason="SIDE_EFFECT_READBACK_AND_RECORD_RECONCILIATION_COMPLETE",
        readback_digest=readback_digest,
        post_record=post,
    )


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal-only WHD v2 transaction executor seam")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--effect", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = execute_terminal_request(
            request_payload=_load(args.request),
            record_payload=_load(args.record),
            candidate_payload=_load(args.candidate),
            effect_payload=_load(args.effect),
        )
    except (TransportError, ExecutionRecordError, json.JSONDecodeError, OSError) as exc:
        result = {"schema": SCHEMA, "result": "FAILED", "reason": str(exc), "receipt": None, "post_record": None}
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result.get("result") == "APPLIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
