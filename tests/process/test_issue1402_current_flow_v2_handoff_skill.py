"""#1402: CURRENT Flow v2 guidance must never re-authorize null-owner HANDOFF."""

from pathlib import Path


FLOW_V2_SKILL = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
)


def _current_work_slot_guidance() -> str:
    skill = FLOW_V2_SKILL.read_text(encoding="utf-8")
    assert "## Work slot / handoff" in skill
    section = skill.split("## Work slot / handoff", 1)[1]
    assert "### DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1" in section
    return section.split("### DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1", 1)[0]


def test_owner_none_handoff_residue_cannot_be_completion_authority():
    section = _current_work_slot_guidance()
    assert "唯一允許 lease-null HANDOFF 正常 return" not in section
    assert "owner_kind=NONE / owner_id=NONE / lane_id=null / lease=null" not in section
    assert "歷史無主 HANDOFF 殘留" in section
    assert "`HANDOFF_COMPLETE`" in section
    assert "`DISPATCH_COMPLETE_HANDOFF`" in section
    assert "`ACQUIRE_REQUIRED`" in section
    assert "`DISPATCH_INCOMPLETE`" in section
    assert "`may_return=false`" in section


def test_same_physical_assistant_self_switch_does_not_require_handoff():
    section = _current_work_slot_guidance()
    assert "同一 physical assistant" in section
    assert "不得用 HANDOFF 偽裝角色切換" in section
    assert "exact `next_action`" in section
