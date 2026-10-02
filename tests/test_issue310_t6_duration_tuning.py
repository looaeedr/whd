from copy import deepcopy

import pytest

from tools.test_shard_tuning import (
    KEEP_HRW,
    INVESTIGATE_DURATION_IMBALANCE,
    PERFORMANCE_FAIL,
    PERFORMANCE_INFRA_EXCEPTION,
    PERFORMANCE_TARGET_MET,
    PERFORMANCE_TARGET_MISSED,
    TuningError,
    choose_budget_from_ab,
    classify_performance,
    decide_manifest_strategy,
    job_wait_seconds,
    summarize_lane_imbalance,
    summarize_workflow_timing,
)


T5_HEAD = "9b60d1c8da213fc781b4cb60c6e9d5a030d74b44"
T5_MANIFEST = "9ad38e8019d0a09eab3bac91d5e9605f90513aa1f2ce4c112c7e24c90f49d8db"
T5_RESULT_DIGEST = "1179886db3d321150460feddd1be42db6a4c14d69719df7a46d73dd0c59bbb42"


def _measurement(**overrides):
    payload = {
        "head_sha": T5_HEAD,
        "manifest_sha256": T5_MANIFEST,
        "collection_count": 2246,
        "result_digest": T5_RESULT_DIGEST,
        "correctness_green": True,
        "protected_invariants_green": True,
        "execution_wall_clock_seconds": 449.0,
        "end_to_end_wall_clock_seconds": 452.0,
        "budget": 4,
    }
    payload.update(overrides)
    return payload


def test_t5_accepted_timing_keeps_queue_execution_and_end_to_end_separate():
    summary = summarize_workflow_timing(
        created_at="2026-09-16T16:55:22Z",
        first_required_job_started_at="2026-09-16T16:55:25Z",
        final_required_job_completed_at="2026-09-16T17:02:54Z",
    )
    assert summary == {
        "initial_queue_seconds": 3.0,
        "execution_wall_clock_seconds": 449.0,
        "end_to_end_wall_clock_seconds": 452.0,
    }


def test_job_wait_is_measured_independently_from_job_runtime():
    assert job_wait_seconds(
        created_at="2026-09-16T16:56:31Z",
        started_at="2026-09-16T16:58:44Z",
    ) == 133.0


def test_performance_contract_uses_12_minute_target_and_15_minute_hard_ceiling():
    assert classify_performance(720.0) == PERFORMANCE_TARGET_MET
    assert classify_performance(720.001) == PERFORMANCE_TARGET_MISSED
    assert classify_performance(900.0) == PERFORMANCE_TARGET_MISSED
    assert classify_performance(900.001) == PERFORMANCE_FAIL


def test_over_15_minutes_requires_explicit_infra_degradation_evidence_for_exception():
    assert classify_performance(901.0) == PERFORMANCE_FAIL
    assert (
        classify_performance(901.0, infra_degradation_evidence="github-status://incident-123")
        == PERFORMANCE_INFRA_EXCEPTION
    )
    with pytest.raises(TuningError):
        classify_performance(901.0, infra_degradation_evidence="   ")


@pytest.mark.parametrize(
    ("lane", "durations", "median", "ratio", "investigate"),
    [
        ("geometry", [8.0, 8.0, 7.0, 11.0], 8.0, 1.375, False),
        ("integration", [12.0, 7.0, 15.0, 8.0, 6.0, 12.0], 10.0, 1.5, False),
        ("synthetic-over", [10.0, 10.0, 18.0], 10.0, 1.8, True),
        ("synthetic-boundary", [10.0, 10.0, 17.5], 10.0, 1.75, False),
    ],
)
def test_large_lane_imbalance_gate_is_strictly_above_1_75x_median(
    lane, durations, median, ratio, investigate
):
    report = summarize_lane_imbalance(lane, durations)
    assert report["median_seconds"] == median
    assert report["max_to_median_ratio"] == pytest.approx(ratio)
    assert report["requires_investigation"] is investigate


def test_current_measured_large_lanes_keep_hrw_authority():
    reports = [
        summarize_lane_imbalance("geometry", [8.0, 8.0, 7.0, 11.0]),
        summarize_lane_imbalance("integration", [12.0, 7.0, 15.0, 8.0, 6.0, 12.0]),
        summarize_lane_imbalance("unit", [3.0, 5.0]),
        summarize_lane_imbalance("projection", [5.0, 4.0]),
        summarize_lane_imbalance("ui", [7.0, 8.0]),
    ]
    assert decide_manifest_strategy(reports) == KEEP_HRW


def test_any_measured_lane_over_threshold_requires_investigation_not_automatic_rebalance():
    reports = [summarize_lane_imbalance("integration", [10.0, 10.0, 18.0])]
    assert decide_manifest_strategy(reports) == INVESTIGATE_DURATION_IMBALANCE


def test_budget_ab_requires_same_head_manifest_collection_and_result_semantics():
    baseline = _measurement()
    for field, bad_value in (
        ("head_sha", "a" * 40),
        ("manifest_sha256", "b" * 64),
        ("collection_count", 2247),
        ("result_digest", "c" * 64),
        ("correctness_green", False),
        ("protected_invariants_green", False),
    ):
        candidate = deepcopy(baseline)
        candidate.update({"budget": 8, "execution_wall_clock_seconds": 400.0, field: bad_value})
        with pytest.raises(TuningError):
            choose_budget_from_ab(baseline, candidate, logical_shard_count=20)


def test_budget_ab_selects_candidate_only_on_measured_execution_improvement():
    baseline = _measurement()
    faster = _measurement(
        budget=8,
        execution_wall_clock_seconds=400.0,
        end_to_end_wall_clock_seconds=405.0,
    )
    decision = choose_budget_from_ab(baseline, faster, logical_shard_count=20)
    assert decision["selected_budget"] == 8
    assert decision["reason"] == "MEASURED_EXECUTION_IMPROVEMENT"

    slower = _measurement(
        budget=8,
        execution_wall_clock_seconds=470.0,
        end_to_end_wall_clock_seconds=475.0,
    )
    decision = choose_budget_from_ab(baseline, slower, logical_shard_count=20)
    assert decision["selected_budget"] == 4
    assert decision["reason"] == "NO_MEASURED_EXECUTION_IMPROVEMENT"


def test_budget_ab_rejects_invalid_or_oversubscribed_budget():
    baseline = _measurement()
    with pytest.raises(TuningError):
        choose_budget_from_ab(baseline, _measurement(budget=0), logical_shard_count=20)
    with pytest.raises(TuningError):
        choose_budget_from_ab(baseline, _measurement(budget=21), logical_shard_count=20)
