"""Derived, rebuildable ready-work cache for WHD Flow v2.

The index is deliberately non-authoritative. It is a projection of validated
ExecutionRecord V2 objects and never selects, claims, leases, or mutates work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable

from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_record import ExecutionRecord, execution_record_fingerprint


SCHEMA = "WHD_EXECUTION_READY_INDEX_V1"
AUTHORITY = "DERIVED_CACHE_ONLY"


class ReadyIndexError(ValueError):
    """Raised when a ready-index projection cannot be built deterministically."""


@dataclass(frozen=True)
class ReadyIndexEntry:
    issue: int
    generation: int
    record_fingerprint: str
    execution_intent: str
    target_branch: str
    target_sha: str
    next_action_kind: str
    next_action_display: str
    updated_at: str | None


@dataclass(frozen=True)
class ExecutionReadyIndex:
    source_digest: str
    entries: tuple[ReadyIndexEntry, ...]


def _source_digest(records: Iterable[ExecutionRecord]) -> str:
    rows = [
        {
            "issue": record.issue,
            "generation": record.generation,
            "fingerprint": execution_record_fingerprint(record),
        }
        for record in records
    ]
    rows.sort(key=lambda row: row["issue"])
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_ready_index(records: Iterable[ExecutionRecord]) -> ExecutionReadyIndex:
    """Project READY records into a deterministic cache.

    Input records remain the authority. Duplicate Issue identities fail closed
    because an index cannot safely project two canonical states for one Issue.
    """
    materialized = tuple(records)
    seen: set[int] = set()
    entries: list[ReadyIndexEntry] = []

    for record in materialized:
        if not isinstance(record, ExecutionRecord):
            raise ReadyIndexError("all records must be ExecutionRecord instances")
        if record.issue in seen:
            raise ReadyIndexError(f"duplicate issue in execution records: {record.issue}")
        seen.add(record.issue)
        if record.state != "READY":
            continue
        if record.next_action is None:
            raise ReadyIndexError(f"READY issue {record.issue} is missing next_action")
        try:
            validate_execution_action(record.next_action)
        except ActionContractError as exc:
            raise ReadyIndexError(
                f"READY issue {record.issue} has non-executable next_action: {exc}"
            ) from exc
        entries.append(
            ReadyIndexEntry(
                issue=record.issue,
                generation=record.generation,
                record_fingerprint=execution_record_fingerprint(record),
                execution_intent=record.execution_intent,
                target_branch=record.target_branch,
                target_sha=record.target_sha,
                next_action_kind=record.next_action.kind,
                next_action_display=record.next_action.display,
                updated_at=record.updated_at,
            )
        )

    entries.sort(key=lambda entry: entry.issue)
    return ExecutionReadyIndex(
        source_digest=_source_digest(materialized),
        entries=tuple(entries),
    )


def ready_index_to_payload(index: ExecutionReadyIndex) -> dict[str, object]:
    if not isinstance(index, ExecutionReadyIndex):
        raise ReadyIndexError("index must be an ExecutionReadyIndex")
    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "source_digest": index.source_digest,
        "entries": [asdict(entry) for entry in index.entries],
    }


def validate_ready_index(
    index: ExecutionReadyIndex,
    records: Iterable[ExecutionRecord],
) -> bool:
    """Return whether ``index`` exactly matches a fresh rebuild from ``records``."""
    if not isinstance(index, ExecutionReadyIndex):
        raise ReadyIndexError("index must be an ExecutionReadyIndex")
    rebuilt = build_ready_index(records)
    return rebuilt == index
