"""Trustworthy PR-file classifier for WHD local governance-to-X fast lane.

Only non-product control documents and their machine checks qualify. Any
unknown, renamed, or mixed product path must use localX and exact /推推 proof.
This module is intended to run from a trusted base-branch checkout, never
from untrusted PR candidate code.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.request import Request, urlopen

from tools.localx_publish_gate import (
    PRODUCTION_X, INTEGRATION_BRANCH, require_publish_approval,
)

GOVERNANCE_BRANCH_PREFIXES = ("governance/", "docs/", "skills/")
GOVERNANCE_ROOT_FILES = frozenset({
    "AGENTS.md",
    "AI_HANDOFF.md",
    "release_required_artifacts.json",
})
GOVERNANCE_PREFIXES = (
    ".agents/skills/",
    ".agents/contracts/",
    ".github/workflows/",
    "docs/governance/",
    "個人AI檔案庫/踩坑庫/",
    "tests/governance/",
    "tests/knowledge/",
)
GOVERNANCE_EXACT_FILES = frozenset({
    "tools/change_lane_gate.py",
    "tools/localx_publish_gate.py",
    "tools/phase6_skill_preflight.py",
    "tools/knowledge_governance.py",
    "tools/change_test_profile.py",
    "tests/process/test_change_lane_gate.py",
    "tests/process/test_localx_publish_gate.py",
    "tests/test_phase6_skill_preflight_gate.py",
    "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md",
    "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md",
})


# The product regression workflow is *not* blanket governance. A trusted
# base-X check can exempt a strictly bounded numeric runner/scheduling edit.
# Canonical selectors/CPR/AC, hooks, triggers, shard sets, conditionals, scripts,
# dependencies and artifact collection remain product acceptance authority.
PROTECTED_PRODUCT_CI_WORKFLOW = ".github/workflows/whd-product-regression.yml"
_SAFE_CI_SCHEDULING_LINE = re.compile(
    r"^(?P<indent> +)(?P<key>runs-on|timeout-minutes|max-parallel|retention-days): "
    r"(?P<value>[a-z0-9.-]+)$"
)
_SAFE_CI_RANGES = {
    "timeout-minutes": (10, 90),
    "max-parallel": (1, 8),
    "retention-days": (1, 90),
}


def _safe_scheduling_line_pair(before: str, after: str) -> bool:
    old = _SAFE_CI_SCHEDULING_LINE.fullmatch(before)
    new = _SAFE_CI_SCHEDULING_LINE.fullmatch(after)
    if not old or not new:
        return False
    if old.group("indent", "key") != new.group("indent", "key"):
        return False
    key = old.group("key")
    values = (old.group("value"), new.group("value"))
    if key == "runs-on":
        return all(v in {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04"} for v in values)
    lower, upper = _SAFE_CI_RANGES[key]
    return all(v.isascii() and v.isdecimal() and lower <= int(v) <= upper for v in values)


def is_safe_product_ci_scheduling_edit(before: str, after: str) -> bool:
    """Fail closed unless every changed line is a numeric/existing-runner tuning.

    No insertion/deletion, YAML control flow, triggers, job names, scripts, matrix
    membership, artifact names, acceptance rules or test lists can be modified
    through this direct-X lane. A product CI redesign still uses localX + /推推.
    """
    if not before or not after or before == after:
        return False
    left, right = before.splitlines(), after.splitlines()
    changes = 0
    for op, i, j, k, l in difflib.SequenceMatcher(
        a=left, b=right, autojunk=False,
    ).get_opcodes():
        if op == "equal":
            continue
        if op != "replace" or (j - i) != (l - k):
            return False
        for old_line, new_line in zip(left[i:j], right[k:l]):
            if not _safe_scheduling_line_pair(old_line, new_line):
                return False
            changes += 1
    return changes > 0


def classify_verified_pr_changes(
    repo_root: Path, base_sha: str, head_sha: str, paths: list[str],
) -> str:
    """Classify using trusted actual blobs when a protected workflow is touched."""
    if PROTECTED_PRODUCT_CI_WORKFLOW not in paths:
        return classify_changes(paths)
    if not all(re.fullmatch(r"[0-9a-f]{40}", x or "") for x in (base_sha, head_sha)):
        raise ChangeLaneDenied("INVALID_COMMIT_SHA")
    try:
        blobs = [
            subprocess.run(
                ["git", "show", f"{sha}:{PROTECTED_PRODUCT_CI_WORKFLOW}"],
                cwd=repo_root, check=True, capture_output=True,
            ).stdout.decode("utf-8", "strict")
            for sha in (base_sha, head_sha)
        ]
    except (OSError, UnicodeError, subprocess.CalledProcessError):
        # If an acceptance file was added/removed or the diff is unavailable,
        # treat the change as product instead of silently granting direct X.
        return "PRODUCT_LOCALX_ONLY"
    verified = is_safe_product_ci_scheduling_edit(*blobs)
    return classify_changes(paths, verified_ci_scheduling=verified)


TAIWAN_ZONE = "Asia/Taipei"
TAIWAN_OFFSET = timedelta(hours=8)
# New-code source guard only: legacy timestamps must be migrated with targeted
# product regression, not silently rewritten by a governance-only patch.
_UNQUALIFIED_CLOCK = re.compile(
    r"(?:\bdatetime\s*\.\s*(?:now|today|utcnow)\s*\(\s*\)"
    r"|\.\s*astimezone\s*\(\s*\)"
    r"|\btime\s*\.\s*localtime\s*\(\s*\))"
)


def require_taipei_timezone(env: dict | None = None) -> str:
    """Block operators/CI that inherit host-local or UTC wall-clock time."""
    source = os.environ if env is None else env
    if source.get("TZ") != TAIWAN_ZONE:
        raise ChangeLaneDenied("TAIWAN_TIMEZONE_HARD_GATE_FAILED:TZ_NOT_ASIA_TAIPEI")
    try:
        zone = ZoneInfo(TAIWAN_ZONE)
        for month in (1, 7):
            if datetime(2026, month, 1, tzinfo=zone).utcoffset() != TAIWAN_OFFSET:
                raise ChangeLaneDenied(
                    "TAIWAN_TIMEZONE_HARD_GATE_FAILED:INVALID_TAIPEI_OFFSET"
                )
        value = datetime.now(zone)
        if value.utcoffset() != TAIWAN_OFFSET:
            raise ChangeLaneDenied(
                "TAIWAN_TIMEZONE_HARD_GATE_FAILED:ACTIVE_OFFSET_MISMATCH"
            )
    except ZoneInfoNotFoundError as exc:
        raise ChangeLaneDenied(
            "TAIWAN_TIMEZONE_HARD_GATE_FAILED:TIMEZONE_DATABASE_UNAVAILABLE"
        ) from exc
    return value.isoformat(timespec="seconds")


def human_timestamp_taipei(value: datetime) -> str:
    """Convert valid instants for reports; reject timezone-naive input."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ChangeLaneDenied("TAIWAN_TIMEZONE_HARD_GATE_FAILED:NAIVE_TIMESTAMP")
    try:
        result = value.astimezone(ZoneInfo(TAIWAN_ZONE))
    except ZoneInfoNotFoundError as exc:
        raise ChangeLaneDenied(
            "TAIWAN_TIMEZONE_HARD_GATE_FAILED:TIMEZONE_DATABASE_UNAVAILABLE"
        ) from exc
    return result.isoformat(timespec="seconds")


