"""Fail-closed T4 aggregation for deterministic WHD shard evidence.

This module consumes accepted manifest ownership plus structured shard evidence.
It never re-derives lane/shard ownership from pytest markers or collection order.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from tools.test_shard_execution import SHARD_MANIFEST_SCHEMA


AGGREGATION_SCHEMA = "WHD_TEST_AGGREGATION_V1"
ALLOWED_OUTCOMES = {"passed", "failed", "error", "skipped"}
INHERITED_RED = "INHERITED_BASELINE_RED"
UNCLASSIFIED_RED = "UNCLASSIFIED_RED"
FLAKY_WARNING = "[FLAKY-WARNING]"


class AggregationError(ValueError):
    """Fail-closed aggregation error with a stable reason token."""


def _manifest_shards(manifest: Mapping[str, object]) -> Mapping[str, object]:
    if manifest.get("schema") != SHARD_MANIFEST_SCHEMA:
        raise AggregationError(
            f"MANIFEST_SCHEMA_MISMATCH: {manifest.get('schema')!r}"
        )
    shards = manifest.get("shards")
    if not isinstance(shards, Mapping):
        raise AggregationError("MANIFEST_SHARDS_INVALID")
    return shards


def _expected_ownership(
    manifest: Mapping[str, object],
) -> tuple[dict[tuple[str, str], list[str]], dict[str, tuple[str, str]]]:
    shards = _manifest_shards(manifest)
    expected: dict[tuple[str, str], list[str]] = {}
    owner_by_node: dict[str, tuple[str, str]] = {}
    for lane_raw, lane_value in shards.items():
        lane = str(lane_raw)
        if not isinstance(lane_value, Mapping):
            raise AggregationError(f"MANIFEST_LANE_INVALID:{lane}")
        for shard_raw, item in lane_value.items():
            shard_id = str(shard_raw)
            if not isinstance(item, Mapping):
                raise AggregationError(f"MANIFEST_SHARD_INVALID:{lane}:{shard_id}")
            nodes = item.get("nodes")
            count = item.get("count")
            if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
                raise AggregationError(f"MANIFEST_NODES_INVALID:{lane}:{shard_id}")
            if count != len(nodes):
                raise AggregationError(f"MANIFEST_COUNT_MISMATCH:{lane}:{shard_id}")
            canonical = sorted(nodes)
            expected[(lane, shard_id)] = canonical
            for node in canonical:
                if node in owner_by_node:
                    prior = owner_by_node[node]
                    raise AggregationError(
                        f"MANIFEST_DUPLICATE_NODE:{node}:{prior[0]}:{prior[1]}:{lane}:{shard_id}"
                    )
                owner_by_node[node] = (lane, shard_id)
    declared_count = manifest.get("full_collection_count")
    if declared_count is not None and declared_count != len(owner_by_node):
        raise AggregationError(
            f"MANIFEST_FULL_COUNT_MISMATCH:declared={declared_count}:actual={len(owner_by_node)}"
        )
    return expected, owner_by_node


def _require_str_list(value: object, *, token: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AggregationError(token)
    return list(value)


def _node_result_map(value: object, *, shard_key: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AggregationError(f"NODE_RESULTS_INVALID:{shard_key}")
    if not all(isinstance(node, str) for node in value):
        raise AggregationError(f"NODE_RESULTS_INVALID:{shard_key}")
    return value


def _normalize_record(node: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise AggregationError(f"NODE_RESULT_INVALID:{node}")
    outcome = raw.get("outcome")
    if outcome not in ALLOWED_OUTCOMES:
        raise AggregationError(f"NODE_OUTCOME_INVALID:{node}:{outcome!r}")
    duration = raw.get("duration_seconds", 0.0)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
        raise AggregationError(f"NODE_DURATION_INVALID:{node}:{duration!r}")
    record: dict[str, object] = {
        "outcome": str(outcome),
        "duration_seconds": float(duration),
    }
    classification = raw.get("classification")
    if classification is not None:
        record["classification"] = str(classification)
    excerpt = raw.get("error_excerpt")
    if excerpt is not None:
        record["error_excerpt"] = str(excerpt)
    return record


def _node_identity(node: str) -> tuple[str, str]:
    parts = node.split("::")
    if len(parts) < 2 or not parts[0].endswith(".py"):
        raise AggregationError(f"NODE_ID_INVALID:{node}")
    module = parts[0][:-3].replace("\\", "/").replace("/", ".")
    classname = ".".join([module, *parts[1:-1]])
    return classname, parts[-1]


def _failure_excerpt(item: ET.Element) -> str:
    message = (item.get("message") or "").strip()
    if message:
        return " ".join(message.split())[:500]
    text = (item.text or "").strip()
    if not text:
        return ""
    first = next((line.strip() for line in text.splitlines() if line.strip()), text)
    return " ".join(first.split())[:500]


def _read_junit_nodes(path: Path, assigned: Sequence[str]) -> dict[str, dict[str, object]]:
    identities: dict[tuple[str, str], str] = {}
    for node in assigned:
        identity = _node_identity(node)
        if identity in identities:
            raise AggregationError(f"JUNIT_ASSIGNMENT_AMBIGUOUS:{node}")
        identities[identity] = node

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise AggregationError(f"JUNIT_INVALID:{path}:{exc}") from exc

    node_results: dict[str, dict[str, object]] = {}
    for case in root.iter("testcase"):
        identity = (case.get("classname") or "", case.get("name") or "")
        node = identities.get(identity)
        if node is None:
            raise AggregationError(f"JUNIT_UNEXPECTED_NODE:{identity}")
        if node in node_results:
            raise AggregationError(f"JUNIT_DUPLICATE_NODE:{node}")
        raw_time = case.get("time", "0") or "0"
        try:
            duration = float(raw_time)
        except ValueError as exc:
            raise AggregationError(f"JUNIT_DURATION_INVALID:{node}:{raw_time!r}") from exc
        if duration < 0:
            raise AggregationError(f"JUNIT_DURATION_INVALID:{node}:{raw_time!r}")
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        record: dict[str, object] = {"duration_seconds": duration}
        if error is not None:
            record["outcome"] = "error"
            record["error_excerpt"] = _failure_excerpt(error)
        elif failure is not None:
            record["outcome"] = "failed"
            record["error_excerpt"] = _failure_excerpt(failure)
        elif skipped is not None:
            record["outcome"] = "skipped"
        else:
            record["outcome"] = "passed"
        node_results[node] = record

    missing = sorted(set(assigned) - set(node_results))
    if missing:
        raise AggregationError(f"JUNIT_MISSING_NODE:{missing}")
    return node_results


def normalize_shard_artifact(
    *,
    result_payload: Mapping[str, object],
    junit_xml: Path,
    expected_source_sha: str,
    artifact_refs: Sequence[str] = (),
) -> dict[str, object]:
    """Normalize accepted T2/T3 shard JSON + JUnit into the T4 evidence schema."""
    lane = result_payload.get("lane")
    shard_id = result_payload.get("shard_id")
    if not isinstance(lane, str) or not isinstance(shard_id, str):
        raise AggregationError("SHARD_IDENTITY_INVALID")
    embedded_sha = result_payload.get("source_sha")
    if embedded_sha is not None and embedded_sha != expected_source_sha:
        raise AggregationError(
            f"RESULT_SOURCE_SHA_MISMATCH:{lane}:{shard_id}:expected={expected_source_sha}:actual={embedded_sha}"
        )
    assigned = _require_str_list(
        result_payload.get("assigned_nodes"),
        token=f"ASSIGNED_NODES_INVALID:{lane}:{shard_id}",
    )
    assigned_count = result_payload.get("assigned_count")
    if assigned_count is not None and assigned_count != len(assigned):
        raise AggregationError(f"ASSIGNED_COUNT_MISMATCH:{lane}:{shard_id}")
    executed = result_payload.get("executed_nodes")
    if executed is not None:
        executed_nodes = _require_str_list(
            executed, token=f"EXECUTED_NODES_INVALID:{lane}:{shard_id}"
        )
        if sorted(executed_nodes) != sorted(assigned):
            raise AggregationError(f"EXECUTED_NODE_MISMATCH:{lane}:{shard_id}")

    node_results = _read_junit_nodes(junit_xml, assigned)
    counts = Counter(str(record["outcome"]) for record in node_results.values())
    expected_counts = {
        "passed": counts["passed"],
        "failures": counts["failed"],
        "errors": counts["error"],
        "skipped": counts["skipped"],
    }
    for field, actual in expected_counts.items():
        if field in result_payload and result_payload.get(field) != actual:
            raise AggregationError(
                f"RESULT_JUNIT_COUNT_MISMATCH:{lane}:{shard_id}:{field}:"
                f"result={result_payload.get(field)!r}:junit={actual}"
            )
    if "tests" in result_payload and result_payload.get("tests") != len(node_results):
        raise AggregationError(
            f"RESULT_JUNIT_COUNT_MISMATCH:{lane}:{shard_id}:tests:"
            f"result={result_payload.get('tests')!r}:junit={len(node_results)}"
        )

    failed_nodes = sorted(
        node for node, record in node_results.items()
        if record["outcome"] in {"failed", "error"}
    )
    embedded_failed = result_payload.get("failed_nodes")
    if embedded_failed is not None:
        embedded_failed_nodes = _require_str_list(
            embedded_failed, token=f"FAILED_NODES_INVALID:{lane}:{shard_id}"
        )
        if sorted(embedded_failed_nodes) != failed_nodes:
            raise AggregationError(f"RESULT_JUNIT_FAILURE_NODE_MISMATCH:{lane}:{shard_id}")

    shard_classification = result_payload.get("classification")
    if shard_classification == INHERITED_RED:
        for node in failed_nodes:
            node_results[node]["classification"] = INHERITED_RED

    duration = result_payload.get("execution_seconds", 0.0)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
        raise AggregationError(f"SHARD_DURATION_INVALID:{lane}:{shard_id}")
    refs = list(artifact_refs)
    if not all(isinstance(ref, str) for ref in refs):
        raise AggregationError(f"ARTIFACT_REFS_INVALID:{lane}:{shard_id}")
    return {
        "lane": lane,
        "shard_id": shard_id,
        "source_sha": expected_source_sha,
        "assigned_nodes": assigned,
        "node_results": node_results,
        "execution_seconds": float(duration),
        "artifact_refs": refs,
    }


def _validate_invariants(
    protected_invariants: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for name, evidence in (protected_invariants or {}).items():
        if not isinstance(evidence, Mapping):
            raise AggregationError(f"PROTECTED_INVARIANT_INVALID:{name}")
        before = evidence.get("before")
        after = evidence.get("after")
        if not isinstance(before, str) or not isinstance(after, str):
            raise AggregationError(f"PROTECTED_INVARIANT_INVALID:{name}")
        if before != after:
            raise AggregationError(
                f"PROTECTED_INVARIANT_DRIFT:{name}:before={before}:after={after}"
            )
        normalized[str(name)] = {"before": before, "after": after}
    return normalized


def aggregate_shard_results(
    *,
    manifest: Mapping[str, object],
    shard_results: Sequence[Mapping[str, object]],
    expected_source_sha: str,
    protected_invariants: Mapping[str, Mapping[str, str]] | None = None,
    retry_results: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Reconcile exact shard evidence and return one structured acceptance summary."""
    if not expected_source_sha:
        raise AggregationError("SOURCE_SHA_MISSING")
    if manifest.get("source_sha") != expected_source_sha:
        raise AggregationError(
            f"MANIFEST_SOURCE_SHA_MISMATCH:expected={expected_source_sha}:actual={manifest.get('source_sha')}"
        )

    expected_shards, owner_by_node = _expected_ownership(manifest)
    expected_keys = set(expected_shards)
    actual_by_key: dict[tuple[str, str], Mapping[str, object]] = {}
    for result in shard_results:
        if not isinstance(result, Mapping):
            raise AggregationError("SHARD_RESULT_INVALID")
        lane = result.get("lane")
        shard_id = result.get("shard_id")
        if not isinstance(lane, str) or not isinstance(shard_id, str):
            raise AggregationError("SHARD_IDENTITY_INVALID")
        key = (lane, shard_id)
        if key in actual_by_key:
            raise AggregationError(f"DUPLICATE_SHARD:{lane}:{shard_id}")
        actual_by_key[key] = result

    missing_shards = sorted(expected_keys - set(actual_by_key))
    if missing_shards:
        formatted = [f"{lane}:{shard}" for lane, shard in missing_shards]
        raise AggregationError(f"MISSING_SHARD:{formatted}")
    extra_shards = sorted(set(actual_by_key) - expected_keys)
    if extra_shards:
        formatted = [f"{lane}:{shard}" for lane, shard in extra_shards]
        raise AggregationError(f"UNEXPECTED_SHARD:{formatted}")

    execution_owners: dict[str, list[str]] = defaultdict(list)
    for (lane, shard_id), result in actual_by_key.items():
        node_results = _node_result_map(
            result.get("node_results"), shard_key=f"{lane}:{shard_id}"
        )
        for node in node_results:
            execution_owners[node].append(f"{lane}:{shard_id}")
    duplicates = {
        node: owners
        for node, owners in sorted(execution_owners.items())
        if len(owners) > 1
    }
    if duplicates:
        raise AggregationError(f"DUPLICATE_NODE:{duplicates}")

    normalized_nodes: dict[str, dict[str, object]] = {}
    shard_summaries: dict[str, dict[str, object]] = {}
    lane_counts: dict[str, Counter[str]] = defaultdict(Counter)
    lane_durations: Counter[str] = Counter()
    global_counts: Counter[str] = Counter()

    for (lane, shard_id) in sorted(expected_keys):
        result = actual_by_key[(lane, shard_id)]
        if result.get("source_sha") != expected_source_sha:
            raise AggregationError(f"RESULT_SOURCE_SHA_MISMATCH:{lane}:{shard_id}")
        assigned = _require_str_list(
            result.get("assigned_nodes"), token=f"ASSIGNED_NODES_INVALID:{lane}:{shard_id}"
        )
        node_results = _node_result_map(
            result.get("node_results"), shard_key=f"{lane}:{shard_id}"
        )
        assigned_set = set(assigned)
        result_set = set(node_results)
        missing_nodes = sorted(assigned_set - result_set)
        if missing_nodes:
            raise AggregationError(f"MISSING_NODE:{lane}:{shard_id}:{missing_nodes}")
        extra_nodes = sorted(result_set - assigned_set)
        if extra_nodes:
            raise AggregationError(f"UNEXPECTED_NODE:{lane}:{shard_id}:{extra_nodes}")
        if sorted(assigned) != expected_shards[(lane, shard_id)]:
            raise AggregationError(f"SHARD_ASSIGNMENT_MISMATCH:{lane}:{shard_id}")

        duration = result.get("execution_seconds", 0.0)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
            raise AggregationError(f"SHARD_DURATION_INVALID:{lane}:{shard_id}")
        artifact_refs = _require_str_list(
            result.get("artifact_refs", []), token=f"ARTIFACT_REFS_INVALID:{lane}:{shard_id}"
        )
        shard_counts: Counter[str] = Counter()
        for node in sorted(node_results):
            normalized = _normalize_record(node, node_results[node])
            normalized["lane"] = lane
            normalized["shard_id"] = shard_id
            normalized["artifact_refs"] = list(artifact_refs)
            normalized_nodes[node] = normalized
            outcome = str(normalized["outcome"])
            shard_counts[outcome] += 1
            lane_counts[lane][outcome] += 1
            global_counts[outcome] += 1
        shard_summaries[f"{lane}:{shard_id}"] = {
            "lane": lane,
            "shard_id": shard_id,
            "assigned_count": len(assigned),
            "counts": dict(shard_counts),
            "execution_seconds": float(duration),
            "artifact_refs": list(artifact_refs),
        }
        lane_durations[lane] += float(duration)

    expected_nodes = set(owner_by_node)
    actual_nodes = set(normalized_nodes)
    missing_global = sorted(expected_nodes - actual_nodes)
    if missing_global:
        raise AggregationError(f"MISSING_NODE:{missing_global}")
    extra_global = sorted(actual_nodes - expected_nodes)
    if extra_global:
        raise AggregationError(f"UNEXPECTED_NODE:{extra_global}")

    invariants = _validate_invariants(protected_invariants)
    retries = retry_results or {}
    failures: list[dict[str, object]] = []
    warnings: list[str] = []
    decision = "GREEN"
    for node in sorted(normalized_nodes):
        record = normalized_nodes[node]
        outcome = str(record["outcome"])
        if outcome not in {"failed", "error"}:
            continue
        classification = str(record.get("classification") or UNCLASSIFIED_RED)
        if classification != INHERITED_RED:
            classification = UNCLASSIFIED_RED
            decision = "FAIL"
        retry_outcome: str | None = None
        retry_state: str | None = None
        if node in retries:
            retry_record = _normalize_record(node, retries[node])
            retry_outcome = str(retry_record["outcome"])
            if retry_outcome == "passed":
                retry_state = FLAKY_WARNING
                if FLAKY_WARNING not in warnings:
                    warnings.append(FLAKY_WARNING)
        failures.append(
            {
                "node": node,
                "lane": record["lane"],
                "shard_id": record["shard_id"],
                "first_run_outcome": outcome,
                "classification": classification,
                "retry_outcome": retry_outcome,
                "retry_state": retry_state,
                "error_excerpt": record.get("error_excerpt"),
                "artifact_refs": record["artifact_refs"],
            }
        )

    lane_summaries: dict[str, dict[str, object]] = {}
    for lane in sorted(lane_counts):
        counts = lane_counts[lane]
        lane_summaries[lane] = {
            "counts": {
                "passed": counts["passed"],
                "failed": counts["failed"],
                "errors": counts["error"],
                "skipped": counts["skipped"],
            },
            "execution_seconds": float(lane_durations[lane]),
        }

    return {
        "schema": AGGREGATION_SCHEMA,
        "source_sha": expected_source_sha,
        "decision": decision,
        "full_collection_count": len(expected_nodes),
        "executed_unique_count": len(actual_nodes),
        "counts": {
            "passed": global_counts["passed"],
            "failed": global_counts["failed"],
            "errors": global_counts["error"],
            "skipped": global_counts["skipped"],
        },
        "lanes": lane_summaries,
        "shards": shard_summaries,
        "failures": failures,
        "warnings": warnings,
        "protected_invariants": invariants,
    }


