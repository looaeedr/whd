from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tools.test_shard_execution import (
    ExecutionError,
    build_non_xvfb_matrix,
    parse_junit_counts,
    select_lane_nodes,
    select_shard_nodes,
)
from tools.test_shard_aggregate import AggregationError, reconcile_shard_results


def _manifest() -> dict[str, object]:
    return {
        "schema": "WHD_TEST_SHARD_MANIFEST_V1",
        "source_sha": "abc123",
        "shards": {
            "governance": {
                "s00": {"count": 1, "nodes": ["tests/g.py::test_g"]},
            },
            "unit": {
                "s00": {"count": 2, "nodes": ["tests/u.py::test_a", "tests/u.py::test_b"]},
                "s01": {"count": 1, "nodes": ["tests/u.py::test_c"]},
            },
            "integration": {
                "s00": {"count": 1, "nodes": ["tests/i.py::test_i"]},
            },
            "xvfb_ui": {
                "s00": {"count": 1, "nodes": ["tests/x.py::test_x"]},
                "s01": {"count": 1, "nodes": ["tests/x.py::test_y"]},
            },
        },
    }


def test_matrix_uses_manifest_ownership_and_excludes_xvfb() -> None:
    plan = build_non_xvfb_matrix(_manifest(), concurrency_budget=2)
    assert plan.max_parallel == 2
    assert [(entry["lane"], entry["shard_id"], entry["node_count"]) for entry in plan.matrix] == [
        ("governance", "s00", 1),
        ("integration", "s00", 1),
        ("unit", "s00", 2),
        ("unit", "s01", 1),
    ]
    assert all(entry["lane"] != "xvfb_ui" for entry in plan.matrix)
    assert all("nodes" not in entry for entry in plan.matrix)


def test_concurrency_budget_does_not_change_matrix_ownership() -> None:
    one = build_non_xvfb_matrix(_manifest(), concurrency_budget=1)
    four = build_non_xvfb_matrix(_manifest(), concurrency_budget=4)
    assert one.matrix == four.matrix
    assert one.max_parallel == 1
    assert four.max_parallel == 4


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "4"])
def test_invalid_concurrency_budget_fails_closed(budget: object) -> None:
    with pytest.raises(ExecutionError, match="INVALID_CONCURRENCY_BUDGET"):
        build_non_xvfb_matrix(_manifest(), concurrency_budget=budget)  # type: ignore[arg-type]


def test_node_selection_is_exact_and_t2_refuses_xvfb() -> None:
    assert select_shard_nodes(_manifest(), "unit", "s00") == [
        "tests/u.py::test_a",
        "tests/u.py::test_b",
    ]
    assert select_lane_nodes(_manifest(), "unit") == [
        "tests/u.py::test_a",
        "tests/u.py::test_b",
        "tests/u.py::test_c",
    ]
    with pytest.raises(ExecutionError, match="XVFB_FORBIDDEN_IN_T2"):
        select_lane_nodes(_manifest(), "xvfb_ui")
    with pytest.raises(ExecutionError, match="UNKNOWN_SHARD"):
        select_shard_nodes(_manifest(), "unit", "s99")
    with pytest.raises(ExecutionError, match="UNKNOWN_LANE"):
        select_lane_nodes(_manifest(), "missing")


def _write_junit(path: Path, *, tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    root = ET.Element(
        "testsuite",
        tests=str(tests),
        failures=str(failures),
        errors=str(errors),
        skipped=str(skipped),
        time="1.25",
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_junit_counts_require_exact_assigned_testcase_count(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    _write_junit(xml, tests=2, skipped=1)
    summary = parse_junit_counts(xml, assigned_count=2)
    assert summary == {
        "tests": 2,
        "passed": 1,
        "failures": 0,
        "errors": 0,
        "skipped": 1,
        "junit_time_seconds": 1.25,
    }
    with pytest.raises(ExecutionError, match="JUNIT_COUNT_MISMATCH"):
        parse_junit_counts(xml, assigned_count=3)


def _result(lane: str, shard: str, nodes: list[str], *, passed: int, skipped: int = 0) -> dict[str, object]:
    return {
        "lane": lane,
        "shard_id": shard,
        "assigned_nodes": nodes,
        "assigned_count": len(nodes),
        "tests": len(nodes),
        "passed": passed,
        "failures": 0,
        "errors": 0,
        "skipped": skipped,
        "child_rc": 0,
        "execution_seconds": 0.5,
    }


def _reference() -> dict[str, dict[str, object]]:
    return {
        "governance": _result("governance", "serial", ["tests/g.py::test_g"], passed=1),
        "integration": _result("integration", "serial", ["tests/i.py::test_i"], passed=1),
        "unit": _result(
            "unit",
            "serial",
            ["tests/u.py::test_a", "tests/u.py::test_b", "tests/u.py::test_c"],
            passed=2,
            skipped=1,
        ),
    }


def _shard_results() -> list[dict[str, object]]:
    return [
        _result("governance", "s00", ["tests/g.py::test_g"], passed=1),
        _result("integration", "s00", ["tests/i.py::test_i"], passed=1),
        _result("unit", "s00", ["tests/u.py::test_a", "tests/u.py::test_b"], passed=1, skipped=1),
        _result("unit", "s01", ["tests/u.py::test_c"], passed=1),
    ]


def test_aggregate_proves_exact_union_and_lane_result_parity() -> None:
    summary = reconcile_shard_results(_manifest(), _shard_results(), _reference())
    assert summary["expected_node_count"] == 5
    assert summary["executed_unique_node_count"] == 5
    assert summary["missing_nodes"] == []
    assert summary["extra_nodes"] == []
    assert summary["duplicate_nodes"] == {}
    assert summary["xvfb_executed_nodes"] == []
    assert summary["lane_result_parity"] is True


def test_aggregate_fails_closed_on_missing_duplicate_extra_or_semantic_drift() -> None:
    missing = _shard_results()[:-1]
    with pytest.raises(AggregationError, match="EXECUTION_MISSING"):
        reconcile_shard_results(_manifest(), missing, _reference())

    duplicate = _shard_results() + [_result("unit", "s99", ["tests/u.py::test_a"], passed=1)]
    with pytest.raises(AggregationError, match="EXECUTION_DUPLICATE"):
        reconcile_shard_results(_manifest(), duplicate, _reference())

    extra = _shard_results() + [_result("unit", "s99", ["tests/u.py::test_extra"], passed=1)]
    with pytest.raises(AggregationError, match="EXECUTION_EXTRA"):
        reconcile_shard_results(_manifest(), extra, _reference())

    semantic = _shard_results()
    semantic[-1] = dict(semantic[-1], passed=0, skipped=1)
    with pytest.raises(AggregationError, match="LANE_RESULT_MISMATCH"):
        reconcile_shard_results(_manifest(), semantic, _reference())


def test_aggregate_rejects_any_xvfb_execution() -> None:
    bad = _shard_results() + [_result("xvfb_ui", "s00", ["tests/x.py::test_x"], passed=1)]
    with pytest.raises(AggregationError, match="XVFB_EXECUTED_IN_T2"):
        reconcile_shard_results(_manifest(), bad, _reference())
