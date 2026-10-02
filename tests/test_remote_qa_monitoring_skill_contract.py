from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_remote_qa_monitoring_skill_is_registered_and_flow_v2_owned():
    skill = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    for token in (
        "name: monitoring-remote-qa",
        "whd_doc_role: MIRROR",
        "whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md",
        "FLOW_V2_EXECUTION_BRIDGE_V1",
        "ExecutionRecord.active_run",
        "exact run/head",
        "CONSUME_QA",
        "START_QA",
        "POLL_QA",
        "ACCEPT_QA",
        "FAIL_QA",
        "不擁有 execution state machine",
    ):
        assert token in text

    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(item for item in registry["routes"] if item.get("id") == "remote-qa-monitoring")
    assert route["required_skills"][:2] == ["flow-v2-execution", "monitoring-remote-qa"]
    assert "long-log-context-safe-execution" in route["required_skills"]
    assert {"遠端 QA", "同步遠端QA", "GitHub Actions", "workflow run"} <= set(route["keywords"])

    dispatch = (ROOT / ".agents/skills/engineering/派工/SKILL.md").read_text(encoding="utf-8")
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in dispatch
    assert "不擁有 execution state machine" in dispatch
