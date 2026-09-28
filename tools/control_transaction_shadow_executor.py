"""Read-only shadow executor for WHD Flow v2 transaction transport.

This CLI is intentionally incapable of repository mutation. It validates a
transport request against one native ExecutionRecord snapshot and emits a
machine-readable diagnostic suitable for an Actions shadow run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction_transport import (
    TransportError,
    transport_request_fingerprint,
    transport_request_from_payload,
    validate_transport_request,
)
from tools.execution_record import (
    ExecutionRecordError,
    execution_record_fingerprint,
    execution_record_from_payload,
)

SCHEMA = "WHD_CONTROL_TRANSACTION_SHADOW_RESULT_V1"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_shadow(request_payload: object, record_payload: object) -> dict[str, object]:
    try:
        request = transport_request_from_payload(request_payload)
        record = execution_record_from_payload(record_payload)
        validate_transport_request(request, record)
    except (TransportError, ExecutionRecordError, ValueError, TypeError) as exc:
        return {
            "schema": SCHEMA,
            "result": "SHADOW_CONFLICT",
            "reason": str(exc),
        }
    return {
        "schema": SCHEMA,
        "result": "SHADOW_VALIDATED",
        "reason": "EXACT_REQUEST_RECORD_IDENTITY_MATCH",
        "issue": record.issue,
        "transaction_id": request.transaction_id,
        "kind": request.kind,
        "request_fingerprint": transport_request_fingerprint(request),
        "record_fingerprint": execution_record_fingerprint(record),
        "generation": record.generation,
        "work_branch": record.work_branch,
        "head_sha": record.head_sha,
        "target_sha": record.target_sha,
        "candidate_effect_digest": request.candidate_effect_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only WHD v2 control transaction shadow validator")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_shadow(_load(args.request), _load(args.record))
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["result"] == "SHADOW_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
