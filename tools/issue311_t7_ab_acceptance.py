"""Fail-closed legacy-vs-optimized CI A/B comparison for issue #311.

The comparator consumes normalized semantic evidence from the legacy and optimized
paths. Unstable pytest pretty-print text is intentionally outside this contract.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class ABParityError(ValueError):
    """Stable fail-closed error for non-equivalent or malformed A/B evidence."""


_TIMING_FIELDS = (
    "execution_wall_clock_seconds",
    "end_to_end_wall_clock_seconds",
    "queue_seconds",
)


def _require_mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ABParityError(f"{label}_EVIDENCE_INVALID")
    return value


def _require_string(value: object, *, token: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ABParityError(token)
    return value.strip()


def _require_sequence(value: object, *, token: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ABParityError(token)
    return value


def _canonical_strings(value: object, *, token: str) -> tuple[str, ...]:
    items = _require_sequence(value, token=token)
    normalized = []
    for item in items:
        normalized.append(_require_string(item, token=token))
    return tuple(sorted(normalized))


def _canonical_reason_records(value: object, *, token: str) -> tuple[tuple[str, str], ...]:
    items = _require_sequence(value, token=token)
    normalized: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ABParityError(token)
        nodeid = _require_string(item.get("nodeid"), token=token)
        reason = _require_string(item.get("reason"), token=token)
        normalized.append((nodeid, reason))
    return tuple(sorted(normalized))


def _canonical_protected_drift(value: object, *, token: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ABParityError(token)
    normalized: list[tuple[str, str]] = []
    for key, raw in value.items():
        name = _require_string(key, token=token)
        normalized.append((name, repr(raw)))
    return tuple(sorted(normalized))


def _timing(payload: Mapping[str, Any], *, label: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for field in _TIMING_FIELDS:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ABParityError(f"TIMING_EVIDENCE_MISSING:{label}:{field}")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ABParityError(f"TIMING_EVIDENCE_MISSING:{label}:{field}")
        result[field] = number
    if result["end_to_end_wall_clock_seconds"] < result["execution_wall_clock_seconds"]:
        raise ABParityError(f"TIMING_EVIDENCE_INVALID:{label}:END_TO_END_LT_EXECUTION")
    return result


def compare_ab_evidence(
    legacy_evidence: Mapping[str, Any],
    optimized_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Require exact semantic parity and return a canonical GREEN summary."""
    legacy = _require_mapping(legacy_evidence, label="LEGACY")
    optimized = _require_mapping(optimized_evidence, label="OPTIMIZED")

    old_head = _require_string(legacy.get("head_sha"), token="HEAD_SHA_MISSING")
    new_head = _require_string(optimized.get("head_sha"), token="HEAD_SHA_MISSING")
    if old_head != new_head:
        raise ABParityError("HEAD_SHA_MISMATCH")

    old_collection = _canonical_strings(
        legacy.get("full_collection"), token="FULL_COLLECTION_INVALID"
    )
    new_collection = _canonical_strings(
        optimized.get("full_collection"), token="FULL_COLLECTION_INVALID"
    )
    if old_collection != new_collection:
        raise ABParityError("FULL_COLLECTION_MISMATCH")

    old_failed = _canonical_reason_records(
        legacy.get("failed_nodes"), token="FAILED_NODE_SET_INVALID"
    )
    new_failed = _canonical_reason_records(
        optimized.get("failed_nodes"), token="FAILED_NODE_SET_INVALID"
    )
    if old_failed != new_failed:
        raise ABParityError("FAILED_NODE_SET_MISMATCH")

    old_skips = _canonical_reason_records(
        legacy.get("allowed_skip_contract"), token="ALLOWED_SKIP_CONTRACT_INVALID"
    )
    new_skips = _canonical_reason_records(
        optimized.get("allowed_skip_contract"), token="ALLOWED_SKIP_CONTRACT_INVALID"
    )
    if old_skips != new_skips:
        raise ABParityError("ALLOWED_SKIP_CONTRACT_MISMATCH")

    new_missing = list(
        _canonical_strings(optimized.get("missing_nodes"), token="NEW_MISSING_NODES_INVALID")
    )
    if new_missing:
        raise ABParityError(f"NEW_MISSING_NODES:{new_missing}")

    new_duplicates = list(
        _canonical_strings(
            optimized.get("duplicate_nodes"), token="NEW_DUPLICATE_NODES_INVALID"
        )
    )
    if new_duplicates:
        raise ABParityError(f"NEW_DUPLICATE_NODES:{new_duplicates}")

    old_drift = _canonical_protected_drift(
        legacy.get("protected_drift"), token="PROTECTED_DRIFT_INVALID"
    )
    new_drift = _canonical_protected_drift(
        optimized.get("protected_drift"), token="PROTECTED_DRIFT_INVALID"
    )
    if old_drift or new_drift or old_drift != new_drift:
        raise ABParityError("PROTECTED_DRIFT")

    legacy_timing = _timing(legacy, label="LEGACY")
    optimized_timing = _timing(optimized, label="OPTIMIZED")

    return {
        "decision": "GREEN",
        "head_sha": old_head,
        "full_collection_count": len(old_collection),
        "failed_node_count": len(old_failed),
        "allowed_skip_count": len(old_skips),
        "new_missing_nodes": new_missing,
        "new_duplicate_nodes": new_duplicates,
        "protected_drift": {},
        "legacy_timing": legacy_timing,
        "optimized_timing": optimized_timing,
    }


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ABParityError(f"JSON_EVIDENCE_INVALID:{path}") from exc
    if not isinstance(value, Mapping):
        raise ABParityError(f"JSON_EVIDENCE_INVALID:{path}")
    return value


