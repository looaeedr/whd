import json
from pathlib import Path

import pytest

from tools.issue311_t7_ab_acceptance import (
    ABParityError,
    build_legacy_evidence,
    build_optimized_evidence,
    compare_ab_evidence,
)


HEAD = "cf656c1efaf0e3f9c2a74330d7fb988847226db7"


def _evidence(**overrides):
    payload = {
        "head_sha": HEAD,
        "full_collection": ["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
        "failed_nodes": [
            {
                "nodeid": "tests/test_b.py::test_b",
                "reason": "EXPECTED_BASELINE_RED",
            }
        ],
        "allowed_skip_contract": [
            {"nodeid": "tests/test_a.py::test_a", "reason": "platform-contract"}
        ],
        "missing_nodes": [],
        "duplicate_nodes": [],
        "protected_drift": {},
        "execution_wall_clock_seconds": 392.0,
        "end_to_end_wall_clock_seconds": 396.0,
        "queue_seconds": 4.0,
    }
    payload.update(overrides)
    return payload


def test_exact_legacy_and_optimized_semantics_are_green():
    summary = compare_ab_evidence(_evidence(), _evidence())
    assert summary["decision"] == "GREEN"
    assert summary["head_sha"] == HEAD
    assert summary["full_collection_count"] == 2
    assert summary["failed_node_count"] == 1
    assert summary["allowed_skip_count"] == 1
    assert summary["new_missing_nodes"] == []
    assert summary["new_duplicate_nodes"] == []
    assert summary["protected_drift"] == {}


@pytest.mark.parametrize(
    ("field", "value", "token"),
    [
        ("head_sha", "a" * 40, "HEAD_SHA_MISMATCH"),
        ("full_collection", ["tests/test_a.py::test_a"], "FULL_COLLECTION_MISMATCH"),
        ("failed_nodes", [], "FAILED_NODE_SET_MISMATCH"),
        ("allowed_skip_contract", [], "ALLOWED_SKIP_CONTRACT_MISMATCH"),
        ("missing_nodes", ["tests/test_b.py::test_b"], "NEW_MISSING_NODES"),
        ("duplicate_nodes", ["tests/test_a.py::test_a"], "NEW_DUPLICATE_NODES"),
        ("protected_drift", {"config.ini": ["before", "after"]}, "PROTECTED_DRIFT"),
    ],
)
def test_any_parity_or_safety_violation_fails_closed(field, value, token):
    legacy = _evidence()
    optimized = _evidence(**{field: value})
    with pytest.raises(ABParityError, match=token):
        compare_ab_evidence(legacy, optimized)


def test_failure_identity_includes_canonical_reason_not_only_nodeid():
    optimized = _evidence(
        failed_nodes=[
            {
                "nodeid": "tests/test_b.py::test_b",
                "reason": "BROADER_UNCLASSIFIED_EXCEPTION",
            }
        ]
    )
    with pytest.raises(ABParityError, match="FAILED_NODE_SET_MISMATCH"):
        compare_ab_evidence(_evidence(), optimized)


def test_timing_requires_separate_execution_end_to_end_and_queue_metrics():
    for field in (
        "execution_wall_clock_seconds",
        "end_to_end_wall_clock_seconds",
        "queue_seconds",
    ):
        broken = _evidence()
        del broken[field]
        with pytest.raises(ABParityError, match="TIMING_EVIDENCE_MISSING"):
            compare_ab_evidence(_evidence(), broken)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _junit(cases: str) -> str:
    return f'<testsuites><testsuite>{cases}</testsuite></testsuites>'


def _pass_case(module: str, name: str) -> str:
    return f'<testcase classname="{module}" name="{name}" time="0.1" />'


def _skip_case(module: str, name: str, reason: str) -> str:
    return (
        f'<testcase classname="{module}" name="{name}" time="0.0">'
        f'<skipped type="pytest.skip" message="{reason}" />'
        '</testcase>'
    )


def _fail_case(module: str, name: str) -> str:
    return (
        f'<testcase classname="{module}" name="{name}" time="0.2">'
        '<failure message="AssertionError">trace</failure>'
        '</testcase>'
    )


def test_legacy_and_optimized_artifacts_normalize_to_same_semantics(tmp_path):
    a = "tests/test_a.py::test_a"
    b = "tests/test_b.py::test_b"
    c = "tests/test_c.py::test_c"
    skip_reason = "requires display"

    legacy = tmp_path / "legacy"
    _write(legacy / "full-collection.txt", f"{a}\n{b}\n{c}\n")
    _write(legacy / "collection-unit.txt", f"{a}\n{b}\n")
    _write(legacy / "collection-xvfb_ui.txt", f"{c}\n")
    _write(
        legacy / "unit.xml",
        _junit(_pass_case("tests.test_a", "test_a") + _skip_case("tests.test_b", "test_b", skip_reason)),
    )
    _write(legacy / "xvfb_ui.xml", _junit(_fail_case("tests.test_c", "test_c")))
    _write(
        legacy / "lane-summary.json",
        json.dumps(
            {
                "lanes": {
                    "unit": {"failed_nodes": []},
                    "xvfb_ui": {"failed_nodes": [c]},
                }
            }
        ),
    )
    _write(
        legacy / "lane-membership.json",
        json.dumps({"missing_from_union": [], "extra_in_union": []}),
    )
    _write(
        legacy / "timing-summary.json",
        json.dumps(
            {
                "queue_delay_seconds": 3.0,
                "execution_wall_clock_seconds": 100.0,
                "end_to_end_wall_clock_seconds": 103.0,
            }
        ),
    )
    for stem in ("tracked", "config-dxf"):
        _write(legacy / f"{stem}-before.sha256", "same\n")
        _write(legacy / f"{stem}-after.sha256", "same\n")
    contract = tmp_path / "failure-contract.json"
    _write(contract, json.dumps({"failures": {c: {"exception_type": "AssertionError"}}}))

    optimized = tmp_path / "optimized"
    plan = optimized / "plan"
    aggregate = optimized / "aggregate"
    timing = optimized / "timing"
    nongui = optimized / "all-nongui" / "issue311-nongui-unit-s00"
    xvfb = optimized / "all-xvfb" / "issue311-xvfb-s00"
    _write(
        plan / "manifest" / "shard-manifest.json",
        json.dumps(
            {
                "source_sha": HEAD,
                "shards": {
                    "unit": {"s00": {"count": 2, "nodes": [a, b]}},
                    "xvfb_ui": {"s00": {"count": 1, "nodes": [c]}},
                },
            }
        ),
    )
    _write(nongui / "shard-result.json", json.dumps({"assigned_nodes": [a, b]}))
    _write(
        nongui / "result.xml",
        _junit(_pass_case("tests.test_a", "test_a") + _skip_case("tests.test_b", "test_b", skip_reason)),
    )
    _write(xvfb / "result.json", json.dumps({"assigned_nodes": [c]}))
    _write(xvfb / "result.xml", _junit(_fail_case("tests.test_c", "test_c")))
    for root in (nongui, xvfb):
        _write(root / "protected-before.sha256", "same\n")
        _write(root / "protected-after.sha256", "same\n")
    _write(
        aggregate / "aggregation.json",
        json.dumps(
            {
                "source_sha": HEAD,
                "decision": "GREEN",
                "failures": [{"node": c, "classification": "INHERITED_BASELINE_RED"}],
            }
        ),
    )
    _write(
        timing / "timing.json",
        json.dumps(
            {
                "source_sha": HEAD,
                "initial_queue_seconds": 2.0,
                "execution_wall_clock_seconds": 50.0,
                "end_to_end_wall_clock_seconds": 52.0,
            }
        ),
    )

    old = build_legacy_evidence(legacy, contract, head_sha=HEAD)
    new = build_optimized_evidence(
        plan_root=plan,
        aggregate_root=aggregate,
        timing_root=timing,
        non_gui_root=optimized / "all-nongui",
        xvfb_root=optimized / "all-xvfb",
        head_sha=HEAD,
    )
    assert old["allowed_skip_contract"] == [{"nodeid": b, "reason": skip_reason}]
    assert new["allowed_skip_contract"] == old["allowed_skip_contract"]
    assert old["failed_nodes"] == [{"nodeid": c, "reason": "INHERITED_BASELINE_RED"}]
    assert new["failed_nodes"] == old["failed_nodes"]
    assert compare_ab_evidence(old, new)["decision"] == "GREEN"
