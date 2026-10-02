"""Canonical fail-closed validator for sealed parent-branch identity repair.

This module validates only the durable claim/checkpoint projection for one repair.
It does not mutate refs, acquire claims, or create an independent continuity state
machine. The trusted transport owns GitHub readback and exact coordination CAS.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class ParentBranchIdentityRepairError(RuntimeError):
    """Raised when a sealed-identity repair attempts to widen authority."""


def _branch(value: object, label: str) -> str:
    branch = str(value or "").strip()
    if (
        not _BRANCH_RE.fullmatch(branch)
        or branch.startswith("/")
        or branch.endswith("/")
        or ".." in branch
        or "//" in branch
        or "@{" in branch
    ):
        raise ParentBranchIdentityRepairError(f"{label} is invalid")
    return branch


def _sha(value: object, label: str) -> str:
    sha = str(value or "").strip()
    if not _SHA_RE.fullmatch(sha):
        raise ParentBranchIdentityRepairError(f"{label} is invalid")
    return sha


def _object(value: Mapping[str, Any] | object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ParentBranchIdentityRepairError(f"{label} must be an object")
    return dict(value)


def validate_parent_branch_identity_repair_candidate(
    *,
    current_claim: Mapping[str, Any],
    current_checkpoint: Mapping[str, Any],
    candidate_claim: Mapping[str, Any],
    candidate_checkpoint: Mapping[str, Any],
    original_branch: str,
    replacement_branch: str,
    sealed_head_sha: str,
) -> None:
    """Require an exact branch-only durable rebind around an already sealed HEAD.

    The current pair must already agree on the original branch and sealed HEAD.
    The candidate pair must be identical except for claim.work_branch and
    checkpoint.branch moving to the replacement branch.
    """

    original = _branch(original_branch, "original branch")
    replacement = _branch(replacement_branch, "replacement branch")
    sealed = _sha(sealed_head_sha, "sealed head SHA")
    if replacement == original:
        raise ParentBranchIdentityRepairError(
            "replacement branch must differ from original branch"
        )

    live_claim = _object(current_claim, "current claim")
    live_checkpoint = _object(current_checkpoint, "current checkpoint")
    next_claim = _object(candidate_claim, "candidate claim")
    next_checkpoint = _object(candidate_checkpoint, "candidate checkpoint")

    if str(live_claim.get("work_branch") or "") != original:
        raise ParentBranchIdentityRepairError("current claim branch is not original branch")
    if str(live_checkpoint.get("branch") or "") != original:
        raise ParentBranchIdentityRepairError(
            "current checkpoint branch is not original branch"
        )
    if _sha(live_claim.get("head_sha"), "current claim head SHA") != sealed:
        raise ParentBranchIdentityRepairError("current claim is not sealed at requested HEAD")
    if _sha(live_checkpoint.get("head_sha"), "current checkpoint head SHA") != sealed:
        raise ParentBranchIdentityRepairError(
            "current checkpoint is not sealed at requested HEAD"
        )

    claim_issue = str(live_claim.get("issue") or "")
    checkpoint_issue = str(live_checkpoint.get("issue") or "")
    if not claim_issue or claim_issue != checkpoint_issue:
        raise ParentBranchIdentityRepairError("current claim/checkpoint issue mismatch")

    expected_claim = dict(live_claim)
    expected_claim["work_branch"] = replacement
    expected_checkpoint = dict(live_checkpoint)
    expected_checkpoint["branch"] = replacement

    if next_claim != expected_claim:
        raise ParentBranchIdentityRepairError(
            "candidate claim must change only work_branch"
        )
    if next_checkpoint != expected_checkpoint:
        raise ParentBranchIdentityRepairError(
            "candidate checkpoint must change only branch"
        )

    if _sha(next_claim.get("head_sha"), "candidate claim head SHA") != sealed:
        raise ParentBranchIdentityRepairError("candidate claim changed sealed HEAD")
    if _sha(next_checkpoint.get("head_sha"), "candidate checkpoint head SHA") != sealed:
        raise ParentBranchIdentityRepairError("candidate checkpoint changed sealed HEAD")
