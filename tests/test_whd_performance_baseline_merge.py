# -*- coding: utf-8 -*-
"""Strict, synthetic evidence tests; actual latency is measured only by Tk CI."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.merge_whd_performance_baseline import combine_baselines
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
