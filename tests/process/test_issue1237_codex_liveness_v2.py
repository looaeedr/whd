from pathlib import Path

from tools.root_local_first_gate import (
    build_remote_connection_authority,
    validate_remote_connection_authority,
)

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workspace_delivery_carries_remote_qa_and_issue_finalization():
    authority = build_remote_connection_authority(
        kind="WORKSPACE_DELIVERY",
        target="GITHUB",
        user_explicit=True,
    )
    required = {
        "PR_READ",
        "PR_COMMENT",
        "WORKFLOW_READ",
        "REMOTE_QA",
        "ISSUE_READ",
        "ISSUE_COMMENT",
        "ISSUE_CLOSE",
        "READBACK",
        "MERGE",
    }
    assert required <= set(authority["allowed_actions"])
    for action in required:
        assert validate_remote_connection_authority(
            authority, target="GITHUB", action=action
        )["kind"] == "WORKSPACE_DELIVERY"


def test_common_flow_bridges_are_not_chat_only():
    paths = [
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/engineering/工作槽/SKILL.md",
        ".agents/skills/engineering/強制接手/SKILL.md",
        ".agents/skills/engineering/issue-closure-gate/SKILL.md",
        ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
        ".agents/skills/engineering/寫排程/SKILL.md",
    ]
    for path in paths:
        text = _read(path)
        assert "WHD_EXECUTION_STARTUP_COMMUNICATION_V1" in text
        assert "必須重新 user-visible 產生" not in text

    scheduler = _read(".agents/skills/engineering/寫排程/SKILL.md")
    assert "每個 fresh invocation 必須先 user-visible" not in scheduler


def test_development_task_startup_has_headless_surface():
    text = _read(".agents/skills/engineering/執行開發任務/SKILL.md")
    assert "Codex/CLI/headless/scheduler" in text
    assert "STDOUT / TASK_EVENT / LOG" in text
    assert "再 user-visible 公告" not in text


def test_diagnosing_bugs_uses_workspace_first_not_drive_first():
    text = _read(".agents/skills/engineering/diagnosing-bugs/SKILL.md")
    assert "WORKSPACE_DEFAULT" in text
    assert "SHARED_ZERO_FALLBACK" not in text
    assert "Missing Drive mount is not a blocker" in text
    assert "Fresh-read canonical Drive root + Current Source Manifest" not in text
    assert "content mutation follows CURRENT shared-0" not in text


def test_remote_qa_and_finalize_consume_workspace_delivery():
    qa = _read(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    closure = _read(".agents/skills/engineering/issue-closure-gate/SKILL.md")
    assert "WORKSPACE_DELIVERY" in qa
    assert "WORKFLOW_READ / REMOTE_QA" in qa
    assert "WORKSPACE_DELIVERY" in closure
    assert "ISSUE_READ / ISSUE_COMMENT / ISSUE_CLOSE / READBACK" in closure


def test_explicit_issue_and_review_tasks_do_not_reprompt_same_authority():
    dispatch = _read(".agents/skills/engineering/派工/SKILL.md")
    slot = _read(".agents/skills/engineering/工作槽/SKILL.md")
    review = _read(".agents/skills/engineering/code-review/SKILL.md")
    for text in (dispatch, slot, review):
        assert "USER_EXPLICIT_REMOTE" in text
    assert "不得再向使用者重問同一授權" in dispatch
    assert "不得因 bridge 需要再向使用者重問" in slot
    assert "不得回頭要求第二次授權" in review


def test_ticket_breakdown_ai_library_is_surface_optional():
    text = _read(".agents/skills/engineering/拆解任務工單/SKILL.md")
    assert "NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE" in text
    assert "N/A_NO_AI_LIBRARY_SURFACE" in text
    assert "Codex/CLI/headless 沒有 AI Library surface" in text
