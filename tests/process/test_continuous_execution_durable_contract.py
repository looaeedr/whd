from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
LEGACY_SKILL = ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
CURRENT_BRIDGES = (
    ".agents/skills/engineering/執行開發任務/SKILL.md",
    ".agents/skills/engineering/派工/SKILL.md",
    ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
    ".agents/skills/engineering/issue-closure-gate/SKILL.md",
)
LEGACY_CURRENT_MARKERS = (
    "EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE",
    "NONTERMINAL_NEXT_ACTION_GATE",
    "REMOTE_QA_ACTIVE_LOCK",
    "STALE_WAIT_WATCHDOG",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_flow_v2_owns_continuity_resume_and_terminal_exit() -> None:
    flow = _read(FLOW)
    assert "whd_doc_role: CURRENT" in flow
    assert "WHD_EXECUTION_RECORD_V2" in flow
    assert "tools/execution_invocation_exit.py" in flow
    assert "MERGE" in flow and "FINALIZE" in flow and "DONE" in flow


def test_legacy_continuity_skill_is_only_a_flow_v2_mirror() -> None:
    text = _read(LEGACY_SKILL)
    assert "whd_doc_role: MIRROR" in text
    assert f"whd_canonical: {FLOW}" in text
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text
    assert "不擁有 execution state machine" in text


def test_current_entry_bridges_cannot_restore_legacy_continuity_markers() -> None:
    for rel in CURRENT_BRIDGES:
        text = _read(rel)
        for marker in LEGACY_CURRENT_MARKERS:
            assert marker not in text, f"{rel} regrew legacy continuity marker {marker!r}"


def test_legacy_controller_and_pitfalls_cannot_be_runtime_authority() -> None:
    assert (ROOT / "tools/continuity_controller.py").exists()
    pitfalls = _read("個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md")
    assert "REFERENCE — FLOW V2 CURRENT SEMANTICS ONLY" in pitfalls
    assert "tools/continuity_controller.py` 只保留 MIRROR / historical compatibility" in pitfalls
    assert "marker/string presence 不是 executable enforcement" in pitfalls
