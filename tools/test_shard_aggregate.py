"""Fail-closed result reconciliation for WHD CI T2 non-Xvfb sharding."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.test_shard_execution import (
    ExecutionError,
    XVFB_LANE,
    expected_non_xvfb_nodes,
)


class AggregationError(ValueError):
    """Fail-closed aggregation error with a stable reason token."""


def _node_owners(results: Iterable[dict[str, object]]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = defaultdict(list)
    for result in results:
        lane = str(result.get("lane", ""))
        shard = str(result.get("shard_id", ""))
        nodes = result.get("assigned_nodes")
        if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
            raise AggregationError(f"RESULT_NODES_INVALID: {lane}:{shard}")
        for node in nodes:
            owners[node].append(f"{lane}:{shard}")
    return dict(owners)


def _result_totals(results: Iterable[dict[str, object]]) -> dict[str, int]:
    totals = {key: 0 for key in ("tests", "passed", "failures", "errors", "skipped")}
    for result in results:
        assigned = result.get("assigned_nodes")
        if not isinstance(assigned, list):
            raise AggregationError("RESULT_NODES_INVALID")
        assigned_count = result.get("assigned_count")
        if assigned_count != len(assigned):
            raise AggregationError(
                f"RESULT_ASSIGNED_COUNT_MISMATCH: assigned_count={assigned_count!r} nodes={len(assigned)}"
            )
        tests = result.get("tests")
        if tests != len(assigned):
            raise AggregationError(
                f"RESULT_COUNT_MISMATCH: tests={tests!r} assigned={len(assigned)}"
            )
        for key in totals:
            value = result.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AggregationError(f"RESULT_TOTAL_INVALID: {key}={value!r}")
            totals[key] += value
        if totals["tests"] < totals["passed"] + totals["failures"] + totals["errors"] + totals["skipped"]:
            raise AggregationError("RESULT_TOTAL_INVALID: outcomes exceed tests")
    return totals


def _expected_shard_ids(shard_manifest: dict[str, object]) -> set[tuple[str, str]]:
    shards = shard_manifest.get("shards")
    if not isinstance(shards, dict):
        raise AggregationError("MANIFEST_SHARDS_INVALID")
    expected: set[tuple[str, str]] = set()
    for lane, lane_shards in shards.items():
        lane_name = str(lane)
        if lane_name == XVFB_LANE:
            continue
        if not isinstance(lane_shards, dict):
            raise AggregationError(f"MANIFEST_LANE_INVALID: {lane_name}")
        for shard_id in lane_shards:
            expected.add((lane_name, str(shard_id)))
    return expected


def reconcile_shard_results(
    shard_manifest: dict[str, object],
    shard_results: list[dict[str, object]],
    reference_results: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Prove exact non-Xvfb node execution and serial-reference result parity."""
    expected_by_lane = expected_non_xvfb_nodes(shard_manifest)
    expected = set().union(*(set(nodes) for nodes in expected_by_lane.values())) if expected_by_lane else set()

    xvfb_nodes: list[str] = []
    for result in shard_results:
        if str(result.get("lane", "")) == XVFB_LANE:
            nodes = result.get("assigned_nodes")
            if isinstance(nodes, list):
                xvfb_nodes.extend(str(node) for node in nodes)
    if xvfb_nodes:
        raise AggregationError(f"XVFB_EXECUTED_IN_T2: {sorted(xvfb_nodes)}")

    owners = _node_owners(shard_results)
    actual = set(owners)
    duplicate = {
        node: sorted(node_owners)
        for node, node_owners in sorted(owners.items())
        if len(node_owners) > 1
    }
    if duplicate:
        raise AggregationError(f"EXECUTION_DUPLICATE: {duplicate}")
    missing = sorted(expected - actual)
    if missing:
        raise AggregationError(f"EXECUTION_MISSING: {missing}")
    extra = sorted(actual - expected)
    if extra:
        raise AggregationError(f"EXECUTION_EXTRA: {extra}")

    expected_shards = _expected_shard_ids(shard_manifest)
    actual_shards = {
        (str(result.get("lane", "")), str(result.get("shard_id", "")))
        for result in shard_results
    }
    missing_shards = sorted(expected_shards - actual_shards)
    extra_shards = sorted(actual_shards - expected_shards)
    if missing_shards:
        raise AggregationError(f"SHARD_RESULT_MISSING: {missing_shards}")
    if extra_shards:
        raise AggregationError(f"SHARD_RESULT_EXTRA: {extra_shards}")
    if len(actual_shards) != len(shard_results):
        raise AggregationError("SHARD_RESULT_DUPLICATE")

    lane_summary: dict[str, dict[str, object]] = {}
    for lane in sorted(expected_by_lane):
        lane_shards = [result for result in shard_results if result.get("lane") == lane]
        sharded_totals = _result_totals(lane_shards)
        if lane not in reference_results:
            raise AggregationError(f"REFERENCE_MISSING: {lane}")
        reference = reference_results[lane]
        reference_nodes = reference.get("assigned_nodes")
        if not isinstance(reference_nodes, list) or set(reference_nodes) != set(expected_by_lane[lane]):
            raise AggregationError(f"REFERENCE_NODE_MISMATCH: {lane}")
        reference_totals = _result_totals([reference])
        if sharded_totals != reference_totals:
            raise AggregationError(
                f"LANE_RESULT_MISMATCH: {lane} sharded={sharded_totals} reference={reference_totals}"
            )
        if int(reference.get("child_rc", 0)) != 0:
            raise AggregationError(f"REFERENCE_CHILD_RED: {lane} rc={reference.get('child_rc')}")
        red_shards = [
            f"{result.get('lane')}:{result.get('shard_id')}={result.get('child_rc')}"
            for result in lane_shards
            if int(result.get("child_rc", 0)) != 0
        ]
        if red_shards:
            raise AggregationError(f"SHARD_CHILD_RED: {red_shards}")
        lane_summary[lane] = {
            "node_count": len(expected_by_lane[lane]),
            "sharded": sharded_totals,
            "reference": reference_totals,
        }

    return {
        "expected_node_count": len(expected),
        "executed_unique_node_count": len(actual),
        "missing_nodes": [],
        "extra_nodes": [],
        "duplicate_nodes": {},
        "xvfb_executed_nodes": [],
        "lane_result_parity": True,
        "lanes": lane_summary,
    }


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AggregationError(f"JSON_ROOT_INVALID: {path}")
    return payload


def _find_results(root: Path, pattern: str) -> list[dict[str, object]]:
    paths = sorted(root.glob(pattern))
    if not paths:
        raise AggregationError(f"RESULT_FILES_MISSING: {root}/{pattern}")
    return [_load_json(path) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate WHD non-Xvfb shard results")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shard-results-dir", type=Path, required=True)
    parser.add_argument("--reference-results-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    try:
        manifest = _load_json(args.manifest)
        shard_results = _find_results(args.shard_results_dir, "**/shard-result.json")
        references = _find_results(args.reference_results_dir, "**/reference-*.json")
        reference_map = {str(result.get("lane")): result for result in references}
        if len(reference_map) != len(references):
            raise AggregationError("REFERENCE_DUPLICATE_LANE")
        summary = reconcile_shard_results(manifest, shard_results, reference_map)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (AggregationError, ExecutionError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
