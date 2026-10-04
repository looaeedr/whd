import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json"
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
    "phase": "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN",
    "record_fingerprint": "f" * 64,
}

def _lane(sha="a" * 40, generation=4, lane="docs"):
    return {
        "schema": "WHD_UNPUSHED_LANE_EVIDENCE_V1",
        "lane": lane,
        "issue": 996,
        "source_sha": sha,
        "target_branch": "cleanup/2d-3d-sync",
        "generation": generation,
        "write_paths": ["AGENTS.md"],
        "delete_paths": [],
        "manifest_digest": "",
        "state": "ACTIVE",
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


def _worker_census(generation=4, *, mergeable=0, blocking=0, lane="docs"):
    return {
        "schema": "WHD_SHARED_ZERO_WORKER_CENSUS_V1",
        "lane": lane,
        "latest_zero_generation": generation,
        "fresh": True,
        "mergeable_green_count": mergeable,
        "blocking_candidate_count": blocking,
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
    assert payload["required_order"][:4] == [
        "ROOT_SOURCE_CURRENT", "UNPUSHED_LANE_CLASSIFIED",
        "LATEST_0_BASE_BOUND", "ROOT_MUTATIONS_COMPLETE",
    ]
    assert payload["shared_unpushed_integration"]["machine_owner"] == "tools/shared_unpushed_integration.py"
    assert payload["shared_unpushed_integration"]["conflict_state"] == "BLOCKED_USER_DECISION"
    assert payload["path_reservation"]["phase"] == "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN"
    assert payload["execution_mode_provenance"]["schema"] == "WHD_EXECUTION_MODE_PROVENANCE_V1"
    assert payload["git_write_receipt"]["schema"] == "ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1"
    assert payload["test_execution_receipt"]["schema"] == "WHD_TEST_EXECUTION_RECEIPT_V1"
    assert payload["execution_modes"]["SCHEDULER_LANE"].endswith("ROOT_WORKSPACE_HANDOFF")
    assert payload["remote_content_implementation"]["github_side_hotfix_forbidden"] is True
    fast_path = payload["orchestration_fast_path"]
    assert fast_path["outer_action_gate"] == "tools/root_local_first_gate.py::assert_outer_primary_action"
    assert fast_path["outer_primary_action_policy"] == "PHASE_OUTCOME_OR_REAL_BLOCKER_ONLY"
    assert fast_path["control_plane_event_disposition"] == "BACKGROUND_CONTINUE_PRIMARY_TASK"
    assert "RECONCILE" in fast_path["machine_internal_transaction_kinds"]
    assert "EXPIRED_LEASE" in fast_path["background_only_events"]


def test_interactive_order_uses_shared_zero_then_delivery_reservation():
    from tools.root_local_first_gate import (
        build_gate_evidence,
        build_remote_connection_authority,
        validate_source_current,
    )
    source = validate_source_current(
        workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40},
        live_source_sha="a" * 40, live_tree_sha="b" * 40,
    )
    authority = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    locked = build_gate_evidence(execution_mode="INTERACTIVE", source_evidence=source)
    assert locked["next_action"] == "UNPUSHED_LANE_CLASSIFIED"

    lane_bound = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane()
    )
    assert lane_bound["next_action"] == "ROOT_MUTATIONS_COMPLETE"

    merged = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True,
        tests_green=True, test_receipt=_test_receipt(),
        expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="c" * 64,
    )
    assert merged["git_write_unlocked"] is False
    assert merged["next_action"] == "REMOTE_CONNECTION_AUTHORIZED"

    reserved = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True,
        tests_green=True, test_receipt=_test_receipt(),
        expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="c" * 64,
        remote_connection_authority=authority,
    )
    assert reserved["git_write_unlocked"] is False
    assert reserved["next_action"] == "DELIVERY_PATHS_RESERVED"

    unlocked = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True,
        tests_green=True, test_receipt=_test_receipt(),
        expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="c" * 64,
        remote_connection_authority=authority,
        path_reservation_evidence=_reservation(),
    )
    assert unlocked["git_write_unlocked"] is True
    assert unlocked["completed"][-1] == "GIT_WRITE_UNLOCKED"
    assert unlocked["next_action"] == "EXACT_TESTED_DIFF_ONLY"


