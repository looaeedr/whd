from pathlib import Path

import pytest

from tools.continuity_controller import (
    Checkpoint,
    ContinuityState,
    FinalizationBlocked,
    assert_finalizable,
)


DISPATCH_SKILL = Path(".agents/skills/engineering/派工/SKILL.md")
EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")
PITFALLS = Path("個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md")
EXECUTABLE_PITFALL = Path("個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md")
MONITORING_SKILL = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
CLOSURE_SKILL = Path(".agents/skills/engineering/issue-closure-gate/SKILL.md")
CONTROLLER_SKILL = Path(".agents/skills/engineering/executable-continuity-controller/SKILL.md")
CONTROLLER = Path("tools/continuity_controller.py")


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_dispatch_issue_creation_is_not_a_terminal_state():
    text = _read(DISPATCH_SKILL)
    assert "同一次工作流程直接進下一狀態" in text
    assert "不以「已派工」作為停工點" in text


def test_nonterminal_next_action_blocks_final_response():
    text = _read(EXECUTION_SKILL)
    assert "NONTERMINAL_NEXT_ACTION_GATE" in text
    assert "存在可自主執行的下一步" in text
    assert "final 禁止" in text
    assert "Gate RED" in text
    assert "完成 Gate 所要求的 evidence" in text
    assert "continuous_execution_pitfalls.md" in text


def test_ai_library_records_dispatch_stop_as_a_repeatable_pitfall():
    text = _read(PITFALLS)
    assert "把派工完成當成停工點" in text
    assert "進度回報不是工作終點" in text
    assert "使用者不是續跑 scheduler" in text


def test_remote_qa_authority_remains_delegated_to_monitoring_skill():
    dispatch = _read(DISPATCH_SKILL)
    execution = _read(EXECUTION_SKILL)
    monitoring = _read(MONITORING_SKILL)

    assert "monitoring-remote-qa" in dispatch
    assert "monitoring-remote-qa" in execution
    assert "REMOTE_QA_ACTIVE_LOCK" in monitoring
    assert "使用者不是 remote-QA scheduler" in monitoring


def test_execution_window_cut_is_recovery_not_rollback_or_scheduler_handoff():
    execution = _read(EXECUTION_SKILL)
    pitfalls = _read(PITFALLS)

    assert "EXECUTION_WINDOW_INTERRUPTION_RECOVERY" in execution
    assert "ISSUE188_EXECUTION_WINDOW_RECOVERY_PITFALL" in pitfalls
    assert "execution window interruption" in pitfalls
    assert "RECOVERING" in pitfalls
    assert "completed phase evidence" in pitfalls
    assert "只有 drift 才重驗受影響範圍" in pitfalls
    assert "使用者不是續跑 scheduler" in pitfalls


def test_remote_qa_waiting_state_cannot_survive_without_an_active_locked_run():
    monitoring = _read(MONITORING_SKILL)
    pitfalls = _read(PITFALLS)

    assert "STALE_WAIT_WATCHDOG" in monitoring
    assert "WAITING_REMOTE_QA" in monitoring
    assert "RECOVERING_STALE_WAIT" in monitoring
    assert "active run = 0" in monitoring
    assert "沒有 run_id + head_sha 就禁止進入 waiting" in monitoring
    assert "只有 queued / in_progress 才允許維持 waiting" in monitoring
    assert "terminal run 立即退出 waiting" in monitoring
    assert "連續 2 次" in monitoring
    assert "30 秒" in monitoring
    assert "ISSUE188_STALE_WAIT_PITFALL" in pitfalls
    assert "checkpoint 寫著 WAITING_REMOTE_QA" in pitfalls
    assert "GitHub 已無 active run" in pitfalls
    assert "STALE_WAIT" in pitfalls
    assert "使用者不是 watchdog" in pitfalls


def test_work_order_children_must_preserve_one_accepted_lineage_until_final_integration():
    dispatch = _read(DISPATCH_SKILL)
    pitfalls = _read(PITFALLS)

    assert "WORK_ORDER_LINEAGE_CONTRACT" in dispatch
    assert "工單主分支" in dispatch
    assert "子票不得重新從 production target 起跑" in dispatch
    assert "production target 只作 integration target / drift authority" in dispatch
    assert "整張工單 final verified work-order HEAD" in dispatch
    assert "一次 non-force 整合" in dispatch
    assert "WORK_ORDER_LINEAGE_PITFALL" in pitfalls
    assert "T4 吃到舊 T3 HEAD" in pitfalls
    assert "前序 accepted lineage" in pitfalls
    assert "task/QA branch" in pitfalls


def test_continuity_docs_delegate_to_executable_controller_not_markers_only():
    execution = _read(EXECUTION_SKILL)
    monitoring = _read(MONITORING_SKILL)
    closure = _read(CLOSURE_SKILL)
    controller_skill = _read(CONTROLLER_SKILL)
    pitfall = _read(EXECUTABLE_PITFALL)

    assert CONTROLLER.exists()
    assert "EXECUTABLE_CONTINUITY_CONTROLLER_V1" in controller_skill
    assert "EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE" in execution
    assert "EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE" in monitoring
    assert "EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE" in closure
    assert "assert_finalizable" in execution
    assert "assert_finalizable" in closure
    assert "Documentation != enforcement" in pitfall
    assert "只搜文字不算" in pitfall


def test_nonterminal_finalization_is_behaviorally_rejected_not_just_documented():
    checkpoint = Checkpoint(
        issue="#216",
        branch="fix/continuous-execution-runtime-guard-20260914",
        head_sha="behavior-proof",
        state=ContinuityState.RUNNING,
        next_action="continue exact action",
    )

    with pytest.raises(FinalizationBlocked, match="non-terminal"):
        assert_finalizable(checkpoint)
