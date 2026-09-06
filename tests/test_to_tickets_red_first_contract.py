from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TO_TICKETS = ROOT / ".agents" / "skills" / "engineering" / "拆解任務工單" / "SKILL.md"
DISPATCHING = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_to_tickets_requires_red_gate_before_drafting_any_ticket():
    text = _text(TO_TICKETS)
    for required in (
        "RED Gate",
        "實際執行",
        "正確失敗",
        "使用者逐條論證",
        "使用者核准",
        "才可開始草擬工單",
    ):
        assert required in text


def test_to_tickets_red_must_map_each_requirement_to_executable_evidence():
    text = _text(TO_TICKETS)
    for required in (
        "Requirement",
        "RED command/nodeid",
        "expected failure",
        "observed failure",
        "user decision",
    ):
        assert required in text
    assert "環境錯誤" in text
    assert "語法錯誤" in text
    assert "fixture" in text
    assert "不能算 RED" in text


def test_to_tickets_must_fail_closed_before_red_approval():
    text = _text(TO_TICKETS)
    for forbidden_before_approval in (
        "Draft vertical slices",
        "Publish the tickets",
        "GitHub",
        "Local files",
    ):
        assert forbidden_before_approval in text
    for required in (
        "RED 未核准",
        "不得開始拆工單",
        "不得建立 issue",
        "不得寫入 local ticket",
    ):
        assert required in text


def test_dispatching_pm_cannot_bypass_to_tickets_red_gate():
    text = _text(DISPATCHING)
    assert ".agents/skills/engineering/拆解任務工單/SKILL.md" in text
    for required in (
        "RED-first",
        "使用者核准",
        "不得拆解工單",
        "不得轉移至：實作者",
    ):
        assert required in text


def test_to_tickets_does_not_invent_repair_ticket_when_red_is_already_green():
    text = _text(TO_TICKETS)
    for required in (
        "RED 已是 GREEN",
        "不得建立修復工單",
        "重新確認測試 seam",
    ):
        assert required in text


def test_each_drafted_ticket_must_reference_approved_red_ids():
    text = _text(TO_TICKETS)
    for required in (
        "Approved RED IDs",
        "每張工單",
        "已核准的 RED",
    ):
        assert required in text
