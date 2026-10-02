"""WHD shared unpushed integration lane hard gates.

This module owns the machine rules for the shared `.unpushed/{body|docs}/0`
model.  It deliberately fails closed on merge conflicts: a conflict must be
checkpointed and surfaced to the user; automated conflict resolution is
forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

SCHEMA = "WHD_SHARED_UNPUSHED_INTEGRATION_V1"
CONFLICT_CHECKPOINT_SCHEMA = "WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1"
LANE_EVIDENCE_SCHEMA = "WHD_UNPUSHED_LANE_EVIDENCE_V1"
CONFLICT_STATE = "BLOCKED_USER_DECISION"
LANES = {"body", "docs"}


class UnpushedIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class ConflictCheckpoint:
    lane: str
    path: str
    base_generation: int
    latest_generation: int
    base_hash: str
    latest_hash: str
    worker_hash: str
    conflict_hunks: tuple[str, ...]
    worker: str
    issue: str
    state: str = CONFLICT_STATE
    schema: str = CONFLICT_CHECKPOINT_SCHEMA

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "state": self.state,
            "lane": self.lane,
            "path": self.path,
            "base_generation": self.base_generation,
            "latest_generation": self.latest_generation,
            "base_hash": self.base_hash,
            "latest_hash": self.latest_hash,
            "worker_hash": self.worker_hash,
            "conflict_hunks": list(self.conflict_hunks),
            "worker": self.worker,
            "issue": self.issue,
            "requires": "EXPLICIT_USER_CONFLICT_DECISION",
            "forbidden": [
                "AUTO_RESOLVE",
                "AUTO_OURS",
                "AUTO_THEIRS",
                "AUTO_REWRITE",
                "ADVANCE_GENERATION",
                "RUN_PUSH",
                "CREATE_DELIVERY_BRANCH",
            ],
        }



def validate_lane_evidence(evidence: Mapping[str, object]) -> dict[str, object]:
    item = dict(evidence)
    if item.get("schema") != LANE_EVIDENCE_SCHEMA:
        raise UnpushedIntegrationError("invalid unpushed lane evidence schema")
    lane = str(item.get("lane") or "")
    if lane not in LANES:
        raise UnpushedIntegrationError(f"invalid lane: {lane}")
    if isinstance(item.get("issue"), bool) or int(item.get("issue") or 0) <= 0:
        raise UnpushedIntegrationError("lane evidence issue must be positive")
    import re
    source_sha = str(item.get("source_sha") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise UnpushedIntegrationError("lane evidence source_sha must be a Git SHA")
    if not str(item.get("target_branch") or "").strip():
        raise UnpushedIntegrationError("lane evidence target_branch must be nonblank")
    generation = item.get("generation")
    if isinstance(generation, bool) or int(generation or 0) <= 0:
        raise UnpushedIntegrationError("lane evidence generation must be positive")
    paths = item.get("write_paths")
    deletes = item.get("delete_paths")
    if not isinstance(paths, list) or not isinstance(deletes, list):
        raise UnpushedIntegrationError("lane evidence paths must be arrays")
    overlap = set(map(str, paths)) & set(map(str, deletes))
    if overlap:
        raise UnpushedIntegrationError(f"lane evidence write/delete overlap: {sorted(overlap)}")
    digest = str(item.get("manifest_digest") or "").lower()
    if digest and not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise UnpushedIntegrationError("lane evidence manifest_digest must be SHA256")
    state = str(item.get("state") or "ACTIVE")
    if state not in {"ACTIVE", "MERGED_TO_0", "FROZEN"}:
        raise UnpushedIntegrationError(f"invalid lane evidence state: {state}")
    return item


def build_lane_evidence(
    *, lane: str, issue: int, source_sha: str, target_branch: str, generation: int,
    write_paths: Iterable[str], delete_paths: Iterable[str] = (),
    manifest_digest: str = "", state: str = "ACTIVE",
) -> dict[str, object]:
    return validate_lane_evidence({
        "schema": LANE_EVIDENCE_SCHEMA,
        "lane": lane,
        "issue": issue,
        "source_sha": source_sha,
        "target_branch": target_branch,
        "generation": generation,
        "write_paths": sorted(set(map(str, write_paths))),
        "delete_paths": sorted(set(map(str, delete_paths))),
        "manifest_digest": manifest_digest,
        "state": state,
    })

def classify_lane(*, path: str, ownership: str, product_required: bool = False) -> str:
    """Classify by semantic ownership, never by file extension alone."""
    ownership = str(ownership or "").strip().lower()
    if product_required:
        return "body"
    if ownership in {
        "product", "product_code", "product_test", "ui", "renderer",
        "geometry", "manufacturing", "product_contract", "product_required_doc",
    }:
        return "body"
    if ownership in {
        "governance", "skill", "agents", "process", "authority", "registry",
        "sop", "governance_contract", "governance_test", "human_doc", "docs",
    }:
        return "docs"
    raise UnpushedIntegrationError(
        f"UNCLASSIFIED_PATH_OWNERSHIP path={path!r} ownership={ownership!r}"
    )


def assert_worker_base_is_latest(*, base_generation: int, latest_generation: int) -> None:
    if int(base_generation) != int(latest_generation):
        raise UnpushedIntegrationError(
            "STALE_0_BASE_REQUIRES_REBASE_TO_LATEST_0 "
            f"base_generation={base_generation} latest_generation={latest_generation}"
        )


def next_generation(*, latest_generation: int, has_conflict: bool) -> int:
    if has_conflict:
        raise UnpushedIntegrationError(
            "MERGE_CONFLICT_BLOCKS_GENERATION_ADVANCE_UNTIL_USER_DECISION"
        )
    if int(latest_generation) < 0:
        raise UnpushedIntegrationError("latest_generation must be non-negative")
    return int(latest_generation) + 1


def build_conflict_checkpoint(
    *,
    lane: str,
    path: str,
    base_generation: int,
    latest_generation: int,
    base_hash: str,
    latest_hash: str,
    worker_hash: str,
    conflict_hunks: Iterable[str],
    worker: str,
    issue: str,
) -> dict[str, object]:
    lane = str(lane)
    if lane not in LANES:
        raise UnpushedIntegrationError(f"invalid lane: {lane}")
    hunks = tuple(str(x) for x in conflict_hunks if str(x).strip())
    if not hunks:
        raise UnpushedIntegrationError("conflict checkpoint requires conflict hunks")
    for label, value in {
        "path": path,
        "base_hash": base_hash,
        "latest_hash": latest_hash,
        "worker_hash": worker_hash,
        "worker": worker,
        "issue": issue,
    }.items():
        if not str(value).strip():
            raise UnpushedIntegrationError(f"conflict checkpoint missing {label}")
    return ConflictCheckpoint(
        lane=lane,
        path=str(path),
        base_generation=int(base_generation),
        latest_generation=int(latest_generation),
        base_hash=str(base_hash),
        latest_hash=str(latest_hash),
        worker_hash=str(worker_hash),
        conflict_hunks=hunks,
        worker=str(worker),
        issue=str(issue),
    ).as_dict()


def assert_conflict_checkpoint_blocks_action(
    checkpoint: Mapping[str, object], *, action: str, user_decision: str | None = None
) -> None:
    if checkpoint.get("schema") != CONFLICT_CHECKPOINT_SCHEMA:
        raise UnpushedIntegrationError("invalid conflict checkpoint schema")
    if checkpoint.get("state") != CONFLICT_STATE:
        return
    if not (user_decision or "").strip():
        raise UnpushedIntegrationError(
            f"BLOCKED_USER_DECISION action={action}: explicit user conflict decision required"
        )


def assert_push_scope(*, selected_lane: str, manifest_paths: Iterable[str], staged_paths: Iterable[str]) -> None:
    if selected_lane not in LANES:
        raise UnpushedIntegrationError(f"invalid selected lane: {selected_lane}")
    expected = tuple(sorted(set(map(str, manifest_paths))))
    actual = tuple(sorted(set(map(str, staged_paths))))
    if expected != actual:
        raise UnpushedIntegrationError(
            f"PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST expected={expected} actual={actual}"
        )
