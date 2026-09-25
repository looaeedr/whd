from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"


def test_remote_execution_guard_skill_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for marker in (
        "name: 遠端執行守門",
        "whd_contract: remote-execution-guard",
        "WHD_REMOTE_GUARD_REQUEST_V1",
        "WHD_REMOTE_GUARD_RECEIPT_V1",
        "LOCAL_GUARD_UNAVAILABLE + REMOTE_GUARD_AVAILABLE",
        "REMOTE_GUARD_UNAVAILABLE",
        "claim_blob_sha",
        "orchestrator_head_sha",
        "tested_target_sha",
        "Single-action / single-use rule",
        "receipt stale",
        "no repository command execution",
        "interactive handoff",
    ):
        assert marker in text


def test_remote_execution_guard_registry_route() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in data["routes"]}
    route = routes["remote-execution-guard"]

    assert "遠端執行守門" in route["required_skills"]
    assert "monitoring-remote-qa" in route["required_skills"]
    assert "long-log-context-safe-execution" in route["required_skills"]
    assert "executable-continuity-controller" in route["required_skills"]
    assert ".github/workflows/whd-remote-execution-guard.yml" in route["file_globs"]
    assert ".agents/skills/engineering/remote-execution-guard/**" in route["file_globs"]

    keywords = set(route["keywords"])
    assert {
        "遠端執行守門",
        "Remote Guard",
        "WHD_REMOTE_GUARD_REQUEST_V1",
        "WHD_REMOTE_GUARD_RECEIPT_V1",
        "repository command execution",
    } <= keywords
