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
DELIVERY_FILESET_LOCK_SCHEMA = "WHD_DELIVERY_FILESET_LOCK_V1"
DELIVERY_FINALIZATION_SCHEMA = "WHD_FINALIZE_DELIVERED_PATHS_V1"
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



def _normalize_hash(value: object, *, label: str, allow_delete_marker: bool = False) -> str:
    import re
    text = str(value or "").strip().lower()
    if allow_delete_marker and text == "delete":
        return "DELETE"
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise UnpushedIntegrationError(f"{label} must be SHA256")
    return text


def build_delivery_fileset_lock(
    *,
    lane: str,
    generation: int,
    manifest_digest: str,
    source_zero_identity: str,
    invocation_identity: str,
    write_hashes: Mapping[str, str],
    delete_paths: Iterable[str] = (),
    target_base_hashes: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Freeze the exact file set that one /推推 delivery is allowed to carry."""
    if lane not in LANES:
        raise UnpushedIntegrationError(f"invalid lane: {lane}")
    if isinstance(generation, bool) or int(generation) <= 0:
        raise UnpushedIntegrationError("delivery fileset generation must be positive")
    digest = _normalize_hash(manifest_digest, label="manifest_digest")
    if not str(source_zero_identity or "").strip():
        raise UnpushedIntegrationError("source_zero_identity must be nonblank")
    if not str(invocation_identity or "").strip():
        raise UnpushedIntegrationError("invocation_identity must be nonblank")

    writes = {str(k): _normalize_hash(v, label=f"write_hash[{k}]") for k, v in write_hashes.items()}
    deletes = sorted(set(map(str, delete_paths)))
    overlap = set(writes) & set(deletes)
    if overlap:
        raise UnpushedIntegrationError(f"delivery write/delete overlap: {sorted(overlap)}")
    paths = sorted(set(writes) | set(deletes))
    if not paths:
        raise UnpushedIntegrationError("delivery fileset lock cannot be empty")

    base = {}
    for path, value in (target_base_hashes or {}).items():
        path = str(path)
        if path not in paths:
            raise UnpushedIntegrationError(f"target_base_hash path not locked: {path}")
        base[path] = _normalize_hash(value, label=f"target_base_hash[{path}]", allow_delete_marker=True)

    return {
        "schema": DELIVERY_FILESET_LOCK_SCHEMA,
        "lane": lane,
        "generation": int(generation),
        "manifest_digest": digest,
        "source_zero_identity": str(source_zero_identity),
        "invocation_identity": str(invocation_identity),
        "write_hashes": dict(sorted(writes.items())),
        "delete_paths": deletes,
        "locked_paths": paths,
        "target_base_hashes": dict(sorted(base.items())),
        "scope_rule": "EXACT_LOCK_EQUALITY",
    }


def validate_delivery_fileset_lock(lock: Mapping[str, object]) -> dict[str, object]:
    item = dict(lock)
    if item.get("schema") != DELIVERY_FILESET_LOCK_SCHEMA:
        raise UnpushedIntegrationError("invalid delivery fileset lock schema")
    rebuilt = build_delivery_fileset_lock(
        lane=str(item.get("lane") or ""),
        generation=int(item.get("generation") or 0),
        manifest_digest=str(item.get("manifest_digest") or ""),
        source_zero_identity=str(item.get("source_zero_identity") or ""),
        invocation_identity=str(item.get("invocation_identity") or ""),
        write_hashes=item.get("write_hashes") if isinstance(item.get("write_hashes"), Mapping) else {},
        delete_paths=item.get("delete_paths") if isinstance(item.get("delete_paths"), list) else (),
        target_base_hashes=item.get("target_base_hashes") if isinstance(item.get("target_base_hashes"), Mapping) else {},
    )
    if item.get("locked_paths") != rebuilt["locked_paths"]:
        raise UnpushedIntegrationError("delivery locked_paths do not match write/delete set")
    if item.get("scope_rule") != "EXACT_LOCK_EQUALITY":
        raise UnpushedIntegrationError("delivery scope rule must be EXACT_LOCK_EQUALITY")
    return item


def assert_push_scope_matches_lock(*, lock: Mapping[str, object], changed_paths: Iterable[str]) -> None:
    item = validate_delivery_fileset_lock(lock)
    expected = tuple(item["locked_paths"])
    actual = tuple(sorted(set(map(str, changed_paths))))
    if expected != actual:
        raise UnpushedIntegrationError(
            f"PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_LOCK expected={expected} actual={actual}"
        )


def assert_delivery_hashes_match_lock(*, lock: Mapping[str, object], delivery_hashes: Mapping[str, str]) -> None:
    item = validate_delivery_fileset_lock(lock)
    expected = dict(item["write_hashes"])
    actual = {str(k): _normalize_hash(v, label=f"delivery_hash[{k}]") for k, v in delivery_hashes.items()}
    if expected != actual:
        raise UnpushedIntegrationError("DELIVERY_BLOB_HASH_MUST_EQUAL_FROZEN_LOCK")


def assert_premerge_latest_file_recheck(
    *,
    lock: Mapping[str, object],
    fresh_target_hashes: Mapping[str, str],
    delivery_hashes: Mapping[str, str],
    changed_paths: Iterable[str],
) -> None:
    """Fail closed if the target changed any locked path after the delivery lock was built."""
    item = validate_delivery_fileset_lock(lock)
    assert_push_scope_matches_lock(lock=item, changed_paths=changed_paths)
    assert_delivery_hashes_match_lock(lock=item, delivery_hashes=delivery_hashes)
    base = dict(item.get("target_base_hashes") or {})
    if set(base) != set(item["locked_paths"]):
        raise UnpushedIntegrationError("PRE_MERGE_RECHECK_REQUIRES_TARGET_BASE_HASH_FOR_EVERY_LOCKED_PATH")
    fresh = {
        str(k): _normalize_hash(v, label=f"fresh_target_hash[{k}]", allow_delete_marker=True)
        for k, v in fresh_target_hashes.items()
    }
    if set(fresh) != set(item["locked_paths"]):
        raise UnpushedIntegrationError("PRE_MERGE_RECHECK_REQUIRES_FRESH_HASH_FOR_EVERY_LOCKED_PATH")
    touched = sorted(path for path in item["locked_paths"] if base[path] != fresh[path])
    if touched:
        raise UnpushedIntegrationError(
            "TARGET_TOUCHED_LOCKED_PATH_REQUIRES_ROOT_0_RECONCILE_RETEST_REFREEZE "
            f"paths={touched}"
        )


def finalize_delivered_paths(
    *,
    lock: Mapping[str, object],
    merge_readback_verified: bool,
    accepted_commit: str,
    readback_hashes: Mapping[str, str],
    current_zero_hashes: Mapping[str, str],
    later_or_foreign_paths: Iterable[str] = (),
    cleared_at: str,
) -> dict[str, object]:
    """Return the exact paths that may be cleared from unpushed state after durable readback."""
    item = validate_delivery_fileset_lock(lock)
    if not merge_readback_verified:
        raise UnpushedIntegrationError("MERGE_READBACK_VERIFIED_REQUIRED_BEFORE_FINALIZE")
    if not str(accepted_commit or "").strip():
        raise UnpushedIntegrationError("accepted_commit must be nonblank")
    if not str(cleared_at or "").strip():
        raise UnpushedIntegrationError("cleared_at must be nonblank")

    readback = {
        str(k): _normalize_hash(v, label=f"readback_hash[{k}]")
        for k, v in readback_hashes.items()
    }
    current = {
        str(k): _normalize_hash(v, label=f"current_zero_hash[{k}]")
        for k, v in current_zero_hashes.items()
    }
    foreign = set(map(str, later_or_foreign_paths))
    expected_writes = dict(item["write_hashes"])
    cleared: list[str] = []
    preserved: list[str] = []
    for path in item["locked_paths"]:
        if path in foreign:
            preserved.append(path)
            continue
        if path in expected_writes:
            if readback.get(path) != expected_writes[path] or current.get(path) != expected_writes[path]:
                preserved.append(path)
                continue
        else:
            # Delete paths are cleared only when the accepted target no longer has the path.
            if path in readback or path in current:
                preserved.append(path)
                continue
        cleared.append(path)

    return {
        "schema": DELIVERY_FINALIZATION_SCHEMA,
        "lane": item["lane"],
        "generation": item["generation"],
        "manifest_digest": item["manifest_digest"],
        "accepted_commit": str(accepted_commit),
        "cleared_paths": sorted(cleared),
        "preserved_paths": sorted(preserved),
        "delivered_hashes": dict(sorted(expected_writes.items())),
        "cleared_at": str(cleared_at),
        "repository_files_deleted": False,
        "future_modification_rule": "RE_REGISTER_AS_NEW_UNPUSHED_CHANGE_FROM_CURRENT_ROOT_OR_LATEST_0",
    }
