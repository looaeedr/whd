from __future__ import annotations

from pathlib import Path

import pytest

from tools.test_shard_aggregation import (
    AggregationError,
    aggregate_shard_results,
    normalize_shard_artifact,
    render_unified_summary,
)


def _manifest() -> dict[str, object]:
    return {
        "schema": "WHD_TEST_SHARD_MANIFEST_V1",
        "source_sha": "accepted-t3",
        "full_collection_count": 4,
        "full_collection_sha256": "full-digest",
        "reconciliation": {
            "full_count": 4,
            "lane_union_count": 4,
            "unique_shard_union_count": 4,
            "lane_missing": [],
            "lane_extra": [],
            "lane_duplicate": {},
            "shard_missing": [],
            "shard_extra": [],
            "shard_duplicate": {},
        },
        "shards": {
            "unit": {
                "s00": {
                    "count": 2,
                    "nodes": ["tests/a.py::test_a", "tests/b.py::test_b"],
                }
            },
            "xvfb_ui": {
                "s00": {
                    "count": 2,
                    "nodes": ["tests/c.py::test_c", "tests/d.py::test_d"],
                }
            },
        },
    }


def _record(
    outcome: str,
    *,
    duration: float = 0.1,
    classification: str | None = None,
    error_excerpt: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "outcome": outcome,
        "duration_seconds": duration,
    }
    if classification is not None:
        record["classification"] = classification
    if error_excerpt is not None:
        record["error_excerpt"] = error_excerpt
    return record


def _results() -> list[dict[str, object]]:
    return [
        {
            "lane": "unit",
            "shard_id": "s00",
            "source_sha": "accepted-t3",
            "assigned_nodes": ["tests/a.py::test_a", "tests/b.py::test_b"],
            "node_results": {
                "tests/a.py::test_a": _record("passed", duration=0.11),
                "tests/b.py::test_b": _record("skipped", duration=0.02),
            },
            "execution_seconds": 1.2,
            "artifact_refs": ["artifact://unit-s00"],
        },
        {
            "lane": "xvfb_ui",
            "shard_id": "s00",
            "source_sha": "accepted-t3",
            "assigned_nodes": ["tests/c.py::test_c", "tests/d.py::test_d"],
            "node_results": {
                "tests/c.py::test_c": _record("passed", duration=0.2),
                "tests/d.py::test_d": _record(
                    "failed",
                    duration=0.3,
                    classification="INHERITED_BASELINE_RED",
                    error_excerpt="AssertionError: accepted baseline",
                ),
            },
            "execution_seconds": 2.4,
            "artifact_refs": ["artifact://xvfb-s00"],
        },
    ]


def _invariants() -> dict[str, dict[str, str]]:
    return {
        "config.ini": {"before": "cfg", "after": "cfg"},
        "protected-dxf": {"before": "dxf", "after": "dxf"},
    }


def test_aggregate_reconciles_manifest_nodes_counts_owners_and_inherited_red() -> None:
    summary = aggregate_shard_results(
        manifest=_manifest(),
        shard_results=_results(),
        expected_source_sha="accepted-t3",
        protected_invariants=_invariants(),
    )

    assert summary["decision"] == "GREEN"
    assert summary["full_collection_count"] == 4
    assert summary["executed_unique_count"] == 4
    assert summary["counts"] == {
        "passed": 2,
        "failed": 1,
        "errors": 0,
        "skipped": 1,
    }
    assert summary["failures"] == [
        {
            "node": "tests/d.py::test_d",
            "lane": "xvfb_ui",
            "shard_id": "s00",
            "first_run_outcome": "failed",
            "classification": "INHERITED_BASELINE_RED",
            "retry_outcome": None,
            "retry_state": None,
            "error_excerpt": "AssertionError: accepted baseline",
            "artifact_refs": ["artifact://xvfb-s00"],
        }
    ]


def test_missing_expected_shard_fails_closed() -> None:
    with pytest.raises(AggregationError, match="MISSING_SHARD"):
        aggregate_shard_results(
            manifest=_manifest(),
            shard_results=_results()[:1],
            expected_source_sha="accepted-t3",
            protected_invariants=_invariants(),
        )


