import pytest

from tools.execution_record import ActionSpec, ExecutionRecord, ExecutionRecordError


LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
SHA = "5ac44bf638229606a3f6a53a33ad4d173476c9b1"


def _record(*, owner_id: str, lane_id: str | None) -> ExecutionRecord:
    return ExecutionRecord(
        issue=1080,
        execution_intent="SCHEDULER_LANE",
        owner_kind="SCHEDULER",
        owner_id=owner_id,
        lane_id=lane_id,
        slot_id=None,
        source_branch="cleanup/2d-3d-sync",
        source_sha=SHA,
        work_branch="scheduler/issue1080-auto-dispatch",
        head_sha=SHA,
        target_branch="cleanup/2d-3d-sync",
        target_sha=SHA,
        state="ACTIVE",
        semantic_state="RUNNING",
        next_action=ActionSpec(
            kind="FINALIZE",
            args={},
            display="Finalize scheduler work",
        ),
    )


def test_scheduler_owner_identity_matches_lane() -> None:
    record = _record(owner_id=LANE, lane_id=LANE)
    assert record.owner_kind == "SCHEDULER"
    assert record.owner_id == record.lane_id


@pytest.mark.parametrize(
    ("owner_id", "lane_id"),
    [
        ("chatgpt.flowv2.work2", LANE),
        (LANE, None),
    ],
)
def test_scheduler_owner_lane_split_is_rejected(
    owner_id: str,
    lane_id: str | None,
) -> None:
    with pytest.raises(ExecutionRecordError, match="owner_id must equal non-null lane_id"):
        _record(owner_id=owner_id, lane_id=lane_id)
