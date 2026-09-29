import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
SKILL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"


def _contract(): return json.loads(CONTRACT.read_text(encoding="utf-8"))
def _manifest(sha="a" * 40, tree="b" * 40): return {"source_sha": sha, "tree_sha": tree, "durable_snapshot_status": "STALE_BOOTSTRAP_BASE"}
def _reservation(sha="a" * 40): return {
    "schema": "WHD_PATH_RESERVATION_EVIDENCE_V1",
    "issue": 996,
    "generation": 4,
    "target_branch": "cleanup/2d-3d-sync",
    "base_sha": sha,
    "write_paths": ["AGENTS.md"],
    "delete_paths": [],
    "reservation_state": "ACTIVE",
    "workspace_path": f"/Google Drive/WHD/work/active/issue-996/{sha[:12]}",
    "record_fingerprint": "f" * 64,
}




def _test_receipt(sha="a" * 40, issue=996, generation=4):
    return {
        "schema": "WHD_TEST_EXECUTION_RECEIPT_V1",
        "status": "GREEN",
        "source_sha": sha,
        "issue": issue,
        "generation": generation,
        "exact_commands": ["python tools/control_plane_regression.py"],
        "manifest_digest": "e" * 64,
    }

def test_contract_and_skill_are_current_and_single_owner():
    from tools.root_local_first_gate import validate_contract
    payload = validate_contract(_contract())
    assert payload["owner"] == "tools/root_local_first_gate.py"
    assert payload["skill_owner"] == ".agents/skills/engineering/root-local-first/SKILL.md"
    text = SKILL.read_text(encoding="utf-8")
    assert "name: root-local-first" in text
    assert "WHD_CHANGE_TEST_PROFILE_V1" in text
    assert "tools/change_test_profile.py" in text
    assert "EXACT_TESTED_DIFF_ONLY" in text
    assert payload["required_order"][:3] == ["ROOT_SOURCE_CURRENT", "PATHS_RESERVED", "ROOT_MUTATIONS_COMPLETE"]
    assert payload["path_reservation"]["state_owner"] == "WHD_EXECUTION_RECORD_V2.mutation_scope"
    assert payload["path_reservation"]["evaluator"] == "tools/execution_path_reservation.py"


def test_interactive_order_unlocks_only_after_root_green_and_frozen_diff():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current
    source = validate_source_current(manifest=_manifest(), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    locked = build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source)
    assert locked["git_write_unlocked"] is False
    assert locked["next_action"] == "PATHS_RESERVED"
    reserved = build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation())
    assert reserved["next_action"] == "ROOT_MUTATIONS_COMPLETE"
    unlocked = build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation(), root_mutations_complete=True, test_classified=True, tests_green=True, test_receipt=_test_receipt(), expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="c" * 64)
    assert unlocked["git_write_unlocked"] is True
    assert unlocked["completed"][-1] == "GIT_WRITE_UNLOCKED"
    assert unlocked["next_action"] == "EXACT_TESTED_DIFF_ONLY"


def test_git_content_write_is_forbidden_before_unlock():
    from tools.root_local_first_gate import assert_git_content_write_allowed, build_gate_evidence
    evidence = build_gate_evidence(execution_mode="INTERACTIVE")
    assert_git_content_write_allowed(evidence, action="READ")
    with pytest.raises(ValueError, match="GIT_WRITE_LOCKED"):
        assert_git_content_write_allowed(evidence, action="COMMIT")


def test_target_drift_forces_resync_and_retest_before_git_write():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current
    source = validate_source_current(manifest=_manifest(), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    evidence = build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation(), root_mutations_complete=True, test_classified=True, tests_green=True, test_receipt=_test_receipt(), expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="d" * 64, target_drift=True)
    assert evidence["git_write_unlocked"] is False
    assert evidence["next_action"] == "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE"


def test_stale_manifest_requires_exact_touched_path_proofs():
    from tools.root_local_first_gate import validate_source_current
    with pytest.raises(ValueError, match="manifest stale"):
        validate_source_current(manifest=_manifest("1" * 40, "2" * 40), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    recovered = validate_source_current(manifest=_manifest("1" * 40, "2" * 40), live_source_sha="a" * 40, live_tree_sha="b" * 40, touched_path_proofs=[{"path": "AGENTS.md", "live_blob_sha": "3" * 40, "workspace_blob_sha": "3" * 40}])
    assert recovered["status"] == "SCOPED_CURRENT_RECOVERY"


def test_remote_execution_modes_are_explicit_scope_exception_not_unlock_token():
    from tools.root_local_first_gate import assert_git_content_write_allowed, build_gate_evidence
    evidence = build_gate_evidence(execution_mode="SCHEDULER_LANE")
    assert evidence["applicable"] is False
    assert evidence["next_action"] == "FOLLOW_FLOW_V2_REMOTE_AUTHORITY"
    with pytest.raises(ValueError, match="does not authorize"):
        assert_git_content_write_allowed(evidence, action="COMMIT")


def test_agents_registry_authority_map_and_root_gate_wire_forward():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V1") < agents.index("ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1") < agents.index("# 0. 啟動硬閘門")
    root_gate = json.loads((ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(encoding="utf-8"))
    assert root_gate["next_gate"]["schema"] == "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1"
    assert "ROOT_LOCAL_FIRST_GATE_READ" in root_gate["required_sequence"]
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(r for r in registry["routes"] if r["id"] == "root-local-first")
    assert route["file_globs"] == ["**"]
    assert "root-local-first" in route["required_skills"]
    authority = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    assert "whd_contract: canonical-authority-map" in authority
    assert "contract=root-local-first-entry-gate role=CURRENT path=tools/root_local_first_gate.py" in authority
    assert "contract=root-local-first-workflow role=CURRENT path=.agents/skills/engineering/root-local-first/SKILL.md" in authority
    assert "contract=flow-v2-path-reservation role=CURRENT path=tools/execution_path_reservation.py" in authority


def test_active_governance_does_not_regrow_old_branch_before_root_write_rule():
    active = ["AGENTS.md", ".agents/skills/engineering/diagnosing-bugs/SKILL.md", ".agents/skills/engineering/phase6-release-packaging/SKILL.md", ".agents/skills/engineering/寫技能/SKILL.md", ".agents/skills/misc/git-remote-sync-fallback/SKILL.md", ".agents/skills/productivity/MCP工具操作/SKILL.md", ".agents/skills/productivity/找技能/SKILL.md", ".agents/skills/engineering/拷問邊建立文件/SKILL.md", ".agents/skills/engineering/UI設計與去AI味/SKILL.md", "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md", "個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md", "個人AI檔案庫/第二層_專案與SOP/12_WHD規格書Skill前置與Grounding規則.md"]
    forbidden = ("branch-first", "BRANCH-FIRST", "第一個 repository write 之前先開新 work branch", "Before the first write of a new modification task, create a fresh branch")
    for rel in active:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, (rel, phrase)


def test_bare_tests_green_boolean_is_rejected():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current
    source = validate_source_current(manifest=_manifest(), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    with pytest.raises(ValueError, match="WHD_TEST_EXECUTION_RECEIPT_V1"):
        build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation(), root_mutations_complete=True, test_classified=True, tests_green=True, diff_digest="f" * 64)
