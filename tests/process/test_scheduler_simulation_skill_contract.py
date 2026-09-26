from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"

A = "scheduler.6ab13fa557fc8191935c671214b865e2"
B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_scheduler_simulation_skill_declares_exact_commands_and_lanes() -> None:
    text = _text()
    assert "name: 排程模擬" in text
    assert "`/排程A`" in text
    assert "`/排程B`" in text
    assert A in text
    assert B in text
    assert "live_prompt_source=00" in text
    assert "live_prompt_source=B15+B45" in text


def test_same_lane_resume_does_not_create_second_owner() -> None:
    text = _text()
    assert "SAME_LANE_RESUME_NO_RECLAIM" in text
    assert "不得另建 parallel claim" in text
    assert "不得把 worker 改成 `chatgpt.*`" in text
    assert "禁止把 worker 直接覆寫成 A/B" in text
    assert "actual_invocation_source = chatgpt_interactive" in text


def test_chat_handoff_is_post_authority_and_fail_visible() -> None:
    text = _text()
    assert "LANE_RESUME_ESTABLISHED" in text
    assert "NEW排程A" in text
    assert "NEW排程B" in text
    assert "取消釘選" in text
    assert "CHAT_UI_HANDOFF_UNAVAILABLE" in text
    assert "CHAT_UI_HANDOFF_PARTIAL" in text
    assert "聊天室 title/pin 當 claim authority" in text


def test_b_profile_preserves_parallel_claim_gate() -> None:
    text = _text()
    assert "PARALLEL CLAIM RULE" in text
    assert "安全平行的不同 executable leaf" in text
    assert "exclusive integration/finalization gate" in text


def test_registry_routes_commands_to_scheduler_simulation_skill() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    route = next(item for item in data["routes"] if item["id"] == "scheduler-simulation")
    assert "/排程A" in route["keywords"]
    assert "/排程B" in route["keywords"]
    assert "排程模擬" in route["required_skills"]
    assert "派工" in route["required_skills"]
    assert "遠端執行守門" in route["required_skills"]
    assert "monitoring-remote-qa" in route["required_skills"]
    assert "executable-continuity-controller" in route["required_skills"]


def test_work_slot_planned_handoff_receiver_precedes_dynamic_discovery() -> None:
    text = _text()
    assert "WORK_SLOT_HANDOFF_RECEIVER_V1" in text
    assert "planned handoff receiver 優先於 ordinary dynamic discovery" in text
    assert "有 matching pending planned handoff 時不得先 claim/discover 另一張 Issue" in text


def test_work_slot_handoff_preserves_slot_identity_across_scheduler_owner_change() -> None:
    text = _text()
    assert "slot_id 必須原值保留" in text
    assert "scheduler owner/location change != work-slot identity change" in text
    assert "不得把 worker.slot.1 改成 worker.slot.2" in text
    assert "不得清除既有 slot_id" in text


def test_work_slot_handoff_receiver_exact_match_is_fail_closed() -> None:
    text = _text()
    for token in (
        "slot_id",
        "issue",
        "branch",
        "head_sha",
        "checkpoint",
        "next_action",
        "target_lane",
    ):
        assert token in text
    assert "WORK_SLOT_HANDOFF_IDENTITY_MISMATCH" in text
    assert "任一 identity 不一致都 fail closed" in text
    assert "不得只靠 Issue、lane、聊天室標題猜 receiver" in text


def test_scheduler_status_projects_slot_and_handoff_source() -> None:
    text = _text()
    assert "slot_id=worker.slot.1|worker.slot.2|worker.slot.3|UNBOUND" in text
    assert "handoff_source=LOCAL|SCHEDULER|NONE" in text
    assert "UNBOUND 不得猜 slot" in text


def test_scheduler_chain_successor_may_rebind_only_the_same_slot() -> None:
    text = _text()
    assert "WORK_SLOT_SUCCESSOR_REBIND_V1" in text
    assert "只有 SCHEDULER_LANE / chain authority" in text
    assert "terminal successor 可沿同一 slot_id rebind" in text
    assert "不得把 successor 靜默搬到另一個工作槽" in text
