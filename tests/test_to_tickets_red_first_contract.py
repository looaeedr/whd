from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
TO_TICKETS = ROOT / ".agents" / "skills" / "engineering" / "拆解任務工單" / "SKILL.md"
DISPATCHING = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_approved_requirement_fast_path_does_not_require_requirement_red_or_second_approval():
    text = _text(TO_TICKETS)
    assert "APPROVED_REQUIREMENT_FAST_PATH" in text
    assert "已核准規格" in text
    assert "直接拆票" in text
    assert "不得重新要求 requirement-level RED" in text
    assert "不得再要求第二次核准" in text


def test_unclear_requirement_path_keeps_red_as_discovery_not_universal_gate():
    text = _text(TO_TICKETS)
    assert "REQUIREMENT_DISCOVERY_PATH" in text
    for required in (
        "需求尚未核准",
        "executable RED",
        "正確失敗",
        "使用者核准需求",
    ):
        assert required in text
    assert "RED 只用來釐清未核准需求" in text


def test_approved_spec_ticket_requires_traceability_and_acceptance_not_approved_red_ids():
    text = _text(TO_TICKETS)
    for required in (
        "Requirement Authority",
        "Spec References",
        "Acceptance Tests",
        "Blocked by",
        "Issue Closure owner",
        "AI Library References",
        "AI Library Writeback",
    ):
        assert required in text
    assert "Approved RED IDs" not in text


def test_ticket_decomposition_is_explicit_and_dispatch_cannot_own_a_second_decomposition_machine():
    dispatch = _text(DISPATCHING)
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(item for item in registry["routes"] if item["id"] == "explicit-skill-拆解任務工單")
    assert route["required_skills"] == ["拆解任務工單"]
    assert {"拆解任務工單", "拆工單", "拆票", "拆成工單"}.issubset(set(route["keywords"]))
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in dispatch
    assert "不擁有 execution state machine" in dispatch
    assert "tools/execution_dispatch_ingress.py" in dispatch
    assert "explicit READY ingress" in dispatch


def test_approved_spec_can_publish_blockers_first_without_extra_user_gate():
    text = _text(TO_TICKETS)
    assert "blockers first" in text
    assert "GitHub owning Issue" in text
    assert "已核准規格路徑" in text
    assert "不新增人工 approval gate" in text


def test_ticket_closure_owner_machine_guard_is_retained():
    text = _text(TO_TICKETS)
    assert "tools/ticket_breakdown_guard.py" in text
    assert "Issue Closure owner" in text
    assert "恰好一個" in text
