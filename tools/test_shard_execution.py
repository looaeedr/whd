"""Exact non-Xvfb shard planning and execution for WHD CI T2/T5.

Ownership comes exclusively from the accepted T1 shard manifest.  This module
never re-derives lane membership from pytest markers inside shard jobs.  T5 may
optionally add conservative in-job xdist only for exact shards carrying accepted
repeat-proof provenance in the execution config.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def _load_execution_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionError("EXECUTION_CONFIG_INVALID: root is not an object")
    if payload.get("schema") != EXECUTION_CONFIG_SCHEMA:
        raise ExecutionError(f"EXECUTION_CONFIG_SCHEMA_MISMATCH: {payload.get('schema')!r}")
    return payload


def load_execution_config(path: Path) -> int:
    """Return the historical job-level concurrency budget unchanged."""
    payload = _load_execution_payload(path)
    return _validate_budget(payload.get("ci_concurrency_budget"))


def load_xdist_policy(path: Path) -> dict[str, object]:
    """Load an exact-shard xdist allowlist with mandatory proof provenance.

    Absence of an ``xdist`` section is backward-compatible and means serial
    execution for every shard.  There is deliberately no lane-wide/default
    parallel mode and ``xvfb_ui`` can never appear in this allowlist.
    """
    payload = _load_execution_payload(path)
    raw = payload.get("xdist")
    if raw is None:
        return {
            "default_workers": 1,
            "distribution": "load",
            "safe_shards": {},
        }
    if not isinstance(raw, dict):
        raise ExecutionError("XDIST_POLICY_INVALID: xdist is not an object")

    default_workers = raw.get("default_workers", 1)
    if default_workers != 1 or isinstance(default_workers, bool):
        raise ExecutionError(f"XDIST_DEFAULT_MUST_BE_SERIAL: {default_workers!r}")
    distribution = raw.get("distribution", "load")
    if distribution != "load":
        raise ExecutionError(f"XDIST_DISTRIBUTION_UNSUPPORTED: {distribution!r}")
    safe_shards = raw.get("safe_shards", {})
    if not isinstance(safe_shards, dict):
        raise ExecutionError("XDIST_SAFE_SHARDS_INVALID: safe_shards is not an object")

    normalized: dict[str, dict[str, object]] = {}
    for raw_key, raw_entry in sorted(safe_shards.items()):
        key = str(raw_key)
        if ":" not in key:
            raise ExecutionError(f"XDIST_SAFE_SHARD_KEY_INVALID: {key!r}")
        lane, shard_id = key.split(":", 1)
        if not lane or not shard_id:
            raise ExecutionError(f"XDIST_SAFE_SHARD_KEY_INVALID: {key!r}")
        if lane == XVFB_LANE:
            raise ExecutionError(f"XDIST_XVFB_FORBIDDEN: {key}")
        if not isinstance(raw_entry, dict):
            raise ExecutionError(f"XDIST_SAFE_SHARD_INVALID: {key}")

        workers = raw_entry.get("workers")
        if isinstance(workers, bool) or not isinstance(workers, int) or workers != 2:
            raise ExecutionError(f"XDIST_WORKERS_MUST_BE_EXPLICIT_TWO: {key}={workers!r}")
        proof_run_id = raw_entry.get("proof_run_id")
        proof_head_sha = raw_entry.get("proof_head_sha")
        proof_artifact_id = raw_entry.get("proof_artifact_id")
        proof_digest = raw_entry.get("proof_artifact_sha256")
        if isinstance(proof_run_id, bool) or not isinstance(proof_run_id, int) or proof_run_id <= 0:
            raise ExecutionError(f"XDIST_PROOF_RUN_REQUIRED: {key}")
        if not isinstance(proof_head_sha, str) or re.fullmatch(r"[0-9a-f]{40}", proof_head_sha) is None:
            raise ExecutionError(f"XDIST_PROOF_HEAD_REQUIRED: {key}")
        if isinstance(proof_artifact_id, bool) or not isinstance(proof_artifact_id, int) or proof_artifact_id <= 0:
            raise ExecutionError(f"XDIST_PROOF_ARTIFACT_REQUIRED: {key}")
        if not isinstance(proof_digest, str) or re.fullmatch(r"[0-9a-f]{64}", proof_digest) is None:
            raise ExecutionError(f"XDIST_PROOF_DIGEST_REQUIRED: {key}")

        normalized[key] = {
            "workers": workers,
            "proof_run_id": proof_run_id,
            "proof_head_sha": proof_head_sha,
            "proof_artifact_id": proof_artifact_id,
            "proof_artifact_sha256": proof_digest,
        }

    return {
        "default_workers": 1,
        "distribution": distribution,
        "safe_shards": normalized,
    }


def resolve_xdist_workers(policy: dict[str, object], *, lane: str, shard_id: str) -> int:
    if lane == XVFB_LANE:
        return 1
    safe_shards = policy.get("safe_shards", {})
    if not isinstance(safe_shards, dict):
        raise ExecutionError("XDIST_SAFE_SHARDS_INVALID: safe_shards is not an object")
    entry = safe_shards.get(f"{lane}:{shard_id}")
    if entry is None:
        return 1
    if not isinstance(entry, dict) or entry.get("workers") != 2:
        raise ExecutionError(f"XDIST_SAFE_SHARD_INVALID: {lane}:{shard_id}")
    return 2


def build_pytest_command(
    *,
    nodes: Iterable[str],
    junit_xml: Path,
    basetemp: Path,
    xdist_workers: int = 1,
    xdist_distribution: str = "load",
) -> list[str]:
    assigned = sorted(str(node) for node in nodes)
    if isinstance(xdist_workers, bool) or xdist_workers not in {1, 2}:
        raise ExecutionError(f"XDIST_WORKER_COUNT_INVALID: {xdist_workers!r}")
    if xdist_distribution != "load":
        raise ExecutionError(f"XDIST_DISTRIBUTION_UNSUPPORTED: {xdist_distribution!r}")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--junitxml={junit_xml}",
        f"--basetemp={basetemp}",
    ]
    if xdist_workers == 2:
        cmd.extend(["-n", "2", "--dist=load"])
    cmd.extend(assigned)
    return cmd


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
    xdist_workers: int = 1,
    xdist_distribution: str = "load",
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
            "xdist_workers": xdist_workers,
            "xdist_distribution": xdist_distribution,
        }
        _write_json(result_json, payload)
        return 0

    cmd = build_pytest_command(
        nodes=assigned,
        junit_xml=junit_xml,
        basetemp=basetemp,
        xdist_workers=xdist_workers,
        xdist_distribution=xdist_distribution,
    )
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
        "xdist_workers": xdist_workers,
        "xdist_distribution": xdist_distribution,
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
    policy = load_xdist_policy(args.execution_config)
    distribution = str(policy["distribution"])
    if args.all_shards:
        nodes = select_lane_nodes(manifest, args.lane)
        shard_id = "serial"
        xdist_workers = 1
    else:
        if not args.shard:
            raise ExecutionError("SHARD_REQUIRED")
        nodes = select_shard_nodes(manifest, args.lane, args.shard)
        shard_id = args.shard
        xdist_workers = resolve_xdist_workers(policy, lane=args.lane, shard_id=args.shard)
    return run_exact_nodes(
        nodes=nodes,
        lane=args.lane,
        shard_id=shard_id,
        result_json=args.result_json,
        junit_xml=args.junit_xml,
        log_path=args.log,
        basetemp=args.basetemp,
        xdist_workers=xdist_workers,
        xdist_distribution=distribution,
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
    run.add_argument(
        "--execution-config",
        type=Path,
        default=ROOT / "config" / "ci_test_execution.json",
    )
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
