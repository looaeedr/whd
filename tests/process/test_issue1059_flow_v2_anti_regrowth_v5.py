from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
CLASSIFICATION = ROOT / "tests/process/WHD_PROCESS_TEST_CLASSIFICATION_V1.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_x_second_main_governance_is_historical_only() -> None:
    rel = "個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md"
    text = _read(rel)
    assert "whd_doc_role: HISTORICAL" in text
    assert "FLOW_V2_LEGACY_EXECUTION_HISTORY_FENCE_V2" in text
    assert "HISTORICAL / SUPERSEDED BY FLOW V2" in text
    authority = _read("個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    assert f"contract=x-independent-task-chain-governance role=HISTORICAL path={rel}" in authority


def test_current_flow_bridges_do_not_regrow_retired_execution_contracts() -> None:
    surfaces = [
        "AGENTS.md",
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/engineering/排程模擬/SKILL.md",
        ".agents/skills/engineering/工作槽/SKILL.md",
        ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
        ".agents/skills/engineering/issue-closure-gate/SKILL.md",
        ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
        ".agents/skills/engineering/remote-execution-guard/SKILL.md",
        ".agents/skills/engineering/強制接手/SKILL.md",
        ".agents/skills/engineering/執行開發任務/SKILL.md",
        ".agents/skills/engineering/寫排程/SKILL.md",
    ]
    retired = (
        "X_SECOND_MAIN_INDEPENDENT_CHAIN_CONTRACT",
        "MAIN_TO_X_BATCH_FIRST_PARITY_V1",
        "EXECUTION_STATE_MACHINE",
        "OWNING_FINALIZATION_GUARD_V2",
        "SCHEDULED_WAKEUP_CONTINUITY_CONTRACT",
        "REMOTE_QA_STATE_BRIDGE",
        "WHD_REMOTE_GUARD_REQUEST_V1",
        "GITHUB_DURABLE_STATE_RECONSTRUCTION_HARD_GATE_V1_BRIDGE",
        "EXECUTION_CLAIM_PREWRITE_HARD_GATE",
    )
    for rel in surfaces:
        text = _read(rel)
        for marker in retired:
            assert marker not in text, (rel, marker)


def test_historical_process_tests_are_executable_anti_regrowth_wrappers() -> None:
    payload = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    assert payload["status"] == "CURRENT"
    assert payload["policy"] == "RETIRED_EXECUTION_CONTRACT_TESTS_REMAIN_EXECUTABLE_ONLY_AS_HISTORICAL_ANTI_REGROWTH"
    assert payload["historical_anti_regrowth_tests"]
    expected = (
        "from tests.process._flow_v2_historical_cutover import assert_historical_cutover\n\n"
        "def test_retired_execution_contract_cannot_regrow() -> None:\n"
        "    assert_historical_cutover(__file__)\n"
    )
    for rel in payload["historical_anti_regrowth_tests"]:
        assert _read(rel) == expected, rel


def test_git_connector_pitfall_cannot_authorize_production_update_ref() -> None:
    text = _read("個人AI檔案庫/踩坑庫/git_connector_target_write_pitfall.md")
    assert "所有 repository-content 修改先走 canonical root-local-first" in text
    assert "production integration 禁用 chat/runtime Contents API 與 `update_ref`" in text
    assert "Flow v2 trusted `MERGE / SYNC_TARGET`" in text
    assert "UPDATE_REF(force=false) → POST_MERGE" not in text


def test_ha_poweroff_usage_uses_current_flow_v2_resume_owners() -> None:
    text = _read("docs/governance/whd_ha_poweroff_integration_usage.md")
    assert "native `WHD_EXECUTION_RECORD_V2` + `tools/execution_invocation_exit.py`" in text
    assert "chain.next_issue + chain.next_action" in text
    owners = text.split("## Machine owners", 1)[1].split("## Current request identity", 1)[0]
    assert "tools/continuity_controller.py" not in owners
    assert "tools/execution_claim_guard.py" not in owners


def test_legacy_finalization_commands_have_chunk_local_fence() -> None:
    for rel in (
        "docs/superpowers/plans/2026-09-16-issue292-t4-part-panels.md",
        "docs/superpowers/plans/2026-09-17-issue293-t5-editors.md",
        "docs/superpowers/plans/2026-09-18-issue294-t6-rendering.md",
        "docs/superpowers/plans/2026-09-18-issue295-t7-controller.md",
    ):
        lines = _read(rel).splitlines()
        for idx, line in enumerate(lines):
            if any(token in line for token in ("assert-finalizable", "authorize-finalization", "verify-finalization-proof")):
                window = "\n".join(lines[max(0, idx - 2):idx])
                assert "FLOW_V2_LEGACY_CHUNK_FENCE_V2" in window, (rel, idx + 1)


def test_behavior_matrix_is_frozen_historical_not_runtime_authority() -> None:
    payload = json.loads(_read("docs/governance/issue843_control_plane_behavior_matrix.json"))
    assert payload["runtime_authority"] is False
    assert payload["snapshot_role"] == "HISTORICAL_PRE_FLOW_V2_CONTROL_PLANE_MATRIX"
    assert payload["superseded_by"] == ".agents/skills/engineering/flow-v2-execution/SKILL.md"


def test_control_plane_owns_current_execution_skill_contract_surfaces() -> None:
    from tools.control_plane_regression import PYTEST_PATHS
    for rel in (
        "tests/test_dispatching_skill_timeout_contract.py",
        "tests/test_execution_work_slot_autoincrement.py",
        "tests/test_dm5_deep_module_writeback_contract.py",
        "tests/test_issue443_t1_dead_glue.py",
        "tests/test_issue_closure_completion_skill_contract.py",
        "tests/test_phase6_skill_preflight_gate.py",
        "tests/test_remote_qa_monitoring_skill_contract.py",
        "tests/test_to_tickets_red_first_contract.py",
    ):
        assert rel in PYTEST_PATHS


def test_control_plane_auto_includes_every_flow_v2_process_test() -> None:
    from tools.control_plane_regression import FLOW_V2_PYTEST_PATHS, PYTEST_PATHS
    discovered = tuple(sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "tests/process").glob("test_flow_v2_*.py")))
    assert FLOW_V2_PYTEST_PATHS == discovered
    assert set(discovered) <= set(PYTEST_PATHS)
    assert "tests/process/test_issue1059_flow_v2_anti_regrowth_v5.py" in PYTEST_PATHS


def test_transport_binds_lease_and_next_action_identity() -> None:
    text = _read("tools/control_transaction_transport.py")
    terminal = _read("tools/control_transaction_terminal_executor.py")
    for token in ("expected_lease_token", "expected_next_action_kind"):
        assert token in text
        assert token in terminal


def test_product_full_regression_remains_real_full_pytest() -> None:
    text = _read("tools/change_test_profile.py")
    assert '"PRODUCT_FULL_REGRESSION": ("python -m pytest -q",)' in text
    assert "HISTORICAL_ANTI_REGROWTH" not in text


def test_v5_does_not_hide_product_tests_through_pytest_collection_filters() -> None:
    config = _read("pytest.ini")
    assert "testpaths = tests" not in config
    assert "--ignore=" not in config
    assert "-m not" not in config
    assert "norecursedirs = BACKUP" in config