def test_duplicate_node_execution_fails_closed() -> None:
    results = _results()
    results[1]["assigned_nodes"] = ["tests/c.py::test_c", "tests/a.py::test_a"]
    results[1]["node_results"] = {
        "tests/c.py::test_c": _record("passed"),
        "tests/a.py::test_a": _record("passed"),
    }
    with pytest.raises(AggregationError, match="DUPLICATE_NODE"):
        aggregate_shard_results(
            manifest=_manifest(),
            shard_results=results,
            expected_source_sha="accepted-t3",
            protected_invariants=_invariants(),
        )


def test_missing_node_terminal_result_fails_closed() -> None:
    results = _results()
    del results[0]["node_results"]["tests/b.py::test_b"]
    with pytest.raises(AggregationError, match="MISSING_NODE"):
        aggregate_shard_results(
            manifest=_manifest(),
            shard_results=results,
            expected_source_sha="accepted-t3",
            protected_invariants=_invariants(),
        )


def test_unclassified_red_is_preserved_and_makes_decision_fail() -> None:
    results = _results()
    results[0]["node_results"]["tests/a.py::test_a"] = _record(
        "failed", error_excerpt="RuntimeError: new regression"
    )
    summary = aggregate_shard_results(
        manifest=_manifest(),
        shard_results=results,
        expected_source_sha="accepted-t3",
        protected_invariants=_invariants(),
    )

    assert summary["decision"] == "FAIL"
    failure = next(item for item in summary["failures"] if item["node"] == "tests/a.py::test_a")
    assert failure["first_run_outcome"] == "failed"
    assert failure["classification"] == "UNCLASSIFIED_RED"


def test_retry_green_never_erases_first_run_red_and_surfaces_flaky_warning() -> None:
    results = _results()
    results[0]["node_results"]["tests/a.py::test_a"] = _record(
        "failed", error_excerpt="AssertionError: transient first run"
    )
    summary = aggregate_shard_results(
        manifest=_manifest(),
        shard_results=results,
        expected_source_sha="accepted-t3",
        protected_invariants=_invariants(),
        retry_results={
            "tests/a.py::test_a": _record("passed", duration=0.04),
        },
    )

    assert summary["decision"] == "FAIL"
    failure = next(item for item in summary["failures"] if item["node"] == "tests/a.py::test_a")
    assert failure["first_run_outcome"] == "failed"
    assert failure["retry_outcome"] == "passed"
    assert failure["retry_state"] == "[FLAKY-WARNING]"
    assert "[FLAKY-WARNING]" in summary["warnings"]

    markdown = render_unified_summary(summary)
    assert "[FLAKY-WARNING]" in markdown
    assert "tests/a.py::test_a" in markdown
    assert "unit:s00" in markdown
    assert "artifact://unit-s00" in markdown


def test_protected_invariant_drift_fails_closed() -> None:
    invariants = _invariants()
    invariants["config.ini"]["after"] = "changed"
    with pytest.raises(AggregationError, match="PROTECTED_INVARIANT_DRIFT"):
        aggregate_shard_results(
            manifest=_manifest(),
            shard_results=_results(),
            expected_source_sha="accepted-t3",
            protected_invariants=invariants,
        )


def test_summary_contains_tested_sha_reconciliation_lane_and_shard_durations() -> None:
    summary = aggregate_shard_results(
        manifest=_manifest(),
        shard_results=_results(),
        expected_source_sha="accepted-t3",
        protected_invariants=_invariants(),
    )
    markdown = render_unified_summary(summary)

    assert "accepted-t3" in markdown
    assert "4 / 4" in markdown
    assert "unit" in markdown
    assert "xvfb_ui" in markdown
    assert "unit:s00" in markdown
    assert "xvfb_ui:s00" in markdown
    assert "1.200" in markdown
    assert "2.400" in markdown


