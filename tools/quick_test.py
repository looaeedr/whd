#!/usr/bin/env python3
"""Run local/authorized-workspace targeted tests BEFORE creating a PR commit.

This script only runs pytest. It never stages, commits, pushes, downloads data,
modifies config.ini or claims the mandatory exact-head GitHub CI has passed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import subprocess
import sys

try:
    from tools.change_test_profile import build_fast_feedback
except ModuleNotFoundError:  # python tools/quick_test.py
    from change_test_profile import build_fast_feedback

ROOT = Path(__file__).resolve().parents[1]


def _git_paths(root: Path) -> tuple[str, ...]:
    """Include tracked staged/unstaged changes and newly written test files."""
    paths: list[str] = []
    commands = (
        ["git", "-C", str(root), "diff", "--name-only", "-z", "HEAD", "--"],
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z", "--"],
    )
    for command in commands:
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode:
            raise ValueError("GIT_WORKTREE_READ_FAILED; use --test explicitly")
        paths.extend(p.decode("utf-8", "strict") for p in result.stdout.split(b"\x00") if p)
    return tuple(dict.fromkeys(paths))


def choose_tests(*, changed_files: tuple[str, ...], tests: tuple[str, ...],
                 root: Path) -> tuple[str, ...]:
    """Reuse authoritative selector validation; never infer tests from product paths."""
    seed = changed_files or tuple(s.partition("::")[0] for s in tests)
    if not seed:
        raise ValueError("NO_TARGETED_TEST: use --test for the bug reproducer")
    feedback = build_fast_feedback(seed, feedback_tests=tests)
    if feedback["status"] != "READY":
        raise ValueError("NEEDS_EXPLICIT_TEST: use --test tests/test_file.py::test_case")
    selectors = tuple(feedback["test_selectors"])
    base = root.resolve()
    for item in selectors:
        filename = item.split("::", 1)[0]
        resolved = (base / filename).resolve()
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ValueError("TARGETED_TEST_FILE_MISSING: " + filename)
    return selectors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="append", default=[], metavar="PYTEST_NODE",
                        help="Exact tests/test_*.py or tests/test_*.py::test_name; repeatable")
    parser.add_argument("--changed-file", action="append", default=[], metavar="PATH",
                        help="Declared modified path, for auto-selecting changed test files")
    parser.add_argument("--auto", action="store_true",
                        help="Read git staged/unstaged and untracked test paths (default if no args)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show selected tests; DOES NOT count as a passed test")
    args = parser.parse_args(argv)
    try:
        changed = list(args.changed_file)
        if args.auto or not (args.test or args.changed_file):
            changed.extend(_git_paths(ROOT))
        selectors = choose_tests(changed_files=tuple(changed),
                                 tests=tuple(args.test), root=ROOT)
    except (ValueError, UnicodeError, OSError) as exc:
        print("WHD_QUICK_TEST_BLOCKED=" + str(exc), file=sys.stderr, flush=True)
        return 2
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", *selectors]
    display = (subprocess.list2cmdline(command) if os.name == "nt"
               else __import__("shlex").join(command))
    print("WHD_QUICK_TEST_AUTHORITY=DEVELOPMENT_FEEDBACK_ONLY", flush=True)
    print("WHD_QUICK_TEST_SELECTORS=" + str(len(selectors)), flush=True)
    print("WHD_QUICK_TEST_COMMAND=" + display, flush=True)
    if args.dry_run:
        print("WHD_QUICK_TEST_NOT_EXECUTED=true", flush=True)
        return 0
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
    except OSError as exc:
        print("WHD_QUICK_TEST_LAUNCH_FAILED=" + type(exc).__name__, file=sys.stderr)
        return 2
    print("WHD_QUICK_TEST_RESULT=" + ("PASS" if result.returncode == 0 else "RED"),
          flush=True)
    print("WHD_QUICK_TEST_FINAL_GITHUB_CI=STILL_REQUIRED", flush=True)
    return result.returncode if result.returncode >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
