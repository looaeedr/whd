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
from typing import Mapping, Sequence

from tools.execution_entry_contract import DEFAULT_REPOSITORY, build_startup_evidence
from tools.control_transaction_step_executor import REQUEST_KIND as STEP_SEQUENCE_KIND, normalize_step_sequence

REQUEST_SCHEMA = "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1"

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
    purpose: str,
    work_root_gate_evidence: Mapping[str, object],
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
    execution_mode = execution_mode_for_lane(lane_id)
    startup = build_startup_evidence(
        purpose=purpose,
        invocation_identity=invocation_identity,
        work_root_gate_evidence=work_root_gate_evidence,
        execution_mode=execution_mode,
        repository=repository,
        issued_at=issued_at,
    )
    return {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "issue": int(issue),
        "kind": kind,
        "lane_id": lane_id,
        "invocation_identity": invocation_identity,
        "startup_evidence": startup,
        "expected_coord_head": expected_coord_head,
        "expected_generation": int(expected_generation),
        "effect": dict(effect),
    }



def build_control_step_sequence_request(
    *,
    request_id: str,
    issue: int,
    lane_id: str,
    invocation_identity: str,
    expected_coord_head: str,
    expected_generation: int,
    steps: Sequence[Mapping[str, object]],
    purpose: str,
    work_root_gate_evidence: Mapping[str, object],
    repository: str = DEFAULT_REPOSITORY,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    first, second = normalize_step_sequence(steps)
    base = build_control_transaction_request(
        request_id=request_id,
        issue=issue,
        kind=STEP_SEQUENCE_KIND,
        lane_id=lane_id,
        invocation_identity=invocation_identity,
        expected_coord_head=expected_coord_head,
        expected_generation=expected_generation,
        effect={},
        purpose=purpose,
        work_root_gate_evidence=work_root_gate_evidence,
        repository=repository,
        issued_at=issued_at,
    )
    base["steps"] = [first, second]
    return base

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
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--work-root-evidence", type=Path, required=True)
    parser.add_argument("--effect", type=Path)
    parser.add_argument("--steps", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--issued-at")
    args = parser.parse_args()

    issued_at = None
    if args.issued_at:
        issued_at = datetime.fromisoformat(args.issued_at.replace("Z", "+00:00"))

    if args.kind == STEP_SEQUENCE_KIND:
        if args.steps is None:
            raise SystemExit("--steps is required for STEP_SEQUENCE")
        raw_steps = json.loads(args.steps.read_text(encoding="utf-8"))
        if not isinstance(raw_steps, list):
            raise SystemExit("--steps must contain a JSON array")
        request = build_control_step_sequence_request(
            request_id=args.request_id,
            issue=args.issue,
            lane_id=args.lane_id,
            invocation_identity=args.invocation_identity,
            expected_coord_head=args.expected_coord_head,
            expected_generation=args.expected_generation,
            steps=raw_steps,
            purpose=args.purpose,
            work_root_gate_evidence=_load_json(args.work_root_evidence),
            repository=args.repository,
            issued_at=issued_at,
        )
    else:
        if args.effect is None:
            raise SystemExit("--effect is required for a single transaction")
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
            work_root_gate_evidence=_load_json(args.work_root_evidence),
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
