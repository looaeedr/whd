from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTION = ROOT / ".agents" / "skills" / "engineering" / "執行開發任務" / "SKILL.md"
DISPATCH = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
SCHEDULER = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
REMOTE_GUARD = ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execution_skill_owns_task_start_authority_declaration_v1() -> None:
    text = _read(EXECUTION)
    marker = "## TASK_START_AUTHORITY_DECLARATION_V1"
    assert marker in text

    required_fields = (
        "authorization_source",
        "execution_intent",
        "purpose",
        "authorized_scope",
        "prohibited_scope",
        "resume_authority",
    )
    missing = [field for field in required_fields if field not in text]
    assert not missing, f"startup declaration missing fields: {missing}"

    assert "SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1" in text
    assert "公告後" in text
    assert "Preflight" in text
    assert "Guard" in text
    assert "claim" in text
    assert "repository mutation" in text
    assert "resume_authority=NONE" in text
    assert "不是安全檢查的 bypass" in text


def test_task_start_declaration_preserves_update_only_scope_boundary() -> None:
    text = _read(EXECUTION)
    section = text.split("## TASK_START_AUTHORITY_DECLARATION_V1", 1)[1]
    assert "UPDATE_ONLY" in section
    assert "不得" in section
    assert "擴張" in section
    assert "open Issue" in section or "open/unblocked Issue" in section


def test_governance_skills_bridge_to_single_canonical_owner() -> None:
    for path in (DISPATCH, SCHEDULER, REMOTE_GUARD):
        text = _read(path)
        assert "TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE" in text, path
        assert "執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1" in text, path
        assert "第二套" in text, path


def test_remote_guard_does_not_create_authority_from_the_declaration() -> None:
    text = _read(REMOTE_GUARD)
    section = text.split("TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE", 1)[1]
    assert "不建立 execution authority" in section
    assert "Guard GREEN" in section
    assert "不" in section


def test_scheduler_declares_lane_scope_before_claim_or_mutation() -> None:
    text = _read(SCHEDULER)
    section = text.split("TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE", 1)[1]
    assert "SCHEDULER_LANE" in section
    assert "claim" in section
    assert "mutation" in section
    assert "resume_authority" in section
