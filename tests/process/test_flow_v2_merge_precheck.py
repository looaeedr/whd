from tools.flow_v2_merge_precheck import (
    PR_IDENTITY_MISMATCH,
    READY_TO_MERGE,
    REQUIRED_CHECKS_PENDING,
    TARGET_DRIFT,
    evaluate_merge_precheck,
)


HEAD = "a" * 40
TARGET = "b" * 40
NEW_TARGET = "c" * 40


def _evaluate(**overrides):
    kwargs = {
        "record_head_sha": HEAD,
        "record_target_branch": "cleanup/2d-3d-sync",
        "record_target_sha": TARGET,
        "pr_number": 891,
        "pr_state": "open",
        "pr_merged": False,
        "pr_head_sha": HEAD,
        "pr_base_branch": "cleanup/2d-3d-sync",
        "pr_base_sha": TARGET,
        "pr_mergeable": True,
        "observed_target_sha": TARGET,
        "required_checks": ["Governance Mirror Hard Gate"],
        "check_conclusions": {"Governance Mirror Hard Gate": "success"},
    }
    kwargs.update(overrides)
    return evaluate_merge_precheck(**kwargs)


def test_ready_requires_exact_live_target_and_required_checks():
    result = _evaluate()
    assert result.classification == READY_TO_MERGE
    assert result.missing_required_checks == ()


def test_target_drift_redirects_before_mergeability_or_check_errors():
    result = _evaluate(
        observed_target_sha=NEW_TARGET,
        pr_base_sha=NEW_TARGET,
        pr_mergeable=False,
        check_conclusions={"Governance Mirror Hard Gate": "failure"},
    )
    assert result.classification == TARGET_DRIFT
    assert result.observed_target_sha == NEW_TARGET


def test_missing_required_check_is_not_ready_to_merge():
    result = _evaluate(check_conclusions={})
    assert result.classification == REQUIRED_CHECKS_PENDING
    assert result.missing_required_checks == ("Governance Mirror Hard Gate",)


def test_pr_head_identity_mismatch_fails_before_merge():
    result = _evaluate(pr_head_sha="d" * 40)
    assert result.classification == PR_IDENTITY_MISMATCH
