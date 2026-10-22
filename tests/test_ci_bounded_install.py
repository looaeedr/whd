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
