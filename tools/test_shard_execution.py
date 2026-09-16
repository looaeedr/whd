"""Exact non-Xvfb shard planning and execution for WHD CI T2.

Ownership comes exclusively from the accepted T1 shard manifest.  This module
never re-derives lane membership from pytest markers inside shard jobs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SHARD_MANIFEST_SCHEMA = "WHD_TEST_SHARD_MANIFEST_V1"
EXECUTION_CONFIG_SCHEMA = "WHD_TEST_EXECUTION_CONFIG_V1"
XVFB_LANE = "xvfb_ui"


class ExecutionError(ValueError):
    """Fail-closed execution/planning error with a stable reason token."""


@dataclass(frozen=True)
class ExecutionPlan:
    matrix: list[dict[str, object]]
    max_parallel: int


def _require_manifest(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("schema") != SHARD_MANIFEST_SCHEMA:
        raise ExecutionError(f"MANIFEST_SCHEMA_MISMATCH: {payload.get('schema')!r}")
    shards = payload.get("shards")
    if not isinstance(shards, dict):
        raise ExecutionError("MANIFEST_SHARDS_INVALID: shards is not an object")
    return shards


def _validate_budget(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExecutionError(f"INVALID_CONCURRENCY_BUDGET: {value!r}")
    return value


def load_execution_config(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != EXECUTION_CONFIG_SCHEMA:
        raise ExecutionError(f"EXECUTION_CONFIG_SCHEMA_MISMATCH: {payload.get('schema')!r}")
    return _validate_budget(payload.get("ci_concurrency_budget"))


def build_non_xvfb_matrix(
    shard_manifest: dict[str, object],
    *,
    concurrency_budget: int,
) -> ExecutionPlan:
    """Build compact lane/shard matrix while keeping node lists in the manifest."""
    budget = _validate_budget(concurrency_budget)
    shards = _require_manifest(shard_manifest)
    matrix: list[dict[str, object]] = []
    for lane in sorted(str(name) for name in shards):
        if lane == XVFB_LANE:
            continue
        lane_shards = shards[lane]
        if not isinstance(lane_shards, dict):
            raise ExecutionError(f"MANIFEST_LANE_INVALID: {lane}")
        for shard_id in sorted(str(name) for name in lane_shards):
            item = lane_shards[shard_id]
            if not isinstance(item, dict):
                raise ExecutionError(f"MANIFEST_SHARD_INVALID: {lane}:{shard_id}")
            nodes = item.get("nodes")
            count = item.get("count")
            if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
                raise ExecutionError(f"MANIFEST_NODES_INVALID: {lane}:{shard_id}")
            if count != len(nodes):
                raise ExecutionError(
                    f"MANIFEST_COUNT_MISMATCH: {lane}:{shard_id} count={count!r} nodes={len(nodes)}"
                )
            matrix.append({"lane": lane, "shard_id": shard_id, "node_count": len(nodes)})
    return ExecutionPlan(matrix=matrix, max_parallel=budget)


def select_shard_nodes(
    shard_manifest: dict[str, object],
    lane: str,
    shard_id: str,
    *,
    allow_xvfb: bool = False,
) -> list[str]:
    shards = _require_manifest(shard_manifest)
    if lane == XVFB_LANE and not allow_xvfb:
        raise ExecutionError("XVFB_FORBIDDEN_IN_T2")
    if lane not in shards:
        raise ExecutionError(f"UNKNOWN_LANE: {lane}")
    lane_shards = shards[lane]
    if not isinstance(lane_shards, dict):
        raise ExecutionError(f"MANIFEST_LANE_INVALID: {lane}")
    if shard_id not in lane_shards:
        raise ExecutionError(f"UNKNOWN_SHARD: {lane}:{shard_id}")
    item = lane_shards[shard_id]
    if not isinstance(item, dict):
        raise ExecutionError(f"MANIFEST_SHARD_INVALID: {lane}:{shard_id}")
    nodes = item.get("nodes")
    count = item.get("count")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise ExecutionError(f"MANIFEST_NODES_INVALID: {lane}:{shard_id}")
    if count != len(nodes):
        raise ExecutionError(f"MANIFEST_COUNT_MISMATCH: {lane}:{shard_id}")
    return sorted(nodes)


def select_lane_nodes(
    shard_manifest: dict[str, object],
    lane: str,
    *,
    allow_xvfb: bool = False,
) -> list[str]:
    shards = _require_manifest(shard_manifest)
    if lane == XVFB_LANE and not allow_xvfb:
        raise ExecutionError("XVFB_FORBIDDEN_IN_T2")
    if lane not in shards:
        raise ExecutionError(f"UNKNOWN_LANE: {lane}")
    lane_shards = shards[lane]
    if not isinstance(lane_shards, dict):
        raise ExecutionError(f"MANIFEST_LANE_INVALID: {lane}")
    nodes: list[str] = []
    for shard_id in sorted(str(name) for name in lane_shards):
        nodes.extend(select_shard_nodes(shard_manifest, lane, shard_id, allow_xvfb=allow_xvfb))
    if len(nodes) != len(set(nodes)):
        raise ExecutionError(f"LANE_DUPLICATE_NODE: {lane}")
    return sorted(nodes)


def non_xvfb_lanes(shard_manifest: dict[str, object]) -> list[str]:
    shards = _require_manifest(shard_manifest)
    return sorted(str(lane) for lane in shards if str(lane) != XVFB_LANE)


def expected_non_xvfb_nodes(shard_manifest: dict[str, object]) -> dict[str, list[str]]:
    return {lane: select_lane_nodes(shard_manifest, lane) for lane in non_xvfb_lanes(shard_manifest)}


def _testsuite_elements(root: ET.Element) -> list[ET.Element]:
    if root.tag == "testsuite":
        return [root]
    suites = list(root.findall("./testsuite"))
    if not suites:
        raise ExecutionError(f"JUNIT_SCHEMA_INVALID: root={root.tag!r}")
    return suites


def parse_junit_counts(path: Path, *, assigned_count: int) -> dict[str, object]:
    if not path.exists():
        raise ExecutionError(f"JUNIT_MISSING: {path}")
    root = ET.parse(path).getroot()
    tests = failures = errors = skipped = 0
    duration = 0.0
    for suite in _testsuite_elements(root):
        tests += int(suite.attrib.get("tests", "0"))
        failures += int(suite.attrib.get("failures", "0"))
        errors += int(suite.attrib.get("errors", "0"))
        skipped += int(suite.attrib.get("skipped", "0"))
        duration += float(suite.attrib.get("time", "0") or 0)
    if tests != assigned_count:
        raise ExecutionError(
            f"JUNIT_COUNT_MISMATCH: assigned={assigned_count} junit_tests={tests}"
        )
    passed = tests - failures - errors - skipped
    if passed < 0:
        raise ExecutionError("JUNIT_COUNTS_INVALID")
    return {
        "tests": tests,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "junit_time_seconds": duration,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionError("MANIFEST_INVALID: root is not an object")
    _require_manifest(payload)
    return payload


def run_exact_nodes(
    *,
    nodes: Iterable[str],
    lane: str,
    shard_id: str,
    result_json: Path,
    junit_xml: Path,
    log_path: Path,
    basetemp: Path,
) -> int:
    assigned = sorted(str(node) for node in nodes)
    result_json.parent.mkdir(parents=True, exist_ok=True)
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    basetemp.parent.mkdir(parents=True, exist_ok=True)

    started_epoch = time.time()
    started_monotonic = time.monotonic()
    if not assigned:
        log_path.write_text("EMPTY_SHARD_NOOP\n", encoding="utf-8")
        payload = {
            "lane": lane,
            "shard_id": shard_id,
            "assigned_nodes": [],
            "assigned_count": 0,
            "tests": 0,
            "passed": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "child_rc": 0,
            "execution_seconds": 0.0,
            "started_epoch": started_epoch,
            "ended_epoch": time.time(),
        }
        _write_json(result_json, payload)
        return 0

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--junitxml={junit_xml}",
        f"--basetemp={basetemp}",
        *assigned,
    ]
    with log_path.open("w", encoding="utf-8") as stream:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    ended_epoch = time.time()
    execution_seconds = time.monotonic() - started_monotonic
    payload: dict[str, object] = {
        "lane": lane,
        "shard_id": shard_id,
        "assigned_nodes": assigned,
        "assigned_count": len(assigned),
        "child_rc": proc.returncode,
        "execution_seconds": execution_seconds,
        "started_epoch": started_epoch,
        "ended_epoch": ended_epoch,
    }
    try:
        payload.update(parse_junit_counts(junit_xml, assigned_count=len(assigned)))
    except ExecutionError as exc:
        payload.update(
            {
                "tests": -1,
                "passed": -1,
                "failures": -1,
                "errors": -1,
                "skipped": -1,
                "harness_error": str(exc),
            }
        )
        _write_json(result_json, payload)
        return proc.returncode or 2
    _write_json(result_json, payload)
    return proc.returncode


def _cmd_matrix(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.manifest)
    budget = load_execution_config(args.execution_config)
    plan = build_non_xvfb_matrix(manifest, concurrency_budget=budget)
    payload = {"include": plan.matrix}
    matrix_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print(matrix_json)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"matrix={matrix_json}\n")
            stream.write(f"max_parallel={plan.max_parallel}\n")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.manifest)
    if args.all_shards:
        nodes = select_lane_nodes(manifest, args.lane)
        shard_id = "serial"
    else:
        if not args.shard:
            raise ExecutionError("SHARD_REQUIRED")
        nodes = select_shard_nodes(manifest, args.lane, args.shard)
        shard_id = args.shard
    return run_exact_nodes(
        nodes=nodes,
        lane=args.lane,
        shard_id=shard_id,
        result_json=args.result_json,
        junit_xml=args.junit_xml,
        log_path=args.log,
        basetemp=args.basetemp,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute exact WHD non-Xvfb manifest shards")
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
    run.add_argument("--lane", required=True)
    run.add_argument("--shard")
    run.add_argument("--all-shards", action="store_true")
    run.add_argument("--result-json", type=Path, required=True)
    run.add_argument("--junit-xml", type=Path, required=True)
    run.add_argument("--log", type=Path, required=True)
    run.add_argument("--basetemp", type=Path, required=True)
    run.set_defaults(handler=_cmd_run)

    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (ExecutionError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
