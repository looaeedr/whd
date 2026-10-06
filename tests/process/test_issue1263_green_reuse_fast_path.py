import json
from pathlib import Path

from tools.root_local_first_gate import (
    GREEN_REUSE_RETEST,
    GREEN_REUSE_REUSED,
    GREEN_REUSE_REVALIDATE,
    classify_target_drift_action,
    validate_contract,
)


DIFF = "a" * 64
HEAD = "b" * 40
OLD_TARGET = "c" * 40
NEW_TARGET = "d" * 40


def _reuse_evidence(**overrides):
    evidence = {
        "schema": "WHD_GREEN_REUSE_REVALIDATION_V1",
        "status": "REUSE_GREEN",
        "fresh": True,
        "candidate_diff_digest": DIFF,
        "prior_green_head_sha": HEAD,
        "current_head_sha": HEAD,
        "prior_green_status": "GREEN",
        "prior_target_sha": OLD_TARGET,
        "fresh_target_sha": NEW_TARGET,
        "candidate_paths": ["fold_designer_bridge.py"],
        "target_changed_paths": ["docs/unrelated.md"],
        "dependency_impact": False,
        "test_profile_changed": False,
        "test_contract_changed": False,
        "exact_commands_unchanged": True,
        "extra_test_run_performed": False,
    }
    evidence.update(overrides)
    return evidence


def test_missing_reuse_evidence_revalidates_before_retest():
    result = classify_target_drift_action(
        target_drift=True,
        expected_diff_digest=DIFF,
    )
    assert result["classification"] == GREEN_REUSE_REVALIDATE
    assert result["retest_required"] is False
    assert result["extra_test_run"] is False


def test_non_impacting_target_drift_reuses_green_without_extra_test_run():
    result = classify_target_drift_action(
        target_drift=True,
        expected_diff_digest=DIFF,
        green_reuse_evidence=_reuse_evidence(),
    )
    assert result["classification"] == GREEN_REUSE_REUSED
    assert result["retest_required"] is False
    assert result["extra_test_run"] is False


def test_path_overlap_fails_closed_to_retest():
    result = classify_target_drift_action(
        target_drift=True,
        expected_diff_digest=DIFF,
        green_reuse_evidence=_reuse_evidence(
            target_changed_paths=["fold_designer_bridge.py"]
        ),
    )
    assert result["classification"] == GREEN_REUSE_RETEST
    assert result["retest_required"] is True


def test_candidate_head_change_fails_closed_to_retest():
    result = classify_target_drift_action(
        target_drift=True,
        expected_diff_digest=DIFF,
        green_reuse_evidence=_reuse_evidence(current_head_sha="e" * 40),
    )
    assert result["classification"] == GREEN_REUSE_RETEST


def test_dependency_or_test_contract_change_requires_retest():
    for update in (
        {"dependency_impact": True},
        {"test_profile_changed": True},
        {"test_contract_changed": True},
        {"exact_commands_unchanged": False},
    ):
        result = classify_target_drift_action(
            target_drift=True,
            expected_diff_digest=DIFF,
            green_reuse_evidence=_reuse_evidence(**update),
        )
        assert result["classification"] == GREEN_REUSE_RETEST


def test_current_contract_declares_no_extra_test_on_green_reuse():
    payload = json.loads(
        Path(".agents/contracts/WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    validated = validate_contract(payload)
    fast_path = validated["green_reuse_fast_path"]
    assert fast_path["extra_test_run_on_reuse"] is False
    assert fast_path["retest_when_any_impact"] is True
    assert validated["target_drift_action"] == "REVALIDATE_GREEN_REUSE_IF_UNCHANGED_ELSE_RETEST"
