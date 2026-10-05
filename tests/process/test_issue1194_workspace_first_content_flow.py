from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
X = "cleanup/2d-3d-sync"


def _entry(workspace: str):
    from tools.root_local_first_gate import build_entry_router_evidence

    return build_entry_router_evidence(
        workspace_root=workspace,
        fresh_reads=[
            ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ],
    )


def _source():
    from tools.root_local_first_gate import validate_source_current

    return validate_source_current(
        workspace_git={"head_sha": "a" * 40, "tree_sha": "b" * 40},
        live_source_sha="a" * 40,
        live_tree_sha="b" * 40,
    )


def _reservation():
    return {
        "schema": "WHD_PATH_RESERVATION_EVIDENCE_V1",
        "phase": "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN",
        "issue": 1194,
        "generation": 1,
        "target_branch": X,
        "base_sha": "a" * 40,
        "write_paths": ["AGENTS.md"],
        "delete_paths": [],
        "reservation_state": "ACTIVE",
        "record_fingerprint": "f" * 64,
    }


def test_default_route_is_executor_workspace_without_drive_or_sync():
    from tools.root_local_first_gate import select_repository_content_route

    route = select_repository_content_route(
        shared_zero_drift_present=False,
        workspace_root="/mnt/data/chatgpt-whd",
    )
    assert route["route"] == "WORKSPACE_DEFAULT"
    assert route["workspace_root"] == "/mnt/data/chatgpt-whd"
    assert route["production_branch"] == X
    assert route["workspace_canonical_sync_required"] is False
    assert route["shared_zero_required"] is False


def test_shared_zero_drift_is_historical_and_never_changes_current_route():
    from tools.root_local_first_gate import select_repository_content_route

    route = select_repository_content_route(
        shared_zero_drift_present=True,
        workspace_root="/workspace/whd",
    )
    assert route["route"] == "WORKSPACE_DEFAULT"
    assert route["workspace_canonical_sync_required"] is False
    assert route["shared_zero_required"] is False
    assert route["retired_shared_zero_drift_observed"] is True


def test_two_executors_may_use_different_workspace_paths_with_same_x_baseline():
    from tools.work_root_gate import READ_MODE_WORKSPACE, build_work_root_gate_evidence

    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8")
    )
    entries = [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"]

    a = build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=entries,
        workspace_root="/workspace/whd",
        production_head_sha="a" * 40,
    )
    b = build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=entries,
        workspace_root="/mnt/data/whd",
        production_head_sha="a" * 40,
    )
    assert a["workspace_root"] != b["workspace_root"]
    assert a["production_branch"] == b["production_branch"] == X
    assert a["production_head_sha"] == b["production_head_sha"] == "a" * 40


def test_workspace_default_can_reach_exact_tested_delivery_without_shared_zero():
    from tools.root_local_first_gate import (
        assert_git_content_write_allowed,
        build_gate_evidence,
        build_remote_connection_authority,
    )

    authority = build_remote_connection_authority(
        kind="WORKSPACE_DELIVERY",
        target="GITHUB",
        user_explicit=True,
    )
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE",
        repository_content_implementation=True,
        entry_router_evidence=_entry("/mnt/data/whd"),
        source_evidence=_source(),
        workspace_mutations_complete=True,
        workspace_tests_green=True,
        diff_digest="d" * 64,
        workspace_delivery_authority=authority,
        path_reservation_evidence=_reservation(),
    )
    assert evidence["route"] == "WORKSPACE_DEFAULT"
    assert evidence["shared_zero_required"] is False
    assert evidence["workspace_canonical_sync_required"] is False
    assert evidence["git_write_unlocked"] is True
    assert evidence["next_action"] == "EXACT_TESTED_DIFF_ONLY"
    assert_git_content_write_allowed(evidence, action="COMMIT")


def test_baseline_git_reads_are_allowed_but_other_remote_actions_still_need_authority():
    from tools.root_local_first_gate import assert_remote_connection_allowed

    for action in ("READ", "FETCH", "COMPARE", "BRANCH_READ", "REPO_METADATA_READ"):
        assert_remote_connection_allowed(None, target="GITHUB", action=action)
    for action in ("CODE_SEARCH", "ISSUE_READ", "PR_READ", "WORKFLOW_READ", "MERGE"):
        with pytest.raises(ValueError, match="REMOTE_CONNECTION_DENIED"):
            assert_remote_connection_allowed(None, target="GITHUB", action=action)


def test_current_contracts_do_not_make_codex_path_or_drive_sync_global_startup():
    work = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text(encoding="utf-8")
    )
    entry = json.loads(
        (ROOT / ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    shared = json.loads(
        (ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(
            encoding="utf-8"
        )
    )

    assert work["default_work_root"]["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "library_path" not in work["default_work_root"]
    flow = entry["default_repository_content_flow"]
    assert flow["workspace_root_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "workspace_root" not in flow
    assert flow["startup_requires_drive"] is False
    assert flow["startup_requires_shared_zero"] is False
    assert flow["startup_requires_workspace_canonical_sync"] is False
    assert shared["mode"] == "SUPERSEDED_DATA_ONLY"
    assert shared["default_route"] is False
    mirror = shared["delivery_transport"]["workspace_staged_fallback"]["codex_cloud_mount_bridge"][
        "workspace_mirror_policy"
    ]
    assert mirror["workspace_root_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "workspace_root" not in mirror
    assert mirror["ordinary_startup_required"] is False
    assert mirror["activation"] == "RETIRED_DATA_ONLY"


def test_push_skill_explicitly_says_normal_workspace_flow_does_not_use_push_skill():
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    assert "普通 workspace-first 施工不經 `/推推`" in push
    assert "CONDITIONAL_SHARED_ZERO_RECONCILE_V1" in push
    assert "WORKSPACE_CANONICAL_SYNC_IS_CONDITIONAL_FALLBACK_NOT_DEFAULT_STARTUP" in push
