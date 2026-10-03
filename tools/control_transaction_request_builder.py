"""Canonical builder for WHD Flow v2 push transaction requests.

Callers must not hand-compose startup declaration, execution mode, or work-root
binding. This module centralizes that request envelope and delegates startup
evidence construction to tools.execution_entry_contract.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Mapping

from tools.execution_entry_contract import (
    DEFAULT_REPOSITORY,
    build_startup_evidence,
    build_startup_transition,
    validate_phase6_preflight_evidence,
)

REQUEST_SCHEMA = "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1"
INTENT_SCHEMA = "WHD_CONTROL_TRANSACTION_PUSH_INTENT_V1"
SESSION_REUSE_SCHEMA = "WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1"
SESSION_REUSE_KINDS = frozenset({
    "START_BRANCH", "APPLY_COMMIT", "START_QA", "ACCEPT_QA", "CONSUME_QA",
    "FAIL_QA", "BLOCK", "MERGE", "FINALIZE", "YIELD", "RELEASE_PATHS",
})

INTENT_REQUIRED_FIELDS = (
    "request_id",
    "issue",
    "kind",
    "lane_id",
    "invocation_identity",
    "expected_coord_head",
    "expected_generation",
    "effect",
    "purpose",
    "work_root_gate_evidence",
    "preflight_evidence",
)

LANE_EXECUTION_MODES = {
    "scheduler.6ab13fa557fc8191935c671214b865e2": "SCHEDULER_LANE",
    "scheduler.e58ea936e7d0b12bd0d475314709d6f1": "SCHEDULER_LANE",
    "chatgpt.flowv2.work0": "INTERACTIVE",
    "chatgpt.flowv2.work1": "INTERACTIVE",
    "chatgpt.flowv2.work2": "INTERACTIVE",
    "chatgpt.flowv2.work3": "INTERACTIVE",
}


def execution_mode_for_lane(lane_id: str) -> str:
    lane = str(lane_id or "").strip()
    try:
        return LANE_EXECUTION_MODES[lane]
    except KeyError as exc:
        raise ValueError(f"unsupported request lane for startup gate: {lane}") from exc


def build_control_transaction_request(
    *,
    request_id: str,
    issue: int,
    kind: str,
    lane_id: str,
    invocation_identity: str,
    expected_coord_head: str,
    expected_generation: int,
    effect: Mapping[str, object],
    purpose: str | None = None,
    work_root_gate_evidence: Mapping[str, object] | None = None,
    preflight_evidence: Mapping[str, object] | None = None,
    reuse_admission_session: bool = False,
    repository: str = DEFAULT_REPOSITORY,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    request_id = str(request_id or "").strip()
    kind = str(kind or "").strip()
    lane_id = str(lane_id or "").strip()
    invocation_identity = str(invocation_identity or "").strip()
    expected_coord_head = str(expected_coord_head or "").strip()
    purpose = str(purpose or "").strip()
    if not request_id:
        raise ValueError("request_id must be nonblank")
    if isinstance(issue, bool) or int(issue) <= 0:
        raise ValueError("issue must be a positive integer")
    if not kind:
        raise ValueError("kind must be nonblank")
    if not invocation_identity:
        raise ValueError("invocation_identity must be nonblank")
    if not expected_coord_head:
        raise ValueError("expected_coord_head must be nonblank")
    if isinstance(expected_generation, bool) or int(expected_generation) <= 0:
        raise ValueError("expected_generation must be a positive integer")
    if not isinstance(effect, Mapping):
        raise ValueError("effect must be a mapping")
    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "issue": int(issue),
        "kind": kind,
        "lane_id": lane_id,
        "invocation_identity": invocation_identity,
        "expected_coord_head": expected_coord_head,
        "expected_generation": int(expected_generation),
        "effect": dict(effect),
    }
    if reuse_admission_session:
        if preflight_evidence is not None:
            raise ValueError("session reuse must not carry preflight_evidence")
        if kind not in SESSION_REUSE_KINDS:
            raise ValueError(f"transaction kind {kind} requires fresh admission")
        request["session_reuse"] = {
            "schema": SESSION_REUSE_SCHEMA,
            "mode": "LIVE_LEASE_CONTINUATION",
        }
        return request

    if not purpose:
        raise ValueError("purpose is required for fresh admission")
    if not isinstance(work_root_gate_evidence, Mapping):
        raise ValueError("work_root_gate_evidence is required for fresh admission")
    if not isinstance(preflight_evidence, Mapping):
        raise ValueError("preflight_evidence is required for fresh admission")
    execution_mode = execution_mode_for_lane(lane_id)
    request["startup_evidence"] = build_startup_evidence(
        purpose=purpose,
        invocation_identity=invocation_identity,
        work_root_gate_evidence=work_root_gate_evidence,
        execution_mode=execution_mode,
        repository=repository,
        issued_at=issued_at,
    )
    request["preflight_evidence"] = validate_phase6_preflight_evidence(
        preflight_evidence,
        issue=int(issue),
        invocation_identity=invocation_identity,
        now=issued_at,
    )
    request["startup_transition"] = build_startup_transition(
        startup_evidence=request["startup_evidence"],
        preflight_evidence=request["preflight_evidence"],
        invocation_identity=invocation_identity,
        issue=int(issue),
        execution_mode=execution_mode,
        repository=repository,
        now=issued_at,
    )
    return request


def build_control_transaction_request_from_intent(
    intent: Mapping[str, object],
    *,
    repository: str = DEFAULT_REPOSITORY,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    """Materialize a semantic request intent through the canonical startup builder.

    GitHub-only callers submit only transaction semantics plus already-resolved
    work-root evidence.  The trusted ingress owns declaration/execution-mode
    construction, so callers cannot hand-compose startup_evidence.
    """
    if not isinstance(intent, Mapping):
        raise ValueError("intent must be a mapping")
    if intent.get("schema") != INTENT_SCHEMA:
        raise ValueError("unexpected transaction intent schema")
    if "startup_evidence" in intent or "startup_transition" in intent:
        raise ValueError("transaction intent must not supply startup_evidence/startup_transition")
    reuse = intent.get("reuse_admission_session") is True
    required = tuple(field for field in INTENT_REQUIRED_FIELDS if not (reuse and field in {"purpose", "work_root_gate_evidence", "preflight_evidence"}))
    missing = [field for field in required if field not in intent]
    if missing:
        raise ValueError(f"transaction intent missing {missing[0]}")
    root_evidence = intent.get("work_root_gate_evidence")
    if not reuse and not isinstance(root_evidence, Mapping):
        raise ValueError("work_root_gate_evidence must be a mapping")
    return build_control_transaction_request(
        request_id=str(intent["request_id"]),
        issue=int(intent["issue"]),
        kind=str(intent["kind"]),
        lane_id=str(intent["lane_id"]),
        invocation_identity=str(intent["invocation_identity"]),
        expected_coord_head=str(intent["expected_coord_head"]),
        expected_generation=int(intent["expected_generation"]),
        effect=intent["effect"],
        purpose=str(intent.get("purpose") or ""),
        work_root_gate_evidence=root_evidence if isinstance(root_evidence, Mapping) else None,
        preflight_evidence=intent.get("preflight_evidence") if isinstance(intent.get("preflight_evidence"), Mapping) else None,
        reuse_admission_session=reuse,
        repository=repository,
        issued_at=issued_at,
    )


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--invocation-identity", required=True)
    parser.add_argument("--expected-coord-head", required=True)
    parser.add_argument("--expected-generation", type=int, required=True)
    parser.add_argument("--purpose")
    parser.add_argument("--work-root-evidence", type=Path)
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--reuse-admission-session", action="store_true")
    parser.add_argument("--effect", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--issued-at")
    args = parser.parse_args()

    issued_at = None
    if args.issued_at:
        issued_at = datetime.fromisoformat(args.issued_at.replace("Z", "+00:00"))

    request = build_control_transaction_request(
        request_id=args.request_id,
        issue=args.issue,
        kind=args.kind,
        lane_id=args.lane_id,
        invocation_identity=args.invocation_identity,
        expected_coord_head=args.expected_coord_head,
        expected_generation=args.expected_generation,
        effect=_load_json(args.effect),
        purpose=args.purpose,
        work_root_gate_evidence=_load_json(args.work_root_evidence) if args.work_root_evidence else None,
        preflight_evidence=_load_json(args.preflight_evidence) if args.preflight_evidence else None,
        reuse_admission_session=args.reuse_admission_session,
        repository=args.repository,
        issued_at=issued_at,
    )
    args.output.write_text(
        json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
