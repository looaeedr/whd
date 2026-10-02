# -*- coding: utf-8 -*-
"""Resumable pytest/Xvfb runner for Phase6 release verification.

The runner's core contract is durability: completed work is appended to a JSONL
journal immediately, and timed-out/interrupted batches are never considered
complete.  The CLI added below uses the same primitives.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    timed_out: bool
    elapsed_seconds: float


def _collection_digest(nodeids: Iterable[str]) -> str:
    text = "\n".join(str(item) for item in nodeids) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def ensure_collection(self, nodeids: Iterable[str]) -> None:
        nodeids = tuple(str(item) for item in nodeids)
        digest = _collection_digest(nodeids)
        for record in self.records():
            if record.get("kind") != "collection":
                continue
            if record.get("sha256") != digest or int(record.get("count", -1)) != len(nodeids):
                raise ValueError("collection changed; use a fresh journal instead of reusing old release evidence")
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"kind": "collection", "sha256": digest, "count": len(nodeids), "time": time.time()}
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def records(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        result: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
        return result

    def append_batch(
        self,
        nodeids: Iterable[str],
        *,
        status: str,
        returncode: int,
        summary: Mapping[str, int],
        output: str = "",
        elapsed_seconds: float | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": time.time(),
            "nodeids": list(nodeids),
            "status": str(status),
            "returncode": int(returncode),
            "summary": {str(k): int(v) for k, v in summary.items()},
            "elapsed_seconds": None if elapsed_seconds is None else float(elapsed_seconds),
            "output_tail": output[-4000:],
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


def _completed_nodeids(journal: Journal) -> set[str]:
    complete: set[str] = set()
    for record in journal.records():
        if record.get("status") not in {"complete", "complete_teardown_timeout"}:
            continue
        for nodeid in record.get("nodeids", []):
            complete.add(str(nodeid))
    return complete


def pending_nodeids(nodeids: Iterable[str], journal: Journal) -> list[str]:
    complete = _completed_nodeids(journal)
    return [str(nodeid) for nodeid in nodeids if str(nodeid) not in complete]


def summarize_journal(journal: Journal) -> dict[str, int]:
    passed = skipped = failed_batches = teardown_timeout_batches = 0
    for record in journal.records():
        status = record.get("status")
        summary = record.get("summary")
        if status in {"complete", "complete_teardown_timeout"} and isinstance(summary, dict):
            passed += int(summary.get("passed", 0) or 0)
            skipped += int(summary.get("skipped", 0) or 0)
        if status == "failed":
            failed_batches += 1
        if status == "complete_teardown_timeout":
            teardown_timeout_batches += 1
    return {
        "completed_nodeids": len(_completed_nodeids(journal)),
        "passed": passed,
        "skipped": skipped,
        "failed_batches": failed_batches,
        "teardown_timeout_batches": teardown_timeout_batches,
    }


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    if os.name == "posix":
        # The process passed here is the process-group leader.  A timed-out
        # parent can exit promptly on SIGTERM while one of its descendants is
        # still alive in the same group.  Do not return merely because the
        # leader exited; always escalate any surviving group members.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=0.3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass
        return

    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


def run_process_group(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ProcessResult:
    started = time.monotonic()
    kwargs: dict[str, object] = {
        "cwd": None if cwd is None else str(cwd),
        "env": None if env is None else dict(env),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(list(command), **kwargs)  # type: ignore[arg-type]
    try:
        stdout, _ = proc.communicate(timeout=max(0.01, float(timeout_seconds)))
        return ProcessResult(
            returncode=int(proc.returncode or 0),
            stdout=stdout or "",
            timed_out=False,
            elapsed_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        _kill_process_group(proc)
        try:
            tail, _ = proc.communicate(timeout=0.2)
        except Exception:
            tail = ""
        return ProcessResult(
            returncode=int(proc.returncode if proc.returncode is not None else 124),
            stdout=str(partial) + (tail or ""),
            timed_out=True,
            elapsed_seconds=time.monotonic() - started,
        )


def select_batch(
    pending: Sequence[str], journal: Journal, *, default_batch_size: int
) -> list[str]:
    if not pending:
        return []
    size = max(1, int(default_batch_size))
    prefix = [str(item) for item in pending[:size]]
    for record in reversed(journal.records()):
        if record.get("status") not in {"timeout", "failed"}:
            continue
        prior = [str(item) for item in record.get("nodeids", [])]
        if not prior:
            continue
        if prefix[: len(prior)] != prior:
            continue
        if len(prior) > 1:
            return prior[: max(1, len(prior) // 2)]
        return prior
    return prefix


@dataclass(frozen=True)
class XvfbSession:
    display: str
    pid: int


def _linux_parent_death_signal() -> None:
    """Ask Linux to terminate Xvfb if this runner process disappears."""
    if os.name != "posix":
        return
    import sys

    if not sys.platform.startswith("linux"):
        return
    import ctypes

    pr_set_pdeathsig = 1
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(pr_set_pdeathsig, int(signal.SIGTERM), 0, 0, 0) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    # Close the tiny race where the parent dies between fork() and prctl().
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


@contextmanager
def managed_xvfb():
    import shutil

    executable = shutil.which("Xvfb")
    if not executable:
        raise FileNotFoundError("Xvfb executable not found")
    proc = None
    display = None
    for number in range(90, 190):
        lock = Path(f"/tmp/.X{number}-lock")
        socket = Path(f"/tmp/.X11-unix/X{number}")
        if lock.exists() or socket.exists():
            continue
        popen_kwargs: dict[str, object] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "start_new_session": (os.name == "posix"),
        }
        if os.name == "posix":
            import sys

            if sys.platform.startswith("linux"):
                popen_kwargs["preexec_fn"] = _linux_parent_death_signal
        candidate = subprocess.Popen(
            [executable, f":{number}", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
            **popen_kwargs,  # type: ignore[arg-type]
        )
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if candidate.poll() is not None:
                break
            if socket.exists():
                proc = candidate
                display = f":{number}"
                break
            time.sleep(0.02)
        if proc is not None:
            break
        if candidate.poll() is None:
            _kill_process_group(candidate)
    if proc is None or display is None:
        raise RuntimeError("unable to start Xvfb on a free display")
    try:
        yield XvfbSession(display=display, pid=proc.pid)
    finally:
        _kill_process_group(proc)



def _parse_pytest_summary(output: str) -> dict[str, int]:
    import re

    result = {"passed": 0, "skipped": 0, "failed": 0, "errors": 0, "xfailed": 0, "xpassed": 0}
    patterns = {
        "passed": r"(?:^|[, ])(\d+) passed\b",
        "skipped": r"(?:^|[, ])(\d+) skipped\b",
        "failed": r"(?:^|[, ])(\d+) failed\b",
        "errors": r"(?:^|[, ])(\d+) errors?\b",
        "xfailed": r"(?:^|[, ])(\d+) xfailed\b",
        "xpassed": r"(?:^|[, ])(\d+) xpassed\b",
    }
    for key, pattern in patterns.items():
        matches = re.findall(pattern, output, flags=re.MULTILINE)
        if matches:
            result[key] = int(matches[-1])
    return result


def timeout_output_proves_batch_complete(output: str, *, batch_count: int) -> bool:
    summary = _parse_pytest_summary(output)
    completed = (
        summary.get("passed", 0)
        + summary.get("skipped", 0)
        + summary.get("xfailed", 0)
        + summary.get("xpassed", 0)
    )
    return (
        int(batch_count) > 0
        and completed == int(batch_count)
        and summary.get("failed", 0) == 0
        and summary.get("errors", 0) == 0
    )


def collect_nodeids(root: str | Path, pytest_args: Sequence[str] = ("tests",)) -> list[str]:
    import sys

    result = run_process_group(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *pytest_args],
        timeout_seconds=60.0,
        cwd=root,
        env=os.environ.copy(),
    )
    if result.returncode != 0 or result.timed_out:
        raise RuntimeError(f"pytest collection failed rc={result.returncode}\n{result.stdout[-4000:]}")
    nodeids: list[str] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if "::" not in line or line.startswith(("<", "=", "-")):
            continue
        if line not in nodeids:
            nodeids.append(line)
    if not nodeids:
        raise RuntimeError("pytest collection returned no nodeids")
    return nodeids


def _write_state_file(
    path: Path,
    *,
    journal: Journal,
    total: int,
    pending: int,
    mode: str,
    last_status: str,
) -> None:
    data = summarize_journal(journal)
    data.update(
        {
            "total_nodeids": int(total),
            "pending_nodeids": int(pending),
            "mode": mode,
            "last_status": last_status,
            "updated_at": time.time(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def has_full_batch_window(
    *, remaining_seconds: float, batch_timeout_seconds: float, safety_seconds: float = 1.0
) -> bool:
    return float(remaining_seconds) >= float(batch_timeout_seconds) + float(safety_seconds)


def _run_resumable_suite_unlocked(
    *,
    root: str | Path,
    nodeids: Sequence[str],
    journal_path: str | Path,
    mode: str,
    batch_size: int = 10,
    batch_timeout_seconds: float = 12.0,
    budget_seconds: float = 18.0,
    state_path: str | Path | None = None,
) -> int:
    import sys

    root = Path(root).resolve()
    journal = Journal(journal_path)
    journal.ensure_collection(nodeids)
    state = Path(state_path) if state_path is not None else Path(journal_path).with_suffix(".state.json")
    started = time.monotonic()
    last_status = "start"

    if mode not in {"headless", "xvfb"}:
        raise ValueError("mode must be 'headless' or 'xvfb'")
    display_context = managed_xvfb() if mode == "xvfb" else nullcontext(None)

    with display_context as xvfb_session:
        base_env = os.environ.copy()
        if mode == "headless":
            base_env.pop("DISPLAY", None)
        else:
            assert xvfb_session is not None
            base_env["DISPLAY"] = xvfb_session.display

        while True:
            pending = pending_nodeids(nodeids, journal)
            _write_state_file(
                state,
                journal=journal,
                total=len(nodeids),
                pending=len(pending),
                mode=mode,
                last_status=last_status,
            )
            if not pending:
                return 0

            remaining = float(budget_seconds) - (time.monotonic() - started)
            if not has_full_batch_window(
                remaining_seconds=remaining, batch_timeout_seconds=batch_timeout_seconds
            ):
                return 75

            batch = select_batch(pending, journal, default_batch_size=batch_size)
            timeout_seconds = float(batch_timeout_seconds)
            command = [sys.executable, "-m", "pytest", "-q", *batch]
            result = run_process_group(
                command, timeout_seconds=timeout_seconds, cwd=root, env=base_env
            )
            summary = _parse_pytest_summary(result.stdout)
            if result.timed_out:
                if timeout_output_proves_batch_complete(result.stdout, batch_count=len(batch)):
                    last_status = "complete_teardown_timeout"
                    journal.append_batch(
                        batch,
                        status="complete_teardown_timeout",
                        returncode=result.returncode,
                        summary=summary,
                        output=result.stdout,
                        elapsed_seconds=result.elapsed_seconds,
                    )
                    continue
                last_status = "timeout"
                journal.append_batch(
                    batch,
                    status="timeout",
                    returncode=result.returncode,
                    summary=summary,
                    output=result.stdout,
                    elapsed_seconds=result.elapsed_seconds,
                )
                if len(batch) == 1:
                    _write_state_file(
                        state,
                        journal=journal,
                        total=len(nodeids),
                        pending=len(pending),
                        mode=mode,
                        last_status=last_status,
                    )
                    return 124
                continue

            if result.returncode == 0:
                last_status = "complete"
                journal.append_batch(
                    batch,
                    status="complete",
                    returncode=0,
                    summary=summary,
                    output=result.stdout,
                    elapsed_seconds=result.elapsed_seconds,
                )
                continue

            last_status = "failed"
            journal.append_batch(
                batch,
                status="failed",
                returncode=result.returncode,
                summary=summary,
                output=result.stdout,
                elapsed_seconds=result.elapsed_seconds,
            )
            if len(batch) == 1:
                _write_state_file(
                    state,
                    journal=journal,
                    total=len(nodeids),
                    pending=len(pending),
                    mode=mode,
                    last_status=last_status,
                )
                return result.returncode or 1



@contextmanager
def journal_run_lock(journal_path: str | Path):
    """Prevent concurrent runner processes from appending to one journal."""
    lock_path = Path(str(journal_path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "posix":
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(f"release journal already in use: {journal_path}") from exc
            locked = True
        elif os.name == "nt":
            import msvcrt

            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"release journal already in use: {journal_path}") from exc
            locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "posix":
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                elif os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                fh.close()
        else:
            fh.close()


def run_resumable_suite(
    *,
    root: str | Path,
    nodeids: Sequence[str],
    journal_path: str | Path,
    mode: str,
    batch_size: int = 10,
    batch_timeout_seconds: float = 12.0,
    budget_seconds: float = 18.0,
    state_path: str | Path | None = None,
    reset: bool = False,
) -> int:
    with journal_run_lock(journal_path):
        if reset:
            Path(journal_path).unlink(missing_ok=True)
            state = Path(state_path) if state_path is not None else Path(journal_path).with_suffix(".state.json")
            state.unlink(missing_ok=True)
        return _run_resumable_suite_unlocked(
            root=root,
            nodeids=nodeids,
            journal_path=journal_path,
            mode=mode,
            batch_size=batch_size,
            batch_timeout_seconds=batch_timeout_seconds,
            budget_seconds=budget_seconds,
            state_path=state_path,
        )

def _build_cli_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Resumable Phase6 pytest/Xvfb release runner")
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=("headless", "xvfb"), default="xvfb")
    parser.add_argument("--journal", required=True)
    parser.add_argument("--state")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--batch-timeout", type=float, default=12.0)
    parser.add_argument("--budget-seconds", type=float, default=18.0)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("pytest_args", nargs="*", default=["tests"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    journal = Path(args.journal)
    state = Path(args.state) if args.state else journal.with_suffix(".state.json")
    pytest_args = tuple(args.pytest_args or ["tests"])
    nodeids = collect_nodeids(root, pytest_args)
    return run_resumable_suite(
        root=root,
        nodeids=nodeids,
        journal_path=journal,
        state_path=state,
        mode=args.mode,
        batch_size=max(1, args.batch_size),
        batch_timeout_seconds=max(0.5, args.batch_timeout),
        budget_seconds=max(2.0, args.budget_seconds),
        reset=bool(args.reset),
    )


if __name__ == "__main__":
    raise SystemExit(main())