def test_worker_census_compatibility_bridge_is_optional_but_validated():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current

    source = validate_source_current(
        workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40},
        live_source_sha="a" * 40, live_tree_sha="b" * 40,
    )
    common = dict(
        execution_mode="INTERACTIVE", source_evidence=source,
        unpushed_lane_evidence=_lane(), root_mutations_complete=True,
        merge_to_zero_complete=True, test_classified=True, tests_green=True,
        test_receipt=_test_receipt(),
        expected_test_commands=["python tools/control_plane_regression.py"],
        diff_digest="c" * 64,
    )

    current = build_gate_evidence(**common)
    assert current["next_action"] == "REMOTE_CONNECTION_AUTHORIZED"

    compatible = build_gate_evidence(**common, worker_census_evidence=_worker_census())
    assert compatible["next_action"] == "REMOTE_CONNECTION_AUTHORIZED"
    assert "WORKER_CENSUS_NO_MERGEABLE_GREEN" in compatible["completed"]

    mergeable = build_gate_evidence(
        **common, worker_census_evidence=_worker_census(mergeable=1)
    )
    assert mergeable["next_action"] == "MERGE_TO_FRESH_LATEST_ZERO"

    blocked = build_gate_evidence(
        **common, worker_census_evidence=_worker_census(blocking=1)
    )
    assert blocked["next_action"] == "RESOLVE_WORKER_CENSUS_BLOCKERS"

    bad = _worker_census()
    bad["schema"] = "BROKEN"
    with pytest.raises(ValueError, match="worker census evidence schema mismatch"):
        build_gate_evidence(**common, worker_census_evidence=bad)


def test_git_content_write_is_forbidden_before_unlock():
    from tools.root_local_first_gate import (
        assert_git_content_write_allowed,
        build_gate_evidence,
        build_remote_connection_authority,
    )
    evidence = build_gate_evidence(execution_mode="INTERACTIVE")
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_git_content_write_allowed(evidence, action="READ")

    authority = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    authorized = dict(evidence, remote_connection_authority=authority)
    assert_git_content_write_allowed(authorized, action="READ")
    with pytest.raises(ValueError, match="GIT_WRITE_LOCKED"):
        assert_git_content_write_allowed(authorized, action="COMMIT")


def test_target_drift_forces_resync_and_retest_before_git_write():
    from tools.root_local_first_gate import (
        build_gate_evidence,
        build_remote_connection_authority,
        validate_source_current,
    )
    source = validate_source_current(workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40}, live_source_sha="a" * 40, live_tree_sha="b" * 40)
    authority = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True,
        tests_green=True, test_receipt=_test_receipt(),
        expected_test_commands=["python tools/control_plane_regression.py"], diff_digest="d" * 64,
        remote_connection_authority=authority,
        path_reservation_evidence=_reservation(), target_drift=True,
    )
    assert evidence["git_write_unlocked"] is False
    assert evidence["next_action"] == "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE"