def test_t2_artifact_normalization_binds_run_sha_and_reconciles_junit(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="1" time="0.13">'
        '<testcase classname="tests.a" name="test_a" time="0.11" />'
        '<testcase classname="tests.b" name="test_b" time="0.02"><skipped /></testcase>'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    payload = {
        "lane": "unit",
        "shard_id": "s00",
        "assigned_nodes": ["tests/a.py::test_a", "tests/b.py::test_b"],
        "assigned_count": 2,
        "child_rc": 0,
        "execution_seconds": 1.2,
        "tests": 2,
        "passed": 1,
        "failures": 0,
        "errors": 0,
        "skipped": 1,
    }

    normalized = normalize_shard_artifact(
        result_payload=payload,
        junit_xml=xml,
        expected_source_sha="accepted-t4",
        artifact_refs=["artifact://issue306-unit-s00"],
    )

    assert normalized["source_sha"] == "accepted-t4"
    assert normalized["lane"] == "unit"
    assert normalized["shard_id"] == "s00"
    assert normalized["node_results"] == {
        "tests/a.py::test_a": {"outcome": "passed", "duration_seconds": 0.11},
        "tests/b.py::test_b": {"outcome": "skipped", "duration_seconds": 0.02},
    }
    assert normalized["artifact_refs"] == ["artifact://issue306-unit-s00"]


def test_t3_artifact_normalization_preserves_inherited_red_classification(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite tests="2" failures="1" errors="0" skipped="0" time="0.50">'
        '<testcase classname="tests.c" name="test_c" time="0.20" />'
        '<testcase classname="tests.d" name="test_d" time="0.30">'
        '<failure message="AssertionError: accepted baseline">tests/d.py:17: AssertionError</failure>'
        '</testcase>'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    payload = {
        "lane": "xvfb_ui",
        "shard_id": "s00",
        "source_sha": "accepted-t4",
        "assigned_nodes": ["tests/c.py::test_c", "tests/d.py::test_d"],
        "executed_nodes": ["tests/c.py::test_c", "tests/d.py::test_d"],
        "assigned_count": 2,
        "child_rc": 1,
        "classification": "INHERITED_BASELINE_RED",
        "failed_nodes": ["tests/d.py::test_d"],
        "execution_seconds": 2.4,
        "passed": 1,
        "failures": 1,
        "errors": 0,
        "skipped": 0,
    }

    normalized = normalize_shard_artifact(
        result_payload=payload,
        junit_xml=xml,
        expected_source_sha="accepted-t4",
        artifact_refs=["artifact://issue307-xvfb-s00"],
    )

    failed = normalized["node_results"]["tests/d.py::test_d"]
    assert failed["outcome"] == "failed"
    assert failed["classification"] == "INHERITED_BASELINE_RED"
    assert failed["error_excerpt"] == "AssertionError: accepted baseline"


def test_artifact_normalization_rejects_stale_embedded_source_sha(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="tests.a" name="test_a" time="0.01" />'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    payload = {
        "lane": "unit",
        "shard_id": "s00",
        "source_sha": "stale",
        "assigned_nodes": ["tests/a.py::test_a"],
        "passed": 1,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    with pytest.raises(AggregationError, match="RESULT_SOURCE_SHA_MISMATCH"):
        normalize_shard_artifact(
            result_payload=payload,
            junit_xml=xml,
            expected_source_sha="accepted-t4",
        )


def test_artifact_normalization_rejects_missing_junit_node(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="tests.a" name="test_a" time="0.01" />'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    payload = {
        "lane": "unit",
        "shard_id": "s00",
        "assigned_nodes": ["tests/a.py::test_a", "tests/b.py::test_b"],
        "passed": 1,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    with pytest.raises(AggregationError, match="JUNIT_MISSING_NODE"):
        normalize_shard_artifact(
            result_payload=payload,
            junit_xml=xml,
            expected_source_sha="accepted-t4",
        )


def test_artifact_normalization_rejects_result_vs_junit_count_drift(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="tests.a" name="test_a" time="0.01" />'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    payload = {
        "lane": "unit",
        "shard_id": "s00",
        "assigned_nodes": ["tests/a.py::test_a"],
        "passed": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 1,
    }
    with pytest.raises(AggregationError, match="RESULT_JUNIT_COUNT_MISMATCH"):
        normalize_shard_artifact(
            result_payload=payload,
            junit_xml=xml,
            expected_source_sha="accepted-t4",
        )
