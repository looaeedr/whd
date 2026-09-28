"""Read-only fixed work-slot projection for WHD Flow v2.

Work slots are UI/routing tags on canonical ExecutionRecord objects.  This
module intentionally owns no slot database, claim, lease, handoff, or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tools.execution_record import ExecutionRecord, execution_record_fingerprint


FIXED_SLOT_IDS = ("worker.slot.1", "worker.slot.2", "worker.slot.3")


class WorkSlotViewError(ValueError):
    """Raised when records cannot be projected into the three fixed slots."""


@dataclass(frozen=True)
class WorkSlotProjection:
    slot_id: str
    status: str
    issue: int | None
    owner_kind: str | None
    owner_id: str | None
    lane_id: str | None
    state: str | None
    work_branch: str | None
    head_sha: str | None
    next_action_kind: str | None
    next_action_display: str | None
    record_fingerprint: str | None


def project_work_slots(records: Iterable[ExecutionRecord]) -> tuple[WorkSlotProjection, ...]:
    """Project canonical records into the fixed work-slot UI surface.

    DONE records do not occupy capacity.  Unbound records remain unbound; they
    are never guessed into an empty slot.  Duplicate/unknown slot identities
    fail closed rather than creating a second occupancy authority.
    """

    occupancy: dict[str, ExecutionRecord] = {}
    for record in records:
        if not isinstance(record, ExecutionRecord):
            raise WorkSlotViewError("all records must be ExecutionRecord instances")
        if record.state == "DONE" or record.slot_id is None:
            continue
        if record.slot_id not in FIXED_SLOT_IDS:
            raise WorkSlotViewError(
                f"unknown slot_id {record.slot_id!r}; fixed slots are {FIXED_SLOT_IDS}"
            )
        prior = occupancy.get(record.slot_id)
        if prior is not None:
            raise WorkSlotViewError(
                f"duplicate slot occupancy for {record.slot_id}: issues {prior.issue} and {record.issue}"
            )
        occupancy[record.slot_id] = record

    projected: list[WorkSlotProjection] = []
    for slot_id in FIXED_SLOT_IDS:
        record = occupancy.get(slot_id)
        if record is None:
            projected.append(
                WorkSlotProjection(
                    slot_id=slot_id,
                    status="EMPTY",
                    issue=None,
                    owner_kind=None,
                    owner_id=None,
                    lane_id=None,
                    state=None,
                    work_branch=None,
                    head_sha=None,
                    next_action_kind=None,
                    next_action_display=None,
                    record_fingerprint=None,
                )
            )
            continue
        action = record.next_action
        projected.append(
            WorkSlotProjection(
                slot_id=slot_id,
                status="BOUND",
                issue=record.issue,
                owner_kind=record.owner_kind,
                owner_id=record.owner_id,
                lane_id=record.lane_id,
                state=record.state,
                work_branch=record.work_branch,
                head_sha=record.head_sha,
                next_action_kind=action.kind if action else None,
                next_action_display=action.display if action else None,
                record_fingerprint=execution_record_fingerprint(record),
            )
        )
    return tuple(projected)
