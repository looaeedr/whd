from pathlib import Path


EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")


def _text() -> str:
    return EXECUTION_SKILL.read_text(encoding="utf-8")


def test_checkpoint_contract_lists_all_required_fields():
    text = _text()
    assert "CHECKPOINT_RESUME_CONTRACT" in text
    for marker in (
        "issue / task id",
        "current role",
        "branch",
        "HEAD SHA",
        "production target",
        "latest commit",
        "remote QA run_id / head_sha / status",
        "completed / pending / failed / blocked",
        "dirty files",
        "validation commands / results",
        "config / baseline invariant status",
        "temporary workflows / branches",
        "next exact action / resume command",
    ):
        assert marker in text


def test_system_hard_cut_writes_checkpoint_but_never_complete():
    text = _text()
    assert "system hard-cut → checkpoint" in text
    assert "checkpoint 不是 COMPLETE evidence" in text
    assert "不得把系統硬切寫成 COMPLETE" in text


def test_resume_checks_drift_then_continues_exact_action():
    text = _text()
    assert "RESUME_DRIFT_GATE" in text
    assert "無 drift → resume next exact action" in text
    assert "有 drift → 只重驗受 drift 影響部分" in text
    assert "不得整條工作鏈無條件重跑" in text
    assert "不得要求使用者重新交代" in text


def test_resume_preserves_branch_head_and_remote_run_lock_identity():
    text = _text()
    assert "CHECKPOINT_IDENTITY_LOCK" in text
    assert "branch + HEAD SHA" in text
    assert "run_id + head_sha" in text
    assert "不一致時先分類 drift / stale checkpoint" in text


def test_recoverable_fail_is_not_a_hard_blocker():
    text = _text()
    assert "可恢復 FAIL 不得進 BLOCKED" in text
    assert "產品語意決策" in text
    assert "必要權限" in text
    assert "不可推導資料" in text
