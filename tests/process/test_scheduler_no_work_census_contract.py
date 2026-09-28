from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHED_SIM = ROOT / ".agents/skills/engineering/排程模擬/SKILL.md"
WRITE_SCHED = ROOT / ".agents/skills/engineering/寫排程/SKILL.md"
CANONICAL = ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scheduler_entrypoints_bridge_flow_v2_native_state() -> None:
    text = _read(SCHED_SIM)
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text
    assert "coord/execution-v2" in text
    assert "same-lane nonterminal record" in text
    assert "ready-index" in text
    assert "NO_EXECUTABLE_WORK" in text
    assert "YIELD" in text


def test_scheduler_lane_identity_and_recurring_lifecycle_are_preserved() -> None:
    text = _read(SCHED_SIM)
    assert "scheduler.6ab13fa557fc8191935c671214b865e2" in text
    assert "scheduler.e58ea936e7d0b12bd0d475314709d6f1" in text
    assert "00/20/40" in text
    assert "B15/B45" in text
    assert "不得自行 disable/delete/complete/reschedule" in text


def test_scheduler_authoring_points_to_flow_v2_not_parallel_state_machine() -> None:
    text = _read(WRITE_SCHED)
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text
    assert "coord/execution-v2" in text
    assert "lease" in text
    assert "structured next_action" in text
    assert "atomic transaction" in text
    assert "YIELD" in text
    assert "不得內嵌第二套 execution state machine" in text


def test_scheduler_view_has_same_lane_first_and_derived_ready_index_decisions() -> None:
    text = (ROOT / "tools/execution_scheduler_view.py").read_text(encoding="utf-8")
    for token in ("RESUME_CURRENT", "LANE_BUSY", "READY_CANDIDATES", "NO_EXECUTABLE_WORK"):
        assert token in text
    ready = (ROOT / "tools/execution_ready_index.py").read_text(encoding="utf-8")
    assert "DERIVED_CACHE_ONLY" in ready


def test_canonical_flow_v2_owns_progress_exit_and_generation_fencing() -> None:
    text = _read(CANONICAL)
    assert "Progress" in text
    assert "YIELD" in text
    assert "Generation fencing + salvage" in text
    assert "ORPHAN_WRITE" in text
    assert "回報後只要 current invocation 還能合法施工，就立即繼續" in text
# FLOW_V2_SCHEDULER_A_E2E_CANARY_ISSUE_889
