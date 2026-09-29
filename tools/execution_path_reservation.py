"""Flow v2 file-level mutation reservation evaluator.

Reservation state lives inside each canonical ``WHD_EXECUTION_RECORD_V2``.
This module is intentionally a pure evaluator over records; it does not create
another lock database or write coordination state on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tools.execution_record import ExecutionRecord, MutationScopeState

SCHEMA = "WHD_PATH_RESERVATION_V1"
EVIDENCE_SCHEMA = "WHD_PATH_RESERVATION_EVIDENCE_V1"


class PathReservationError(ValueError):
    """Raised when a candidate reservation conflicts with canonical records."""


@dataclass(frozen=True)
class PathReservationConflict:
    conflicting_issue: int
    target_branch: str
    paths: tuple[str, ...]


def active_reserved_paths(record: ExecutionRecord) -> tuple[str, ...]:
    """Return exact reserved repo paths for one active nonterminal record."""
    if not isinstance(record, ExecutionRecord):
        raise PathReservationError("record must be an ExecutionRecord")
    scope = record.mutation_scope
    if record.state == "DONE" or scope is None or scope.reservation_state != "ACTIVE":
        return ()
    return scope.paths


def find_path_reservation_conflicts(
    records: Iterable[ExecutionRecord],
    *,
    candidate_issue: int,
    candidate_scope: MutationScopeState,
) -> tuple[PathReservationConflict, ...]:
    """Find WRITE/WRITE, WRITE/DELETE and DELETE/WRITE exact-path conflicts.

    Only ACTIVE reservations on the same target branch participate.  The
    candidate issue is ignored so a reservation can be expanded atomically.
    """
    if not isinstance(candidate_scope, MutationScopeState):
        raise PathReservationError("candidate_scope must be a MutationScopeState")
    if candidate_scope.reservation_state != "ACTIVE":
        return ()
    candidate_paths = set(candidate_scope.paths)
    conflicts: list[PathReservationConflict] = []
    for record in records:
        if not isinstance(record, ExecutionRecord):
            raise PathReservationError("records must contain ExecutionRecord values")
        if record.issue == candidate_issue or record.state == "DONE":
            continue
        scope = record.mutation_scope
        if scope is None or scope.reservation_state != "ACTIVE":
            continue
        if scope.target_branch != candidate_scope.target_branch:
            continue
        overlap = tuple(sorted(candidate_paths & set(scope.paths)))
        if overlap:
            conflicts.append(
                PathReservationConflict(
                    conflicting_issue=record.issue,
                    target_branch=candidate_scope.target_branch,
                    paths=overlap,
                )
            )
    return tuple(sorted(conflicts, key=lambda row: (row.conflicting_issue, row.paths)))


def require_no_path_reservation_conflict(
    records: Iterable[ExecutionRecord],
    *,
    candidate_issue: int,
    candidate_scope: MutationScopeState,
) -> None:
    conflicts = find_path_reservation_conflicts(
        records,
        candidate_issue=candidate_issue,
        candidate_scope=candidate_scope,
    )
    if not conflicts:
        return
    first = conflicts[0]
    raise PathReservationError(
        "PATH_RESERVATION_CONFLICT "
        f"conflicting_issue={first.conflicting_issue} "
        f"target_branch={first.target_branch} "
        f"paths={','.join(first.paths)}"
    )


def build_path_reservation_evidence(record: ExecutionRecord) -> dict[str, object]:
    """Project one ACTIVE canonical reservation into root-workspace gate evidence."""
    if not isinstance(record, ExecutionRecord):
        raise PathReservationError("record must be an ExecutionRecord")
    scope = record.mutation_scope
    if scope is None or scope.reservation_state != "ACTIVE" or record.state == "DONE":
        raise PathReservationError("ACTIVE mutation_scope reservation is required")
    from tools.execution_record import execution_record_fingerprint
    from tools.work_root_gate import build_interactive_work_path

    return {
        "schema": EVIDENCE_SCHEMA,
        "issue": record.issue,
        "generation": record.generation,
        "target_branch": scope.target_branch,
        "base_sha": scope.base_sha,
        "write_paths": list(scope.write_paths),
        "delete_paths": list(scope.delete_paths),
        "reservation_state": scope.reservation_state,
        "workspace_path": build_interactive_work_path(issue=record.issue, source_sha=scope.base_sha),
        "record_fingerprint": execution_record_fingerprint(record),
    }


def validate_path_reservation_evidence(evidence: object) -> dict[str, object]:
    if not isinstance(evidence, dict):
        raise PathReservationError("path reservation evidence must be an object")
    required = {
        "schema", "issue", "generation", "target_branch", "base_sha",
        "write_paths", "delete_paths", "reservation_state", "workspace_path",
        "record_fingerprint",
    }
    missing = sorted(required - set(evidence))
    if missing:
        raise PathReservationError(f"path reservation evidence missing fields: {missing}")
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise PathReservationError("unexpected path reservation evidence schema")
    if evidence.get("reservation_state") != "ACTIVE":
        raise PathReservationError("path reservation evidence is not ACTIVE")
    issue = evidence.get("issue")
    generation = evidence.get("generation")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise PathReservationError("path reservation evidence issue must be positive")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
        raise PathReservationError("path reservation evidence generation must be positive")
    try:
        scope = MutationScopeState(
            target_branch=str(evidence.get("target_branch") or ""),
            base_sha=str(evidence.get("base_sha") or ""),
            write_paths=tuple(evidence.get("write_paths") or ()),
            delete_paths=tuple(evidence.get("delete_paths") or ()),
            reservation_state="ACTIVE",
        )
    except ValueError as exc:
        raise PathReservationError(str(exc)) from exc
    fingerprint = str(evidence.get("record_fingerprint") or "").strip().lower()
    if len(fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in fingerprint):
        raise PathReservationError("path reservation evidence record_fingerprint must be SHA256")
    from tools.work_root_gate import build_interactive_work_path, validate_interactive_workspace_path
    expected_workspace = build_interactive_work_path(issue=issue, source_sha=scope.base_sha)
    observed_workspace = validate_interactive_workspace_path(str(evidence.get("workspace_path") or ""))
    if observed_workspace != expected_workspace:
        raise PathReservationError("path reservation evidence workspace identity mismatch")
    return {str(k): v for k, v in evidence.items()}