def test_legacy_manifest_and_scoped_recovery_cannot_mint_source_current():
    from tools.root_local_first_gate import validate_source_current
    with pytest.raises(ValueError, match="legacy manifest/scoped recovery is retired"):
        validate_source_current(
            manifest=_manifest("a" * 40, "b" * 40),
            live_source_sha="a" * 40, live_tree_sha="b" * 40,
        )
    with pytest.raises(ValueError, match="legacy manifest/scoped recovery is retired"):
        validate_source_current(
            manifest=_manifest("1" * 40, "2" * 40),
            live_source_sha="a" * 40, live_tree_sha="b" * 40,
            touched_path_proofs=[{
                "path": "AGENTS.md", "live_blob_sha": "3" * 40, "workspace_blob_sha": "3" * 40
            }],
        )


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
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
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
    assert (
        agents.index("ENTRY_ROUTER_FIRST_HARD_GATE_V1")
        < agents.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V2")
        < agents.index("## -0.5. ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1")
        < agents.index("# 0. 啟動硬閘門")
    )
    root_gate = json.loads((ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8"))
    assert root_gate["next_gate"]["schema"] == "WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1"
    assert "ROOT_SHARED_UNPUSHED_GATE_READ" in root_gate["required_sequence"]
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(r for r in registry["routes"] if r["id"] == "root-local-first")
    assert route["file_globs"] == ["**"]
    assert "root-local-first" in route["required_skills"]
    authority = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    assert "whd_contract: canonical-authority-map" in authority
    assert "contract=root-shared-unpushed-entry-gate role=CURRENT path=.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json" in authority
    assert "contract=root-local-first-entry-gate role=HISTORICAL" in authority
    assert "contract=root-shared-unpushed-workflow role=CURRENT path=.agents/skills/engineering/root-local-first/SKILL.md" in authority
    assert "contract=root-shared-unpushed-workflow role=CURRENT path=.agents/skills/engineering/root-local-first/SKILL.md" in authority


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
    from tools.root_local_first_gate import (
        build_gate_evidence,
        build_git_unlock_receipt,
        build_remote_connection_authority,
        validate_git_unlock_receipt,
        validate_source_current,
    )
    source = validate_source_current(workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40}, live_source_sha="a" * 40, live_tree_sha="b" * 40)
    authority = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True, tests_green=True,
        remote_connection_authority=authority, path_reservation_evidence=_reservation(),
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
    source = validate_source_current(workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40}, live_source_sha="a" * 40, live_tree_sha="b" * 40)
    with pytest.raises(ValueError, match="WHD_TEST_EXECUTION_RECEIPT_V1"):
        build_gate_evidence(
            execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
            root_mutations_complete=True, merge_to_zero_complete=True, test_classified=True, tests_green=True,
            path_reservation_evidence=_reservation(), diff_digest="f" * 64,
        )

def test_root_local_contract_points_to_new_git_worktree_root():
    payload = _contract()
    assert payload["canonical_root"]["drive_folder_id"] == "1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN"
    assert payload["canonical_root"]["interactive_work_prefix"] == "/Google Drive/WHD/.unpushed"
    assert payload["canonical_source"]["library_path"].endswith("/.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json")
    assert payload["shared_unpushed_integration"]["body_lane"].endswith("/.unpushed/body/0")
    assert payload["shared_unpushed_integration"]["docs_lane"].endswith("/.unpushed/docs/0")


def test_interactive_orchestration_fast_path_is_machine_owned():
    payload = _contract()
    gate = payload["orchestration_fast_path"]
    assert gate["schema"] == "WHD_INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1"
    assert gate["default"] == "SESSION_INTERNAL_ORCHESTRATION"
    assert "PER_TRANSACTION_MANUAL_ORCHESTRATION" in gate["outer_forbidden"]
    assert "MANUAL_LEASE_RENEW_BEFORE_EXPIRY" in gate["outer_forbidden"]
    assert "START_QA_THEN_ACCEPT_QA_WHEN_CONSUME_QA_IS_ELIGIBLE" in gate["outer_forbidden"]
    assert gate["stale_plan_policy"] == "STALE_PLAN_MUST_DIE"
    assert gate["single_writer_policy"] == "SHARED_0_LINEAGE_ROOT__SINGLE_WRITER_ONLY_AT_DELIVERY"


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
    assert gate["canonical_surface"] == "/Google Drive/WHD/.unpushed"
    assert gate["interactive_first_substantive_action"] == "ROOT_MUTATE"
    assert gate["required_contiguous_outer_sequence"] == [
        "ROOT_MUTATE", "MERGE_TO_0_OR_CONFLICT_CHECKPOINT",
        "POST_MERGE_0_TEST_CLASSIFIED", "POST_MERGE_0_TESTS_GREEN"
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
    assert "POST_MERGE_ZERO_TESTS_GREEN" in text
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

def test_root_gate_conflict_checkpoint_blocks_before_post_merge_tests():
    from tools.root_local_first_gate import build_gate_evidence, validate_source_current
    from tools.shared_unpushed_integration import build_conflict_checkpoint
    source = validate_source_current(
        workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40},
        live_source_sha="a" * 40, live_tree_sha="b" * 40,
    )
    cp = build_conflict_checkpoint(
        lane="docs", path="AGENTS.md", base_generation=3, latest_generation=4,
        base_hash="base", latest_hash="latest", worker_hash="worker",
        conflict_hunks=["startup gate line changed by both workers"], worker="work1", issue="#996",
    )
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE", source_evidence=source, unpushed_lane_evidence=_lane(),
        root_mutations_complete=True, conflict_checkpoint=cp,
    )
    assert evidence["blocked_state"] == "BLOCKED_USER_DECISION"
    assert evidence["next_action"] == "USER_CONFLICT_DECISION"
    assert evidence["git_write_unlocked"] is False