def render_unified_summary(summary: Mapping[str, object]) -> str:
    """Render the structured result as one GitHub-friendly Markdown summary."""
    source_sha = summary.get("source_sha", "")
    decision = summary.get("decision", "UNKNOWN")
    full_count = summary.get("full_collection_count", 0)
    executed = summary.get("executed_unique_count", 0)
    lines = [
        "# WHD Unified Shard Summary",
        "",
        f"- **Tested SHA:** `{source_sha}`",
        f"- **Decision:** **{decision}**",
        f"- **Collection reconciliation:** **{executed} / {full_count}** unique nodes",
        "",
        "## Lane durations",
        "",
        "| Lane | Passed | Failed | Errors | Skipped | Seconds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lanes = summary.get("lanes", {})
    if isinstance(lanes, Mapping):
        for lane, raw in sorted(lanes.items(), key=lambda item: str(item[0])):
            data = raw if isinstance(raw, Mapping) else {}
            counts = data.get("counts", {}) if isinstance(data, Mapping) else {}
            if not isinstance(counts, Mapping):
                counts = {}
            duration = data.get("execution_seconds", 0.0) if isinstance(data, Mapping) else 0.0
            lines.append(
                f"| {lane} | {counts.get('passed', 0)} | {counts.get('failed', 0)} | "
                f"{counts.get('errors', 0)} | {counts.get('skipped', 0)} | {float(duration):.3f} |"
            )

    lines.extend(
        [
            "",
            "## Shard durations",
            "",
            "| Shard | Assigned | Seconds | Artifacts |",
            "|---|---:|---:|---|",
        ]
    )
    shards = summary.get("shards", {})
    if isinstance(shards, Mapping):
        for key, raw in sorted(shards.items(), key=lambda item: str(item[0])):
            data = raw if isinstance(raw, Mapping) else {}
            refs = data.get("artifact_refs", []) if isinstance(data, Mapping) else []
            refs_text = ", ".join(str(ref) for ref in refs) if isinstance(refs, list) else ""
            duration = data.get("execution_seconds", 0.0) if isinstance(data, Mapping) else 0.0
            lines.append(
                f"| {key} | {data.get('assigned_count', 0)} | {float(duration):.3f} | {refs_text} |"
            )

    warnings = summary.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(
        [
            "",
            "## Failures",
            "",
            "| Node | Owner | First run | Classification | Retry | Error | Artifacts |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    failures = summary.get("failures", [])
    if isinstance(failures, list) and failures:
        for raw in failures:
            data = raw if isinstance(raw, Mapping) else {}
            owner = f"{data.get('lane', '')}:{data.get('shard_id', '')}"
            retry = data.get("retry_state") or data.get("retry_outcome") or "—"
            error = str(data.get("error_excerpt") or "").replace("|", "\\|").replace("\n", " ")
            refs = data.get("artifact_refs", [])
            refs_text = ", ".join(str(ref) for ref in refs) if isinstance(refs, list) else ""
            lines.append(
                f"| {data.get('node', '')} | {owner} | {data.get('first_run_outcome', '')} | "
                f"{data.get('classification', '')} | {retry} | {error} | {refs_text} |"
            )
    else:
        lines.append("| — | — | — | — | — | — | — |")
    return "\n".join(lines) + "\n"
