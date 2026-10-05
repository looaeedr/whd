import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
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
    assert source["drive_role"] == "OPTIONAL_MIRROR_NOT_STARTUP_AUTHORITY"
    assert source["drive_required"] is False
    assert source["missing_drive_action"] == "CONTINUE_WORKSPACE_DEFAULT_IF_EXECUTOR_WORKSPACE_CAPABLE"
    assert source["missing_shared_zero_action"] == "CONTINUE_WORKSPACE_DEFAULT"

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

    route = select_repository_content_route(
        shared_zero_drift_present=False,
        workspace_root="/workspace/whd",
    )
    assert route["route"] == "WORKSPACE_DEFAULT"
    assert route["workspace_root"] == "/workspace/whd"
    assert route["shared_zero_required"] is False
    assert route["workspace_canonical_sync_required"] is False

    skill = SKILL.read_text(encoding="utf-8")
    assert "不得先去 Google Drive 尋找同名契約" in skill
    assert "workspace 內沒有 `.unpushed` 都不是要求使用者重新指定施工 root 的理由" in skill


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
