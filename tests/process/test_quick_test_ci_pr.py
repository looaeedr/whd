"""Mandatory GitHub PR fast feedback must execute real, exact-head selectors."""
import json
import subprocess

import pytest

from tools import quick_test


BASE = "a" * 40
HEAD = "b" * 40


def _fake_pr(monkeypatch, tmp_path, changed, *, body="", base_ref="localX",
             checkout_head=HEAD, head=HEAD):
    event = {
        "pull_request": {
            "base": {"ref": base_ref, "sha": BASE},
            "head": {"sha": head},
            "body": body,
        }
    }
    source = tmp_path / "event.json"
    source.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(source))

    def fake_git(argv, *, capture_output, check):
        assert argv[:3] == ["git", "-C", str(tmp_path)]
        if argv[3:] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, (checkout_head + "\n").encode(), b"")
        if argv[3:8] == ["diff", "--no-ext-diff", "--name-only", "-z", BASE]:
            assert argv[8] == HEAD
            return subprocess.CompletedProcess(
                argv, 0, b"\x00".join(s.encode() for s in changed) + b"\x00", b""
            )
        raise AssertionError(f"unexpected Git command: {argv}")

    monkeypatch.setattr(quick_test.subprocess, "run", fake_git)
    return lambda: quick_test._ci_pr_inputs(tmp_path)


def test_ci_pr_requires_real_test_for_product_change(monkeypatch, tmp_path):
    select = _fake_pr(monkeypatch, tmp_path, ("gui_modules/application/custom_part_controls.py",))
    with pytest.raises(ValueError, match="CI_PR_FAST_FEEDBACK_REQUIRED"):
        select()


def test_ci_pr_selects_changed_regression_and_existing_compat(monkeypatch, tmp_path):
    select = _fake_pr(
        monkeypatch, tmp_path,
        ("gui_modules/application/custom_part_controls.py",
         "tests/test_issue1462_custom_parts.py"),
        body="Fast-Feedback-Tests: tests/test_phase6_fold_designer.py::test_legacy",
    )
    changed, requested, required = select()
    assert required is True
    assert "tests/test_issue1462_custom_parts.py" in changed
    assert requested == ("tests/test_phase6_fold_designer.py::test_legacy",)


def test_ci_pr_can_use_existing_test_without_editing_test_file(monkeypatch, tmp_path):
    select = _fake_pr(monkeypatch, tmp_path, ("fold_designer_bridge.py",),
                      body="Fast-Feedback-Tests: tests/test_issue1462_custom_parts.py")
    _, requested, required = select()
    assert required is True
    assert requested == ("tests/test_issue1462_custom_parts.py",)


def test_ci_pr_rejects_only_governance_tests_for_product_change(monkeypatch, tmp_path):
    select = _fake_pr(
        monkeypatch, tmp_path, ("gui.py", "tests/process/test_change_test_profile.py"),
        body="Fast-Feedback-Tests: tests/process/test_change_test_profile.py",
    )
    with pytest.raises(ValueError, match="CI_PR_FAST_FEEDBACK_REQUIRED"):
        select()


def test_ci_pr_governance_only_is_not_product_change(monkeypatch, tmp_path):
    select = _fake_pr(
        monkeypatch, tmp_path,
        (".github/workflows/whd-product-regression.yml",
         "tools/quick_test.py", "tests/process/test_quick_test_ci_pr.py"),
    )
    _, requested, required = select()
    assert not required
    assert not requested


@pytest.mark.parametrize("kwargs,error", [
    ({"base_ref": "cleanup/2d-3d-sync"}, "CI_PR_BASE_MUST_BE_LOCALX"),
    ({"checkout_head": "c" * 40}, "CI_PR_EXACT_HEAD_MISMATCH"),
    ({"head": "not-a-sha"}, "CI_PR_SHA_INVALID"),
    ({"body": "Fast-Feedback-Tests: tests/test_a.py\nFast-Feedback-Tests: tests/test_b.py"},
     "CI_PR_DUPLICATE_FEEDBACK_MARKER"),
])
def test_ci_pr_rejects_invalid_or_ambiguous_evidence(monkeypatch, tmp_path, kwargs, error):
    select = _fake_pr(monkeypatch, tmp_path, ("gui.py",), **kwargs)
    with pytest.raises(ValueError, match=error):
        select()


def test_ci_pr_rejects_empty_diff(monkeypatch, tmp_path):
    select = _fake_pr(monkeypatch, tmp_path, ())
    with pytest.raises(ValueError, match="CI_PR_EMPTY_DIFF"):
        select()


def test_ci_dry_run_is_never_counted_as_executed(monkeypatch, tmp_path, capsys):
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(
        quick_test, "_ci_pr_inputs",
        lambda root: (("gui.py", "tests/test_issue1462_custom_parts.py"), (), True),
    )
    assert quick_test.main(["--ci-pr", "--dry-run"]) == 0
    assert output.read_text(encoding="utf-8") == "run=true\n"
    assert "WHD_QUICK_TEST_NOT_EXECUTED=true" in capsys.readouterr().out


def test_ci_pr_disallows_overriding_diff_with_untrusted_selector(monkeypatch):
    assert quick_test.main(["--ci-pr", "--test", "tests/test_issue1462_custom_parts.py"]) == 2


def test_workflow_requires_real_fast_feedback_before_shard_fanout():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[2] /
                ".github/workflows/whd-product-regression.yml").read_text("utf-8")
    assert "python tools/quick_test.py --ci-pr --dry-run" in workflow
    assert "xvfb-run -a python tools/quick_test.py --ci-pr" in workflow
    assert workflow.index("Execute focused tests before all product shards") < workflow.index("\n  test-shard:")
    assert "needs: prepare" in workflow
    assert "if: steps.fast-feedback.outputs.run == 'true'" in workflow