def _read_nodes(path: Path) -> list[str]:
    try:
        return sorted(
            line.strip()
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except OSError as exc:
        raise ABParityError(f"NODE_EVIDENCE_MISSING:{path}") from exc


def _node_identity(node: str) -> tuple[str, str]:
    parts = node.split("::")
    if len(parts) < 2 or not parts[0].endswith(".py"):
        raise ABParityError(f"NODE_ID_INVALID:{node}")
    module = parts[0][:-3].replace("\\", "/").replace("/", ".")
    classname = ".".join([module, *parts[1:-1]])
    return classname, parts[-1]


def _junit_semantics(path: Path, assigned_nodes: Sequence[str]) -> tuple[list[str], list[dict[str, str]]]:
    identity_to_node: dict[tuple[str, str], str] = {}
    for node in assigned_nodes:
        identity = _node_identity(node)
        if identity in identity_to_node:
            raise ABParityError(f"JUNIT_ASSIGNMENT_AMBIGUOUS:{node}")
        identity_to_node[identity] = node
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ABParityError(f"JUNIT_INVALID:{path}") from exc

    observed: list[str] = []
    skips: list[dict[str, str]] = []
    seen: set[str] = set()
    for case in root.iter("testcase"):
        identity = (case.get("classname") or "", case.get("name") or "")
        node = identity_to_node.get(identity)
        if node is None:
            raise ABParityError(f"JUNIT_UNEXPECTED_NODE:{identity}")
        if node in seen:
            raise ABParityError(f"JUNIT_DUPLICATE_NODE:{node}")
        seen.add(node)
        observed.append(node)
        skipped = case.find("skipped")
        if skipped is not None:
            reason = " ".join((skipped.get("message") or "").split())
            if not reason:
                reason = " ".join((skipped.text or "").split())
            if not reason:
                reason = "pytest.skip"
            skips.append({"nodeid": node, "reason": reason})
    missing = sorted(set(assigned_nodes) - seen)
    if missing:
        raise ABParityError(f"JUNIT_MISSING_NODE:{missing}")
    return sorted(observed), sorted(skips, key=lambda item: (item["nodeid"], item["reason"]))


def _protected_drift_from_pairs(root: Path, pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    drift: dict[str, Any] = {}
    for before_name, after_name in pairs:
        before = root / before_name
        after = root / after_name
        try:
            before_text = before.read_text(encoding="utf-8")
            after_text = after.read_text(encoding="utf-8")
        except OSError as exc:
            raise ABParityError(f"PROTECTED_EVIDENCE_MISSING:{before}:{after}") from exc
        if before_text != after_text:
            drift[before_name.removesuffix("-before.sha256")] = [before_text, after_text]
    return drift


def build_legacy_evidence(
    root: Path,
    failure_contract_path: Path,
    *,
    head_sha: str,
) -> dict[str, Any]:
    """Normalize issue304-style serial lane artifacts into the T7 semantic contract."""
    root = Path(root)
    full = _read_nodes(root / "full-collection.txt")
    lane_files = sorted(root.glob("collection-*.txt"))
    if not lane_files:
        raise ABParityError("LEGACY_LANE_COLLECTION_MISSING")
    observed_all: list[str] = []
    skips: list[dict[str, str]] = []
    for collection_path in lane_files:
        lane = collection_path.stem.removeprefix("collection-")
        assigned = _read_nodes(collection_path)
        observed, lane_skips = _junit_semantics(root / f"{lane}.xml", assigned)
        observed_all.extend(observed)
        skips.extend(lane_skips)

    counts = Counter(observed_all)
    duplicates = sorted(node for node, count in counts.items() if count > 1)
    missing = sorted(set(full) - set(observed_all))
    extra = sorted(set(observed_all) - set(full))
    if extra:
        raise ABParityError(f"LEGACY_UNEXPECTED_NODES:{extra}")

    summary = _read_json(root / "lane-summary.json")
    lanes = summary.get("lanes")
    if not isinstance(lanes, Mapping):
        raise ABParityError("LEGACY_LANE_SUMMARY_INVALID")
    failed: set[str] = set()
    for raw in lanes.values():
        if not isinstance(raw, Mapping):
            raise ABParityError("LEGACY_LANE_SUMMARY_INVALID")
        nodes = raw.get("failed_nodes", [])
        if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
            raise ABParityError("LEGACY_FAILED_NODES_INVALID")
        failed.update(nodes)
    contract = _read_json(failure_contract_path)
    expected_failures = contract.get("failures")
    if not isinstance(expected_failures, Mapping):
        raise ABParityError("FAILURE_CONTRACT_INVALID")
    failed_records = [
        {
            "nodeid": node,
            "reason": "INHERITED_BASELINE_RED" if node in expected_failures else "UNCLASSIFIED_RED",
        }
        for node in sorted(failed)
    ]

    timing = _read_json(root / "timing-summary.json")
    protected_drift = _protected_drift_from_pairs(
        root,
        (
            ("tracked-before.sha256", "tracked-after.sha256"),
            ("config-dxf-before.sha256", "config-dxf-after.sha256"),
        ),
    )
    return {
        "head_sha": _require_string(head_sha, token="HEAD_SHA_MISSING"),
        "full_collection": full,
        "failed_nodes": failed_records,
        "allowed_skip_contract": sorted(skips, key=lambda item: (item["nodeid"], item["reason"])),
        "missing_nodes": missing,
        "duplicate_nodes": duplicates,
        "protected_drift": protected_drift,
        "execution_wall_clock_seconds": timing.get("execution_wall_clock_seconds"),
        "end_to_end_wall_clock_seconds": timing.get("end_to_end_wall_clock_seconds"),
        "queue_seconds": timing.get("queue_delay_seconds"),
    }


def _optimized_artifact_roots(root: Path, *, result_name: str) -> list[tuple[Path, Mapping[str, Any]]]:
    items: list[tuple[Path, Mapping[str, Any]]] = []
    for artifact_root in sorted(Path(root).iterdir() if Path(root).is_dir() else []):
        if not artifact_root.is_dir():
            continue
        result_path = artifact_root / result_name
        if result_path.is_file():
            items.append((artifact_root, _read_json(result_path)))
    return items


def build_optimized_evidence(
    *,
    plan_root: Path,
    aggregate_root: Path,
    timing_root: Path,
    non_gui_root: Path,
    xvfb_root: Path,
    head_sha: str,
) -> dict[str, Any]:
    """Normalize T6-style sharded artifacts into the T7 semantic contract."""
    expected_head = _require_string(head_sha, token="HEAD_SHA_MISSING")
    manifest = _read_json(Path(plan_root) / "manifest" / "shard-manifest.json")
    if manifest.get("source_sha") != expected_head:
        raise ABParityError("OPTIMIZED_MANIFEST_HEAD_MISMATCH")
    shards = manifest.get("shards")
    if not isinstance(shards, Mapping):
        raise ABParityError("OPTIMIZED_MANIFEST_INVALID")
    expected: list[str] = []
    for lane_value in shards.values():
        if not isinstance(lane_value, Mapping):
            raise ABParityError("OPTIMIZED_MANIFEST_INVALID")
        for item in lane_value.values():
            if not isinstance(item, Mapping):
                raise ABParityError("OPTIMIZED_MANIFEST_INVALID")
            nodes = item.get("nodes")
            if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
                raise ABParityError("OPTIMIZED_MANIFEST_INVALID")
            expected.extend(nodes)
    expected_counter = Counter(expected)
    manifest_duplicates = sorted(node for node, count in expected_counter.items() if count > 1)
    if manifest_duplicates:
        raise ABParityError(f"OPTIMIZED_MANIFEST_DUPLICATE_NODES:{manifest_duplicates}")
    full = sorted(expected_counter)

    roots = _optimized_artifact_roots(Path(non_gui_root), result_name="shard-result.json")
    roots += _optimized_artifact_roots(Path(xvfb_root), result_name="result.json")
    if not roots:
        raise ABParityError("OPTIMIZED_ARTIFACTS_MISSING")
    observed_all: list[str] = []
    skips: list[dict[str, str]] = []
    protected_drift: dict[str, Any] = {}
    for artifact_root, payload in roots:
        assigned = payload.get("assigned_nodes")
        if not isinstance(assigned, list) or not all(isinstance(node, str) for node in assigned):
            raise ABParityError(f"OPTIMIZED_ASSIGNED_NODES_INVALID:{artifact_root}")
        observed, shard_skips = _junit_semantics(artifact_root / "result.xml", assigned)
        observed_all.extend(observed)
        skips.extend(shard_skips)
        drift = _protected_drift_from_pairs(
            artifact_root,
            (("protected-before.sha256", "protected-after.sha256"),),
        )
        for key, value in drift.items():
            protected_drift[f"{artifact_root.name}:{key}"] = value

    observed_counter = Counter(observed_all)
    duplicates = sorted(node for node, count in observed_counter.items() if count > 1)
    missing = sorted(set(full) - set(observed_all))
    extra = sorted(set(observed_all) - set(full))
    if extra:
        raise ABParityError(f"OPTIMIZED_UNEXPECTED_NODES:{extra}")

    aggregate = _read_json(Path(aggregate_root) / "aggregation.json")
    if aggregate.get("source_sha") != expected_head:
        raise ABParityError("OPTIMIZED_AGGREGATE_HEAD_MISMATCH")
    failures = aggregate.get("failures")
    if not isinstance(failures, list):
        raise ABParityError("OPTIMIZED_FAILURES_INVALID")
    failed_records: list[dict[str, str]] = []
    for item in failures:
        if not isinstance(item, Mapping):
            raise ABParityError("OPTIMIZED_FAILURES_INVALID")
        failed_records.append(
            {
                "nodeid": _require_string(item.get("node"), token="OPTIMIZED_FAILURES_INVALID"),
                "reason": _require_string(
                    item.get("classification"), token="OPTIMIZED_FAILURES_INVALID"
                ),
            }
        )

    timing = _read_json(Path(timing_root) / "timing.json")
    if timing.get("source_sha") != expected_head:
        raise ABParityError("OPTIMIZED_TIMING_HEAD_MISMATCH")
    return {
        "head_sha": expected_head,
        "full_collection": full,
        "failed_nodes": sorted(failed_records, key=lambda item: (item["nodeid"], item["reason"])),
        "allowed_skip_contract": sorted(skips, key=lambda item: (item["nodeid"], item["reason"])),
        "missing_nodes": missing,
        "duplicate_nodes": duplicates,
        "protected_drift": protected_drift,
        "execution_wall_clock_seconds": timing.get("execution_wall_clock_seconds"),
        "end_to_end_wall_clock_seconds": timing.get("end_to_end_wall_clock_seconds"),
        "queue_seconds": timing.get("initial_queue_seconds"),
    }
