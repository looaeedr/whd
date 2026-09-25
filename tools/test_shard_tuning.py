"""Fail-closed timing and tuning decisions for WHD CI sharding.

T6 deliberately separates measurement from execution policy.  This module does
not mutate manifests, choose shard ownership, or change runner concurrency by
itself.  It only normalizes timing evidence and makes conservative decisions
from same-head A/B evidence.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Iterable, Mapping


PERFORMANCE_TARGET_MET = "PERFORMANCE_TARGET_MET"
PERFORMANCE_TARGET_MISSED = "PERFORMANCE_TARGET_MISSED"
PERFORMANCE_FAIL = "PERFORMANCE_FAIL"
PERFORMANCE_INFRA_EXCEPTION = "PERFORMANCE_INFRA_EXCEPTION"

KEEP_HRW = "KEEP_HRW"
INVESTIGATE_DURATION_IMBALANCE = "INVESTIGATE_DURATION_IMBALANCE"

TARGET_SECONDS = 12 * 60
HARD_CEILING_SECONDS = 15 * 60
IMBALANCE_THRESHOLD = 1.75


class TuningError(ValueError):
    """Fail-closed error for invalid or non-comparable tuning evidence."""


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TuningError(f"TIMESTAMP_REQUIRED: {value!r}")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise TuningError(f"TIMESTAMP_INVALID: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TuningError(f"TIMESTAMP_MUST_BE_OFFSET_AWARE: {value!r}")
    return parsed


def _seconds(value: object, *, field: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TuningError(f"{field}_INVALID: {value!r}")
    number = float(value)
    if not math.isfinite(number) or number < 0 or (not allow_zero and number == 0):
        raise TuningError(f"{field}_INVALID: {value!r}")
    return number


def summarize_workflow_timing(
    *,
    created_at: str,
    first_required_job_started_at: str,
    final_required_job_completed_at: str,
) -> dict[str, float]:
    """Return queue, execution, and end-to-end wall clocks independently."""
    created = _timestamp(created_at)
    started = _timestamp(first_required_job_started_at)
    completed = _timestamp(final_required_job_completed_at)
    if started < created:
        raise TuningError("WORKFLOW_START_PRECEDES_CREATION")
    if completed < started:
        raise TuningError("WORKFLOW_COMPLETION_PRECEDES_START")
    return {
        "initial_queue_seconds": (started - created).total_seconds(),
        "execution_wall_clock_seconds": (completed - started).total_seconds(),
        "end_to_end_wall_clock_seconds": (completed - created).total_seconds(),
    }


def job_wait_seconds(*, created_at: str, started_at: str) -> float:
    """Measure job scheduling/queue wait without mixing in job runtime."""
    created = _timestamp(created_at)
    started = _timestamp(started_at)
    if started < created:
        raise TuningError("JOB_START_PRECEDES_CREATION")
    return (started - created).total_seconds()


def classify_performance(
    execution_wall_clock_seconds: float,
    *,
    infra_degradation_evidence: str | None = None,
) -> str:
    """Apply the T6 12-minute target and 15-minute hard ceiling."""
    seconds = _seconds(
        execution_wall_clock_seconds,
        field="EXECUTION_WALL_CLOCK_SECONDS",
    )
    if infra_degradation_evidence is not None:
        if not isinstance(infra_degradation_evidence, str) or not infra_degradation_evidence.strip():
            raise TuningError("INFRA_DEGRADATION_EVIDENCE_INVALID")
        infra_degradation_evidence = infra_degradation_evidence.strip()

    if seconds <= TARGET_SECONDS:
        return PERFORMANCE_TARGET_MET
    if seconds <= HARD_CEILING_SECONDS:
        return PERFORMANCE_TARGET_MISSED
    if infra_degradation_evidence:
        return PERFORMANCE_INFRA_EXCEPTION
    return PERFORMANCE_FAIL


def summarize_lane_imbalance(lane: str, shard_durations_seconds: Iterable[float]) -> dict[str, object]:
    """Summarize measured shard imbalance without automatically rebalancing."""
    if not isinstance(lane, str) or not lane.strip():
        raise TuningError("LANE_REQUIRED")
    durations = [
        _seconds(value, field="SHARD_DURATION_SECONDS", allow_zero=False)
        for value in shard_durations_seconds
    ]
    if not durations:
        raise TuningError(f"LANE_DURATIONS_REQUIRED: {lane}")
    median = float(statistics.median(durations))
    maximum = max(durations)
    ratio = maximum / median
    return {
        "lane": lane,
        "shard_count": len(durations),
        "median_seconds": median,
        "max_seconds": maximum,
        "max_to_median_ratio": ratio,
        "requires_investigation": ratio > IMBALANCE_THRESHOLD,
    }


def decide_manifest_strategy(lane_reports: Iterable[Mapping[str, object]]) -> str:
    """Keep HRW unless measured evidence crosses the investigation gate."""
    reports = list(lane_reports)
    if not reports:
        raise TuningError("LANE_REPORTS_REQUIRED")
    for report in reports:
        if not isinstance(report, Mapping):
            raise TuningError(f"LANE_REPORT_INVALID: {report!r}")
        flag = report.get("requires_investigation")
        if not isinstance(flag, bool):
            raise TuningError(f"LANE_REPORT_INVESTIGATION_FLAG_INVALID: {report!r}")
        if flag:
            return INVESTIGATE_DURATION_IMBALANCE
    return KEEP_HRW


def _validate_measurement(payload: Mapping[str, object], *, label: str, logical_shard_count: int) -> None:
    if not isinstance(payload, Mapping):
        raise TuningError(f"{label}_MEASUREMENT_INVALID")
    budget = payload.get("budget")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise TuningError(f"{label}_BUDGET_INVALID: {budget!r}")
    if budget > logical_shard_count:
        raise TuningError(f"{label}_BUDGET_OVERSUBSCRIBES_LOGICAL_SHARDS: {budget}>{logical_shard_count}")
    for field in ("execution_wall_clock_seconds", "end_to_end_wall_clock_seconds"):
        _seconds(payload.get(field), field=f"{label}_{field.upper()}")
    if payload.get("correctness_green") is not True:
        raise TuningError(f"{label}_CORRECTNESS_NOT_GREEN")
    if payload.get("protected_invariants_green") is not True:
        raise TuningError(f"{label}_PROTECTED_INVARIANTS_NOT_GREEN")


def choose_budget_from_ab(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    logical_shard_count: int,
) -> dict[str, object]:
    """Choose a concurrency budget only from comparable same-head A/B evidence.

    The candidate is accepted only when execution wall clock is strictly lower
    and end-to-end wall clock does not regress.  Correctness and protected
    invariants must be GREEN for both variants.
    """
    if isinstance(logical_shard_count, bool) or not isinstance(logical_shard_count, int) or logical_shard_count <= 0:
        raise TuningError(f"LOGICAL_SHARD_COUNT_INVALID: {logical_shard_count!r}")
    _validate_measurement(baseline, label="BASELINE", logical_shard_count=logical_shard_count)
    _validate_measurement(candidate, label="CANDIDATE", logical_shard_count=logical_shard_count)

    for field in ("head_sha", "manifest_sha256", "collection_count", "result_digest"):
        if baseline.get(field) != candidate.get(field):
            raise TuningError(f"AB_{field.upper()}_MISMATCH")

    base_execution = float(baseline["execution_wall_clock_seconds"])
    candidate_execution = float(candidate["execution_wall_clock_seconds"])
    base_e2e = float(baseline["end_to_end_wall_clock_seconds"])
    candidate_e2e = float(candidate["end_to_end_wall_clock_seconds"])

    if candidate_execution < base_execution and candidate_e2e <= base_e2e:
        return {
            "selected_budget": candidate["budget"],
            "reason": "MEASURED_EXECUTION_IMPROVEMENT",
            "baseline_execution_wall_clock_seconds": base_execution,
            "candidate_execution_wall_clock_seconds": candidate_execution,
            "baseline_end_to_end_wall_clock_seconds": base_e2e,
            "candidate_end_to_end_wall_clock_seconds": candidate_e2e,
        }
    return {
        "selected_budget": baseline["budget"],
        "reason": "NO_MEASURED_EXECUTION_IMPROVEMENT",
        "baseline_execution_wall_clock_seconds": base_execution,
        "candidate_execution_wall_clock_seconds": candidate_execution,
        "baseline_end_to_end_wall_clock_seconds": base_e2e,
        "candidate_end_to_end_wall_clock_seconds": candidate_e2e,
    }
