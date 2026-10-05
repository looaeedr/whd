import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# Issue 1297: Drive/shared-zero cannot regain CURRENT routing authority.
CONTRACT = ROOT / ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json"
SKILL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_workspace_entry_bootstrap_does_not_require_drive_or_unpushed():
    from tools.root_local_first_gate import (
        build_entry_router_evidence,
        select_repository_content_route,
        validate_contract,
    )

    payload = validate_contract(_contract())
    source = payload["canonical_source"]
    router = payload["entry_router_hard_gate"]
    default_flow = payload["default_repository_content_flow"]

    assert source["provider"] == "executor_local_repo_workspace"
    assert source["repo_relative_path"] == ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json"
    assert source["resolution_method"] == "WORKSPACE_REPO_RELATIVE_PATH"
    assert source["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert source["drive_required"] is False
    assert source["missing_drive_action"] == "CONTINUE_WORKSPACE_DEFAULT_IF_EXECUTOR_WORKSPACE_CAPABLE"
    assert source["missing_shared_zero_action"] == "IGNORE_RETIRED_SHARED_ZERO_AND_CONTINUE_WORKSPACE_DEFAULT"

    assert router["bootstrap_source"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert router["bootstrap_paths_are_repo_relative"] is True
    assert router["drive_lookup_before_ready"] == "FORBIDDEN"
    assert router["missing_drive_is_blocker"] is False
    assert router["missing_shared_zero_is_blocker"] is False
    assert router["workspace_root_user_renomination_required"] is False

    assert default_flow["startup_requires_drive"] is False
    assert default_flow["startup_requires_shared_zero"] is False
    assert default_flow["startup_requires_workspace_canonical_sync"] is False

    evidence = build_entry_router_evidence(
        fresh_reads=[
            ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ],
        workspace_root="/workspace/whd",
    )
    assert evidence["state"] == "ENTRY_ROUTER_READY"
    assert evidence["workspace_root"] == "/workspace/whd"

    for drift in (False, True):
        route = select_repository_content_route(
            shared_zero_drift_present=drift,
            workspace_root="/workspace/whd",
        )
        assert route["route"] == "WORKSPACE_DEFAULT"
        assert route["workspace_root"] == "/workspace/whd"
        assert route["shared_zero_required"] is False
        assert route["workspace_canonical_sync_required"] is False
        assert route["retired_shared_zero_drift_observed"] is drift

    skill = SKILL.read_text(encoding="utf-8")
    assert "Google Drive mirror、舊 Drive Skill、`.unpushed`、shared-zero 或任何 Drive 可見性都不得參與 startup routing" in skill
    assert "Drive mount 不可見永遠不是 repository-content blocker" in skill


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("canonical_source", "provider"), "google_drive", "executor-local repo workspace"),
        (("canonical_source", "drive_required"), True, "must not require Drive"),
        (("entry_router_hard_gate", "missing_drive_is_blocker"), True, "must not block workspace-default entry"),
        (("entry_router_hard_gate", "missing_shared_zero_is_blocker"), True, "must not block workspace-default entry"),
        (("entry_router_hard_gate", "workspace_root_user_renomination_required"), True, "must not require user re-nomination"),
    ],
)
def test_validate_contract_rejects_drive_first_or_root_renomination_regrowth(path, value, message):
    from tools.root_local_first_gate import validate_contract

    payload = copy.deepcopy(_contract())
    cursor = payload
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value

    with pytest.raises(ValueError, match=message):
        validate_contract(payload)


def test_current_contract_retires_drive_and_shared_zero_routing():
    from tools.root_local_first_gate import validate_contract

    payload = validate_contract(_contract())
    root = payload["canonical_root"]
    source = payload["canonical_source"]
    shared = payload["shared_unpushed_integration"]
    flow = payload["default_repository_content_flow"]
    direct = payload["direct_root_mutation_test_gate"]

    assert root["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert root["drive_mirror_root"] == "/Google Drive/WHD/WHD_MIRROR/CURRENT"
    assert "canonical_drive_overlay" not in root
    assert source["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert shared["mode"] == "SUPERSEDED_DATA_ONLY"
    assert shared["activation"] == "NEVER_CURRENT"
    assert shared["routing_forbidden"] is True
    assert shared["authority"] is False
    assert flow["shared_zero_fallback_trigger"] == "RETIRED"
    assert flow["shared_zero_fallback_machine"] is None
    assert flow["drive_routing_forbidden"] is True
    assert flow["missing_workspace_action"] == "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME"
    assert direct["status"] == "SUPERSEDED"
    assert direct["applies_when"] == "NEVER_CURRENT"


def test_legacy_shared_zero_drift_cannot_block_repository_content_work():
    from tools.root_local_first_gate import build_entry_router_evidence, build_gate_evidence

    entry = build_entry_router_evidence(
        fresh_reads=[
            ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
            ".agents/skills/engineering/root-local-first/SKILL.md",
        ],
        workspace_root="/workspace/whd",
    )
    evidence = build_gate_evidence(
        execution_mode="INTERACTIVE",
        repository_content_implementation=True,
        entry_router_evidence=entry,
        shared_zero_drift_present=True,
    )
    assert evidence["route"] == "WORKSPACE_DEFAULT"
    assert evidence["next_action"] == "WORKSPACE_SOURCE_CURRENT"
    assert evidence["shared_zero_required"] is False
    assert evidence["workspace_canonical_sync_required"] is False
