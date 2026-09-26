from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
README = ROOT / ".agents" / "skills" / "engineering" / "README.md"


def _skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_work_slot_skill_exists_with_canonical_chinese_identity():
    text = _skill()
    frontmatter = text.split("---", 2)[1]
    assert "name: 工作槽" in frontmatter
    assert "# 工作槽" in text
    assert "whd_contract: work-slot-routing" in frontmatter


def test_three_fixed_user_commands_map_to_three_fixed_durable_slots():
    text = _skill()
    for command, slot in (
        ("/工作1", "worker.slot.1"),
        ("/工作2", "worker.slot.2"),
        ("/工作3", "worker.slot.3"),
    ):
        assert command in text
        assert slot in text
    assert "WORK_SLOT_FIXED_IDENTITY_V1" in text
    assert "不得動態把 /工作1 重新編號成其他 slot" in text


def test_bare_work_commands_and_work_slot_aggregate_are_query_only():
    text = _skill()
    assert "WORK_SLOT_QUERY_ONLY_V1" in text
    assert "裸 `/工作1` / `/工作2` / `/工作3` 預設等同 `狀態`" in text
    assert "`/工作槽` / `/工作槽 狀態`" in text
    assert "`/工作槽 空槽`" in text
    assert "`/工作槽 #<issue>`" in text
    assert "query-only 不取得 execution authority" in text


def test_query_only_never_claims_branches_or_successors():
    text = _skill()
    for forbidden in (
        "不得建立 execution claim",
        "不得建立 implementation branch",
        "不得 takeover",
        "不得啟動 successor",
        "不得因空槽自動找工單",
    ):
        assert forbidden in text


def test_slot_issue_claim_runtime_and_location_are_distinct_identities():
    text = _skill()
    assert "WORK_SLOT_IDENTITY_MODEL_V1" in text
    assert "slot != issue != claim owner != runtime != execution location" in text
    for token in (
        "Issue = 工作本體",
        "claim = durable ownership",
        "checkpoint = progress / next_action",
        "work slot = execution capacity / occupancy / routing identity",
        "runtime = 本輪 physical invocation",
        "execution location = LOCAL / SCHEDULER / REMOTE_ACTION",
    ):
        assert token in text
    assert "claim exists != runtime is live" in text


def test_execution_verbs_are_explicit_authority_transitions_and_bridge_existing_owners():
    text = _skill()
    for token in (
        "/工作1 指派 #<issue>",
        "/工作1 繼續",
        "/工作1 接手",
        "/工作1 強制接手",
        "EXECUTE_TICKET",
        "WHD_USER_DIRECTED_TAKEOVER_V1",
        "派工",
        "stale_claim_takeover.py",
        "executable-continuity-controller",
    ):
        assert token in text
    assert "不得建立第二套 claim/checkpoint/takeover state machine" in text


def test_location_and_planned_handoff_commands_are_routing_intent_not_fake_transfer():
    text = _skill()
    for token in (
        "/工作1 本機",
        "/工作1 交給排程A",
        "/工作1 交給排程B",
        "/工作1 收回本機",
        "/工作1 準備關機",
        "LOCAL",
        "SCHEDULER",
        "planned handoff",
    ):
        assert token in text
    assert "工作槽本身不冒充 handoff transaction owner" in text
    assert "排程 A/B lane != work slot" in text


def test_release_is_fail_closed_and_cannot_erase_active_claim():
    text = _skill()
    assert "/工作1 釋放" in text
    assert "WORK_SLOT_RELEASE_GATE_V1" in text
    assert "不得刪除、覆寫或假裝釋放 active claim" in text
    assert "closed/released" in text
    assert "safe empty-slot transition" in text


def test_update_only_and_empty_slots_never_auto_start_existing_issues():
    text = _skill()
    assert "UPDATE_DOES_NOT_IMPLY_EXECUTION" in text
    assert "ISSUE_EXISTENCE_IS_NOT_EXECUTION_AUTHORITY" in text
    assert "empty slot != execution authority" in text
    assert "open / unblocked Issue != execution authority" in text
    assert "UPDATE_ONLY 不得自動佔用空槽" in text


def test_registry_routes_user_commands_to_work_slot_skill_only():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in registry["routes"]}
    route = routes["work-slot-routing"]
    assert route["required_skills"] == ["工作槽"]
    for keyword in ("/工作1", "/工作2", "/工作3", "/工作槽", "工作槽"):
        assert keyword in route["keywords"]
    assert ".agents/skills/engineering/工作槽/**" in route["file_globs"]


def test_engineering_readme_exposes_work_slot_as_user_invoked_navigation():
    text = README.read_text(encoding="utf-8")
    assert "[工作槽](./工作槽/SKILL.md)" in text
    assert "/工作1" in text
    assert "/工作2" in text
    assert "/工作3" in text
