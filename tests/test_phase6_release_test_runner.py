from __future__ import annotations

import os
from pathlib import Path
import sys
import time

import pytest

from tools.phase6_release_test_runner import (
    Journal,
    pending_nodeids,
    run_process_group,
    select_batch,
    summarize_journal,
)


def test_pending_nodeids_resumes_only_unfinished(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append_batch(
        ["tests/a.py::test_a", "tests/a.py::test_b"],
        status="complete",
        returncode=0,
        summary={"passed": 2, "skipped": 0, "failed": 0},
    )

    assert pending_nodeids(
        ["tests/a.py::test_a", "tests/a.py::test_b", "tests/a.py::test_c"],
        journal,
    ) == ["tests/a.py::test_c"]


def test_interrupted_or_timeout_batches_are_not_treated_as_completed(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append_batch(
        ["tests/a.py::test_a", "tests/a.py::test_b"],
        status="timeout",
        returncode=124,
        summary={},
    )

    assert pending_nodeids(
        ["tests/a.py::test_a", "tests/a.py::test_b"],
        journal,
    ) == ["tests/a.py::test_a", "tests/a.py::test_b"]


def test_timeout_batch_is_automatically_split_on_resume(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    nodeids = [f"tests/a.py::test_{i}" for i in range(8)]
    journal.append_batch(nodeids, status="timeout", returncode=124, summary={})

    assert select_batch(nodeids, journal, default_batch_size=8) == nodeids[:4]


def test_collection_change_refuses_to_reuse_old_journal(tmp_path: Path) -> None:
    from tools.phase6_release_test_runner import journal_run_lock

    journal = Journal(tmp_path / "journal.jsonl")
    journal.ensure_collection(["tests/a.py::test_a", "tests/a.py::test_b"])

    with pytest.raises(ValueError, match="collection changed"):
        journal.ensure_collection(["tests/a.py::test_a", "tests/a.py::test_c"])

    with journal_run_lock(journal.path):
        with pytest.raises(RuntimeError, match="already in use"):
            with journal_run_lock(journal.path):
                pytest.fail("second writer lock unexpectedly acquired")


def test_cli_reset_refuses_locked_journal_without_deleting_collection(tmp_path: Path) -> None:
    """A failed concurrent --reset attempt must leave durable collection identity intact."""
    import json
    import subprocess

    from tools.phase6_release_test_runner import journal_run_lock

    root = Path(__file__).resolve().parents[1]
    journal_path = tmp_path / "journal.jsonl"
    state_path = tmp_path / "journal.state.json"
    nodeid = "tests/test_phase6_release_test_runner.py::test_pending_nodeids_resumes_only_unfinished"
    journal = Journal(journal_path)
    journal.ensure_collection([nodeid])
    before = journal_path.read_text(encoding="utf-8")

    with journal_run_lock(journal_path):
        proc = subprocess.run(
            [
                sys.executable,
                str(root / "tools/phase6_release_test_runner.py"),
                "--root",
                str(root),
                "--mode",
                "headless",
                "--journal",
                str(journal_path),
                "--state",
                str(state_path),
                "--reset",
                "--budget-seconds",
                "2",
                nodeid,
            ],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=20,
        )

    assert proc.returncode != 0
    assert "already in use" in (proc.stdout + proc.stderr)
    assert journal_path.read_text(encoding="utf-8") == before
    first = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert first["kind"] == "collection"


def test_run_process_group_timeout_kills_child_tree(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time,pathlib; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid)); "
        "time.sleep(30)"
    )

    started = time.monotonic()
    # Child Python startup can approach a second on slower CI/containers.
    # The contract under test is process-tree cleanup after timeout, not a
    # one-second interpreter startup deadline, so leave enough startup margin.
    result = run_process_group([sys.executable, "-c", script], timeout_seconds=3.0)
    elapsed = time.monotonic() - started

    assert result.timed_out is True
    assert result.returncode != 0
    assert elapsed < 5.0
    child_pid = int(pid_file.read_text())
    stat = Path(f"/proc/{child_pid}/stat")
    if stat.exists():
        # Zombie is already dead and consumes no CPU. What must never survive is
        # a live sleeping/running descendant from the timed-out batch.
        state = stat.read_text().split()[2]
        assert state == "Z"


def test_journal_summary_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    first = Journal(path)
    first.append_batch(
        ["tests/a.py::test_a", "tests/a.py::test_b"],
        status="complete",
        returncode=0,
        summary={"passed": 1, "skipped": 1, "failed": 0},
    )
    first.append_batch(
        ["tests/a.py::test_c"],
        status="failed",
        returncode=1,
        summary={"passed": 0, "skipped": 0, "failed": 1},
    )

    reloaded = Journal(path)
    summary = summarize_journal(reloaded)

    assert summary["completed_nodeids"] == 2
    assert summary["passed"] == 1
    assert summary["skipped"] == 1
    assert summary["failed_batches"] == 1


def test_release_policy_requires_resumable_runner_artifacts() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "release_required_artifacts.json").read_text(encoding="utf-8"))
    required = set(data["mandatory_update_files"])
    assert "tools/phase6_release_test_runner.py" in required
    assert "tests/test_phase6_release_test_runner.py" in required


