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
