from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK_SLOT = ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md"
SCHED_SIM = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
WRITE_SCHED = ROOT / ".agents" / "skills" / "engineering" / "寫排程" / "SKILL.md"

MARKER = "REPORT_HANDLER_IDENTITY_PREFIX_V1"
TEMPLATE = "【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>】"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_three_surfaces_require_same_report_prefix_contract() -> None:
    for path in (WORK_SLOT, SCHED_SIM, WRITE_SCHED):
        text = _read(path)
        assert MARKER in text, path
        assert TEMPLATE in text, path
        assert "第一行" in text, path
        assert "user-visible" in text, path


def test_work_slot_prefix_uses_fresh_binding_and_claim_owner() -> None:
    text = _read(WORK_SLOT)
    section = text.split(MARKER, 1)[1]
    for token in ("worker.slot.1", "worker.slot.2", "worker.slot.3", "claim_owner", "UNBOUND"):
        assert token in section
    assert "不得猜" in section
    assert "query-only" in section


def test_scheduler_simulation_prefix_identifies_lane_issue_and_real_owner() -> None:
    text = _read(SCHED_SIM)
    section = text.split(MARKER, 1)[1]
    for token in ("排程A", "排程B", "lane_owner", "claim_issue", "claim_worker"):
        assert token in section
    assert "foreign" in section
    assert "不得" in section
    assert "冒充處理者" in section


def test_scheduler_authoring_requires_generated_prompts_to_emit_prefix() -> None:
    text = _read(WRITE_SCHED)
    section = text.split(MARKER, 1)[1]
    for token in ("scheduler prompt", "lane owner", "active Issue", "fresh", "progress", "CHECKPOINT"):
        assert token in section
    assert "prompt" in section
    assert "不得刪除" in section


def test_prefix_is_provenance_not_ownership_authority() -> None:
    for path in (WORK_SLOT, SCHED_SIM, WRITE_SCHED):
        section = _read(path).split(MARKER, 1)[1]
        assert "不建立 execution authority" in section
        assert "ownership" in section
