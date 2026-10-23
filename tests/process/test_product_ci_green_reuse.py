import io
import json
from unittest.mock import patch

from tools.product_ci_green_reuse import (
    CHECK_NAME,
    _prior_green,
    decide_green_reuse,
    dependency_impact,
    surface,
)

# Issue 1302: first candidate must run full regression; only target-sync commits may reuse GREEN.


def test_governance_candidate_can_reuse_green_across_unrelated_product_target_drift():
    candidate = {
        ".agents/skills/engineering/root-local-first/SKILL.md",
        "tools/change_test_profile.py",
        "tests/process/test_localx_publish_gate.py",
    }
    target = {
        "gui_modules/application/receiving_set_bay_controls.py",
        "fold_designer_bridge.py",
    }
    assert dependency_impact(candidate, target) is False
    reuse, reason = decide_green_reuse(
        prior_green=True,
        candidate_paths=candidate,
        target_paths=target,
        prior_patch_digest="a" * 64,
        current_patch_digest="a" * 64,
    )
    assert reuse is True
    assert reason == "GREEN_REUSED_NO_RETEST"


def test_overlap_requires_retest():
    reuse, reason = decide_green_reuse(
        prior_green=True,
        candidate_paths={"gui_modules/a.py"},
        target_paths={"gui_modules/a.py"},
        prior_patch_digest="a" * 64,
        current_patch_digest="a" * 64,
    )
    assert reuse is False
    assert reason == "TARGET_DRIFT_OVERLAPS_CANDIDATE_PATHS"


def test_same_dependency_surface_requires_retest_even_without_exact_overlap():
    assert dependency_impact(
        {"gui_modules/a.py"},
        {"ae_engine/b.py"},
    ) is True


def test_global_test_contract_drift_requires_retest():
    assert dependency_impact(
        {".agents/contracts/example.json"},
        {"requirements.txt"},
    ) is True
    assert surface(".github/workflows/whd-product-regression.yml") == "global"
    assert surface("tools/whd_v15_acceptance_evidence.py") == "global"
    assert surface("tools/product_ci_green_reuse.py") == "global"
    assert surface("tests/governance/test_rules.py") == "governance"
    assert surface("tests/knowledge/test_docs.py") == "governance"


def test_prior_green_rejects_failed_latest_rerun_and_paginates():
    class _FakeResp:
        def __init__(self, data):
            self._buf = io.BytesIO(json.dumps(data).encode("utf-8"))

        def __enter__(self):
            return self._buf

        def __exit__(self, *args):
            return False

    rerun_failed = {
        "check_runs": [
            {"id": 10, "name": CHECK_NAME, "status": "completed", "conclusion": "success"},
            {"id": 20, "name": CHECK_NAME, "status": "completed", "conclusion": "failure"},
        ]
    }
    with patch("urllib.request.urlopen", return_value=_FakeResp(rerun_failed)):
        assert _prior_green("looaeedr/whd", "a" * 40, "tok") is False

    page1 = {
        "check_runs": [
            {"id": i, "name": f"other-{i}", "status": "completed", "conclusion": "success"}
            for i in range(100)
        ]
    }
    page2 = {
        "check_runs": [
            {"id": 101, "name": CHECK_NAME, "status": "completed", "conclusion": "success"}
        ]
    }
    with patch("urllib.request.urlopen", side_effect=[_FakeResp(page1), _FakeResp(page2)]):
        assert _prior_green("looaeedr/whd", "a" * 40, "tok") is True


def test_patch_identity_change_requires_retest():
    reuse, reason = decide_green_reuse(
        prior_green=True,
        candidate_paths={"tests/process/a.py"},
        target_paths={"gui_modules/b.py"},
        prior_patch_digest="a" * 64,
        current_patch_digest="b" * 64,
    )
    assert reuse is False
    assert reason == "CANDIDATE_PATCH_IDENTITY_CHANGED"


def test_missing_prior_green_requires_retest():
    reuse, reason = decide_green_reuse(
        prior_green=False,
        candidate_paths={"tests/process/a.py"},
        target_paths={"gui_modules/b.py"},
        prior_patch_digest="a" * 64,
        current_patch_digest="a" * 64,
    )
    assert reuse is False
    assert reason == "PRIOR_REQUIRED_CHECK_NOT_GREEN"


def test_unknown_general_surface_is_conservative_and_retests():
    assert dependency_impact(
        {"some_new_top_level/file.txt"},
        {"gui_modules/b.py"},
    ) is True
