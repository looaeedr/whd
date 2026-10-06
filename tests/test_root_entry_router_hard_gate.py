import json
from pathlib import Path

import pytest

from tools.root_local_first_gate import (
    ENTRY_ROUTER_READY,
    assert_entry_router_action_allowed,
    assert_git_content_write_allowed,
    assert_remote_connection_allowed,
    build_entry_router_evidence,
    build_gate_evidence,
    build_remote_connection_authority,
    build_root_path_resolution_evidence,
    validate_contract,
    validate_root_path_resolution_evidence,
 )

from tools.shared_unpushed_integration import (
    assert_delivery_hashes_match_lock,
    assert_premerge_latest_file_recheck,
    assert_push_scope_matches_lock,
    build_delivery_fileset_lock,
    historical_finalize_delivered_paths,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / ".agents" / "contracts" / "WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json"


def _ready():
    return build_entry_router_evidence(
        workspace_root="/workspace/whd",
        fresh_reads=(
            ".agents/contracts/WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ),
    )


def test_entry_router_requires_exact_fresh_read_order():
    with pytest.raises(ValueError, match="ENTRY_ROUTER_FIRST_REQUIRED"):
        build_entry_router_evidence(
            workspace_root="/workspace/whd",
            fresh_reads=(".agents/skills/engineering/root-local-first/SKILL.md",),
        )
    evidence = _ready()
    assert evidence["state"] == ENTRY_ROUTER_READY


def test_general_discovery_is_forbidden_before_entry_ready():
    for action in (
        "GENERAL_FILE_DISCOVERY",
        "GENERIC_DRIVE_SEARCH",
        "REMOTE_DESKTOP",
        "LOCAL_MACHINE_SEARCH",
        "GITHUB_CONTENT_DISCOVERY",
        "GITHUB_MUTATION",
        "BRANCH_CREATE",
        "CLAIM",
        "FLOW_V2_DISCOVERY",
    ):
        with pytest.raises(ValueError, match="ENTRY_ROUTER_FIRST_HARD_GATE"):
            assert_entry_router_action_allowed(None, action=action)


def test_ready_entry_router_allows_substantive_action():
    assert_entry_router_action_allowed(_ready(), action="ROOT_MUTATE")


def test_repository_content_gate_requires_entry_router_evidence():
    with pytest.raises(ValueError, match="entry router evidence"):
        build_gate_evidence(
            execution_mode="INTERACTIVE",
            repository_content_implementation=True,
        )


def test_contract_wires_entry_router_hard_gate():
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validated = validate_contract(payload)
    gate = validated["entry_router_hard_gate"]
    assert gate["schema"] == "WHD_ENTRY_ROUTER_FIRST_HARD_GATE_V1"
    assert gate["fresh_each_invocation"] is True
    assert gate["chat_memory_is_not_evidence"] is True

def test_agents_routes_to_entry_before_general_discovery():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ENTRY_ROUTER_FIRST_HARD_GATE_V1" in text
    assert "FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY" in text
    assert "Remote Desktop/local-machine search" in text


def test_pitfall_records_entry_discovery_regression():
    text = (ROOT / "個人AI檔案庫" / "踩坑庫" / "root_local_first_entry_gate_pitfall.md").read_text(encoding="utf-8")
    assert "入口 contract 已存在，但 agent 先做 generic discovery" in text
    assert "ENTRY_ROUTER_READY" in text




def test_root_path_resolution_requires_workspace_relative_identity():
    evidence = build_root_path_resolution_evidence(
        workspace_root="/workspace/whd", repo_relative_path="AGENTS.md",
        resolved_absolute_path="/workspace/whd/AGENTS.md",
    )
    assert validate_root_path_resolution_evidence(evidence)["resolution_method"] == "WORKSPACE_REPO_RELATIVE_PATH"
    with pytest.raises(ValueError, match="WORKSPACE_PATH_UNRESOLVED_FAIL_CLOSED"):
        build_root_path_resolution_evidence(workspace_root="/workspace/whd", repo_relative_path="AGENTS.md",
                                            resolved_absolute_path="/tmp/AGENTS.md")


def test_remote_connection_is_denied_without_explicit_authority():
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_remote_connection_allowed(None, target="GITHUB", action="CREATE_PR")
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_remote_connection_allowed(None, target="REMOTE_LOCAL", action="READ")


def test_open_issue_authority_cannot_be_reused_for_repository_content():
    authority = build_remote_connection_authority(
        kind="OPEN_ISSUE_ONLY",
        target="GITHUB",
        user_explicit=True,
    )
    assert_remote_connection_allowed(authority, target="GITHUB", action="CREATE_ISSUE")
    assert_remote_connection_allowed(authority, target="GITHUB", action="ISSUE_READBACK")
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_remote_connection_allowed(authority, target="GITHUB", action="READ")


def test_push_docs_authority_is_lane_scoped_and_unlocks_git_reads_only_for_delivery():
    authority = build_remote_connection_authority(
        kind="PUSH_DOCS",
        target="GITHUB",
        lane="docs",
        user_explicit=True,
    )
    for action in ("READ", "FETCH", "COMPARE", "CREATE_BRANCH", "COMMIT", "PUSH", "CREATE_PR", "MERGE", "READBACK"):
        assert_remote_connection_allowed(authority, target="GITHUB", action=action)
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        assert_remote_connection_allowed(authority, target="REMOTE_LOCAL", action="READ")
    with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
        build_remote_connection_authority(
            kind="PUSH_DOCS",
            target="GITHUB",
            lane="body",
            user_explicit=True,
        )


def test_git_read_no_longer_bypasses_remote_authority():
    assert_git_content_write_allowed(
        {"applicable": True, "git_write_unlocked": False, "next_action": "WORKSPACE_MUTATIONS_COMPLETE"},
        action="READ",
    )

    authority = build_remote_connection_authority(
        kind="PUSH_DOCS", target="GITHUB", lane="docs", user_explicit=True
    )
    assert_git_content_write_allowed(
        {
            "applicable": True,
            "git_write_unlocked": False,
            "next_action": "DELIVERY_PATHS_RESERVED",
            "remote_connection_authority": authority,
        },
        action="READ",
    )
    with pytest.raises(ValueError, match="GIT_WRITE_LOCKED"):
        assert_git_content_write_allowed(
            {
                "applicable": True,
                "git_write_unlocked": False,
                "next_action": "DELIVERY_PATHS_RESERVED",
                "remote_connection_authority": authority,
            },
            action="COMMIT",
        )


def test_contract_denies_remote_by_default_and_locks_delivery_fileset():
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validated = validate_contract(payload)
    assert set(validated["git_before_unlock"]) == {"READ", "FETCH", "COMPARE", "BRANCH_READ", "REPO_METADATA_READ"}
    assert set(validated["git_after_remote_authority_before_unlock"]) == {"READ", "FETCH", "COMPARE", "BRANCH_READ", "REPO_METADATA_READ"}
    assert validated["root_path_resolution_hard_gate"]["remote_fallback_forbidden"] is False
    assert validated["remote_connection_hard_gate"]["default"] == "ALLOW_WORKSPACE_BASELINE_READ_ONLY"
    assert validated["remote_connection_hard_gate"]["pre_delivery_git_read_allowed_without_authority"] is True
    assert validated["delivery_fileset_lock"]["push_scope"] == "EXACT_LOCK_EQUALITY"
    assert validated["delivery_fileset_lock"]["merge_precheck"] == "FRESH_TARGET_HEAD_AND_LOCKED_BLOB_RECHECK"
    assert validated["post_delivery_cleanup"]["clear_policy"] == "ONLY_LOCKED_PATHS_WITH_EXACT_READBACK_HASH"
    assert validated["post_delivery_cleanup"]["repository_file_delete_forbidden"] is True


def test_current_docs_only_route_workspace_and_trusted_delivery():
    agents = (ROOT / "AGENTS.md").read_text()
    skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text()
    assert "WORKSPACE_DEFAULT" in agents and "WORKSPACE_DEFAULT" in skill
    assert "GitHub network READ / FETCH / COMPARE 也禁止" not in agents
    assert "Drive/shared-zero 不再有 CURRENT delivery route" in agents


def _delivery_lock():
    return build_delivery_fileset_lock(
        lane="docs",
        generation=9,
        manifest_digest="a" * 64,
        source_zero_identity="docs/0@generation-9",
        invocation_identity="chatgpt.work0.invocation-test",
        write_hashes={
            "AGENTS.md": "1" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "2" * 64,
        },
        target_base_hashes={
            "AGENTS.md": "3" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "4" * 64,
        },
    )


def test_delivery_fileset_lock_requires_exact_paths_and_hashes():
    lock = _delivery_lock()
    assert_push_scope_matches_lock(
        lock=lock,
        changed_paths=["AGENTS.md", ".agents/skills/engineering/推推/SKILL.md"],
    )
    assert_delivery_hashes_match_lock(
        lock=lock,
        delivery_hashes={
            "AGENTS.md": "1" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "2" * 64,
        },
    )
    with pytest.raises(ValueError, match="PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_LOCK"):
        assert_push_scope_matches_lock(lock=lock, changed_paths=["AGENTS.md"])
    with pytest.raises(ValueError, match="DELIVERY_BLOB_HASH_MUST_EQUAL_FROZEN_LOCK"):
        assert_delivery_hashes_match_lock(
            lock=lock,
            delivery_hashes={
                "AGENTS.md": "9" * 64,
                ".agents/skills/engineering/推推/SKILL.md": "2" * 64,
            },
        )


def test_premerge_recheck_rejects_target_change_on_locked_path():
    lock = _delivery_lock()
    delivery = {
        "AGENTS.md": "1" * 64,
        ".agents/skills/engineering/推推/SKILL.md": "2" * 64,
    }
    assert_premerge_latest_file_recheck(
        lock=lock,
        fresh_target_hashes={
            "AGENTS.md": "3" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "4" * 64,
        },
        delivery_hashes=delivery,
        changed_paths=delivery,
    )
    with pytest.raises(ValueError, match="TARGET_TOUCHED_LOCKED_PATH_REQUIRES_WORKSPACE_RECONCILE_RETEST_REFREEZE"):
        assert_premerge_latest_file_recheck(
            lock=lock,
            fresh_target_hashes={
                "AGENTS.md": "5" * 64,
                ".agents/skills/engineering/推推/SKILL.md": "4" * 64,
            },
            delivery_hashes=delivery,
            changed_paths=delivery,
        )


def test_finalize_clears_only_exact_readback_delivered_paths():
    lock = _delivery_lock()
    receipt = historical_finalize_delivered_paths(
        lock=lock,
        merge_readback_verified=True,
        accepted_commit="accepted-head",
        readback_hashes={
            "AGENTS.md": "1" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "2" * 64,
        },
        current_zero_hashes={
            "AGENTS.md": "1" * 64,
            ".agents/skills/engineering/推推/SKILL.md": "9" * 64,
        },
        later_or_foreign_paths=(),
        cleared_at="2026-10-03T10:00:00+08:00",
    )
    assert receipt["cleared_paths"] == ["AGENTS.md"]
    assert receipt["preserved_paths"] == [".agents/skills/engineering/推推/SKILL.md"]
    assert receipt["repository_files_deleted"] is False
    assert receipt["future_modification_rule"] == "HISTORICAL_ONLY_NO_CURRENT_ROUTE"


def test_pitfall_records_workspace_only_entry_correction():
    text = (ROOT / "個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md").read_text()
    assert "ROOT_PARENT_CHAIN_AND_LATEST_ZERO_PITFALL_V1" in text
    assert "歷史 Drive/shared-zero authority 被 generic search 重播" in text
    assert "executor-local repo workspace" in text
    assert "fresh Git production X" in text
    assert "SHARED_ZERO_FALLBACK" not in text
    assert "回 root/latest 0 reconcile" not in text

