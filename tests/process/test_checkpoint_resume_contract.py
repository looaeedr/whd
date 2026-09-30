from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
BRIDGES = (
    ".agents/skills/engineering/執行開發任務/SKILL.md",
    ".agents/skills/engineering/派工/SKILL.md",
    ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
    ".agents/skills/engineering/issue-closure-gate/SKILL.md",
)
LEGACY_CHECKPOINT_MARKERS = (
    "USER_VISIBLE_CHECKPOINT_GATE",
    "USER_VISIBLE_CHECKPOINT_GATE_BRIDGE",
    "CHECKPOINT_RESUME_CONTRACT",
    "RUNNING ↔ WAITING_REMOTE ↔ RECOVERING",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_flow_v2_is_the_only_durable_resume_authority() -> None:
    flow = _read(FLOW)
    assert "whd_doc_role: CURRENT" in flow
    assert "WHD_EXECUTION_RECORD_V2" in flow
    assert "tools/execution_invocation_exit.py" in flow
    assert "structured next_action" in flow


def test_execution_entry_skills_are_projection_bridges_not_checkpoint_state_machines() -> None:
    for rel in BRIDGES:
        text = _read(rel)
        assert "whd_doc_role: MIRROR" in text, rel
        assert f"whd_canonical: {FLOW}" in text, rel
        assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text, rel
        assert "不擁有 execution state machine" in text, rel
        for marker in LEGACY_CHECKPOINT_MARKERS:
            assert marker not in text, f"{rel} regrew legacy marker {marker!r}"


def test_agents_dispatch_is_projection_only() -> None:
    agents = _read("AGENTS.md")
    assert "FLOW_V2_DISPATCH_PROJECTION_ONLY_V1" in agents
    section = agents.split("FLOW_V2_DISPATCH_PROJECTION_ONLY_V1", 1)[1].split(
        "### DURABLE_TERMINAL_EXIT_HARD_GATE_V1", 1
    )[0]
    assert "WHD_EXECUTION_RECORD_V2" in section
    assert "不擁有第二套 execution state machine" in section
    assert "每個工單有實體 checkpoint path" not in section
    assert "PM → Worker → QA" not in section
