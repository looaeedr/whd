"""T3 Xvfb extension for the authoritative T2 shard execution system.

Shard ownership stays in ``tools.test_shard_execution``.  This module adds only
the Xvfb-specific process/display and terminal-classification boundary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

from tools.phase6_release_test_runner import managed_xvfb, run_process_group
from tools.test_shard_execution import (
    ROOT,
    XVFB_LANE,
    ExecutionError,
    ExecutionPlan,
    _require_manifest,
    _validate_budget,
    _write_json,
    load_execution_config,
    select_shard_nodes,
)


XVFB_SHARD_COUNT = 4
XVFB_ACCEPTED_CLASSIFICATIONS = {"GREEN", "INHERITED_BASELINE_RED"}


def _matrix_entry(shard_id: str, item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ExecutionError(f"MANIFEST_SHARD_INVALID: {XVFB_LANE}:{shard_id}")
    nodes = item.get("nodes")
    count = item.get("count")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise ExecutionError(f"MANIFEST_NODES_INVALID: {XVFB_LANE}:{shard_id}")
    if count != len(nodes):
        raise ExecutionError(
            f"MANIFEST_COUNT_MISMATCH: {XVFB_LANE}:{shard_id} count={count!r} nodes={len(nodes)}"
        )
    return {"lane": XVFB_LANE, "shard_id": shard_id, "node_count": len(nodes)}


def build_xvfb_matrix(
    shard_manifest: dict[str, object],
    *,
    concurrency_budget: int,
) -> ExecutionPlan:
    """Build exactly four logical Xvfb jobs from accepted manifest ownership."""
    budget = _validate_budget(concurrency_budget)
    shards = _require_manifest(shard_manifest)
    lane_shards = shards.get(XVFB_LANE)
    if not isinstance(lane_shards, dict):
        raise ExecutionError(f"MANIFEST_LANE_INVALID: {XVFB_LANE}")
    if len(lane_shards) != XVFB_SHARD_COUNT:
        raise ExecutionError(
            f"XVFB_SHARD_COUNT_MISMATCH: expected={XVFB_SHARD_COUNT} actual={len(lane_shards)}"
        )
    matrix = [
        _matrix_entry(shard_id, lane_shards[shard_id])
        for shard_id in sorted(str(name) for name in lane_shards)
    ]
    return ExecutionPlan(matrix=matrix, max_parallel=min(budget, len(matrix)))


def validate_gui_pytest_args(args: Sequence[str]) -> None:
    """Fail closed on xdist process-count options for real GUI tests."""
    for raw in args:
        arg = str(raw)
        if (
            arg == "-n"
            or re.fullmatch(r"-n(?:auto|\d+)", arg) is not None
            or arg == "--numprocesses"
            or arg.startswith("--numprocesses=")
        ):
            raise ExecutionError(f"XVFB_PARALLEL_PYTEST_FORBIDDEN: {arg}")


def classify_xvfb_failed_nodes(
    *,
    child_rc: int,
    failed_nodes: Iterable[str],
    expected_failed_nodes: Iterable[str],
) -> tuple[int, str]:
    """Preserve accepted T0 failed-node semantics after a terminal child rc."""
    actual = {str(node) for node in failed_nodes}
    expected = {str(node) for node in expected_failed_nodes}
    if child_rc == 0 and not actual:
        return 0, "GREEN"
    if child_rc != 0 and actual and actual == expected:
        return 0, "INHERITED_BASELINE_RED"
    return 1, "UNCLASSIFIED_RED"


def resolve_xvfb_terminal_state(
    *,
    child_rc: int | None,
    timed_out: bool,
    classifier_started: bool,
    classifier_rc: int | None,
    classifier_classification: str | None,
) -> str:
    """Keep terminal rc failures distinct from true no-terminal timeout paths."""
    if timed_out:
        if child_rc is None:
            return "HANG_TIMEOUT"
        return "TIMEOUT_TERMINAL_AMBIGUOUS"
    if child_rc is None:
        return "CHILD_TERMINAL_MISSING"
    if not classifier_started:
        return "CLASSIFICATION_NOT_RUN"
    if classifier_rc is None or classifier_classification is None:
        return "CLASSIFIER_INFRA_FAILURE"
    if classifier_classification in XVFB_ACCEPTED_CLASSIFICATIONS:
        return classifier_classification if classifier_rc == 0 else "CLASSIFIER_INFRA_FAILURE"
    if classifier_classification == "UNCLASSIFIED_RED":
        return classifier_classification if classifier_rc != 0 else "CLASSIFIER_INFRA_FAILURE"
    return "CLASSIFIER_INFRA_FAILURE"


def _failed_nodes_from_output(output: str) -> list[str]:
    failed: set[str] = set()
    for line in str(output).splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                failed.add(parts[1])
    return sorted(failed)


def execute_xvfb_shard(
    *,
    nodes: Iterable[str],
    shard_id: str,
    expected_failed_nodes: Iterable[str],
    result_json: Path,
    log_path: Path,
    basetemp: Path,
    timeout_seconds: float,
    pytest_args: Sequence[str] = ("-q", "-ra", "--tb=short", "--durations=30"),
) -> dict[str, object]:
    """Run one exact shard serially in one owned Xvfb display/process."""
    assigned = sorted(str(node) for node in nodes)
    expected = sorted(str(node) for node in expected_failed_nodes)
    if not assigned:
        raise ExecutionError(f"XVFB_EMPTY_SHARD: {shard_id}")
    if timeout_seconds <= 0:
        raise ExecutionError(f"XVFB_TIMEOUT_INVALID: {timeout_seconds!r}")
    validate_gui_pytest_args(pytest_args)
    if any(node not in assigned for node in expected):
        raise ExecutionError(f"XVFB_EXPECTED_FAILURE_OUTSIDE_SHARD: {shard_id}")

    result_json.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *[str(arg) for arg in pytest_args],
        f"--basetemp={basetemp}",
        *assigned,
    ]

    child_started_epoch = time.time()
    with managed_xvfb() as session:
        env = os.environ.copy()
        env["DISPLAY"] = session.display
        result = run_process_group(
            command,
            timeout_seconds=float(timeout_seconds),
            cwd=ROOT,
            env=env,
        )
        xvfb_display = session.display
        xvfb_pid = session.pid
    child_ended_epoch = time.time()
    log_path.write_text(result.stdout, encoding="utf-8")
    failed_nodes = _failed_nodes_from_output(result.stdout)

    if result.timed_out:
        child_rc: int | None = None
        classifier_started = False
        classifier_rc: int | None = None
        classifier_classification: str | None = None
    else:
        child_rc = int(result.returncode)
        classifier_started = True
        classifier_rc, classifier_classification = classify_xvfb_failed_nodes(
            child_rc=child_rc,
            failed_nodes=failed_nodes,
            expected_failed_nodes=expected,
        )

    classification = resolve_xvfb_terminal_state(
        child_rc=child_rc,
        timed_out=bool(result.timed_out),
        classifier_started=classifier_started,
        classifier_rc=classifier_rc,
        classifier_classification=classifier_classification,
    )
    payload: dict[str, object] = {
        "lane": XVFB_LANE,
        "shard_id": shard_id,
        "assigned_nodes": assigned,
        "assigned_count": len(assigned),
        "expected_failed_nodes": expected,
        "failed_nodes": failed_nodes,
        "xvfb_display": xvfb_display,
        "xvfb_pid": xvfb_pid,
        "child_started_epoch": child_started_epoch,
        "child_ended_epoch": child_ended_epoch,
        "child_rc": child_rc,
        "timed_out": bool(result.timed_out),
        "execution_seconds": float(result.elapsed_seconds),
        "classifier_started": classifier_started,
        "classifier_rc": classifier_rc,
        "classifier_classification": classifier_classification,
        "classification": classification,
        "log_path": str(log_path),
        "result_json": str(result_json),
    }
    _write_json(result_json, payload)
    return payload


def _load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionError("MANIFEST_INVALID: root is not an object")
    _require_manifest(payload)
    return payload


def _load_expected_failures(path: Path, *, shard_id: str) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list) and all(isinstance(node, str) for node in payload):
        return sorted(payload)
    if isinstance(payload, dict):
        nodes = payload.get(shard_id, [])
        if isinstance(nodes, list) and all(isinstance(node, str) for node in nodes):
            return sorted(nodes)
    raise ExecutionError(f"XVFB_EXPECTED_FAILURES_INVALID: {path}")


def _cmd_matrix(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.manifest)
    budget = load_execution_config(args.execution_config)
    plan = build_xvfb_matrix(manifest, concurrency_budget=budget)
    matrix_json = json.dumps({"include": plan.matrix}, ensure_ascii=False, separators=(",", ":"))
    print(matrix_json)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"matrix={matrix_json}\n")
            stream.write(f"max_parallel={plan.max_parallel}\n")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.manifest)
    nodes = select_shard_nodes(manifest, XVFB_LANE, args.shard, allow_xvfb=True)
    expected = _load_expected_failures(args.expected_failures, shard_id=args.shard)
    payload = execute_xvfb_shard(
        nodes=nodes,
        shard_id=args.shard,
        expected_failed_nodes=expected,
        result_json=args.result_json,
        log_path=args.log,
        basetemp=args.basetemp,
        timeout_seconds=args.timeout_seconds,
    )
    return 0 if payload["classification"] in XVFB_ACCEPTED_CLASSIFICATIONS else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute exact WHD Xvfb manifest shards")
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--manifest", type=Path, required=True)
    matrix.add_argument(
        "--execution-config",
        type=Path,
        default=ROOT / "config" / "ci_test_execution.json",
    )
    matrix.add_argument("--github-output", type=Path)
    matrix.set_defaults(handler=_cmd_matrix)

    run = subparsers.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--shard", required=True)
    run.add_argument("--expected-failures", type=Path, required=True)
    run.add_argument("--result-json", type=Path, required=True)
    run.add_argument("--log", type=Path, required=True)
    run.add_argument("--basetemp", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=float, default=900.0)
    run.set_defaults(handler=_cmd_run)

    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (ExecutionError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