def require_new_code_taipei(repo_root: Path, base_sha: str, head_sha: str) -> int:
    """Reject newly added host-local clock calls in PR Python implementation.

    Existing historical code is not changed or blocked until that line is
    edited. UTC transport fields remain valid with explicit awareness;
    human-facing formatting is governed by the operator contract.
    """
    for sha in (base_sha, head_sha):
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ChangeLaneDenied("TAIWAN_TIMEZONE_HARD_GATE_FAILED:INVALID_SHA")
    try:
        patch = subprocess.run(
            ["git", "diff", "--unified=0", "--no-ext-diff",
             f"{base_sha}...{head_sha}", "--", "*.py"],
            cwd=repo_root, capture_output=True, check=True,
        ).stdout.decode("utf-8", "strict")
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise ChangeLaneDenied("TAIWAN_TIMEZONE_HARD_GATE_FAILED:DIFF_UNREADABLE") from exc
    path = ""
    checked = 0
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            # Test fixtures frequently *quote* prohibited syntax; production
            # code is the enforced part of this migration-safe source guard.
            if path.startswith(("tests/", "BACKUP/")):
                continue
            added = line[1:].strip()
            if added.startswith("#"):
                continue
            checked += 1
            if _UNQUALIFIED_CLOCK.search(added):
                raise ChangeLaneDenied(
                    "TAIWAN_TIMEZONE_HARD_GATE_FAILED:HOST_LOCAL_CLOCK:" + path
                )
    return checked


class ChangeLaneDenied(ValueError):
    """A PR does not satisfy the chosen X publication route."""


def _valid_path(raw: str) -> bool:
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\\" in raw:
        return False
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or ".." in path.parts
        or raw != path.as_posix()
    ):
        return False
    if raw.startswith(".") and not raw.startswith((".agents/", ".github/")):
        return False
    return True


