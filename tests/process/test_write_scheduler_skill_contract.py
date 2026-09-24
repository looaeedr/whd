from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "寫排程" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
PITFALL = ROOT / "個人AI檔案庫" / "踩坑庫" / "scheduler_prompt_authoring_pitfall.md"

MANDATORY_SKILL_MARKERS = (
    "name: 寫排程",
    "whd_contract: scheduler-authoring",
    "PROMPT_MINIMUM_CONTRACT_V1",
    "派工 + 遠端執行守門",
    "SKILL_FIRST_HARD_GATE",
    "UNCONSUMED_GREEN_FIRST_RECOVERY",
    "HEARTBEAT_IS_NOT_WORK",
    "BLOCKED_IS_NOT_AN_ESCAPE_HATCH",
    "EXACT_REMOTE_RUN_LOCK",
    "TURN_EXIT_MACHINE_GATE",
    "RECURRING_STAYS_ENABLED",
    "POST_UPDATE_READBACK",
    "GREEN_EXPIRY_HARD_GATE",
    "LIVE_DRIFT_RECONCILIATION_FIRST_RECOVERY",
    "STALE_GUARD_RECEIPT",
    "WHD_SCHEDULER_RUNTIME_END_V1",
)


def _missing_markers(text: str) -> set[str]:
    return {marker for marker in MANDATORY_SKILL_MARKERS if marker not in text}


def test_write_scheduler_skill_has_non_drop_contract() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert _missing_markers(text) == set()


def test_contract_would_reject_old_shortened_prompt_shape() -> None:
    broken = """
    使用派工技能。
    發 heartbeat。
    有 next_action 就繼續。
    """
    missing = _missing_markers(broken)
    assert "派工 + 遠端執行守門" in missing
    assert "UNCONSUMED_GREEN_FIRST_RECOVERY" in missing
    assert "HEARTBEAT_IS_NOT_WORK" in missing
    assert "BLOCKED_IS_NOT_AN_ESCAPE_HATCH" in missing
    assert "TURN_EXIT_MACHINE_GATE" in missing
    assert "GREEN_EXPIRY_HARD_GATE" in missing
    assert "LIVE_DRIFT_RECONCILIATION_FIRST_RECOVERY" in missing


def test_scheduler_authoring_registry_route() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in data["routes"]}
    route = routes["scheduler-authoring"]

    assert route["required_skills"] == [
        "寫排程",
        "派工",
        "遠端執行守門",
        "monitoring-remote-qa",
        "executable-continuity-controller",
    ]
    assert ".agents/skills/engineering/寫排程/**" in route["file_globs"]
    keywords = set(route["keywords"])
    assert {
        "寫排程",
        "新增排程",
        "修改排程",
        "排程 prompt",
        "scheduler prompt",
        "recurring automation",
        "automation prompt",
    } <= keywords
    # Avoid turning every ordinary status question containing only 「排程」 into authoring.
    assert "排程" not in keywords


def test_scheduler_authoring_pitfall_records_guard_and_exit_regressions() -> None:
    text = PITFALL.read_text(encoding="utf-8")
    for marker in (
        "SCHEDULER_PROMPT_AUTHORING_PITFALL_V1",
        "遠端執行守門",
        "heartbeat-only",
        "BLOCKED",
        "unconsumed GREEN",
        "machine turn-exit",
        "post-update readback",
        "expired GREEN",
        "STALE_GUARD_RECEIPT",
        "claim.head_sha",
        "live branch HEAD",
    ):
        assert marker in text
