from __future__ import annotations

from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.continuity_controller import (
    Checkpoint,
    ContinuityState,
    TurnExitBlocked,
    assert_turn_exitable,
)


BRANCH = "governance/issue769-terminal-scheduler-census-hard-gate-20260927"
CLAIM_BLOB = "b" * 40
CHECKPOINT_BLOB = "c" * 40
REQUEST_ID = 76901


def _checkpoint() -> Checkpoint:
    return Checkpoint(
        issue="769",
        branch=BRANCH,
        head_sha="a" * 40,
        state=ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
    )


def _scheduler_claim(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "invocation_identity": "scheduler.invocation.issue769",
        "phase": "RELEASED",
    }
    payload.update(overrides)
    return payload


def _zero_leaf_proof(
    checkpoint: Checkpoint,
    *,
    candidates: list[dict[str, object]] | None = None,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "READY_WORK_CENSUS_V1",
        "scheduler_lane": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "invocation_identity": "scheduler.invocation.issue769",
        "claim_blob_sha": CLAIM_BLOB,
        "checkpoint_blob_sha": CHECKPOINT_BLOB,
        "checkpoint_fingerprint": continuity.checkpoint_fingerprint(checkpoint),
        "turn_exit_request_comment_id": REQUEST_ID,
        "exhaustive": True,
        "executable_leaf_count": 0,
        "continuation_action": None,
        "candidates": candidates if candidates is not None else [],
    }
    payload.update(overrides)
    return payload


def _guard_kwargs(checkpoint: Checkpoint, proof: object | None) -> dict[str, object]:
    return {
        "claim_state": _scheduler_claim(),
        "ready_work_census_proof": proof,
        "current_claim_blob_sha": CLAIM_BLOB,
        "current_checkpoint_blob_sha": CHECKPOINT_BLOB,
        "turn_exit_request_comment_id": REQUEST_ID,
    }


def test_terminal_closed_scheduler_requires_ready_work_census_proof() -> None:
    checkpoint = _checkpoint()
    with pytest.raises(TurnExitBlocked, match="READY_WORK_CENSUS"):
        assert_turn_exitable(checkpoint, claim_state=_scheduler_claim())


def test_exhaustive_zero_leaf_census_allows_scheduler_turn_exit() -> None:
    checkpoint = _checkpoint()
    proof = _zero_leaf_proof(
        checkpoint,
        candidates=[
            {
                "issue": "700",
                "classification": "FOREIGN_LIVE_OWNER",
                "evidence": "fresh claim blob 012345; owner is foreign-live",
                "next_action": None,
            }
        ],
    )
    assert_turn_exitable(checkpoint, **_guard_kwargs(checkpoint, proof))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("scheduler_lane", "scheduler.other", "scheduler lane"),
        ("invocation_identity", "stale.invocation", "invocation"),
        ("claim_blob_sha", "d" * 40, "claim blob"),
        ("checkpoint_blob_sha", "e" * 40, "checkpoint blob"),
        ("checkpoint_fingerprint", "f" * 64, "checkpoint fingerprint"),
        ("turn_exit_request_comment_id", REQUEST_ID - 1, "turn-exit request"),
    ],
)
def test_stale_or_replayed_census_identity_fails_closed(
    field: str, value: object, match: str
) -> None:
    checkpoint = _checkpoint()
    proof = _zero_leaf_proof(checkpoint, **{field: value})
    with pytest.raises(TurnExitBlocked, match=match):
        assert_turn_exitable(checkpoint, **_guard_kwargs(checkpoint, proof))


def test_must_claim_or_executable_leaf_blocks_with_exact_continuation() -> None:
    checkpoint = _checkpoint()
    proof = _zero_leaf_proof(
        checkpoint,
        executable_leaf_count=1,
        continuation_action="claim Issue #777 through canonical scheduler claim path",
        candidates=[
            {
                "issue": "777",
                "classification": "MUST_CLAIM",
                "evidence": "fresh issue+dependency+claim census proves scheduler-authorized leaf",
                "next_action": "claim Issue #777 through canonical scheduler claim path",
            }
        ],
    )
    with pytest.raises(
        TurnExitBlocked,
        match=r"EXECUTABLE_LEAF_EXISTS.*claim Issue #777",
    ):
        assert_turn_exitable(checkpoint, **_guard_kwargs(checkpoint, proof))


def test_zero_leaf_candidate_requires_fresh_durable_exclusion_evidence() -> None:
    checkpoint = _checkpoint()
    proof = _zero_leaf_proof(
        checkpoint,
        candidates=[
            {
                "issue": "700",
                "classification": "DEPENDENCY_BLOCKED",
                "evidence": "",
                "next_action": None,
            }
        ],
    )
    with pytest.raises(TurnExitBlocked, match="fresh durable exclusion evidence"):
        assert_turn_exitable(checkpoint, **_guard_kwargs(checkpoint, proof))


def test_non_scheduler_terminal_exit_does_not_require_scheduler_census() -> None:
    checkpoint = _checkpoint()
    assert_turn_exitable(
        checkpoint,
        claim_state={
            "worker": "chatgpt.interactive",
            "executor_source": "chat",
            "invocation_identity": "chat.issue769",
            "phase": "RELEASED",
        },
    )


def test_trusted_turn_exit_transport_binds_ready_work_census_to_request_and_receipt() -> None:
    text = Path(".github/workflows/whd-turn-exit-gate.yml").read_text(encoding="utf-8")
    for token in (
        "ready_work_census_json",
        "ready_work_census_proof",
        "turn_exit_request_comment_id",
        "current_claim_blob_sha",
        "current_checkpoint_blob_sha",
        "ready_work_census_fingerprint",
        "READY_WORK_CENSUS_V1",
    ):
        assert token in text