def test_release_skill_requires_durable_resume_journal() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / ".agents/skills/engineering/phase6-release-packaging/SKILL.md").read_text(encoding="utf-8")
    assert "phase6_release_test_runner.py" in text
    assert "journal" in text.lower()
    assert "exit 75" in text.lower()
    assert "complete_teardown_timeout" in text


def test_global_pitfall_records_resumable_release_runner() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md").read_text(encoding="utf-8")
    assert "phase6_release_test_runner.py" in text
    assert "exit 75" in text.lower()
    assert "journal" in text.lower()


def test_managed_xvfb_runs_tk_and_reaps_server() -> None:
    import shutil

    if shutil.which("Xvfb") is None:
        pytest.skip("Xvfb not installed")
    from tools.phase6_release_test_runner import managed_xvfb

    with managed_xvfb() as session:
        pid = session.pid
        env = os.environ.copy()
        env["DISPLAY"] = session.display
        result = run_process_group(
            [sys.executable, "-c", "import tkinter as tk; r=tk.Tk(); r.update_idletasks(); r.destroy()"],
            timeout_seconds=3.0,
            env=env,
        )
        assert result.returncode == 0
        assert result.timed_out is False
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_budget_guard_never_starts_batch_with_truncated_timeout() -> None:
    from tools.phase6_release_test_runner import has_full_batch_window

    assert has_full_batch_window(remaining_seconds=12.0, batch_timeout_seconds=10.0) is True
    assert has_full_batch_window(remaining_seconds=10.5, batch_timeout_seconds=10.0) is False
    assert has_full_batch_window(remaining_seconds=4.3, batch_timeout_seconds=10.0) is False


def test_timeout_with_complete_pytest_summary_is_teardown_timeout_not_test_timeout() -> None:
    from tools.phase6_release_test_runner import timeout_output_proves_batch_complete

    assert timeout_output_proves_batch_complete(". [100%]\n1 passed in 7.85s\n", batch_count=1)
    assert timeout_output_proves_batch_complete(".. [100%]\n1 passed, 1 skipped in 1.2s\n", batch_count=2)
    assert not timeout_output_proves_batch_complete("........", batch_count=5)
    assert not timeout_output_proves_batch_complete("1 failed in 0.2s", batch_count=1)


def test_teardown_timeout_status_counts_as_completed(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    journal.append_batch(
        ["tests/a.py::test_a"],
        status="complete_teardown_timeout",
        returncode=-15,
        summary={"passed": 1, "skipped": 0, "failed": 0},
    )
    assert pending_nodeids(["tests/a.py::test_a"], journal) == []
    assert summarize_journal(journal)["teardown_timeout_batches"] == 1


def test_summary_does_not_double_count_passes_from_retry_timeout_records(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "journal.jsonl")
    nodeid = "tests/a.py::test_a"
    journal.append_batch(
        [nodeid], status="timeout", returncode=-15,
        summary={"passed": 1, "skipped": 0, "failed": 0},
    )
    journal.append_batch(
        [nodeid], status="complete_teardown_timeout", returncode=-15,
        summary={"passed": 1, "skipped": 0, "failed": 0},
    )
    summary = summarize_journal(journal)
    assert summary["completed_nodeids"] == 1
    assert summary["passed"] == 1


def test_managed_xvfb_dies_when_runner_parent_is_sigkilled(tmp_path: Path) -> None:
    """A hard-killed outer runner must not orphan a live Xvfb server."""
    import shutil
    import subprocess
    import signal

    if os.name != "posix" or not sys.platform.startswith("linux"):
        pytest.skip("Linux parent-death signal contract")
    if shutil.which("Xvfb") is None:
        pytest.skip("Xvfb not installed")

    pid_file = tmp_path / "xvfb.pid"
    script = "\n".join(
        [
            "import pathlib, time",
            "from tools.phase6_release_test_runner import managed_xvfb",
            f"pid_file = pathlib.Path({str(pid_file)!r})",
            "with managed_xvfb() as session:",
            "    pid_file.write_text(str(session.pid), encoding='utf-8')",
            "    time.sleep(60)",
        ]
    )
    parent = subprocess.Popen([sys.executable, "-c", script], cwd=str(Path(__file__).resolve().parents[1]))
    xvfb_pid: int | None = None
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not pid_file.exists():
            if parent.poll() is not None:
                pytest.fail(f"runner parent exited before publishing Xvfb pid: rc={parent.returncode}")
            time.sleep(0.02)
        assert pid_file.exists(), "runner parent did not publish Xvfb pid"
        xvfb_pid = int(pid_file.read_text(encoding="utf-8"))

        os.kill(parent.pid, signal.SIGKILL)
        parent.wait(timeout=2.0)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            stat = Path(f"/proc/{xvfb_pid}/stat")
            if not stat.exists():
                return
            state = stat.read_text(encoding="utf-8").split()[2]
            if state == "Z":
                return
            time.sleep(0.02)
        pytest.fail("Xvfb survived after its runner parent was SIGKILLed")
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=2.0)
        if xvfb_pid is not None:
            try:
                os.kill(xvfb_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