def is_governance_file(
    path: str, *, verified_ci_scheduling: bool = False,
) -> bool:
    """A protected test authority workflow is product unless its actual diff is safe."""
    if not _valid_path(path):
        return False
    if path == PROTECTED_PRODUCT_CI_WORKFLOW:
        return verified_ci_scheduling is True
    return (
        path in GOVERNANCE_ROOT_FILES
        or path in GOVERNANCE_EXACT_FILES
        or path.startswith(GOVERNANCE_PREFIXES)
    )


def classify_changes(
    changed_paths: list[str], *, verified_ci_scheduling: bool = False,
) -> str:
    if not changed_paths:
        raise ChangeLaneDenied("EMPTY_PR_DIFF")
    if all(is_governance_file(path, verified_ci_scheduling=verified_ci_scheduling)
           for path in changed_paths):
        return "GOVERNANCE_DIRECT_X"
    return "PRODUCT_LOCALX_ONLY"


def parse_name_status_zero(blob: bytes) -> list[str]:
    """Resolve git -z statuses, considering BOTH sides of rename/copy."""
    fields = blob.split(b"\x00")
    if fields[-1] != b"":
        raise ChangeLaneDenied("INVALID_GIT_NAME_STATUS")
    fields.pop()
    paths: list[str] = []
    index = 0
    while index < len(fields):
        status = fields[index].decode("ascii", "strict")
        index += 1
        if re.fullmatch(r"[AMDTU]", status):
            n = 1
        elif re.fullmatch(r"[RC][0-9]{1,3}", status):
            n = 2
        else:
            raise ChangeLaneDenied(f"UNEXPECTED_GIT_STATUS:{status}")
        if index + n > len(fields):
            raise ChangeLaneDenied("TRUNCATED_GIT_NAME_STATUS")
        for encoded in fields[index:index + n]:
            path = encoded.decode("utf-8", "strict")
            if not _valid_path(path):
                raise ChangeLaneDenied(f"INVALID_DIFF_PATH:{path!r}")
            paths.append(path)
        index += n
    return paths


def changed_paths_between(repo_root: Path, base_sha: str, head_sha: str) -> list[str]:
    for value in (base_sha, head_sha):
        if not re.fullmatch(r"[0-9a-f]{40}", value or ""):
            raise ChangeLaneDenied("INVALID_COMMIT_SHA")
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-status", "-z", "--find-renames",
             f"{base_sha}...{head_sha}"],
            cwd=repo_root, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ChangeLaneDenied("DIFF_READ_FAILED") from exc
    return parse_name_status_zero(proc.stdout)


def require_x_only_governance_history(
    repo_root: Path, x_sha: str, localx_sha: str,
) -> int:
    """Check each commit exclusive to X; never pre-merge X into localX.

    Merge commits are checked against their first parent, so product changes
    introduced by conflict resolution cannot hide behind a governance label.
    The publish executor must separately verify local and GitHub localX agree,
    then publish localX to X before any back-sync.
    """
    for sha in (x_sha, localx_sha):
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ChangeLaneDenied("INVALID_COMMIT_SHA")
    try:
        listing = subprocess.run(
            ["git", "rev-list", x_sha, f"^{localx_sha}"],
            cwd=repo_root, capture_output=True, check=True,
        )
        unique = listing.stdout.decode("ascii", "strict").split()
        for commit in unique:
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ChangeLaneDenied("X_AHEAD_HISTORY_UNVERIFIABLE")
            first_parent = subprocess.run(
                ["git", "rev-parse", f"{commit}^1"],
                cwd=repo_root, capture_output=True, check=True,
            ).stdout.decode("ascii", "strict").strip()
            changed = subprocess.run(
                ["git", "diff", "--name-status", "-z", "--find-renames",
                 first_parent, commit],
                cwd=repo_root, capture_output=True, check=True,
            )
            paths = parse_name_status_zero(changed.stdout)
            if paths and classify_verified_pr_changes(
                repo_root, first_parent, commit, paths,
            ) != "GOVERNANCE_DIRECT_X":
                raise ChangeLaneDenied(
                    f"X_AHEAD_NON_GOVERNANCE_BLOCKED:{commit}"
                )
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise ChangeLaneDenied("X_AHEAD_HISTORY_UNVERIFIABLE") from exc
    return len(unique)


def _comments(repo: str, number: int, token: str) -> list[dict]:
    if not token:
        raise ChangeLaneDenied("MISSING_GITHUB_TOKEN_FOR_PRODUCT_PUBLISH")
    found: list[dict] = []
    for page in range(1, 11):
        url = (
            f"https://api.github.com/repos/{repo}/issues/{number}/comments"
            f"?per_page=100&page={page}"
        )
        req = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urlopen(req, timeout=15) as response:
            entries = json.load(response)
        if not isinstance(entries, list):
            raise ChangeLaneDenied("INVALID_COMMENTS_RESPONSE")
        found.extend(entries)
        if len(entries) < 100:
            return found
    # An approval beyond our capped search could not be verified.
    raise ChangeLaneDenied("COMMENTS_PAGINATION_LIMIT")


