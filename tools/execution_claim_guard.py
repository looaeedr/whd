"""Fail-closed execution-claim ownership guard for WHD development actions.

This module does not acquire, mutate, or release claims. It validates an already
acquired shared coordination claim immediately before a branch/write/QA/takeover action so a
second worker cannot treat comments, branch names, stale chat state, or a stale claim
snapshot as ownership.
"""

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_ACTIONS = frozenset(
    {
        "branch-create",
        "claim-takeover",
        "write",
        "commit",
        "qa-dispatch",
        "workflow-dispatch",
        "pr-write",
    }
)
ACTIVE_PHASES = frozenset(
    {
        "CLAIMED",
        "RED",
        "IMPLEMENTING",
        "GREEN",
        "REMOTE_QA",
        "RECOVERING",
        "CLEANUP",
        "DRIFT_AUDIT",
        "CLOSING",
    }
)
INACTIVE_PHASES = frozenset(
    {
        "RELEASED",
        "CLOSED",
        "TERMINAL_SUCCESS",
        "TERMINAL_FAILURE",
    }
)
FILE_MUTATION_ACTIONS = frozenset({"write", "commit"})


class ExecutionClaimError(RuntimeError):
    """Raised when execution ownership cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ExecutionClaimError(f"ambiguous execution claim: duplicate JSON key {key!r}")
        payload[key] = value
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionClaimError(f"missing required claim field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise ExecutionClaimError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


def _require_sha(payload: dict[str, object], key: str) -> str:
    return _validate_sha(_require_text(payload, key), f"claim field {key}")


def _normalize_changed_files(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for index, raw in enumerate(values):
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/"):
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: expected repository-relative path"
            )
        if ".." in PurePosixPath(value).parts:
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: path traversal is not allowed"
            )
        if value not in result:
            result.append(value)
    return tuple(result)


def _is_skill_contract_path(path: str) -> bool:
    return path.startswith(".agents/skills/") and path.endswith("/SKILL.md")


def _assert_skill_authoring_preflight(
    changed_files: tuple[str, ...],
    evidence_paths: Iterable[str],
) -> None:
    skill_targets = tuple(path for path in changed_files if _is_skill_contract_path(path))
    if not skill_targets:
        return

    evidence = tuple(str(path).strip() for path in evidence_paths if str(path).strip())
    if not evidence:
        raise ExecutionClaimError(
            "Skill write preflight missing: .agents/skills/**/SKILL.md mutation requires "
            "canonical Phase6 Preflight evidence including 寫技能"
        )

    try:
        from tools.phase6_skill_preflight import (
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )
    except ModuleNotFoundError:
        from phase6_skill_preflight import (  # type: ignore[no-redef]
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )

    required_skills = required_skills_for(task="", changed_files=changed_files)
    required_references = required_references_for(task="", changed_files=changed_files)
    if "寫技能" not in required_skills:
        raise ExecutionClaimError(
            "Skill write preflight registry defect: 寫技能 is not required for Skill mutation"
        )

    completed_skills = completed_skills_from_evidence(evidence)
    completed_references = completed_references_from_evidence(
        evidence, required_references
    )
    missing_skills = [item for item in required_skills if item not in completed_skills]
    missing_references = [
        item for item in required_references if item not in completed_references
    ]
    if missing_skills or missing_references:
        raise ExecutionClaimError(
            "Skill write preflight incomplete: "
            f"missing_skills={missing_skills!r} "
            f"missing_references={missing_references!r}; "
            "寫技能 and all canonical required references must be completed before mutation"
        )


def _load_takeover_evidence(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"claim-takeover evidence not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"claim-takeover evidence invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionClaimError("claim-takeover evidence root must be an object")
    return payload


def _timestamp_epoch(label: str, value: object) -> float:
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionClaimError(f"claim-takeover {label} timestamp invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionClaimError(f"claim-takeover {label} timestamp must be timezone-aware")
    return parsed.timestamp()


def _assert_user_directed_takeover_authority(
    path: Path | None,
    *,
    issue: int,
    previous_worker: str,
    requesting_worker: str,
    expected_comment_id: int,
) -> None:
    if path is None:
        raise ExecutionClaimError(
            "interactive claim-takeover requires owner-authored user authority evidence"
        )
    payload = _load_takeover_evidence(path)
    comment_id = payload.get("id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        raise ExecutionClaimError("user authority comment id is invalid")
    if comment_id != expected_comment_id:
        raise ExecutionClaimError("user authority comment id mismatch")
    user = payload.get("user")
    if not isinstance(user, dict) or str(user.get("login") or "") != "looaeedr":
        raise ExecutionClaimError("user authority comment must be authored by repository owner")
    body = payload.get("body")
    if not isinstance(body, str):
        raise ExecutionClaimError("user authority comment body is missing")
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_USER_DIRECTED_TAKEOVER_V1":
        raise ExecutionClaimError("user authority comment marker mismatch")
    singles: dict[str, str] = {}
    allowed = {"issue", "requesting_worker", "previous_worker", "executor_source"}
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            raise ExecutionClaimError("user authority comment contains malformed line")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in allowed or key in singles:
            raise ExecutionClaimError(
                "user authority comment contains unsupported/duplicate key"
            )
        singles[key] = value
    if set(singles) != allowed:
        raise ExecutionClaimError("user authority comment is missing required keys")
    if singles["issue"] != str(issue):
        raise ExecutionClaimError("user authority issue mismatch")
    if singles["requesting_worker"] != requesting_worker:
        raise ExecutionClaimError("user authority requesting_worker mismatch")
    if singles["previous_worker"] != previous_worker:
        raise ExecutionClaimError("user authority previous_worker mismatch")
    if singles["executor_source"] != "chat":
        raise ExecutionClaimError("user authority executor_source must be chat")


def _assert_takeover_evidence(
    evidence_path: Path | None,
    *,
    claim_path: Path,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    expected_live_head_sha: str,
    user_authority_evidence: Path | None = None,
) -> None:
    if evidence_path is None:
        raise ExecutionClaimError("claim-takeover requires machine stale takeover evidence")
    evidence = _load_takeover_evidence(evidence_path)
    if evidence.get("schema") != "WHD_STALE_CLAIM_TAKEOVER_V1":
        raise ExecutionClaimError("claim-takeover evidence schema mismatch")
    classification = str(evidence.get("classification") or "")
    if classification not in {"EXECUTOR_STUCK", "ORPHANED_SCHEDULER_OWNER"}:
        raise ExecutionClaimError(
            "claim-takeover evidence is not actionable stale/orphaned scheduler evidence"
        )
    if evidence.get("actionable") is not True:
        raise ExecutionClaimError("claim-takeover evidence is not actionable")
    stale_seconds = evidence.get("stale_seconds")
    threshold = evidence.get("stale_after_seconds")
    if isinstance(stale_seconds, bool) or not isinstance(stale_seconds, int):
        raise ExecutionClaimError("claim-takeover stale seconds are invalid")
    if threshold != 600:
        raise ExecutionClaimError("claim-takeover stale threshold must be exactly 600 seconds")
    if classification == "EXECUTOR_STUCK":
        if stale_seconds < 600:
            raise ExecutionClaimError("claim-takeover stale evidence is below 600 seconds")
    else:
        grace = evidence.get("orphan_grace_seconds")
        if grace != 90:
            raise ExecutionClaimError(
                "orphaned scheduler takeover grace must be exactly 90 seconds"
            )
        if stale_seconds < grace or stale_seconds >= 600:
            raise ExecutionClaimError(
                "orphaned scheduler takeover evidence is outside the 90..599 second window"
            )
        if evidence.get("runtime_liveness_status") not in {"MISSING", "EXPIRED"}:
            raise ExecutionClaimError(
                "orphaned scheduler takeover requires missing/expired runtime liveness"
            )
        evidence_blob = _validate_sha(
            str(evidence.get("claim_blob_sha") or ""),
            "orphaned scheduler claim blob SHA",
        )
        actual_blob = _git_blob_sha(claim_path)
        if evidence_blob != actual_blob:
            raise ExecutionClaimError(
                "orphaned scheduler takeover claim blob evidence mismatch"
            )
    observed = _validate_sha(
        str(evidence.get("observed_live_head_sha") or ""),
        "takeover observed live head SHA",
    )
    if observed != expected_live_head_sha:
        raise ExecutionClaimError(
            f"claim-takeover observed live head mismatch expected={expected_live_head_sha} evidence={observed}"
        )
    evidence_claim_head = _validate_sha(
        str(evidence.get("claim_head_sha") or ""),
        "takeover evidence claim head SHA",
    )
    if evidence_claim_head != claim.head_sha:
        raise ExecutionClaimError(
            f"claim-takeover evidence claim head mismatch expected={claim.head_sha} evidence={evidence_claim_head}"
        )
    expected_source = str(raw_claim.get("executor_source") or "unknown").strip() or "unknown"
    if classification == "ORPHANED_SCHEDULER_OWNER" and expected_source != "scheduler":
        raise ExecutionClaimError(
            "orphaned scheduler takeover requires scheduler previous executor source"
        )
    if str(evidence.get("previous_executor_source") or "") != expected_source:
        raise ExecutionClaimError("claim-takeover previous executor source mismatch")

    evidence_previous_worker = str(evidence.get("previous_worker") or "").strip()
    evidence_requesting_worker = str(evidence.get("requesting_worker") or "").strip()
    evidence_requesting_source = str(
        evidence.get("requesting_executor_source") or ""
    ).strip()
    if evidence_previous_worker and evidence_previous_worker != claim.worker:
        raise ExecutionClaimError("claim-takeover previous worker mismatch")
    if expected_source == "scheduler":
        if evidence_previous_worker != claim.worker:
            raise ExecutionClaimError(
                "scheduler claim-takeover requires evidence bound to the previous worker"
            )
        if not evidence_requesting_worker or evidence_requesting_worker == claim.worker:
            raise ExecutionClaimError(
                "scheduler claim-takeover requires a distinct requesting worker"
            )
        if evidence_requesting_worker.startswith("scheduler."):
            if evidence_requesting_source != "scheduler":
                raise ExecutionClaimError(
                    "scheduler requesting worker requires scheduler executor source"
                )
            if evidence.get("user_authority_comment_id") is not None:
                raise ExecutionClaimError(
                    "scheduler claim-takeover must not carry user authority evidence"
                )
        else:
            if evidence_requesting_source != "chat":
                raise ExecutionClaimError(
                    "interactive claim-takeover requires chat executor source"
                )
            authority_id = evidence.get("user_authority_comment_id")
            if isinstance(authority_id, bool) or not isinstance(authority_id, int) or authority_id <= 0:
                raise ExecutionClaimError(
                    "interactive claim-takeover requires user authority comment id"
                )
            _assert_user_directed_takeover_authority(
                user_authority_evidence,
                issue=claim.issue,
                previous_worker=claim.worker,
                requesting_worker=evidence_requesting_worker,
                expected_comment_id=authority_id,
            )
    elif evidence_requesting_worker and not evidence_requesting_worker.startswith("scheduler."):
        raise ExecutionClaimError("non-scheduler previous owner takeover remains scheduler-only")
    if str(evidence.get("claim_phase") or "").upper() != claim.phase:
        raise ExecutionClaimError("claim-takeover evidence claim phase mismatch")
    claim_last_update = raw_claim.get("last_update")
    if claim_last_update is None:
        raise ExecutionClaimError("claim-takeover claim last_update missing")
    if _timestamp_epoch("claim last_update", claim_last_update) != _timestamp_epoch(
        "evidence claim_last_update", evidence.get("claim_last_update")
    ):
        raise ExecutionClaimError("claim-takeover evidence claim last_update mismatch")



def _git_blob_sha(path: Path) -> str:
    data = Path(path).read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def _github_api_json(path: str) -> object:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if repository != "looaeedr/whd":
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation requires GITHUB_REPOSITORY=looaeedr/whd"
        )
    if not token:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation requires authenticated GitHub API access"
        )
    url = f"https://api.github.com/repos/{repository}/{path.lstrip('/')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation GitHub API read failed: {exc}"
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation GitHub API returned invalid JSON"
        ) from exc


def _github_issue_comments(issue: int) -> list[dict[str, object]]:
    comments: list[dict[str, object]] = []
    for page in range(1, 21):
        payload = _github_api_json(f"issues/{issue}/comments?per_page=100&page={page}")
        if not isinstance(payload, list):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation issue-comments response is not a list"
            )
        page_items = [item for item in payload if isinstance(item, dict)]
        comments.extend(page_items)
        if len(payload) < 100:
            return comments
    raise ExecutionClaimError(
        "post-commit claim-head reconciliation exceeded issue-comment pagination limit"
    )


def _github_commit(sha: str) -> dict[str, object]:
    payload = _github_api_json(f"commits/{sha}")
    if not isinstance(payload, dict):
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation commit response is not an object"
        )
    return payload


def _github_issue(issue: int) -> dict[str, object]:
    payload = _github_api_json(f"issues/{issue}")
    if not isinstance(payload, dict):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery issue response is not an object"
        )
    return payload


def _parse_remote_guard_request_comment(
    comment: dict[str, object],
) -> dict[str, object] | None:
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") != "looaeedr":
        return None
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "WHD_REMOTE_GUARD_REQUEST_V1":
        return None
    singles: dict[str, str] = {}
    changed_files: list[str] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        if "=" not in raw:
            return None
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "changed_file":
            changed_files.append(value)
        elif key in singles:
            return None
        else:
            singles[key] = value
    payload: dict[str, object] = dict(singles)
    payload["changed_files"] = changed_files
    payload["comment_id"] = comment.get("id")
    return payload


def _parse_remote_guard_receipt_comment(
    comment: dict[str, object],
) -> dict[str, object] | None:
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
        return None
    body = comment.get("body")
    if not isinstance(body, str) or not body.startswith("WHD_REMOTE_GUARD_RESULT_V1"):
        return None
    match = re.search(r"~~~json\s*(\{.*?\})\s*~~~", body, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _reconcile_timestamp_epoch(label: str, value: object) -> float:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation {label} timestamp invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionClaimError(
            f"post-commit claim-head reconciliation {label} timestamp must be timezone-aware"
        )
    return parsed.timestamp()


def _load_raw_claim_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"cannot re-read execution claim: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionClaimError("execution claim root must be object")
    return payload


def _assert_post_commit_claim_head_reconciliation(
    path: Path,
    *,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    issue: int,
    worker: str,
    branch: str,
    expected_live_head_sha: str,
    changed_files: tuple[str, ...],
) -> None:
    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    if changed_files != (expected_claim_path,):
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation may write only the exact shared claim path"
        )

    commit = _github_commit(expected_live_head_sha)
    if str(commit.get("sha") or "") != expected_live_head_sha:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation live commit SHA mismatch"
        )
    parents = commit.get("parents")
    if not isinstance(parents, list):
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation commit parent evidence is malformed"
        )

    merge_production_parent: str | None = None
    is_direct_child = (
        len(parents) == 1
        and isinstance(parents[0], dict)
        and str(parents[0].get("sha") or "") == claim.head_sha
    )
    if not is_direct_child:
        production_target = str(raw_claim.get("production_target") or "").strip()
        if not production_target:
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation merge sync requires production_target"
            )
        if (
            len(parents) != 2
            or not isinstance(parents[0], dict)
            or not isinstance(parents[1], dict)
            or str(parents[1].get("sha") or "") != claim.head_sha
        ):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation merge sync requires second parent "
                "to match claim HEAD"
            )

        merge_production_parent = str(parents[0].get("sha") or "")
        if not _SHA_RE.fullmatch(merge_production_parent):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production parent SHA is malformed"
            )

        encoded_target = urllib.parse.quote(production_target, safe="")
        production = _github_api_json(f"branches/{encoded_target}")
        if not isinstance(production, dict):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production branch response is malformed"
            )
        production_commit = production.get("commit")
        production_head = (
            str(production_commit.get("sha") or "")
            if isinstance(production_commit, dict)
            else ""
        )
        if not _SHA_RE.fullmatch(production_head):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation production target HEAD is malformed"
            )
        if production_head != merge_production_parent:
            comparison = _github_api_json(
                f"compare/{merge_production_parent}...{production_head}"
            )
            merge_base = (
                comparison.get("merge_base_commit")
                if isinstance(comparison, dict)
                else None
            )
            if (
                not isinstance(comparison, dict)
                or str(comparison.get("status") or "") not in {"ahead", "identical"}
                or not isinstance(merge_base, dict)
                or str(merge_base.get("sha") or "") != merge_production_parent
            ):
                raise ExecutionClaimError(
                    "post-commit claim-head reconciliation production parent is not "
                    "the exact target HEAD used for sync or an ancestor of current production"
                )

    files = commit.get("files")
    if not isinstance(files, list) or not files:
        raise ExecutionClaimError(
            "post-commit claim-head reconciliation commit changed-file evidence missing"
        )
    commit_files: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation commit changed-file evidence malformed"
            )
        filename = str(item["filename"])
        if filename in commit_files:
            raise ExecutionClaimError(
                "post-commit claim-head reconciliation commit changed-file evidence is ambiguous"
            )
        commit_files.append(filename)
    commit_file_set = tuple(sorted(commit_files))

    metadata = commit.get("commit")
    committer = metadata.get("committer") if isinstance(metadata, dict) else None
    committed_at = committer.get("date") if isinstance(committer, dict) else None
    commit_epoch = _reconcile_timestamp_epoch("commit", committed_at)

    comments = _github_issue_comments(issue)
    requests_by_id: dict[int, dict[str, object]] = {}
    for comment in comments:
        request = _parse_remote_guard_request_comment(comment)
        comment_id = request.get("comment_id") if request else None
        if request is not None and isinstance(comment_id, int):
            requests_by_id[comment_id] = request

    current_claim_blob = _git_blob_sha(path)
    raw_source = str(raw_claim.get("executor_source") or "").strip()
    expected_executor_source = "scheduler" if raw_source == "scheduler" else "chat"

    for comment in comments:
        receipt = _parse_remote_guard_receipt_comment(comment)
        if receipt is None:
            continue
        if receipt.get("schema") != "WHD_REMOTE_GUARD_RECEIPT_V1":
            continue
        if receipt.get("result") != "GREEN" or receipt.get("reason") != "EXECUTION_CLAIM_GUARD_GREEN":
            continue
        if receipt.get("action") not in {"write", "commit"}:
            continue
        if receipt.get("issue") != issue:
            continue
        if str(receipt.get("worker") or "") != worker:
            continue
        if str(receipt.get("executor_source") or "") != expected_executor_source:
            continue
        if str(receipt.get("branch") or "") != branch:
            continue
        if str(receipt.get("base_sha") or "") != claim.base_sha:
            continue
        if str(receipt.get("head_sha") or "") != claim.head_sha:
            continue
        if str(receipt.get("tested_target_sha") or "") != claim.head_sha:
            continue
        if str(receipt.get("claim_blob_sha") or "") != current_claim_blob:
            continue
        if (
            merge_production_parent is not None
            and str(receipt.get("guard_authority_sha") or "")
            != merge_production_parent
        ):
            continue

        receipt_files = receipt.get("changed_files")
        if not isinstance(receipt_files, list):
            continue
        receipt_file_set = tuple(sorted(str(item) for item in receipt_files))
        if len(receipt_file_set) != len(set(receipt_file_set)):
            continue
        if not set(commit_file_set).issubset(receipt_file_set):
            continue

        request_comment_id = receipt.get("request_comment_id")
        if isinstance(request_comment_id, bool) or not isinstance(request_comment_id, int):
            continue
        request = requests_by_id.get(request_comment_id)
        if request is None:
            continue
        fixed_keys = (
            "issue",
            "worker",
            "executor_source",
            "action",
            "branch",
            "base_sha",
            "head_sha",
            "claim_blob_sha",
            "guard_authority_sha",
            "tested_target_sha",
        )
        if any(str(request.get(key) or "") != str(receipt.get(key) or "") for key in fixed_keys):
            continue
        request_files = request.get("changed_files")
        if not isinstance(request_files, list):
            continue
        request_file_set = tuple(sorted(str(item) for item in request_files))
        if request_file_set != receipt_file_set:
            continue

        issued_epoch = _reconcile_timestamp_epoch("receipt issued_at", receipt.get("issued_at"))
        expires_epoch = _reconcile_timestamp_epoch("receipt expires_at", receipt.get("expires_at"))
        if issued_epoch <= commit_epoch <= expires_epoch:
            return

    raise ExecutionClaimError(
        "post-commit claim-head reconciliation lacks a matching prior GREEN mutation receipt "
        "bound to the current claim blob, direct child commit, changed-file set, and receipt window"
    )



def _assert_reopened_released_claim_reactivation(
    path: Path,
    *,
    claim: "ExecutionClaim",
    raw_claim: dict[str, object],
    issue: int,
    worker: str,
    branch: str,
    changed_files: tuple[str, ...],
) -> None:
    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    if changed_files != (expected_claim_path,):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery may write only the exact shared claim path"
        )
    if claim.phase != "RELEASED":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires phase=RELEASED"
        )
    if str(raw_claim.get("executor_source") or "").strip() != "scheduler":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery is restricted to scheduler-owned claims"
        )
    if not worker.startswith("scheduler."):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires a unique scheduler lane identity"
        )
    if branch != claim.work_branch:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery cannot use a delegated branch"
        )

    live_issue = _github_issue(issue)
    if str(live_issue.get("state") or "").lower() != "open":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires the owning Issue to be open"
        )
    if str(live_issue.get("state_reason") or "").lower() != "reopened":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires state_reason=reopened"
        )

    pointer: dict[str, str] | None = None
    for comment in _github_issue_comments(issue):
        user = comment.get("user")
        body = comment.get("body")
        if not isinstance(user, dict) or user.get("login") != "looaeedr":
            continue
        if not isinstance(body, str):
            continue
        lines = body.replace("\r\n", "\n").split("\n")
        if not lines or lines[0].strip() != "WHD_PROCESS_RECOVERY_POINTER_V1":
            continue
        fields: dict[str, str] = {}
        malformed = False
        for raw in lines[1:]:
            if not raw.strip():
                continue
            if "=" not in raw:
                malformed = True
                break
            key, value = raw.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key or not value or key in fields:
                malformed = True
                break
            fields[key] = value
        if malformed:
            continue
        if fields.get("process_state") != "REOPENED_INVALID_FINALIZATION_EVIDENCE":
            continue
        if fields.get("resume_condition") != "TRUSTED_REMOTE_FINALIZATION_EXECUTOR_INTEGRATED":
            continue
        if fields.get("resume_action") != "RUN_MACHINE_FINALIZATION_PROOF_THEN_CLOSE_READBACK_RELEASE":
            continue
        pointer = fields

    if pointer is None:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery lacks owner-authored WHD_PROCESS_RECOVERY_POINTER_V1"
        )

    try:
        blocking_issue = int(pointer["blocking_repair_issue"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery pointer has invalid blocking_repair_issue"
        ) from exc
    if blocking_issue <= 0 or blocking_issue == issue:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery pointer blocking issue is invalid"
        )

    repair = _github_issue(blocking_issue)
    repair_body = str(repair.get("body") or "")
    if f"#{issue}" not in repair_body:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery blocking issue is not bound to the owning Issue"
        )
    lowered = repair_body.lower()
    if "trusted" not in lowered or "finalization" not in lowered:
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery blocking issue does not describe trusted finalization repair"
        )

    workflow = _github_api_json(
        "contents/.github/workflows/whd-remote-finalization.yml?ref=main"
    )
    if not isinstance(workflow, dict) or workflow.get("type") != "file":
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery requires trusted finalization workflow on main"
        )
    workflow_sha = str(workflow.get("sha") or "")
    if not _SHA_RE.fullmatch(workflow_sha):
        raise ExecutionClaimError(
            "reopened RELEASED-claim recovery trusted workflow identity is malformed"
        )


def _normalize_delegated(payload: dict[str, object]) -> tuple[str, ...]:
    raw = payload.get("delegated_branches", [])
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ExecutionClaimError("malformed delegated_branches: expected list")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ExecutionClaimError(
                f"malformed delegated_branches[{index}]: expected nonblank branch"
            )
        result.append(item.strip())
    if len(set(result)) != len(result):
        raise ExecutionClaimError("malformed delegated_branches: duplicate branch")
    return tuple(result)


@dataclass(frozen=True)
class ExecutionClaim:
    issue: int
    issue_url: str
    worker: str
    work_branch: str
    claimed_at: str
    base_sha: str
    head_sha: str
    phase: str
    delegated_branches: tuple[str, ...] = ()


def load_execution_claim(
    path: Path, *, allow_released_recovery: bool = False
) -> ExecutionClaim:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"execution claim not found: {path}") from exc
    except ExecutionClaimError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"malformed execution claim {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ExecutionClaimError("malformed execution claim: root must be an object")

    issue = payload.get("issue")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("missing required claim field: issue")

    issue_url = _require_text(payload, "issue_url")
    worker = _require_text(payload, "worker")
    work_branch = _require_text(payload, "work_branch")
    claimed_at = _require_text(payload, "claimed_at")
    base_sha = _require_sha(payload, "base_sha")
    head_sha = _require_sha(payload, "head_sha")
    phase = _require_text(payload, "phase").upper()
    delegated = _normalize_delegated(payload)

    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if issue_url != expected_url:
        raise ExecutionClaimError(
            f"claim issue_url mismatch: expected {expected_url!r}, got {issue_url!r}"
        )
    if phase in INACTIVE_PHASES:
        if not (allow_released_recovery and phase == "RELEASED"):
            raise ExecutionClaimError(f"execution claim is inactive: phase={phase}")
    elif phase not in ACTIVE_PHASES:
        raise ExecutionClaimError(f"ambiguous execution claim state: unknown phase={phase}")

    return ExecutionClaim(
        issue=issue,
        issue_url=issue_url,
        worker=worker,
        work_branch=work_branch,
        claimed_at=claimed_at,
        base_sha=base_sha,
        head_sha=head_sha,
        phase=phase,
        delegated_branches=delegated,
    )


def assert_execution_claim(
    path: Path,
    *,
    issue: int,
    worker: str,
    branch: str,
    action: str,
    expected_base_sha: str,
    expected_head_sha: str,
    changed_files: Iterable[str] = (),
    preflight_evidence: Iterable[str] = (),
    takeover_evidence: Path | None = None,
    user_authority_evidence: Path | None = None,
) -> ExecutionClaim:
    """Return the validated current claim or raise before one repository action."""
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("issue must be a positive integer")
    worker = str(worker).strip()
    branch = str(branch).strip()
    action = str(action).strip()
    expected_base_sha = _validate_sha(expected_base_sha, "expected base SHA")
    expected_head_sha = _validate_sha(expected_head_sha, "expected head SHA")
    if not worker:
        raise ExecutionClaimError("worker must be nonblank")
    if not branch:
        raise ExecutionClaimError("branch must be nonblank")
    if action not in ALLOWED_ACTIONS:
        raise ExecutionClaimError(
            f"unsupported guarded action {action!r}; allowed={sorted(ALLOWED_ACTIONS)!r}"
        )

    normalized_changed_files = _normalize_changed_files(changed_files)
    if action in FILE_MUTATION_ACTIONS and not normalized_changed_files:
        raise ExecutionClaimError(
            f"changed-file identity is required for guarded action {action!r}"
        )

    expected_claim_path = f".dispatch/claims/issue-{issue}.json"
    allow_released_recovery = (
        action == "write" and normalized_changed_files == (expected_claim_path,)
    )
    claim = load_execution_claim(
        path, allow_released_recovery=allow_released_recovery
    )
    if claim.issue != issue:
        raise ExecutionClaimError(
            f"issue mismatch: requested #{issue}, claim owns #{claim.issue}"
        )
    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if claim.issue_url != expected_url:
        raise ExecutionClaimError(
            f"issue URL mismatch: expected {expected_url!r}, got {claim.issue_url!r}"
        )
    if claim.worker != worker:
        raise ExecutionClaimError(
            f"worker is not claim owner: requested={worker!r}, owner={claim.worker!r}"
        )
    if claim.base_sha != expected_base_sha:
        raise ExecutionClaimError(
            f"base SHA mismatch: expected={expected_base_sha}, claim={claim.base_sha}"
        )
    allowed_branches = {claim.work_branch, *claim.delegated_branches}
    if branch not in allowed_branches:
        raise ExecutionClaimError(
            f"branch is not authorized by execution claim: {branch!r}; "
            f"owner_branch={claim.work_branch!r}; delegated={claim.delegated_branches!r}"
        )

    raw_claim: dict[str, object] | None = None
    if claim.phase == "RELEASED":
        raw_claim = _load_raw_claim_payload(path)
        _assert_reopened_released_claim_reactivation(
            path,
            claim=claim,
            raw_claim=raw_claim,
            issue=issue,
            worker=worker,
            branch=branch,
            changed_files=normalized_changed_files,
        )

    if action != "claim-takeover" and claim.head_sha != expected_head_sha:
        if action == "write" and normalized_changed_files == (expected_claim_path,):
            raw_claim = _load_raw_claim_payload(path)
            _assert_post_commit_claim_head_reconciliation(
                path,
                claim=claim,
                raw_claim=raw_claim,
                issue=issue,
                worker=worker,
                branch=branch,
                expected_live_head_sha=expected_head_sha,
                changed_files=normalized_changed_files,
            )
        else:
            raise ExecutionClaimError(
                f"stale claim head SHA: expected={expected_head_sha}, claim={claim.head_sha}"
            )

    if action == "claim-takeover":
        raw_claim = raw_claim or _load_raw_claim_payload(path)
        _assert_takeover_evidence(
            takeover_evidence,
            claim_path=path,
            claim=claim,
            raw_claim=raw_claim,
            expected_live_head_sha=expected_head_sha,
            user_authority_evidence=user_authority_evidence,
        )

    if action in FILE_MUTATION_ACTIONS:
        _assert_skill_authoring_preflight(
            normalized_changed_files,
            preflight_evidence,
        )
    return claim


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed unless the caller owns the current shared WHD execution claim"
    )
    parser.add_argument("--claim", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--base-sha", required=True, dest="expected_base_sha")
    parser.add_argument("--head-sha", required=True, dest="expected_head_sha")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="repository-relative file mutated by write/commit; repeat for multiple files",
    )
    parser.add_argument(
        "--preflight-evidence",
        action="append",
        default=[],
        help="Phase6 Preflight evidence file; required when a changed file is a Skill SKILL.md",
    )
    parser.add_argument(
        "--takeover-evidence",
        type=Path,
        help="machine evidence emitted by tools/stale_claim_takeover.py; required for claim-takeover",
    )
    parser.add_argument(
        "--user-authority-evidence",
        type=Path,
        help="owner-authored WHD_USER_DIRECTED_TAKEOVER_V1 GitHub issue-comment JSON; required for interactive takeover",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        claim = assert_execution_claim(
            args.claim,
            issue=args.issue,
            worker=args.worker,
            branch=args.branch,
            action=args.action,
            expected_base_sha=args.expected_base_sha,
            expected_head_sha=args.expected_head_sha,
            changed_files=args.changed_file,
            preflight_evidence=args.preflight_evidence,
            takeover_evidence=args.takeover_evidence,
            user_authority_evidence=args.user_authority_evidence,
        )
    except ExecutionClaimError as exc:
        print(f"EXECUTION_CLAIM_GUARD_ERROR: {exc}")
        return 2
    print(
        "EXECUTION_CLAIM_GUARD_GREEN "
        f"issue={claim.issue} worker={claim.worker} branch={args.branch} action={args.action} "
        f"base_sha={claim.base_sha} head_sha={claim.head_sha} phase={claim.phase}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
