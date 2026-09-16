from pathlib import Path

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]


def _write_checkpoint(path: Path, state: continuity.ContinuityState) -> None:
    kwargs = {}
    if state is continuity.ContinuityState.WAITING_REMOTE:
        kwargs["run_id"] = 35102914224
    continuity.save_checkpoint(
        path,
        continuity.Checkpoint(
            issue="#321",
            branch="fix/issue321-turn-exit-enforcement-20260916",
            head_sha="abc123",
            state=state,
            next_action="execute exact next action",
            **kwargs,
        ),
    )


def test_path_boundary_exists_and_missing_checkpoint_fails_closed(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    with pytest.raises(continuity.CheckpointError, match="checkpoint file not found"):
        guard(tmp_path / "missing.json")


def test_path_boundary_rejects_malformed_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(continuity.CheckpointError, match="invalid checkpoint JSON"):
        guard(path)


@pytest.mark.parametrize(
    "state",
    (
        continuity.ContinuityState.RUNNING,
        continuity.ContinuityState.WAITING_REMOTE,
        continuity.ContinuityState.RECOVERING,
    ),
)
def test_path_boundary_blocks_every_autonomous_nonterminal_state(
    tmp_path: Path, state: continuity.ContinuityState
):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / f"continuity-{state.value}.json"
    _write_checkpoint(path, state)
    with pytest.raises(continuity.TurnExitBlocked, match="execute exact next action"):
        guard(path)


def test_path_boundary_allows_genuine_blocked_checkpoint(tmp_path: Path):
    guard = getattr(continuity, "assert_turn_exitable_path", None)
    assert callable(guard), "missing canonical path-level turn-exit boundary"

    path = tmp_path / "continuity.json"
    continuity.save_checkpoint(
        path,
        continuity.Checkpoint(
            issue="#321",
            branch="fix/issue321-turn-exit-enforcement-20260916",
            head_sha="abc123",
            state=continuity.ContinuityState.BLOCKED,
            next_action="wait for missing external authority",
        ),
    )
    checkpoint = guard(path)
    assert checkpoint.state is continuity.ContinuityState.BLOCKED


def test_outer_agents_contract_requires_one_machine_turn_exit_hook():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    heading = "### 0.0.3.0 ASSISTANT_TURN_EXIT_HARD_GATE_V2"
    marker = "<!-- ASSISTANT_TURN_EXIT_HARD_GATE_V2 -->"
    assert text.count(heading) == 1, "turn-exit hard gate must have exactly one canonical section"
    assert text.count(marker) == 1, "turn-exit hard gate marker must not be duplicated"
    assert "assert-turn-exitable" in text
    assert "missing / unreadable checkpoint" in text


def test_canonical_controller_skill_requires_path_level_boundary():
    text = (
        ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "assert_turn_exitable_path" in text
    assert "missing / unreadable checkpoint" in text
