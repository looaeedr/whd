# -*- coding: utf-8 -*-
"""Strict, synthetic evidence tests; actual latency is measured only by Tk CI."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.merge_whd_performance_baseline import (
    combine_baselines, combine_isolated_sample_baselines,
)
from tools.whd_performance_baseline import summarize


HEAD = "ab" * 20


def _scope(bay: int) -> dict:
    rows = [
        {
            "bays": bay, "operation": "open_true_2d", "cache_state": "warm",
            "status": "ok", "wall_ms": float(1000 + bay + i),
        }
        for i in range(15)
    ]
    return {
        "metadata": {
            "source_sha": HEAD,
            "bay_scope": bay,
            "samples": 3,
            "cycles": 5,
            "config_sha256": "config",
            "harness_sha256": "harness",
            "pending": ["DXF source index/path not supplied; no DXF latency claim"],
            "workers": [
                {"bays": bay, "sample": i, "returncode": 0,
                 "journal": f"baseline-b{bay}-b{bay}-s{i}.jsonl"}
                for i in range(3)
            ],
        },
        "summary": summarize(rows),
        "rows": rows,
    }


def _both() -> dict:
    return {3: _scope(3), 1: _scope(1)}


def test_combines_all_six_real_worker_slots_without_faking_measurements():
    source = _both()
    result = combine_baselines(source, head_sha=HEAD)
    assert len(result["metadata"]["workers"]) == 6
    assert len(result["rows"]) == 30
    assert {row["bays"] for row in result["rows"]} == {1, 3}
    assert {entry["bays"] for entry in result["summary"]} == {1, 3}
    assert result["metadata"]["independent_runners"] is True
    assert result["metadata"]["environment_files"] == {
        "3": "b3/environment.txt", "1": "b1/environment.txt",
    }
    assert result["metadata"]["source_sha"] == HEAD
    assert result["metadata"]["bay_scope"] is None
    assert source[3]["metadata"]["bay_scope"] == 3  # no input mutation
    assert sum(row["wall_ms"] for row in result["rows"]) == sum(
        row["wall_ms"] for data in source.values() for row in data["rows"]
    )


@pytest.mark.parametrize("change,reason", [
    ("missing_bay", "BASELINE_BAY_SCOPES_INCOMPLETE"),
    ("extra_bay", "BASELINE_BAY_SCOPES_INCOMPLETE"),
    ("wrong_sha", "BASELINE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_scope", "BASELINE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_cycles", "BASELINE_SCOPE_OR_REVISION_MISMATCH"),
    ("different_harness", "BASELINE_HARNESS_OR_CONFIG_MISMATCH"),
    ("missing_worker", "BASELINE_WORKERS_INCOMPLETE"),
    ("duplicate_worker", "BASELINE_WORKERS_INCOMPLETE"),
    ("failed_worker", "BASELINE_WORKERS_INCOMPLETE"),
    ("failed_measurement", "BASELINE_MEASUREMENTS_INCOMPLETE"),
    ("wrong_row_bay", "BASELINE_MEASUREMENTS_INCOMPLETE"),
    ("tampered_summary", "BASELINE_SCOPE_SUMMARY_MISMATCH"),
])
def test_refuses_partial_or_untrustworthy_combined_baseline(change, reason):
    inputs = deepcopy(_both())
    if change == "missing_bay":
        del inputs[1]
    elif change == "extra_bay":
        inputs[2] = _scope(2)
    elif change == "wrong_sha":
        inputs[1]["metadata"]["source_sha"] = "other"
    elif change == "wrong_scope":
        inputs[1]["metadata"]["bay_scope"] = 3
    elif change == "wrong_cycles":
        inputs[1]["metadata"]["cycles"] = 4
    elif change == "different_harness":
        inputs[1]["metadata"]["harness_sha256"] = "other"
    elif change == "missing_worker":
        inputs[1]["metadata"]["workers"].pop()
    elif change == "duplicate_worker":
        inputs[1]["metadata"]["workers"][2]["sample"] = 0
    elif change == "failed_worker":
        inputs[1]["metadata"]["workers"][2]["returncode"] = 1
    elif change == "failed_measurement":
        inputs[1]["rows"][0]["status"] = "failure"
    elif change == "wrong_row_bay":
        inputs[1]["rows"][0]["bays"] = 3
    elif change == "tampered_summary":
        inputs[1]["summary"][0]["median_ms"] = -1

    with pytest.raises(ValueError, match=reason):
        combine_baselines(inputs, head_sha=HEAD)


def test_baseline_cli_preserves_unfiltered_legacy_mode():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1]
              / "tools/whd_performance_baseline.py").read_text(encoding="utf-8")
    assert "choices=(1, 3), default=None" in script
    assert "if args.bay_scope is not None else (3, 1)" in script
    assert "for sample in range(args.samples)" in script


def _isolated() -> dict[tuple[int, int], dict]:
    result = {}
    for bay in (3, 1):
        for sample in range(3):
            item = _scope(bay)
            item["metadata"]["sample_index"] = sample
            item["metadata"]["workers"] = [item["metadata"]["workers"][sample]]
            item["rows"] = [
                {**row, "worker_sample": sample}
                for row in item["rows"][sample * 5:(sample + 1) * 5]
            ]
            item["summary"] = summarize(item["rows"])
            result[(bay, sample)] = item
    return result


def test_six_independent_worker_samples_merge_without_deleting_measurements():
    shards = _isolated()
    result = combine_isolated_sample_baselines(shards, head_sha=HEAD)
    assert result["metadata"]["independent_sample_runners"] is True
    assert result["metadata"]["independent_runners"] is True
    assert len(result["metadata"]["sample_environment_files"]) == 6
    assert result["metadata"]["environment_files"] == {
        "3": "whd-issue1816-tk-baseline-b3-s0/environment.txt",
        "1": "whd-issue1816-tk-baseline-b1-s0/environment.txt",
    }
    assert len(result["metadata"]["workers"]) == 6
    assert len(result["rows"]) == 30
    assert result["metadata"]["source_sha"] == HEAD
    assert {(row["bays"], row["worker_sample"]) for row in result["rows"]} == {
        (bay, sample) for bay in (1, 3) for sample in range(3)
    }
    assert sum(row["wall_ms"] for row in result["rows"]) == sum(
        row["wall_ms"] for shard in shards.values() for row in shard["rows"]
    )
    assert shards[(3, 0)]["metadata"]["sample_index"] == 0


@pytest.mark.parametrize("change,reason", [
    ("missing", "BASELINE_SAMPLE_SHARDS_INCOMPLETE"),
    ("extra", "BASELINE_SAMPLE_SHARDS_INCOMPLETE"),
    ("wrong_sha", "BASELINE_SAMPLE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_index", "BASELINE_SAMPLE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_cycles", "BASELINE_SAMPLE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_scope", "BASELINE_SAMPLE_SCOPE_OR_REVISION_MISMATCH"),
    ("wrong_harness", "BASELINE_HARNESS_OR_CONFIG_MISMATCH"),
    ("missing_worker", "BASELINE_SAMPLE_WORKER_INVALID"),
    ("wrong_worker_sample", "BASELINE_SAMPLE_WORKER_INVALID"),
    ("failed_worker", "BASELINE_SAMPLE_WORKER_INVALID"),
    ("wrong_measurement_sample", "BASELINE_SAMPLE_MEASUREMENTS_INVALID"),
    ("failed_measurement", "BASELINE_SAMPLE_MEASUREMENTS_INVALID"),
    ("tampered_summary", "BASELINE_SAMPLE_SUMMARY_MISMATCH"),
])
def test_rejects_missing_or_unreliable_parallel_tk_samples(change, reason):
    shards = deepcopy(_isolated())
    shard = shards[(3, 1)]
    if change == "missing":
        del shards[(3, 1)]
    elif change == "extra":
        shards[(3, 3)] = deepcopy(shard)
    elif change == "wrong_sha":
        shard["metadata"]["source_sha"] = "different-head"
    elif change == "wrong_index":
        shard["metadata"]["sample_index"] = 0
    elif change == "wrong_cycles":
        shard["metadata"]["cycles"] = 4
    elif change == "wrong_scope":
        shard["metadata"]["bay_scope"] = 1
    elif change == "wrong_harness":
        shard["metadata"]["harness_sha256"] = "different-harness"
    elif change == "missing_worker":
        shard["metadata"]["workers"] = []
    elif change == "wrong_worker_sample":
        shard["metadata"]["workers"][0]["sample"] = 0
    elif change == "failed_worker":
        shard["metadata"]["workers"][0]["returncode"] = 1
    elif change == "wrong_measurement_sample":
        shard["rows"][0]["worker_sample"] = 2
    elif change == "failed_measurement":
        shard["rows"][0]["status"] = "failed"
    elif change == "tampered_summary":
        shard["summary"][0]["median_ms"] = -1.0
    with pytest.raises(ValueError, match=reason):
        combine_isolated_sample_baselines(shards, head_sha=HEAD)


def test_new_baseline_cli_supports_one_real_worker_and_preserves_legacy_path():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1]
              / "tools/whd_performance_baseline.py").read_text(encoding="utf-8")
    assert "--sample-index" in script
    assert "args.sample_index is not None and args.bay_scope is None" in script
    assert "for sample in ((args.sample_index,) if args.sample_index is not None else range(args.samples))" in script
    assert "if args.bay_scope is not None else (3, 1)" in script
