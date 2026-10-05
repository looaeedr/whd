#!/usr/bin/env python3
"""Reuse a prior Canonical Product Regression GREEN after unrelated target drift.

This is intentionally fail-open-to-retest: any missing or ambiguous evidence
returns reuse=false so the workflow runs the full canonical product regression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

SCHEMA = "WHD_PRODUCT_CI_GREEN_REUSE_V1"
CHECK_NAME = "Canonical Product Regression"

GLOBAL_DEPENDENCY_PATHS = {
    ".github/workflows/whd-product-regression.yml",
    "tools/product_ci_regression.py",
    "tools/phase6_bridge_anti_regrowth_guard.py",
    "requirements.txt",
    "pytest.ini",
    "pyproject.toml",
    "docs/architecture/phase6_bridge_anti_regrowth_baseline.json",
}


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    return proc.stdout.decode("utf-8", errors="strict")


def _git_bytes(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout


def _paths(a: str, b: str) -> list[str]:
    raw = _git_bytes("diff", "--name-only", "-z", a, b)
    return sorted(x.decode("utf-8") for x in raw.split(b"\0") if x)


def _patch_digest(a: str, b: str, paths: Iterable[str]) -> str:
    selected = sorted(set(paths))
    if not selected:
        return hashlib.sha256(b"").hexdigest()
    payload = _git_bytes(
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-renames",
        a,
        b,
        "--",
        *selected,
    )
    return hashlib.sha256(payload).hexdigest()


def surface(path: str) -> str:
    p = path.replace("\\", "/")
    if p in GLOBAL_DEPENDENCY_PATHS or p.startswith("requirements"):
        return "global"
    if (
        p.startswith("ae_engine/")
        or p.startswith("gui_modules/")
        or p.startswith("phase6_")
        or p == "fold_designer_bridge.py"
        or (p.startswith("tests/") and not p.startswith("tests/process/"))
    ):
        return "product"
    if (
        p.startswith(".agents/")
        or p == "AGENTS.md"
        or p.startswith("tests/process/")
        or p.startswith("個人AI檔案庫/")
        or p.startswith("coord/")
    ):
        return "governance"
    if p.startswith(".github/"):
        return "global"
    if p.startswith("tools/"):
        return "governance"
    return "general"


def dependency_impact(candidate_paths: Iterable[str], target_paths: Iterable[str]) -> bool:
    candidate_surfaces = {surface(p) for p in candidate_paths}
    target_surfaces = {surface(p) for p in target_paths}
    if "global" in target_surfaces:
        return True
    if "general" in candidate_surfaces or "general" in target_surfaces:
        return True
    return bool(candidate_surfaces & target_surfaces)


def decide_green_reuse(
    *,
    prior_green: bool,
    candidate_paths: Iterable[str],
    target_paths: Iterable[str],
    prior_patch_digest: str,
    current_patch_digest: str,
) -> tuple[bool, str]:
    candidate = set(candidate_paths)
    target = set(target_paths)
    if not prior_green:
        return False, "PRIOR_REQUIRED_CHECK_NOT_GREEN"
    if not candidate:
        return False, "EMPTY_CANDIDATE_PATH_SET"
    if candidate & target:
        return False, "TARGET_DRIFT_OVERLAPS_CANDIDATE_PATHS"
    if prior_patch_digest != current_patch_digest:
        return False, "CANDIDATE_PATCH_IDENTITY_CHANGED"
    if dependency_impact(candidate, target):
        return False, "TARGET_DRIFT_HAS_DEPENDENCY_IMPACT"
    return True, "GREEN_REUSED_NO_RETEST"


def _prior_green(repo: str, sha: str, token: str) -> bool:
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs?per_page=100"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "whd-product-ci-green-reuse",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.load(response)
    for item in payload.get("check_runs", []):
        if (
            item.get("name") == CHECK_NAME
            and item.get("status") == "completed"
            and item.get("conclusion") == "success"
        ):
            return True
    return False


def classify(repo: str, head_sha: str, base_sha: str, token: str) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": SCHEMA,
        "classification": "RETEST_REQUIRED",
        "reuse": False,
        "head_sha": head_sha,
        "base_sha": base_sha,
    }
    try:
        parent_line = _git("rev-list", "--parents", "-n", "1", head_sha).strip().split()
        if len(parent_line) != 3:
            result["reason"] = "HEAD_IS_NOT_TARGET_SYNC_MERGE"
            return result
        _, p1, p2 = parent_line
        if p1 == base_sha:
            prior_head = p2
        elif p2 == base_sha:
            prior_head = p1
        else:
            result["reason"] = "CURRENT_BASE_IS_NOT_A_HEAD_PARENT"
            return result

        old_base = _git("merge-base", prior_head, base_sha).strip()
        if not old_base:
            result["reason"] = "MERGE_BASE_UNAVAILABLE"
            return result

        candidate_paths = _paths(old_base, prior_head)
        current_candidate_paths = _paths(base_sha, head_sha)
        target_paths = _paths(old_base, base_sha)
        if candidate_paths != current_candidate_paths:
            result.update(
                {
                    "reason": "CANDIDATE_PATH_SET_CHANGED",
                    "prior_head": prior_head,
                    "old_base_sha": old_base,
                    "candidate_paths": candidate_paths,
                    "current_candidate_paths": current_candidate_paths,
                    "target_changed_paths": target_paths,
                }
            )
            return result

        prior_digest = _patch_digest(old_base, prior_head, candidate_paths)
        current_digest = _patch_digest(base_sha, head_sha, current_candidate_paths)
        try:
            prior_green = _prior_green(repo, prior_head, token)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            result["reason"] = f"PRIOR_CHECK_LOOKUP_FAILED:{type(exc).__name__}"
            return result

        reuse, reason = decide_green_reuse(
            prior_green=prior_green,
            candidate_paths=candidate_paths,
            target_paths=target_paths,
            prior_patch_digest=prior_digest,
            current_patch_digest=current_digest,
        )
        result.update(
            {
                "classification": "REUSE_GREEN" if reuse else "RETEST_REQUIRED",
                "reuse": reuse,
                "reason": reason,
                "prior_head": prior_head,
                "old_base_sha": old_base,
                "candidate_paths": candidate_paths,
                "target_changed_paths": target_paths,
                "prior_patch_digest": prior_digest,
                "current_patch_digest": current_digest,
                "dependency_impact": dependency_impact(candidate_paths, target_paths),
                "prior_required_check_green": prior_green,
                "extra_test_run_performed": False,
            }
        )
        return result
    except (subprocess.CalledProcessError, UnicodeDecodeError, ValueError) as exc:
        result["reason"] = f"REVALIDATION_ERROR:{type(exc).__name__}"
        return result


def _write_output(result: dict[str, object]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    with open(output, "a", encoding="utf-8") as fh:
        fh.write(f"reuse={'true' if result.get('reuse') else 'false'}\n")
        fh.write(f"classification={result.get('classification', 'RETEST_REQUIRED')}\n")
        fh.write(f"reason={result.get('reason', 'UNKNOWN')}\n")
        fh.write(f"evidence={compact}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = parser.parse_args()
    if not args.github_token:
        result = {
            "schema": SCHEMA,
            "classification": "RETEST_REQUIRED",
            "reuse": False,
            "reason": "GITHUB_TOKEN_MISSING",
            "head_sha": args.head_sha,
            "base_sha": args.base_sha,
        }
    else:
        result = classify(args.repo, args.head_sha, args.base_sha, args.github_token)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    _write_output(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
