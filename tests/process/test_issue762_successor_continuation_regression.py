from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTION = ROOT / ".agents" / "skills" / "engineering" / "執行開發任務" / "SKILL.md"
DISPATCH = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
WORK_SLOT = ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md"
CONTINUITY = ROOT / ".agents" / "skills" / "engineering" / "executable-continuity-controller" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execute_ticket_keeps_exact_durable_successor_in_scope():
    text = _read(EXECUTION)
    assert "NEXT_CHILD_EXECUTABLE" in text
    assert "沿該 handoff 自動續接屬於原授權鏈的 completion，不是 scope expansion" in text
    assert "必須自動續接 exact next issue" in text


def test_dispatch_does_not_stop_at_exact_successor_boundary():
    text = _read(DISPATCH)
    assert "NEXT_CHILD_EXECUTABLE" in text
    assert "不得停在 ticket 邊界" in text
    assert "EXECUTE_TICKET" in text

def test_work_slot_rotates_same_slot_to_exact_successor():
    text = _read(WORK_SLOT)
    assert "必須沿原 slot 自動 claim/start exact successor" in text
    assert "NEXT_CHILD_EXECUTABLE" in text
    assert "工作槽不得用 execution-intent 標籤覆蓋 canonical successor handoff" in text


def test_continuity_treats_exact_durable_handoff_as_authority():
    text = _read(CONTINUITY)
    assert "NEXT_CHILD_EXECUTABLE" in text
    assert "該 successor 已是 durable execution authority，必須續接" in text
    assert "它們不是 `NEXT_CHILD_EXECUTABLE` 唯一允許的 mode" in text


def test_arbitrary_open_issue_discovery_remains_forbidden():
    corpus = "\n".join(_read(path) for path in (EXECUTION, DISPATCH, WORK_SLOT, CONTINUITY))
    assert "arbitrary" in corpus
    assert "open / unblocked Issue != execution authority" in _read(WORK_SLOT)
    assert "不得因單純 open / unblocked successor 自動升級 execution scope" in _read(CONTINUITY)
