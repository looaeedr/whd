"""Fail-closed legacy-vs-optimized CI A/B comparison for issue #311.

The comparator consumes already-normalized evidence from the legacy and optimized
paths.  It compares semantic identities only; unstable pytest pretty-print text
is intentionally outside this contract.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


class ABParityError(ValueError):
    """Stable fail-closed error for non-equivalent A/B evidence."""


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
    """Require exact semantic parity and return a canonical GREEN summary.

    Timing is evidence, not parity: both paths must report execution, end-to-end,
    and queue values separately, but the values are expected to differ.
    """
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
