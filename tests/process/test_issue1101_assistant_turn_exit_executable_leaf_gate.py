from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

from tools.continuity_controller import TurnExitBlocked, assert_no_executable_leaf_for_turn_exit

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/assistant_turn_exit_gate.py"


def test_executable_leaf_blocks_interactive_turn_exit():
    with pytest.raises(TurnExitBlocked, match="EXECUTABLE_LEAF_EXISTS"):
        assert_no_executable_leaf_for_turn_exit(
            exhaustive=True,
            executable_leaf_count=1,
            continuation_action="continue Bridge decomposition #1100",
            observed_at="2026-10-01T12:00:00Z",
            now=datetime(2026, 10, 1, 12, 0, 30, tzinfo=timezone.utc),
        )


def test_non_exhaustive_census_blocks_turn_exit_even_when_count_is_zero():
    with pytest.raises(TurnExitBlocked, match="CENSUS_NOT_EXHAUSTIVE"):
        assert_no_executable_leaf_for_turn_exit(
            exhaustive=False,
            executable_leaf_count=0,
            continuation_action="",
            observed_at="2026-10-01T12:00:00Z",
            now=datetime(2026, 10, 1, 12, 0, 30, tzinfo=timezone.utc),
        )


def test_stale_census_blocks_turn_exit():
    with pytest.raises(TurnExitBlocked, match="CENSUS_STALE"):
        assert_no_executable_leaf_for_turn_exit(
            exhaustive=True,
            executable_leaf_count=0,
            continuation_action="",
            observed_at="2026-10-01T11:00:00Z",
            now=datetime(2026, 10, 1, 12, 0, 30, tzinfo=timezone.utc),
        )


def test_zero_leaf_fresh_exhaustive_census_is_eligible_for_existing_checkpoint_gate():
    assert assert_no_executable_leaf_for_turn_exit(
        exhaustive=True,
        executable_leaf_count=0,
        continuation_action="",
        observed_at="2026-10-01T12:00:00Z",
        now=datetime(2026, 10, 1, 12, 0, 30, tzinfo=timezone.utc),
    )


def test_outer_gate_requires_executable_leaf_census_arguments():
    result = subprocess.run(
        [sys.executable, str(GATE), "missing-checkpoint.json", "missing-receipt.json", "--issue", "#1101", "--branch", "x", "--head-sha", "a" * 40],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "--executable-leaf-count" in result.stderr
    assert "--census-observed-at" in result.stderr


def test_outer_gate_wires_shared_executable_leaf_primitive():
    source = GATE.read_text(encoding="utf-8")
    assert "assert_no_executable_leaf_for_turn_exit" in source
    assert "--census-exhaustive" in source
    assert "--executable-leaf-count" in source
    assert "--continuation-action" in source
    assert "--census-observed-at" in source
