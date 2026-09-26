from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXECUTION_TASK = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
DISPATCH = ROOT / ".agents/skills/engineering/派工/SKILL.md"
SCHED_SIM = ROOT / ".agents/skills/engineering/排程模擬/SKILL.md"
SCHED_AUTHOR = ROOT / ".agents/skills/engineering/寫排程/SKILL.md"
REMOTE_GUARD = ROOT / ".agents/skills/engineering/remote-execution-guard/SKILL.md"
CONTINUITY = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
CLOSURE = ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execution_task_owns_explicit_execution_intent_modes():
    text = _read(EXECUTION_TASK)
    assert "EXECUTION_INTENT_ROUTING_V1" in text
    for token in (
        "UPDATE_ONLY",
        "EXECUTE_TICKET",
        "EXECUTE_CHAIN",
        "SCHEDULER_LANE",
        "UPDATE_DOES_NOT_IMPLY_EXECUTION",
        "ISSUE_EXISTENCE_IS_NOT_EXECUTION_AUTHORITY",
        "NORMAL_PATH_FIRST",
        "RECOVERY_IS_EXCEPTION_NOT_PHASE",
    ):
        assert token in text


def test_update_only_cannot_claim_branch_or_start_successor():
    text = _read(EXECUTION_TASK)
    assert "UPDATE_ONLY" in text
    assert "不得取得或恢復 implementation execution claim" in text
    assert "不得建立 implementation branch" in text
    assert "不得自動進入 successor / next child" in text
    assert "更新完成條件是該更新本身 + 必要驗證/readback" in text


def test_dispatch_normal_path_is_short_and_recovery_is_conditional():
    text = _read(DISPATCH)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "claim → branch → RED → implementation → GREEN → PR/QA → merge → close/release" in text
    assert "NORMAL_PATH_FIRST" in text
    assert "RECOVERY_IS_EXCEPTION_NOT_PHASE" in text
    assert "不得預防性執行 takeover / reactivate / reconciliation / legacy repair" in text


def test_open_issue_or_free_work_slot_is_not_execution_authority():
    dispatch = _read(DISPATCH)
    sched = _read(SCHED_SIM)
    for text in (dispatch, sched):
        assert "WORK_SLOT_EXECUTION_AUTHORITY_BOUNDARY_V1" in text
        assert "空工作槽" in text
        assert "open / unblocked Issue" in text
        assert "不構成 execution authority" in text


def test_scheduler_simulation_is_explicit_execution_entrypoint_not_update_mode():
    text = _read(SCHED_SIM)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "`/排程A` / `/排程B` = `SCHEDULER_LANE`" in text
    assert "普通文字更新排程、Skill、Issue 或 prompt 不得自動進入此模式" in text
    assert "RECOVERY_IS_EXCEPTION_NOT_PHASE" in text


def test_scheduler_authoring_is_update_only_unless_execution_is_explicit():
    text = _read(SCHED_AUTHOR)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "scheduler authoring / automation update 預設為 `UPDATE_ONLY`" in text
    assert "更新 automation 不授權 claim Issue、建立 implementation branch 或執行 successor chain" in text
    assert "POST_UPDATE_READBACK" in text


def test_remote_guard_never_creates_execution_authority():
    text = _read(REMOTE_GUARD)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "Guard 只驗證已授權 mutation" in text
    assert "Guard GREEN 不會建立 execution intent" in text
    assert "沒有 explicit execution mode 時不得因 Guard 可用而開始施工" in text


def test_continuity_does_not_expand_update_only_into_ticket_or_chain_execution():
    text = _read(CONTINUITY)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "UPDATE_ONLY 不進 continuity execution state machine" in text
    assert "NEXT_CHILD_EXECUTABLE" in text
    assert "只有 `EXECUTE_CHAIN` / `SCHEDULER_LANE`" in text
    assert "不得因 open / unblocked successor 自動升級 execution scope" in text


def test_closure_only_auto_handoffs_successor_in_chain_execution_modes():
    text = _read(CLOSURE)
    assert "EXECUTION_INTENT_ROUTING_V1_BRIDGE" in text
    assert "EXECUTE_TICKET" in text
    assert "EXECUTE_CHAIN" in text
    assert "SCHEDULER_LANE" in text
    assert "單票 closure 完成不等於授權啟動 successor" in text


def test_recovery_language_is_explicitly_evidence_triggered_in_scheduler_and_guard():
    for path in (SCHED_SIM, SCHED_AUTHOR, REMOTE_GUARD, CONTINUITY):
        text = _read(path)
        assert "RECOVERY_IS_EXCEPTION_NOT_PHASE" in text, path
        assert "fresh machine evidence" in text, path
