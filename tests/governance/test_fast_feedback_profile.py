"""Focused pytest command generation must never become a merge qualification."""
import json
import shlex
from pathlib import Path

import pytest

from tools.change_test_profile import build_fast_feedback, build_test_profile


def test_changed_test_file_creates_fast_command_without_weakening_full_gate():
    profile = build_test_profile(
        task="修正真 DXF BUG",
        changed_files=["ae_engine/ae_door_indicator.py", "tests/test_dxf_proof.py"],
        explicit_type="BUGFIX",
    )
    feedback = profile["fast_feedback"]
    assert feedback["status"] == "READY"
    assert feedback["test_selectors"] == ["tests/test_dxf_proof.py"]
    assert feedback["command"] == "python -m pytest -q --tb=short tests/test_dxf_proof.py"
    assert feedback["may_replace_full_gate"] is False
    assert profile["full_gate_kind"] == "PRODUCT_FULL_REGRESSION"
    assert profile["full_gate_required"] is True
    assert profile["exact_commands"] == ["python tools/product_ci_regression.py"]


def test_production_only_change_needs_explicit_reproducer_instead_of_guessing():
    feedback = build_fast_feedback(["gui.py"])
    assert feedback["status"] == "NEEDS_EXPLICIT_TEST"
    assert feedback["test_selectors"] == []
    assert feedback["command"] is None


def test_explicit_node_ids_are_deduplicated_and_shell_quoted():
    selectors = ["tests/test_safe.py::test_case[space value]",
                 "tests/test_safe.py::test_case[space value]"]
    feedback = build_fast_feedback(["gui.py"], feedback_tests=selectors)
    assert feedback["status"] == "READY"
    assert feedback["test_selectors"] == selectors[:1]
    assert shlex.split(feedback["command"])[5:] == selectors[:1]
    assert feedback["authority"] == "DEVELOPMENT_FEEDBACK_ONLY"


@pytest.mark.parametrize("bad", [
    "../tests/test_a.py", "/tmp/test_a.py", "tests/../test_a.py",
    "gui.py", "tests/test_a.py::", "tests/test_a.py::test_ok::",
    "tests/test_a.py\n--override-ini=evil",
])
def test_invalid_or_incomplete_selectors_fail_closed(bad):
    with pytest.raises(ValueError):
        build_fast_feedback(["gui.py"], feedback_tests=[bad])


def test_governance_feedback_does_not_upgrade_to_product_full():
    profile = build_test_profile(
        task="治理更新", changed_files=["tools/change_test_profile.py",
                                       "tests/governance/test_fast_feedback_profile.py"],
        explicit_type="GOVERNANCE",
    )
    assert profile["fast_feedback"]["status"] == "READY"
    assert profile["full_gate_kind"] == "GOVERNANCE_FULL_SUITE"


def test_contract_documents_feedback_as_non_qualifying():
    contract = json.loads((Path(__file__).resolve().parents[2]
                           / ".agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json").read_text(encoding="utf-8"))
    assert contract["classification"]["focused_tests_can_replace_full_gate"] is False
    assert contract["fast_feedback"]["final_exact_sha_ci"] == "UNCHANGED_REQUIRED"


def test_quick_test_explicit_node_runs_exact_argv_without_git_or_shell(tmp_path, monkeypatch, capsys):
    from subprocess import CompletedProcess
    from tools import quick_test
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    monkeypatch.setattr(quick_test, "ROOT", tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(command, 0)

    monkeypatch.setattr(quick_test.subprocess, "run", fake_run)
    assert quick_test.main(["--test", "tests/test_sample.py::test_ok"]) == 0
    assert len(calls) == 1
    assert calls[0][0][1:] == [
        "-m", "pytest", "-q", "--tb=short", "tests/test_sample.py::test_ok"
    ]
    assert calls[0][1]["cwd"] == tmp_path
    assert calls[0][1]["check"] is False
    assert "shell" not in calls[0][1]
    assert "WHD_QUICK_TEST_FINAL_GITHUB_CI=STILL_REQUIRED" in capsys.readouterr().out


def test_quick_test_red_exits_nonzero_and_does_not_claim_green(tmp_path, monkeypatch, capsys):
    from subprocess import CompletedProcess
    from tools import quick_test
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_bad.py").write_text("def test_bad(): assert False\n", encoding="utf-8")
    monkeypatch.setattr(quick_test, "ROOT", tmp_path)
    monkeypatch.setattr(quick_test.subprocess, "run",
                        lambda c, **k: CompletedProcess(c, 1))
    assert quick_test.main(["--test", "tests/test_bad.py::test_bad"]) == 1
    assert "WHD_QUICK_TEST_RESULT=RED" in capsys.readouterr().out


def test_quick_test_requires_explicit_test_when_only_product_changed(tmp_path, monkeypatch):
    from tools import quick_test
    monkeypatch.setattr(quick_test, "ROOT", tmp_path)
    assert quick_test.main(["--changed-file", "ae_engine/manufacturing_api.py"]) == 2


def test_quick_test_dry_run_never_executes_and_does_not_claim_pass(tmp_path, monkeypatch, capsys):
    from tools import quick_test
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    monkeypatch.setattr(quick_test, "ROOT", tmp_path)
    monkeypatch.setattr(quick_test.subprocess, "run",
                        lambda *a, **k: pytest.fail("dry run must not run subprocess"))
    assert quick_test.main(["--test", "tests/test_a.py", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "WHD_QUICK_TEST_NOT_EXECUTED=true" in output
    assert "WHD_QUICK_TEST_RESULT=PASS" not in output


def test_quick_test_auto_selects_git_changed_test_without_guessing_product_tests(tmp_path, monkeypatch):
    from subprocess import CompletedProcess
    from tools import quick_test
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_new.py").write_text("def test_new(): pass\n", encoding="utf-8")
    monkeypatch.setattr(quick_test, "ROOT", tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "git" and "diff" in command:
            return CompletedProcess(command, 0, stdout=b"gui.py\x00")
        if command[0] == "git" and "ls-files" in command:
            return CompletedProcess(command, 0, stdout=b"tests/test_new.py\x00")
        return CompletedProcess(command, 0)

    monkeypatch.setattr(quick_test.subprocess, "run", fake_run)
    assert quick_test.main(["--auto"]) == 0
    assert calls[-1][-1] == "tests/test_new.py"


def test_quick_test_and_windows_wrapper_never_stage_commit_push():
    root = Path(__file__).resolve().parents[2]
    source = (root / "tools/quick_test.py").read_text(encoding="utf-8")
    wrapper = (root / "WHD_quick_test.bat").read_text(encoding="utf-8")
    assert "subprocess.run(command, cwd=ROOT, check=False)" in source
    assert "git add" not in wrapper and "git push" not in wrapper
    assert "python tools\\quick_test.py %*" in wrapper
    from tools.change_test_profile import build_test_profile
    profile = build_test_profile(
        task="治理本地快速測試入口",
        changed_files=["AGENTS.md", "tools/quick_test.py",
                       "WHD_quick_test.bat", "tests/governance/test_fast_feedback_profile.py"],
        explicit_type="GOVERNANCE",
    )
    assert profile["full_gate_kind"] == "GOVERNANCE_FULL_SUITE"


def test_batched_feedback_standard_requires_exact_final_gate_and_windows_permission():
    root = Path(__file__).resolve().parents[2]
    source = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "BATCHED_FAST_FEEDBACK_THEN_CANONICAL_CI_V1" in source
    for marker in ("WHD_quick_test.bat", "PRODUCT", "/推推", "RED", "GREEN"):
        assert marker in source
