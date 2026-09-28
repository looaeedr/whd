"""Scheduler-compatible push ingress for WHD Flow v2 control transactions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction import ControlTransactionConflict
from tools.control_transaction_production_executor import (
    ProductionExecutorError,
    _load_state,
    execute_one,
)

REQUEST_SCHEMA = "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1"
ALLOWED_KINDS = {
    "SEED","ACQUIRE","START_BRANCH","APPLY_COMMIT","START_QA","ACCEPT_QA",
    "BLOCK","MERGE","HANDOFF","FINALIZE","RECONCILE","YIELD",
}


def _load_request(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductionExecutorError("request must be a JSON object")
    if payload.get("schema") != REQUEST_SCHEMA:
        raise ProductionExecutorError("unexpected request schema")
    for key in ("request_id","issue","kind","lane_id","invocation_identity","expected_coord_head","expected_generation","effect"):
        if key not in payload:
            raise ProductionExecutorError(f"request missing {key}")
    if str(payload["kind"]) not in ALLOWED_KINDS:
        raise ProductionExecutorError("unsupported transaction kind")
    if not isinstance(payload["effect"], dict):
        raise ProductionExecutorError("effect must be an object")
    return payload


def execute_request(*, request: dict[str, object], repo: str, token: str, coord_branch: str) -> dict[str, object]:
    if str(request["kind"]) == "SEED":
        if int(request["issue"]) != 0:
            raise ProductionExecutorError("SEED request issue must be 0")
        return {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "APPLIED",
            "reason": "SEED_NOOP",
            "issue": 0,
            "generation_before": int(request["expected_generation"]),
            "generation_after": int(request["expected_generation"]),
            "transaction": {"status": "RECONCILED", "kind": "SEED"},
        }

    parent_sha, _, records = _load_state(repo, token, coord_branch)
    expected_parent = str(request["expected_coord_head"])
    if parent_sha != expected_parent:
        raise ControlTransactionConflict(
            f"coord head drift: expected {expected_parent}, observed {parent_sha}"
        )

    issue = int(request["issue"])
    record = records.get(issue)
    if record is None:
        raise ProductionExecutorError(f"native ExecutionRecord missing for issue {issue}")
    expected_generation = int(request["expected_generation"])
    if record.generation != expected_generation:
        raise ControlTransactionConflict(
            f"generation drift: expected {expected_generation}, observed {record.generation}"
        )

    return execute_one(
        repo=repo,
        token=token,
        coord_branch=coord_branch,
        issue=issue,
        kind=str(request["kind"]),
        lane_id=str(request["lane_id"]),
        invocation_identity=str(request["invocation_identity"]),
        supplied_effect=dict(request["effect"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coord-branch", default="coord/execution-v2")
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        raise SystemExit("GITHUB_REPOSITORY and GITHUB_TOKEN are required")

    try:
        request = _load_request(args.request_file)
        result = execute_request(request=request, repo=repo, token=token, coord_branch=args.coord_branch)
        result["request_id"] = request["request_id"]
        code = 0
    except ControlTransactionConflict as exc:
        result = {"schema":"WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2","result":"CONFLICT","reason":str(exc)}
        code = 3
    except Exception as exc:
        result = {"schema":"WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2","result":"FAILED","reason":str(exc)}
        code = 2

    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
