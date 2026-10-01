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
    assert payload["execution_mode_provenance"]["schema"] == "WHD_EXECUTION_MODE_PROVENANCE_V1"
    assert payload["git_write_receipt"]["schema"] == "ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1"
    assert payload["test_execution_receipt"]["schema"] == "WHD_TEST_EXECUTION_RECEIPT_V1"
    assert payload["execution_modes"]["SCHEDULER_LANE"].endswith("ROOT_WORKSPACE_HANDOFF")
    assert payload["remote_content_implementation"]["github_side_hotfix_forbidden"] is True


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


def test_remote_execution_modes_require_trusted_provenance_and_are_not_unlock_tokens():
    from tools.root_local_first_gate import assert_git_content_write_allowed, build_gate_evidence
    with pytest.raises(ValueError, match="provenance"):
        build_gate_evidence(execution_mode="SCHEDULER_LANE")
    evidence = build_gate_evidence(
        execution_mode="SCHEDULER_LANE",
        execution_mode_provenance={
            "schema": "WHD_EXECUTION_MODE_PROVENANCE_V1",
            "execution_mode": "SCHEDULER_LANE",
            "source": "FLOW_V2_LANE_ID",
            "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        },
    )
    assert evidence["applicable"] is False
    assert evidence["next_action"] == "FOLLOW_FLOW_V2_REMOTE_AUTHORITY"
    with pytest.raises(ValueError, match="does not authorize"):
        assert_git_content_write_allowed(evidence, action="COMMIT")

    handoff = build_gate_evidence(
        execution_mode="SCHEDULER_LANE",
        execution_mode_provenance={
            "schema": "WHD_EXECUTION_MODE_PROVENANCE_V1",
            "execution_mode": "SCHEDULER_LANE",
            "source": "FLOW_V2_LANE_ID",
            "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        },
        repository_content_implementation=True,
    )
    assert handoff["scope"] == "REMOTE_CONTENT_IMPLEMENTATION_REQUIRES_HANDOFF"
    assert handoff["next_action"] == "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION"
    assert handoff["git_write_unlocked"] is False


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
    from tools.skill_catalog import inventory

    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    active = {row.path for row in inventory() if row.active}
    required_refs = {
        ref
        for route in registry["routes"]
        for ref in route.get("required_references", [])
        if (ROOT / ref).exists() and (ROOT / ref).is_file()
    }
    scan = {"AGENTS.md", *active, *required_refs}
    # The canonical root-local-first Skill deliberately quotes forbidden legacy
    # wording in its anti-regrowth section; other active routes must not carry it.
    scan.discard(".agents/skills/engineering/root-local-first/SKILL.md")
    forbidden = (
        "每次修改先從最新 target 開新分支",
        "第一個 repository write 之前先開新 work branch",
        "Before the first write of a new modification task, create a fresh branch",
        "建立 branch 後才可開始 Skill/tests/docs/production 修改",
    )
    offenders = []
    for rel in sorted(scan):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                offenders.append((rel, phrase))
    assert offenders == []


def test_git_unlock_receipt_is_machine_bound_to_frozen_diff_and_reservation():
    from tools.root_local_first_gate import build_gate_evidence, build_git_unlock_receipt, validate_git_unlock_receipt, validate_source_current
    source = validate_source_current(manifest=_manifest(), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation(),
        root_mutations_complete=True, test_classified=True, tests_green=True,
        test_receipt=_test_receipt(), expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="c" * 64,
    )
    receipt = build_git_unlock_receipt(evidence)
    assert receipt["schema"] == "ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1"
    assert receipt["source_sha"] == "a" * 40
    assert receipt["diff_digest"] == "c" * 64
    assert receipt["write_mode"] == "EXACT_TESTED_DIFF_ONLY"
    assert validate_git_unlock_receipt(receipt)["git_write_unlocked"] is True
    bad = dict(receipt, git_write_unlocked=False)
    with pytest.raises(ValueError, match="GIT_WRITE_UNLOCKED"):
        validate_git_unlock_receipt(bad)



def test_bare_tests_green_boolean_is_rejected():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current
    source = validate_source_current(manifest=_manifest(), live_source_sha="a" * 40, live_tree_sha="b" * 40)
    with pytest.raises(ValueError, match="WHD_TEST_EXECUTION_RECEIPT_V1"):
        build_gate_evidence(
            execution_mode="INTERACTIVE", source_evidence=source, path_reservation_evidence=_reservation(),
            root_mutations_complete=True, test_classified=True, tests_green=True, diff_digest="f" * 64,
        )

def test_root_local_mirror_points_to_current_drive_v5_identity():
    payload = _contract()
    source = payload["canonical_source"]
    assert source["drive_file_id"] == "1qOMBtDwNGK5yxq_iyfISKYYDkBITXFuV"
    assert source["library_path"] == "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
    assert source["canonical_filename"] == "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
    assert source["versioned_aliases_must_not_be_current"] is True
    assert source["canonical_payload_sha256"] == "a0b218d75e8c3e270519f4f28df1f783b8a1ab60bda30889682ef957a4beb64f"
    assert source["drive_file_id"] != "1vjSwAJNNwcEKIHh4iXqYuuYXJ_1YkA9L"
    assert source["drive_file_id"] != "1p_C-NaNML03xUYxxCjUsisTbpoFv9Zgp"

def test_interactive_orchestration_fast_path_is_machine_owned():
    payload = _contract()
    gate = payload["orchestration_fast_path"]
    assert gate["schema"] == "WHD_INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1"
    assert gate["default"] == "SESSION_INTERNAL_ORCHESTRATION"
    assert "PER_TRANSACTION_MANUAL_ORCHESTRATION" in gate["outer_forbidden"]
    assert "MANUAL_LEASE_RENEW_BEFORE_EXPIRY" in gate["outer_forbidden"]
    assert "START_QA_THEN_ACCEPT_QA_WHEN_CONSUME_QA_IS_ELIGIBLE" in gate["outer_forbidden"]
    assert gate["stale_plan_policy"] == "STALE_PLAN_MUST_DIE"
    assert gate["single_writer_policy"] == "ONE_ISSUE_ONE_MUTATION_WRITER"


def test_root_local_skill_exposes_fast_path_hard_gate():
    text = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(encoding="utf-8")
    assert "INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1" in text
    assert "不得由聊天層逐顆手動編排" in text
    assert "REPORT_PHASE_OUTCOME_NOT_CONTROL_PLANE_INTERNALS" not in text or "phase outcome" in text


def test_task_scope_stickiness_blocks_control_plane_drift():
    from tools.root_local_first_gate import validate_contract
    payload = _contract()
    gate = validate_contract(payload)["direct_root_mutation_test_gate"]
    assert gate["task_scope_sticky_until"] == "ROOT_TESTS_GREEN_OR_REAL_BLOCKER_OR_USER_EXPLICIT_TASK_CHANGE"
    assert gate["control_plane_anomaly_action"] == "RECORD_AS_EVIDENCE_AND_CONTINUE_CURRENT_ROOT_TASK"
    for trigger in (
        "STALE_EXECUTION_RECORD", "EXPIRED_LEASE", "RESERVATION_MISMATCH",
        "GOVERNANCE_DRIFT", "TEST_RED", "STATUS_QUERY", "PROGRESS_QUERY",
    ):
        assert trigger in gate["forbidden_scope_switch_triggers"]
    assert set(gate["scope_switch_allowed_only_on"]) == {
        "USER_EXPLICIT_TASK_CHANGE", "PATH_CONFLICT", "SAME_ISSUE_OTHER_WRITER",
        "SUBSTANTIVE_TARGET_OVERLAP", "MACHINE_FAIL_CLOSED", "USER_INPUT_REQUIRED",
    }
    bad = json.loads(json.dumps(payload))
    bad["direct_root_mutation_test_gate"]["control_plane_anomaly_action"] = "REPAIR_GOVERNANCE_FIRST"
    with pytest.raises(ValueError, match="must not become a new primary task"):
        validate_contract(bad)


def test_direct_root_mutation_test_hard_gate_forbids_handoff_only_stops():
    payload = _contract()
    gate = payload["direct_root_mutation_test_gate"]
    assert gate["schema"] == "WHD_DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1"
    assert gate["canonical_surface"] == "/Google Drive/WHD/work/active"
    assert gate["interactive_first_substantive_action"] == "ROOT_MUTATE"
    assert gate["required_contiguous_outer_sequence"] == [
        "ROOT_MUTATE", "ROOT_TEST_CLASSIFIED", "ROOT_TESTS_GREEN"
    ]
    assert gate["same_invocation_until"] == "ROOT_TESTS_GREEN_OR_REAL_BLOCKER"
    assert gate["root_capability_available_policy"] == "NO_HANDOFF_ONLY_STOP"
    assert gate["status_or_progress_query_is_stop_reason"] is False
    assert "HANDOFF_ONLY" in gate["forbidden_pre_root_green_outcomes"]
    assert "GOVERNANCE_GREEN_ONLY" in gate["forbidden_pre_root_green_outcomes"]
    assert "REMOTE_QA_AS_FIRST_TEST_SURFACE" in gate["forbidden_pre_root_green_outcomes"]
    assert gate["test_red_action"] == "FIX_IN_SAME_ROOT_WORKSPACE_AND_RETEST"
    assert gate["remote_without_root_capability_action"] == "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK"


def test_flow_v2_skill_requires_direct_root_modify_and_test_in_same_invocation():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1" in text
    assert "同一 invocation" in text
    assert "ROOT_MUTATE" in text
    assert "ROOT_TEST_CLASSIFIED → ROOT_TESTS_GREEN" in text
    assert "使用者詢問進度/狀態只算 non-blocking checkpoint" in text
    assert "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK" in text


def test_test_receipt_generation_is_historical_provenance_not_exact_lease_generation():
    from tools.root_local_first_gate import validate_test_execution_receipt
    receipt = _test_receipt(generation=4)
    assert validate_test_execution_receipt(
        receipt,
        expected_source_sha="a" * 40,
        expected_issue=996,
        expected_generation=7,
        expected_commands=["python tools/control_plane_regression.py"],
    )["generation"] == 4
    with pytest.raises(ValueError, match="future"):
        validate_test_execution_receipt(
            _test_receipt(generation=8),
            expected_source_sha="a" * 40,
            expected_issue=996,
            expected_generation=7,
            expected_commands=["python tools/control_plane_regression.py"],
        )


def test_validate_contract_machine_enforces_direct_root_mutation_gate():
    from tools.root_local_first_gate import validate_contract
    payload = _contract()
    assert validate_contract(payload)["direct_root_mutation_test_gate"]["interactive_first_substantive_action"] == "ROOT_MUTATE"
    bad = json.loads(json.dumps(payload))
    bad["direct_root_mutation_test_gate"]["status_or_progress_query_is_stop_reason"] = True
    with pytest.raises(ValueError, match="status/progress query"):
        validate_contract(bad)