def evaluate_pr(
    *, event: dict, changed_paths: list[str],
    comments: list[dict] | None = None,
    verified_ci_scheduling: bool = False,
) -> dict:
    pr = event.get("pull_request") or {}
    if not isinstance(pr, dict):
        raise ChangeLaneDenied("INVALID_PR")
    base = pr.get("base") or {}
    head = pr.get("head") or {}
    base_ref = base.get("ref")
    head_ref = head.get("ref")
    base_sha, head_sha = base.get("sha"), head.get("sha")
    repository = event.get("repository") or {}
    repo = repository.get("full_name")
    if (
        not repo or base_ref != PRODUCTION_X
        or not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha)
        or not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha)
    ):
        raise ChangeLaneDenied("INVALID_EXACT_X_PR_IDENTITY")
    if (base.get("repo") or {}).get("full_name") != repo:
        raise ChangeLaneDenied("BASE_REPOSITORY_MISMATCH")
    if (head.get("repo") or {}).get("full_name") != repo:
        raise ChangeLaneDenied("FORK_NOT_SUPPORTED_FOR_DIRECT_X")
    lane = classify_changes(
        changed_paths, verified_ci_scheduling=verified_ci_scheduling,
    )
    if lane == "GOVERNANCE_DIRECT_X":
        if not isinstance(head_ref, str) or not head_ref.startswith(GOVERNANCE_BRANCH_PREFIXES):
            raise ChangeLaneDenied("GOVERNANCE_REQUIRES_DEDICATED_BRANCH")
        return {
            "status": "PASS", "lane": lane,
            "reason": "PURE_NON_PRODUCT_GOVERNANCE",
            "path_count": len(changed_paths),
            "head_sha": head_sha, "base_sha": base_sha,
        }
    if head_ref != INTEGRATION_BRANCH:
        raise ChangeLaneDenied("PRODUCT_OR_MIXED_REQUIRES_LOCALX")
    try:
        require_publish_approval(
            repo=repo, pr_number=int(pr["number"]),
            pr={"head": {"ref": head_ref, "sha": head_sha},
                "base": {"ref": base_ref, "sha": base_sha}},
            head_sha=head_sha, target_sha=base_sha,
            comments=comments or [],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ChangeLaneDenied(f"PRODUCT_REQUIRES_EXACT_USER_SLASH_PUSH:{exc}") from exc
    return {
        "status": "PASS", "lane": lane,
        "reason": "LOCALX_USER_SLASH_PUSH_VERIFIED",
        "path_count": len(changed_paths),
        "head_sha": head_sha, "base_sha": base_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    opts = parser.parse_args()
    try:
        # Always enforce zone before evaluating governance/product publishing.
        require_taipei_timezone()
        event = json.loads(opts.event_file.read_text(encoding="utf-8"))
        pr = event.get("pull_request") or {}
        paths = changed_paths_between(
            opts.repo_root, pr["base"]["sha"], pr["head"]["sha"]
        )
        lane = classify_verified_pr_changes(
            opts.repo_root, pr["base"]["sha"], pr["head"]["sha"], paths,
        )
        checked = require_new_code_taipei(
            opts.repo_root, pr["base"]["sha"], pr["head"]["sha"]
        )
        comments = None
        if lane != "GOVERNANCE_DIRECT_X":
            comments = _comments(
                event["repository"]["full_name"], int(pr["number"]),
                os.environ.get("GITHUB_TOKEN", ""),
            )
        result = evaluate_pr(
            event=event, changed_paths=paths, comments=comments,
            verified_ci_scheduling=(
                PROTECTED_PRODUCT_CI_WORKFLOW in paths
                and lane == "GOVERNANCE_DIRECT_X"
            ),
        )
        result["timezone"] = TAIWAN_ZONE
        result["new_python_lines_checked"] = checked
        if lane != "GOVERNANCE_DIRECT_X":
            # Trusted X workflow gate: allow X to be ahead of localX only
            # when *every* X-only commit is pure non-product governance.
            result["x_only_governance_commit_count"] = require_x_only_governance_history(
                opts.repo_root, pr["base"]["sha"], pr["head"]["sha"]
            )
    except (ChangeLaneDenied, KeyError, TypeError, ValueError, OSError) as exc:
        print(json.dumps({
            "status": "DENY", "reason": str(exc),
        }, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
