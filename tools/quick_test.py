#!/usr/bin/env python3
"""Run local/authorized-workspace targeted tests BEFORE creating a PR commit.

This script only runs pytest. It never stages, commits, pushes, downloads data,
modifies config.ini or claims the mandatory exact-head GitHub CI has passed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import re
import subprocess
import sys

try:
    from tools.change_test_profile import build_fast_feedback, _is_governance_support_path
except ModuleNotFoundError:  # python tools/quick_test.py
    from change_test_profile import build_fast_feedback, _is_governance_support_path

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
    # A caller can supply --auto and --test together. The explicit test must
    # ADD coverage, never silently suppress other changed test files.
    # Validate both groups with the existing safe selector parser.
    inferred = build_fast_feedback(changed_files)["test_selectors"] if changed_files else ()
    explicit = build_fast_feedback(seed, feedback_tests=tests)["test_selectors"] if tests else ()
    combined = tuple(dict.fromkeys((*inferred, *explicit)))
    # Running the whole changed test file also runs its explicitly selected
    # node; do not execute those cases twice (or obscure failure counts).
    whole_files = {selector for selector in combined if "::" not in selector}
    selectors = tuple(
        selector for selector in combined
        if "::" not in selector or selector.partition("::")[0] not in whole_files
    )
    if not selectors:
        raise ValueError("NEEDS_EXPLICIT_TEST: use --test tests/test_file.py::test_case")
    base = root.resolve()
    for item in selectors:
        filename = item.split("::", 1)[0]
        resolved = (base / filename).resolve()
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ValueError("TARGETED_TEST_FILE_MISSING: " + filename)
    return selectors



def _product_path(path: str) -> bool:
    """Only real product inputs require a focused test before fan-out."""
    return (
        path in {"requirements.txt", "config.ini"}
        or path.startswith(("gui_modules/", "ae_engine/", "integration_cli/",
                            "基準檔/", "config/"))
        or (path.endswith(".py") and not _is_governance_support_path(path))
    )


def _ci_pr_inputs(root: Path) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """Select from the exact localX PR diff, not mutable worktree guesses.

    Changed test files are always included. An existing test may be named in
    the PR body as: Fast-Feedback-Tests: tests/test_a.py::test_case
    This is only a selection hint: the runner itself must execute pytest.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("CI_PR_EVENT_MISSING")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pr = event["pull_request"]
        if pr["base"]["ref"] != "localX":
            raise ValueError("CI_PR_BASE_MUST_BE_LOCALX")
        base, head = pr["base"]["sha"], pr["head"]["sha"]
        if not all(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha)
                   for sha in (base, head)):
            raise ValueError("CI_PR_SHA_INVALID")
        body = pr.get("body") or ""
        if not isinstance(body, str):
            raise ValueError("CI_PR_BODY_INVALID")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("CI_PR_EVENT_INVALID") from exc

    def git(*args: str) -> bytes:
        result = subprocess.run(["git", "-C", str(root), *args],
                                capture_output=True, check=False)
        if result.returncode:
            raise ValueError("CI_PR_GIT_READ_FAILED")
        return result.stdout

    if git("rev-parse", "HEAD").decode("ascii", "strict").strip() != head:
        raise ValueError("CI_PR_EXACT_HEAD_MISMATCH")
    changed = tuple(dict.fromkeys(
        name.decode("utf-8", "strict") for name in
        git("diff", "--no-ext-diff", "--name-only", "-z", base, head).split(b"\x00")
        if name
    ))
    if not changed:
        raise ValueError("CI_PR_EMPTY_DIFF")

    markers = re.findall(r"(?im)^Fast-Feedback-Tests:[ \t]*(.*)$", body)
    if len(markers) > 1:
        raise ValueError("CI_PR_DUPLICATE_FEEDBACK_MARKER")
    requested = tuple(markers[0].split()) if markers else ()
    required = any(_product_path(path) for path in changed)
    changed_product_tests = [
        path for path in changed
        if path.startswith("tests/") and path.endswith(".py")
        and (root / path).is_file()
        and not _is_governance_support_path(path)
        and (Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py"))
    ]
    requested_product_tests = [
        node for node in requested
        if not _is_governance_support_path(node.partition("::")[0])
    ]
    if required and not (changed_product_tests or requested_product_tests):
        raise ValueError(
            "CI_PR_FAST_FEEDBACK_REQUIRED: change a relevant product test or "
            "declare Fast-Feedback-Tests: tests/test_file.py::test_case in PR body"
        )
    return changed, requested, required


def _ci_output_run(run: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("run=" + ("true" if run else "false") + "\n")


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
    parser.add_argument("--ci-pr", action="store_true",
                        help="GitHub PR exact-head focused-test gate before full CI shards")
    args = parser.parse_args(argv)
    try:
        if args.ci_pr:
            if args.auto or args.test or args.changed_file:
                raise ValueError("CI_PR_SELECTOR_OVERRIDE_FORBIDDEN")
            changed, requested, required = _ci_pr_inputs(ROOT)
            if not required and not requested and not any(
                path.startswith("tests/") and path.endswith(".py") for path in changed
            ):
                print("WHD_CI_PR_FAST_FEEDBACK=NOT_APPLICABLE", flush=True)
                if args.dry_run:
                    _ci_output_run(False)
                return 0
            selectable_changed = tuple(
                path for path in changed
                if not (
                    path.startswith("tests/") and path.endswith(".py")
                    and not (ROOT / path).is_file()
                )
            )
            selectors = choose_tests(changed_files=selectable_changed,
                                     tests=requested, root=ROOT)
        else:
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
        if args.ci_pr:
            _ci_output_run(True)
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
