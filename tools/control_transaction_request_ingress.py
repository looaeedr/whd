"""Scheduler-compatible push ingress for WHD Flow v2 control transactions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction import (
    ControlTransactionConflict,
    assert_mutation_writer_guard,
)
from tools.execution_entry_contract import validate_startup_evidence
from tools.root_local_first_gate import validate_git_unlock_receipt
from tools.control_transaction_request_builder import (
    INTENT_SCHEMA,
    REQUEST_SCHEMA,
    SESSION_REUSE_KINDS,
    SESSION_REUSE_SCHEMA,
    build_control_transaction_request_from_intent,
    execution_mode_for_lane,
)

# Backward-compatible schema marker; canonical owner remains the request builder.
# WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1
from tools.control_transaction_production_executor import (
    ProductionExecutorError,
    _load_state,
    _read_branch_head,
    execute_one,
)

ALLOWED_KINDS = {
    "SEED","ACQUIRE","START_BRANCH","APPLY_COMMIT","START_QA","ACCEPT_QA","CONSUME_QA","FAIL_QA",
    "BLOCK","MERGE","SYNC_TARGET","HANDOFF","FINALIZE","RECONCILE","RESERVE_PATHS","RELEASE_PATHS","YIELD",
}

REQUEST_BRANCH_LANES = {
    "coord/transaction-requests-a": "scheduler.6ab13fa557fc8191935c671214b865e2",
    "coord/transaction-requests-b": "scheduler.e58ea936e7d0b12bd0d475314709d6f1",
    "coord/transaction-requests-work0": "chatgpt.flowv2.work0",
    "coord/transaction-requests-work1": "chatgpt.flowv2.work1",
    "coord/transaction-requests-work2": "chatgpt.flowv2.work2",
    "coord/transaction-requests-work3": "chatgpt.flowv2.work3",
}


def _validate_request_branch(*, request: dict[str, object], request_branch: str) -> None:
    expected_lane = REQUEST_BRANCH_LANES.get(request_branch)
    if expected_lane is None:
        raise ProductionExecutorError(f"unsupported request branch: {request_branch}")
    observed_lane = str(request["lane_id"])
    if observed_lane != expected_lane:
        raise ProductionExecutorError(
            f"request lane mismatch: branch {request_branch} requires {expected_lane}, observed {observed_lane}"
        )


def _execution_mode_for_request(request: dict[str, object]) -> str:
    try:
        return execution_mode_for_lane(str(request.get("lane_id") or ""))
    except ValueError as exc:
        raise ProductionExecutorError(str(exc)) from exc




INTERACTIVE_GIT_WRITE_KINDS = {"START_BRANCH", "APPLY_COMMIT"}


def _validate_interactive_git_write_receipt(
    request: dict[str, object],
    *,
    execution_mode: str,
    record,
    repo: str,
    token: str,
) -> None:
    if execution_mode != "INTERACTIVE" or str(request.get("kind") or "") not in INTERACTIVE_GIT_WRITE_KINDS:
        return
    effect = request.get("effect")
    if not isinstance(effect, dict):
        raise ProductionExecutorError("effect must be an object")
    receipt = effect.get("root_local_first_git_write_receipt")
    if receipt is None:
        raise ProductionExecutorError("interactive Git write requires root-local-first Git write receipt")
    try:
        validated_receipt = validate_git_unlock_receipt(receipt)
    except ValueError as exc:
        raise ProductionExecutorError(f"root-local-first Git write receipt rejected: {exc}") from exc

    guard = effect.get("mutation_writer_guard")
    kind = str(request.get("kind") or "")
    invocation = str(request.get("invocation_identity") or "")
    assert_mutation_writer_guard(record, guard, kind=kind, invocation_identity=invocation)

    if int(validated_receipt.get("issue") or 0) != record.issue:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt issue drift")
    if int(validated_receipt.get("generation") or 0) != record.generation:
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt generation drift")
    if str(validated_receipt.get("record_fingerprint") or "") != str(guard.get("record_fingerprint") or ""):
        raise ControlTransactionConflict("STALE_PLAN_MUST_DIE Git receipt fingerprint drift")

    live_target = _read_branch_head(repo, token, record.target_branch)
    if live_target != record.target_sha or live_target != str(guard.get("expected_target_head") or ""):
        raise ControlTransactionConflict(
            f"STALE_PLAN_MUST_DIE live target drift: expected {record.target_sha}, observed {live_target}"
        )

    expected_post_head = str(effect.get("head_sha") or "").strip()
    if not expected_post_head:
        raise ProductionExecutorError(f"{kind} effect requires head_sha for writer guard")
    live_work = _read_branch_head(repo, token, record.work_branch)
    if live_work != expected_post_head:
        raise ControlTransactionConflict(
            "ONE_ISSUE_ONE_MUTATION_WRITER live work head changed before ingress: "
            f"expected {expected_post_head}, observed {live_work}"
        )



def _session_reuse_requested(request: dict[str, object]) -> bool:
    payload = request.get("session_reuse")
    if payload is None:
        return False
    if not isinstance(payload, dict):
        raise ProductionExecutorError("session_reuse must be an object")
    if payload.get("schema") != SESSION_REUSE_SCHEMA:
        raise ProductionExecutorError("unexpected session_reuse schema")
    if payload.get("mode") != "LIVE_LEASE_CONTINUATION":
        raise ProductionExecutorError("unsupported session_reuse mode")
    kind = str(request.get("kind") or "")
    if kind not in SESSION_REUSE_KINDS:
        raise ProductionExecutorError(f"transaction kind {kind} requires fresh admission")
    if "startup_evidence" in request:
        raise ProductionExecutorError("session reuse must not carry startup_evidence")
    return True


def _validate_live_session_reuse(record, *, request: dict[str, object]) -> None:
    invocation = str(request.get("invocation_identity") or "").strip()
    lane_id = str(request.get("lane_id") or "").strip()
    if record.state == "DONE":
        raise ProductionExecutorError("session reuse cannot mutate DONE record")
    if record.lease is None:
        raise ProductionExecutorError("session reuse requires active live lease")
    if record.lease.invocation_identity != invocation:
        raise ControlTransactionConflict("session reuse live lease belongs to a different invocation")
    try:
        expires = datetime.fromisoformat(record.lease.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductionExecutorError("session reuse lease expiry is invalid") from exc
    if expires.tzinfo is None or expires.utcoffset() is None:
        raise ProductionExecutorError("session reuse lease expiry must be timezone-aware")
    if expires <= datetime.now(timezone.utc):
        raise ControlTransactionConflict("session reuse lease expired; fresh ACQUIRE required")
    if record.owner_kind != "SCHEDULER" or record.owner_id != lane_id or record.lane_id != lane_id:
        raise ControlTransactionConflict("session reuse owner/lane identity mismatch")

def _load_request(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductionExecutorError("request must be a JSON object")
    schema = payload.get("schema")
    if schema not in {REQUEST_SCHEMA, INTENT_SCHEMA}:
        raise ProductionExecutorError("unexpected request schema")
    for key in ("request_id","issue","kind","lane_id","invocation_identity","expected_coord_head","expected_generation","effect"):
        if key not in payload:
            raise ProductionExecutorError(f"request missing {key}")
    kind = str(payload["kind"])
    if kind not in ALLOWED_KINDS:
        raise ProductionExecutorError("unsupported transaction kind")
    if not isinstance(payload["effect"], dict):
        raise ProductionExecutorError("effect must be an object")

    if schema == REQUEST_SCHEMA:
        reuse = _session_reuse_requested(payload)
        if kind != "SEED" and "startup_evidence" not in payload and not reuse:
            raise ProductionExecutorError("request missing startup_evidence or valid session_reuse")
        return payload

    if kind == "SEED":
        raise ProductionExecutorError("semantic intent does not support SEED")
    if "startup_evidence" in payload:
        raise ProductionExecutorError("semantic intent must not supply startup_evidence")
    reuse = payload.get("reuse_admission_session") is True
    if not reuse:
        for key in ("purpose", "work_root_gate_evidence"):
            if key not in payload:
                raise ProductionExecutorError(f"transaction intent missing {key}")
        if not isinstance(payload["work_root_gate_evidence"], dict):
            raise ProductionExecutorError("work_root_gate_evidence must be an object")
    return payload


def _materialize_request(request: dict[str, object], *, repo: str) -> dict[str, object]:
    if request.get("schema") == REQUEST_SCHEMA:
        return request
    try:
        return build_control_transaction_request_from_intent(request, repository=repo)
    except (TypeError, ValueError) as exc:
        raise ProductionExecutorError(f"transaction intent rejected: {exc}") from exc


def execute_request(*, request: dict[str, object], repo: str, token: str, coord_branch: str) -> dict[str, object]:
    request = _materialize_request(request, repo=repo)
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

    execution_mode = _execution_mode_for_request(request)
    reuse_session = _session_reuse_requested(request)
    if not reuse_session:
        try:
            validate_startup_evidence(
                request.get("startup_evidence"),
                invocation_identity=str(request["invocation_identity"]),
                execution_mode=execution_mode,
                repository=repo,
            )
        except ValueError as exc:
            raise ProductionExecutorError(f"startup hard gate rejected request: {exc}") from exc

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
    if reuse_session:
        _validate_live_session_reuse(record, request=request)

    _validate_interactive_git_write_receipt(
        request,
        execution_mode=execution_mode,
        record=record,
        repo=repo,
        token=token,
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
        request_branch = os.environ.get("GITHUB_REF_NAME", "").strip()
        if not request_branch:
            raise ProductionExecutorError("GITHUB_REF_NAME is required for push request branch binding")
        _validate_request_branch(request=request, request_branch=request_branch)
        result = execute_request(request=request, repo=repo, token=token, coord_branch=args.coord_branch)
        result["request_id"] = request["request_id"]
        code = 0
    except ControlTransactionConflict as exc:
        reason = str(exc)
        if reason.startswith("coord head drift"):
            conflict_class = "STALE_COORD_HEAD"
        elif reason.startswith("generation drift"):
            conflict_class = "STALE_GENERATION"
        elif "live lease" in reason:
            conflict_class = "LIVE_LEASE"
        elif reason.startswith("merge precheck required checks pending:"):
            conflict_class = "REQUIRED_CHECKS_PENDING"
        elif reason.startswith("merge precheck PR is not mergeable"):
            conflict_class = "PR_NOT_MERGEABLE"
        elif reason.startswith("SYNC_TARGET target drift:"):
            conflict_class = "TARGET_DRIFT"
        elif reason.startswith("SYNC_TARGET work head drift:"):
            conflict_class = "WORK_HEAD_DRIFT"
        else:
            conflict_class = "STALE_EXECUTION_RECORD"
        result = {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "CONFLICT",
            "reason": reason,
            "conflict_class": conflict_class,
            "retryable": True,
            "retry_action": (
                "POLL_REQUIRED_CHECKS"
                if conflict_class == "REQUIRED_CHECKS_PENDING"
                else "FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION"
            ),
            "semantic_effect_applied": False,
        }
        code = 3
    except Exception as exc:
        reason = str(exc)
        result = {
            "schema": "WHD_CONTROL_TRANSACTION_PRODUCTION_RESULT_V2",
            "result": "FAILED",
            "reason": reason,
            "error_class": (
                "STARTUP_EVIDENCE_INVALID"
                if reason.startswith("startup hard gate rejected request:")
                else "NON_RETRYABLE_REQUEST_FAILURE"
            ),
            "retryable": False,
        }
        code = 2

    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
