#!/usr/bin/env python3
"""Fail-closed, bounded and auditable dependency-install retry for CI.

Run without a shell: -- <executable> [arguments ...].
Each attempt has its own real process-group timeout; dependency installation
never borrows the complete product-test job timeout. Print one receipt per
attempt and preserve a nonzero exit status after exhausted attempts.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def _run_once(command: list[str], limit: float) -> int:
    proc = subprocess.Popen(command, start_new_session=(os.name == "posix"))
    try:
        return proc.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait()
        return 124


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--retry-delay-seconds", type=float, default=3)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd or args.attempts not in (1, 2, 3) or not 0 < args.timeout_seconds <= 600 or not 0 <= args.retry_delay_seconds <= 30:
        parser.error("command required; attempts=1..3; timeout=0..600s; delay=0..30s")
    for attempt in range(1, args.attempts + 1):
        started = time.monotonic()
        print(
            f"CI_INSTALL_START label={args.label} attempt={attempt}/{args.attempts} "
            f"timeout_seconds={args.timeout_seconds:g}", flush=True,
        )
        try:
            code = _run_once(cmd, args.timeout_seconds)
        except OSError as exc:
            print(f"CI_INSTALL_LAUNCH_FAILED label={args.label} error={exc}", flush=True)
            code = 127
        elapsed = time.monotonic() - started
        print(
            f"CI_INSTALL_RESULT label={args.label} attempt={attempt}/{args.attempts} "
            f"exit_code={code} elapsed_seconds={elapsed:.2f}", flush=True,
        )
        if code == 0:
            return 0
        if attempt < args.attempts:
            time.sleep(args.retry_delay_seconds)
    print(f"CI_INSTALL_EXHAUSTED label={args.label} exit_code={code}", flush=True)
    return code if code > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
