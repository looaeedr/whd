from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
TO_TICKETS = ROOT / ".agents" / "skills" / "engineering" / "拆解任務工單" / "SKILL.md"
RELEASE = ROOT / ".agents" / "skills" / "engineering" / "phase6-release-packaging" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dispatch_merge_is_not_issue_completion_and_requires_remote_readback():
    text = _text(DISPATCH)
    for required in (
        "合併不等於關單",
        "integration != completion",
        "逐票反讀",
        "state=closed",
        "state_reason=completed",
        "不得宣告 Master 完成",
        "code integrated, process incomplete",
    ):
        assert required in text


def test_dispatch_closes_dependency_chain_leaf_to_master():
    text = _text(DISPATCH)
    for required in (
        "leaf/current ticket",
        "closing/Final Combined ticket",
        "Master/parent",
        "依 dependency 順序",
        "所有 required child",
        "全部 CLOSED/completed",
    ):
        assert required in text


def test_ticket_breakdown_assigns_explicit_issue_closure_owner():
    text = _text(TO_TICKETS)
    for required in (
        "Issue Closure owner",
        "closing/acceptance ticket",
        "逐票關單",
        "Master/parent",
        "不得把 target 已整合當成工單完成",
    ):
        assert required in text


def test_release_completion_requires_issue_chain_terminal_state():
    text = _text(RELEASE)
    for required in (
        "GitHub completion gate",
        "target integration 只是 code-state gate",
        "open issue",
        "CLOSED/completed",
        "不得回報正式完成",
    ):
        assert required in text
