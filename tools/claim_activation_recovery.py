"""Pure durable-readback classifier for trusted Claim Activation crash re-entry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ClaimActivationReadbackState(str, Enum):
    NOT_APPLIED = "NOT_APPLIED"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class ClaimActivationReadbackDecision:
    state: ClaimActivationReadbackState
    commit_sha: str | None
    reason: str


def _decision(
    state: ClaimActivationReadbackState,
    *,
    commit_sha: str | None = None,
    reason: str,
) -> ClaimActivationReadbackDecision:
    return ClaimActivationReadbackDecision(
        state=state,
        commit_sha=commit_sha,
        reason=reason,
    )


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA_RE.fullmatch(value) is not None


def _files(values: Iterable[str]) -> tuple[str, ...] | None:
    normalized = tuple(str(value) for value in values)
    if not all(normalized) or len(normalized) != len(set(normalized)):
        return None
    return tuple(sorted(normalized))


def classify_claim_activation_readback(
    *,
    coord_parent_sha: str,
    current_coord_sha: str,
    current_parent_shas: Iterable[str],
    current_changed_files: Iterable[str],
    claim_path: str,
    checkpoint_path: str,
    current_claim_blob_sha: str,
    current_checkpoint_blob_sha: str,
    candidate_claim_blob_sha: str,
    candidate_checkpoint_blob_sha: str,
) -> ClaimActivationReadbackDecision:
    """Classify whether one fixed Claim Activation CAS is absent, applied, or ambiguous.

    NOT_APPLIED means the exact requested coordination parent is still current, so
    the caller may attempt the one guarded CAS. EFFECT_OBSERVED means the current
    coordination head is exactly one direct child of that parent and contains only
    the requested claim/checkpoint candidate blobs. Every other state fails closed
    as AMBIGUOUS.
    """

    if not _valid_sha(coord_parent_sha) or not _valid_sha(current_coord_sha):
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="coordination parent/current SHA is malformed",
        )
    if not claim_path or not checkpoint_path or claim_path == checkpoint_path:
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="claim/checkpoint path identity is malformed",
        )
    if not _valid_sha(candidate_claim_blob_sha) or not _valid_sha(
        candidate_checkpoint_blob_sha
    ):
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="candidate claim/checkpoint blob SHA is malformed",
        )

    if current_coord_sha == coord_parent_sha:
        return _decision(
            ClaimActivationReadbackState.NOT_APPLIED,
            reason="requested coordination parent is still current",
        )

    parents = tuple(str(value) for value in current_parent_shas)
    if parents != (coord_parent_sha,):
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="current coordination head is not the exact direct child of requested parent",
        )

    changed = _files(current_changed_files)
    expected = tuple(sorted((claim_path, checkpoint_path)))
    if changed != expected:
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="current coordination commit changed-file set does not match activation pair",
        )

    if (
        current_claim_blob_sha != candidate_claim_blob_sha
        or current_checkpoint_blob_sha != candidate_checkpoint_blob_sha
    ):
        return _decision(
            ClaimActivationReadbackState.AMBIGUOUS,
            reason="current coordination claim/checkpoint blobs do not match activation candidates",
        )

    return _decision(
        ClaimActivationReadbackState.EFFECT_OBSERVED,
        commit_sha=current_coord_sha,
        reason="exact Claim Activation candidate pair is already durably applied",
    )
