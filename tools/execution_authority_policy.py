"""Flow v2 execution-state authority boundary.

After production cutover, legacy claim/checkpoint files remain readable audit
artifacts but cannot be written by normal execution paths. Native semantic state
lives only under .dispatch/execution on the dedicated coordination branch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

SCHEMA = "WHD_FLOW_V2_AUTHORITY_POLICY_V1"
CANONICAL_STATE_BRANCH = "coord/execution-v2"
NATIVE_ROOT = PurePosixPath(".dispatch/execution")
LEGACY_ROOTS = (
    PurePosixPath(".dispatch/claims"),
    PurePosixPath(".dispatch/checkpoints"),
)

class ExecutionAuthorityError(ValueError):
    pass

@dataclass(frozen=True)
class MutationAuthority:
    branch: str
    path: str
    classification: str
    allowed: bool


def classify_execution_path(path: str) -> str:
    p = PurePosixPath(str(path).strip())
    if p.parent == NATIVE_ROOT and p.name.startswith("issue-") and p.suffix == ".json":
        return "NATIVE_EXECUTION_RECORD"
    if any(p.parent == root for root in LEGACY_ROOTS):
        return "LEGACY_AUDIT_ONLY"
    if p == NATIVE_ROOT / "ready-index.json":
        return "DERIVED_READY_INDEX"
    return "NON_EXECUTION_STATE"


def authorize_state_mutation(*, branch: str, path: str) -> MutationAuthority:
    branch = str(branch or "").strip()
    classification = classify_execution_path(path)
    allowed = branch == CANONICAL_STATE_BRANCH and classification in {
        "NATIVE_EXECUTION_RECORD", "DERIVED_READY_INDEX"
    }
    if classification == "LEGACY_AUDIT_ONLY":
        allowed = False
    return MutationAuthority(branch=branch, path=path, classification=classification, allowed=allowed)


def require_state_mutation_authority(*, branch: str, path: str) -> None:
    decision = authorize_state_mutation(branch=branch, path=path)
    if not decision.allowed:
        raise ExecutionAuthorityError(
            f"Flow v2 state mutation denied: branch={branch!r} path={path!r} "
            f"classification={decision.classification}"
        )
