from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_current_root_gate_is_v2_full_repo_shared_unpushed() -> None:
    work_root = json.loads(_read(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"))
    assert work_root["status"] == "CURRENT"
    assert work_root["default_work_root"]["drive_folder_id"] == "1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN"
    assert set(work_root["required_root_entries"]) >= {".git", ".unpushed", ".agents", "tools", "tests"}
    assert work_root["next_gate"]["schema"] == "WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1"
    root_gate = json.loads(_read(".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json"))
    assert root_gate["status"] == "CURRENT"
    assert json.loads(_read(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"))["status"] == "SUPERSEDED"
    assert json.loads(_read(".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"))["status"] == "SUPERSEDED"


def test_dispatch_and_ask_matt_cannot_recreate_a_second_execution_state_machine() -> None:
    agents = _read("AGENTS.md")
    section = agents.split("FLOW_V2_DISPATCH_PROJECTION_ONLY_V1", 1)[1].split(
        "### DURABLE_TERMINAL_EXIT_HARD_GATE_V1", 1
    )[0]
    assert "WHD_EXECUTION_RECORD_V2" in section
    assert "不擁有第二套 execution state machine" in section
    assert "每個工單有實體 checkpoint path" not in section
    ask = _read(".agents/skills/engineering/ask-matt/SKILL.md")
    assert "durable execution state 唯一由 **Flow v2 / WHD_EXECUTION_RECORD_V2** 擁有" in ask
    assert "狀態機由 **派工** 擁有" not in ask


def test_exact_mirror_skill_routes_always_load_flow_v2_first() -> None:
    registry = json.loads(_read(".agents/skills/skill_registry.json"))
    by_id = {route["id"]: route for route in registry["routes"]}
    for route_id in (
        "explicit-skill-monitoring-remote-qa",
        "explicit-skill-issue-closure-gate",
        "explicit-skill-executable-continuity-controller",
        "explicit-skill-執行開發任務",
    ):
        assert by_id[route_id]["required_skills"][0] == "flow-v2-execution", route_id


def test_stale_checkpoint_and_continuity_tests_are_now_anti_regrowth() -> None:
    checkpoint_test = _read("tests/process/test_checkpoint_resume_contract.py")
    continuity_test = _read("tests/process/test_continuous_execution_durable_contract.py")
    assert "LEGACY_CHECKPOINT_MARKERS" in checkpoint_test
    assert "regrew legacy marker" in checkpoint_test
    assert "from tools.continuity_controller import" not in continuity_test
    assert "LEGACY_CURRENT_MARKERS" in continuity_test
    assert "regrew legacy continuity marker" in continuity_test


def test_cleanup_cannot_regrow_retired_main_governance_transports() -> None:
    retired = (
        ".github/workflows/whd-governance-mirror-gate.yml",
        ".github/workflows/whd-governance-ancestry-reconcile.yml",
        "docs/governance/governance_mirror_manifest.json",
        "tools/governance_parity_gate.py",
    )
    for rel in retired:
        assert not (ROOT / rel).exists(), f"retired governance artifact regrew: {rel}"


def test_control_plane_regression_owns_the_anti_regrowth_suite() -> None:
    runner = _read("tools/control_plane_regression.py")
    workflow = _read(".github/workflows/whd-control-plane-regression.yml")
    for rel in (
        "tests/process/test_checkpoint_resume_contract.py",
        "tests/process/test_continuous_execution_durable_contract.py",
        "tests/process/test_issue1046_flow_v2_anti_regrowth_v2.py",
    ):
        assert rel in runner
        assert rel in workflow
