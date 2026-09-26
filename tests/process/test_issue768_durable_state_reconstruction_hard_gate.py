from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "execution": ROOT / ".agents" / "skills" / "engineering" / "執行開發任務" / "SKILL.md",
    "dispatch": ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md",
    "slot": ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md",
    "continuity": ROOT / ".agents" / "skills" / "engineering" / "executable-continuity-controller" / "SKILL.md",
    "scheduler": ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md",
}

def _read(key: str) -> str:
    return SKILLS[key].read_text(encoding="utf-8")

def test_canonical_continuity_defines_github_durable_state_reconstruction_hard_gate():
    text = _read("continuity")
    assert "GITHUB_DURABLE_STATE_RECONSTRUCTION_HARD_GATE_V1" in text
    for token in (
        "owning Issue",
        "claim blob",
        "checkpoint blob",
        "work branch HEAD",
        "production target HEAD",
        "exact next_action",
        "stream",
        "fresh runtime",
    ):
        assert token in text

def test_all_execution_entrypoints_bridge_durable_reconstruction_gate():
    for key in ("execution", "dispatch", "slot", "scheduler"):
        text = _read(key)
        assert "GITHUB_DURABLE_STATE_RECONSTRUCTION_HARD_GATE_V1_BRIDGE" in text
        assert "GitHub durable state重新接" in text
        assert "不得靠聊天記憶" in text

def test_reconstruction_gate_forbids_false_wait_block_complete_and_requires_continuation():
    text = _read("continuity")
    assert "不得宣告 WAITING" in text
    assert "不得宣告 BLOCKED" in text
    assert "不得宣告 COMPLETE" in text
    assert "立即執行 exact next_action" in text
