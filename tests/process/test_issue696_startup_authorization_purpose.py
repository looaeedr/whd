from pathlib import Path

import pytest


OWNER = Path("tools/execution_entry_contract.py")
AGENTS = Path("AGENTS.md")
BRIDGES = (
    Path(".agents/skills/engineering/執行開發任務/SKILL.md"),
    Path(".agents/skills/engineering/派工/SKILL.md"),
    Path(".agents/skills/engineering/排程模擬/SKILL.md"),
    Path(".agents/skills/engineering/寫排程/SKILL.md"),
    Path(".agents/skills/engineering/強制接手/SKILL.md"),
)
BRIDGE_MARKER = "EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1"
OWNER_POINTER = "tools/execution_entry_contract.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_red_stop_16_has_one_canonical_startup_contract_owner():
    assert OWNER.is_file(), "RED-STOP-16: canonical startup contract owner is missing"


def test_red_stop_16_owner_renders_authorization_purpose_scope_first():
    if not OWNER.is_file():
        pytest.fail("RED-STOP-16: canonical startup contract owner is missing")
    from tools.execution_entry_contract import build_startup_declaration

    block = build_startup_declaration(
        purpose="continue Issue #696 implementation and verification",
        repository="looaeedr/whd",
    )
    lines = [line for line in block.splitlines() if line.strip()]
    assert lines[0] == "WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1"
    assert lines[1].startswith("授權：")
    assert "looaeedr/whd" in lines[1]
    assert lines[2] == "目的：continue Issue #696 implementation and verification"
    assert lines[3].startswith("範圍：")
    assert "不取代 claim / Guard / Preflight" in lines[3]


def test_red_stop_16_all_interactive_entry_surfaces_bridge_same_owner():
    agents = _read(AGENTS)
    assert BRIDGE_MARKER in agents
    assert OWNER_POINTER in agents
    for path in BRIDGES:
        text = _read(path)
        assert BRIDGE_MARKER in text, f"{path} missing startup bridge"
        assert OWNER_POINTER in text, f"{path} does not point to canonical owner"
