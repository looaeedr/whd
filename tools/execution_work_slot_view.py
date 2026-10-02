"""Read-only fixed work-slot projection for WHD Flow v2.

Work slots are UI/routing tags on canonical ExecutionRecord objects.  This
module intentionally owns no slot database, claim, lease, handoff, or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable, Mapping

from tools.execution_record import ExecutionRecord, execution_record_fingerprint
from tools.flow_v2_runtime_observation import derive_liveness_state


FIXED_SLOT_IDS = ("worker.slot.0", "worker.slot.1", "worker.slot.2", "worker.slot.3")


class WorkSlotViewError(ValueError):
    """Raised when records cannot be projected into the four fixed slots."""


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
    claim_worker: str | None = None
    invocation_identity: str | None = None
    conversation_identity: str | None = None
    last_wake_at: str | None = None
    last_heartbeat_at: str | None = None
    heartbeat_expires_at: str | None = None
    last_progress_at: str | None = None
    exit_at: str | None = None
    exit_state: str | None = None
    liveness_state: str = "UNKNOWN"


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

def select_first_available_work_slot(
    records: Iterable[ExecutionRecord],
    *,
    start_slot_id: str = FIXED_SLOT_IDS[0],
) -> str:
    """Return the first EMPTY fixed slot at or above start_slot_id.

    This is a routing helper for new interactive work. It never renumbers a
    slot, mutates a record, steals occupancy, or wraps around to a lower slot.
    DONE records do not occupy capacity because project_work_slots already
    excludes them. A fully occupied suffix fails closed.
    """

    if start_slot_id not in FIXED_SLOT_IDS:
        raise WorkSlotViewError(
            f"unknown start_slot_id {start_slot_id!r}; fixed slots are {FIXED_SLOT_IDS}"
        )

    projections = project_work_slots(records)
    start_index = FIXED_SLOT_IDS.index(start_slot_id)
    for projection in projections[start_index:]:
        if projection.status == "EMPTY":
            return projection.slot_id

    raise WorkSlotViewError(
        f"NO_AVAILABLE_WORK_SLOT: no EMPTY slot at or above {start_slot_id}"
    )


def project_work_slot_liveness(
    records: Iterable[ExecutionRecord],
    observations: Mapping[str, Mapping[str, object]],
    *,
    now: datetime | None = None,
) -> tuple[WorkSlotProjection, ...]:
    """Attach non-authoritative runtime liveness to canonical slot projection.

    ExecutionRecord remains authority for occupancy/owner/branch/head.  Runtime
    observation is consumed only when issue + slot + owner + branch + head all
    match the canonical record; otherwise liveness remains UNKNOWN.
    """
    current = now or datetime.now(timezone.utc)
    base = project_work_slots(records)
    projected: list[WorkSlotProjection] = []
    for slot in base:
        if slot.status != "BOUND" or slot.issue is None:
            projected.append(slot)
            continue
        idx = slot.slot_id.rsplit(".", 1)[-1]
        obs = observations.get(f"work-{idx}.json") or observations.get(f"work-{idx}")
        if not isinstance(obs, Mapping):
            projected.append(replace(slot, claim_worker=slot.owner_id))
            continue
        exact = (
            obs.get("issue") == slot.issue
            and obs.get("slot_id") == slot.slot_id
            and (obs.get("claim_worker") or obs.get("owner_id")) == slot.owner_id
            and obs.get("branch") == slot.work_branch
            and obs.get("head_sha") == slot.head_sha
        )
        if not exact:
            projected.append(replace(slot, claim_worker=slot.owner_id))
            continue
        projected.append(
            replace(
                slot,
                claim_worker=slot.owner_id,
                invocation_identity=(
                    str(obs["invocation_identity"]) if obs.get("invocation_identity") else None
                ),
                conversation_identity=(
                    str(obs["conversation_identity"]) if obs.get("conversation_identity") else None
                ),
                last_wake_at=(str(obs["last_wake_at"]) if obs.get("last_wake_at") else None),
                last_heartbeat_at=(
                    str(obs["last_heartbeat_at"]) if obs.get("last_heartbeat_at") else None
                ),
                heartbeat_expires_at=(
                    str(obs["heartbeat_expires_at"]) if obs.get("heartbeat_expires_at") else None
                ),
                last_progress_at=(
                    str(obs["last_progress_at"]) if obs.get("last_progress_at") else None
                ),
                exit_at=(str(obs["exit_at"]) if obs.get("exit_at") else None),
                exit_state=(str(obs["exit_state"]) if obs.get("exit_state") else None),
                liveness_state=derive_liveness_state(obs, now=current),
            )
        )
    return tuple(projected)
