import pytest

from tools.issue311_t7_ab_acceptance import ABParityError, compare_ab_evidence


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