def test_remote_connection_authority_covers_all_github_network_surfaces_and_does_not_propagate():
    from tools.root_local_first_gate import (
        assert_remote_connection_allowed,
        build_remote_connection_authority,
        validate_contract,
    )

    payload = validate_contract(_contract())
    gate = payload["remote_connection_hard_gate"]
    assert gate["default"] == "DENY"
    assert gate["covers_all_network_surfaces"] is True
    assert gate["authority_non_propagating"] is True
    assert gate["skill_invocation_is_not_authority"] is True
    assert {
        "repo_metadata", "code_search", "contents", "branches", "commits",
        "issues", "pull_requests", "actions_workflows", "actions_runs",
        "artifacts", "connector_api", "git_network_transport",
    } <= set(gate["covered_github_surfaces"])

    for action in ("REPO_METADATA_READ", "CODE_SEARCH", "ISSUE_READ", "PR_READ", "WORKFLOW_READ", "REMOTE_QA"):
        with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
            assert_remote_connection_allowed(None, target="GITHUB", action=action)

    issue_only = build_remote_connection_authority(
        kind="OPEN_ISSUE_ONLY", target="GITHUB", user_explicit=True
    )
    assert_remote_connection_allowed(issue_only, target="GITHUB", action="CREATE_ISSUE")
    assert_remote_connection_allowed(issue_only, target="GITHUB", action="ISSUE_READBACK")
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_remote_connection_allowed(issue_only, target="GITHUB", action="ISSUE_READ")

    push = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    for action in ("WORKFLOW_READ", "REMOTE_QA", "ISSUE_CLOSE", "PR_READ", "CODE_SEARCH"):
        assert_remote_connection_allowed(push, target="GITHUB", action=action)


def test_high_risk_skills_are_wired_to_remote_authority_gate_and_no_readonly_bypass_regrows():
    required = (
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        ".agents/skills/misc/git-remote-sync-fallback/SKILL.md",
        ".agents/skills/engineering/code-review/SKILL.md",
        ".agents/skills/engineering/triage/SKILL.md",
        ".agents/skills/engineering/wayfinder/SKILL.md",
        ".agents/skills/productivity/找技能/SKILL.md",
        ".agents/skills/productivity/MCP工具操作/SKILL.md",
        ".agents/skills/engineering/工作槽/SKILL.md",
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
        ".agents/skills/engineering/issue-closure-gate/SKILL.md",
        ".agents/skills/engineering/long-log-context-safe-execution/SKILL.md",
    )
    offenders = []
    for rel in required:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "assert_remote_connection_allowed" not in text:
            offenders.append((rel, "missing machine gate wiring"))
        if "WHD_REMOTE_CONNECTION_AUTHORITY_V1" not in text:
            offenders.append((rel, "missing authority schema"))
    assert offenders == []

    fallback = (ROOT / ".agents/skills/misc/git-remote-sync-fallback/SKILL.md").read_text(encoding="utf-8")
    assert "before `GIT_WRITE_UNLOCKED`, GitHub/Contents/Connector is read-only" not in fallback
    assert "READ / FETCH / COMPARE`" in fallback
    assert "fully denied" in fallback

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    root_skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(encoding="utf-8")
    for text in (agents, root_skill):
        assert "Skill 自動觸發" in text
        assert "REMOTE_CONNECTION_DENIED" in text

