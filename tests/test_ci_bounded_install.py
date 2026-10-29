"""Product CI dependency setup is bounded, independently logged and fail closed."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "ci_bounded_install.py"


def _run(*args, deadline=12):
    return subprocess.run(
        [sys.executable, str(INSTALLER), *args], cwd=ROOT,
        text=True, capture_output=True, timeout=deadline, check=False,
    )


def test_bounded_install_success_records_exit_zero():
    proc = _run("--label", "pass", "--attempts", "2",
                "--timeout-seconds", "3", "--retry-delay-seconds", "0",
                "--", sys.executable, "-c", "print('IMPORT_OK')")
    assert proc.returncode == 0, proc.stderr
    assert "IMPORT_OK" in proc.stdout
    assert "CI_INSTALL_RESULT label=pass attempt=1/2 exit_code=0" in proc.stdout
    assert "attempt=2/2" not in proc.stdout


def test_bounded_install_retries_failed_download_and_then_succeeds(tmp_path):
    marker = tmp_path / "retry-marker"
    code = (
        "from pathlib import Path; import sys; "
        "p=Path(sys.argv[1]); was=p.exists(); p.touch(); "
        "sys.exit(0 if was else 17)"
    )
    proc = _run("--label", "retry", "--attempts", "2",
                "--timeout-seconds", "3", "--retry-delay-seconds", "0",
                "--", sys.executable, "-c", code, str(marker))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CI_INSTALL_RESULT label=retry attempt=1/2 exit_code=17" in proc.stdout
    assert "CI_INSTALL_RESULT label=retry attempt=2/2 exit_code=0" in proc.stdout


def test_bounded_install_exhaustion_stays_red():
    proc = _run("--label", "exhaust", "--attempts", "2",
                "--timeout-seconds", "3", "--retry-delay-seconds", "0",
                "--", sys.executable, "-c", "import sys; sys.exit(23)")
    assert proc.returncode == 23
    assert "CI_INSTALL_EXHAUSTED label=exhaust exit_code=23" in proc.stdout


def test_bounded_install_kills_hung_process_before_job_budget():
    started = time.monotonic()
    proc = _run("--label", "hung", "--attempts", "1",
                "--timeout-seconds", "0.2", "--retry-delay-seconds", "0",
                "--", sys.executable, "-c", "import time; time.sleep(20)")
    assert proc.returncode == 124, proc.stdout + proc.stderr
    assert "CI_INSTALL_EXHAUSTED label=hung exit_code=124" in proc.stdout
    assert time.monotonic() - started < 5


def test_bounded_install_requires_command_and_positive_deadline():
    proc = _run("--label", "bad", "--attempts", "2",
                "--timeout-seconds", "0")
    assert proc.returncode == 2


def test_workflow_splits_every_network_step_and_preserves_canonical_gate():
    source = (ROOT / ".github/workflows/whd-product-regression.yml").read_text(
        encoding="utf-8",
    )
    for label in ("apt-index", "xvfb", "pip-upgrade", "pip-product", "pip-canonical"):
        assert f"--label {label} --attempts 2 --timeout-seconds" in source
    assert "python tools/ci_bounded_install.py" in source
    assert "cache: pip" in source
    assert "timeout-minutes: 30" in source
    assert "name: Canonical Product Regression" in source
    assert "--merge-junit junit/shard-0.xml" in source
    assert "--merge-junit junit/shard-2.xml" in source
    assert "if-no-files-found: error" in source


def test_ci_failure_feedback_identifies_exact_failed_case_for_local_red(tmp_path):
    import shlex
    from tools.ci_failure_feedback import inspect_junit

    suite = tmp_path / "tests"
    suite.mkdir()
    (suite / "test_example.py").write_text("def test_broken(): pass\n", encoding="utf-8")
    report = tmp_path / "shard-0.xml"
    report.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="tests.test_example" name="test_broken[one; echo unsafe]">'
        '<failure message="assert mismatch"/></testcase>'
        '<testcase classname="tests.test_example" name="test_ok"/>'
        '</testsuite></testsuites>', encoding="utf-8",
    )
    result = inspect_junit(report, root=tmp_path)
    assert result["status"] == "READY"
    assert result["failed_cases"] == 1
    assert result["selectors"] == [
        "tests/test_example.py::test_broken[one; echo unsafe]"
    ]
    assert shlex.split(result["command"]) == [
        "python", "-m", "pytest", "-q", "--tb=short",
        "tests/test_example.py::test_broken[one; echo unsafe]",
    ]


def test_ci_failure_feedback_never_pretends_missing_or_corrupt_report_is_green(tmp_path):
    from tools.ci_failure_feedback import inspect_junit

    assert inspect_junit(tmp_path / "missing.xml", root=tmp_path)["status"] == "NO_JUNIT"
    report = tmp_path / "bad.xml"
    report.write_text("<broken", encoding="utf-8")
    assert inspect_junit(report, root=tmp_path)["status"] == "INVALID_JUNIT"
    report.write_text('<!DOCTYPE x [<!ENTITY unsafe "abc">]><testsuite/>', encoding="utf-8")
    assert inspect_junit(report, root=tmp_path)["status"] == "INVALID_JUNIT"


def test_ci_failure_feedback_refuses_fake_or_partial_test_nodes(tmp_path):
    from tools.ci_failure_feedback import inspect_junit

    report = tmp_path / "bad-shard.xml"
    report.write_text(
        '<testsuites><testsuite>'
        '<testcase file="../outside.py" classname="../outside" name="test_injected">'
        '<failure/></testcase>'
        '</testsuite></testsuites>', encoding="utf-8",
    )
    result = inspect_junit(report, root=tmp_path)
    assert result["status"] == "UNRESOLVED_FAILED_CASE"
    assert result["failed_cases"] == 1
    assert result["command"] is None


def test_ci_workflow_skips_apt_only_with_both_real_xvfb_binaries():
    workflow = (ROOT / ".github/workflows/whd-product-regression.yml").read_text(
        encoding="utf-8"
    )
    assert "command -v Xvfb" in workflow and "command -v xvfb-run" in workflow
    assert workflow.count("if: steps.xvfb-check.outputs.available != 'true'") == 2
    assert "CI_XVFB_PREINSTALLED=false; bounded APT fallback required" in workflow
    assert "name: Report exact failing tests for fast RED feedback" in workflow
    assert "python tools/ci_failure_feedback.py --junit" in workflow
    assert "if: failure()" in workflow
    assert "name: Publish shard JUnit for mandatory full acceptance\n        if: always()" in workflow
    assert "name: Canonical Product Regression" in workflow
    assert "--merge-junit junit/shard-17.xml" in workflow
