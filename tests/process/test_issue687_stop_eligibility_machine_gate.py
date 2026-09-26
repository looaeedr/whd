from __future__ import annotations

import inspect

import pytest

import tools.continuity_controller as continuity


def _blocked() -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue="687",
        branch="work/issue687-continuous-legal-stop-20260926",
        head_sha="a" * 40,
        state=continuity.ContinuityState.BLOCKED,
        next_action="wait for external authority",
    )


def test_red_stop_01_bare_blocked_requires_exhaustive_machine_proof() -> None:
    with pytest.raises(
        continuity.TurnExitBlocked,
        match="BLOCKER_NOT_EXHAUSTIVELY_PROVEN",
    ):
        continuity.assert_turn_exitable(_blocked())


def test_red_stop_02_turn_exit_api_accepts_blocked_exit_proof() -> None:
    params = inspect.signature(continuity.assert_turn_exitable).parameters
    assert "blocked_exit_proof" in params, (
        "turn-exit API has no machine input for exhaustive BLOCKED/path proof"
    )


class _PositiveLeafProof:
    exhaustive = True
    executable_leaf_count = 1
    evidence = ("fresh durable leaf #688 remains executable",)
    stop_reason = "NO_EXECUTABLE_PATH"


def test_red_stop_03_executable_alternative_blocks_turn_exit() -> None:
    try:
        continuity.assert_turn_exitable(
            _blocked(),
            blocked_exit_proof=_PositiveLeafProof(),
        )
    except TypeError as exc:
        pytest.fail(f"turn-exit API cannot consume leaf census proof: {exc}")
    except continuity.TurnExitBlocked as exc:
        assert "EXECUTABLE_LEAF_EXISTS" in str(exc)
    else:
        pytest.fail("turn exit was permitted while an executable leaf exists")


def test_red_stop_04_canonical_executable_leaf_reason_exists() -> None:
    stop_reason = getattr(continuity, "StopReason", None)
    assert stop_reason is not None, "no canonical StopReason schema exists"
    values = {member.value for member in stop_reason}
    assert "EXECUTABLE_LEAF_EXISTS" in values


def test_red_stop_05_stop_reason_schema_excludes_progress_observations() -> None:
    stop_reason = getattr(continuity, "StopReason", None)
    assert stop_reason is not None, "no machine StopReason/STOP_REASON schema exists"

    values = {member.value for member in stop_reason}
    assert {
        "BLOCKER_NOT_EXHAUSTIVELY_PROVEN",
        "EXECUTABLE_LEAF_EXISTS",
        "NO_EXECUTABLE_PATH",
        "EXTERNAL_AUTHORITY_REQUIRED",
        "CAPABILITY_BLOCKED",
    } <= values

    forbidden = {
        "USER_ASKED_STATUS",
        "PROGRESS_REPORTED",
        "CHECKPOINT_REPORTED",
        "GUARD_GREEN_REPORTED",
    }
    assert values.isdisjoint(forbidden)
