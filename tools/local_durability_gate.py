"""Side-effect-free local workstation durability classifier for WHD."""

from __future__ import annotations

import re
from enum import Enum
from typing import Mapping

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SCHEMA = "WHD_LOCAL_DURABILITY_SNAPSHOT_V1"
RESULT_SCHEMA = "WHD_LOCAL_DURABILITY_V1"


class LocalDurabilityError(RuntimeError):
    """Raised when a local durability snapshot is malformed."""


class LocalDurabilityState(str, Enum):
    LOCAL_CLEAN_SYNCED = "LOCAL_CLEAN_SYNCED"
    LOCAL_DIRTY_RECOVERABLE = "LOCAL_DIRTY_RECOVERABLE"
    LOCAL_DIRTY_CONFLICT = "LOCAL_DIRTY_CONFLICT"
    LOCAL_UNPUSHED = "LOCAL_UNPUSHED"
    LOCAL_MUTATION_IN_PROGRESS = "LOCAL_MUTATION_IN_PROGRESS"
    LOCAL_MACHINE_UNAVAILABLE = "LOCAL_MACHINE_UNAVAILABLE"


def _decision(
    snapshot: Mapping[str, object],
    state: LocalDurabilityState,
    result: str,
    reason: str,
) -> dict[str, object]:
    return {
        "schema": RESULT_SCHEMA,
        "state": state.value,
        "poweroff_result": result,
        "poweroff_reason": reason,
        "branch": snapshot.get("branch"),
        "local_head_sha": snapshot.get("local_head_sha"),
        "remote_head_sha": snapshot.get("remote_head_sha"),
        "worktree_clean": snapshot.get("worktree_clean"),
        "has_conflicts": snapshot.get("has_conflicts"),
        "unpushed_commits": snapshot.get("unpushed_commits"),
        "mutation_in_progress": snapshot.get("mutation_in_progress"),
    }


def _require_bool_or_none(name: str, value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise LocalDurabilityError(f"{name} must be boolean or null")
    return value


def _require_unpushed_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LocalDurabilityError("unpushed_commits must be a non-negative integer or null")
    return value


def classify_local_durability(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Classify one fresh local-machine snapshot without mutating any external state."""

    if not isinstance(snapshot, Mapping):
        raise LocalDurabilityError("snapshot must be a mapping")
    if snapshot.get("schema") != SCHEMA:
        raise LocalDurabilityError(f"schema must be {SCHEMA}")

    reachable = snapshot.get("machine_reachable")
    if not isinstance(reachable, bool):
        raise LocalDurabilityError("machine_reachable must be boolean")

    if reachable is False:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_MACHINE_UNAVAILABLE,
            "ERROR",
            "LOCAL_MACHINE_UNREACHABLE",
        )

    branch = snapshot.get("branch")
    local_head = snapshot.get("local_head_sha")
    remote_head = snapshot.get("remote_head_sha")
    worktree_clean = _require_bool_or_none("worktree_clean", snapshot.get("worktree_clean"))
    has_conflicts = _require_bool_or_none("has_conflicts", snapshot.get("has_conflicts"))
    mutation = _require_bool_or_none(
        "mutation_in_progress", snapshot.get("mutation_in_progress")
    )
    unpushed = _require_unpushed_or_none(snapshot.get("unpushed_commits"))

    complete = (
        isinstance(branch, str)
        and bool(branch.strip())
        and isinstance(local_head, str)
        and bool(_SHA_RE.fullmatch(local_head))
        and isinstance(remote_head, str)
        and bool(_SHA_RE.fullmatch(remote_head))
        and worktree_clean is not None
        and has_conflicts is not None
        and mutation is not None
        and unpushed is not None
    )
    if not complete:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_DIRTY_CONFLICT,
            "NOT_SAFE",
            "LOCAL_STATE_CONFLICT",
        )

    if mutation:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_MUTATION_IN_PROGRESS,
            "NOT_SAFE",
            "LOCAL_MUTATION_IN_PROGRESS",
        )
    if has_conflicts:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_DIRTY_CONFLICT,
            "NOT_SAFE",
            "LOCAL_STATE_CONFLICT",
        )
    if unpushed > 0:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_UNPUSHED,
            "NOT_SAFE",
            "LOCAL_UNPUSHED",
        )
    if worktree_clean is False:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_DIRTY_RECOVERABLE,
            "NOT_SAFE",
            "LOCAL_DIRTY_NOT_DURABLE",
        )
    if local_head != remote_head:
        return _decision(
            snapshot,
            LocalDurabilityState.LOCAL_DIRTY_CONFLICT,
            "NOT_SAFE",
            "LOCAL_STATE_CONFLICT",
        )
    return _decision(
        snapshot,
        LocalDurabilityState.LOCAL_CLEAN_SYNCED,
        "SAFE",
        "LOCAL_CLEAN_SYNCED",
    )
