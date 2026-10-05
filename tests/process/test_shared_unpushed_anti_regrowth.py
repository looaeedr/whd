from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
# Issue 1308: CURRENT routing must not regain Drive/shared-zero authority.


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str):
    return json.loads(_read(path))


def test_shared_zero_contract_is_superseded_data_only():
    contract = _json(".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json")
    assert contract["mode"] == "SUPERSEDED_DATA_ONLY"
    assert contract["activation"] == "NEVER_CURRENT"
    assert contract["routing_forbidden"] is True
    assert contract["authority"] is False
    assert contract["default_route"] is False


def test_work_root_contract_keeps_drive_compatibility_non_authoritative():
    contract = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert contract["default_work_root"]["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "unpushed" not in contract
    assert "canonical_drive_overlay" not in contract
    mirror = contract["drive_mirror"]
    assert mirror["library_path"] == "/Google Drive/WHD/WHD_MIRROR/CURRENT"
    assert mirror["role"] == "MIRROR_BACKUP_ONLY"
    assert mirror["authority"] is False


def test_current_router_never_selects_drive_or_shared_zero():
    from tools.root_local_first_gate import select_repository_content_route

    for drift in (False, True):
        route = select_repository_content_route(
            shared_zero_drift_present=drift,
            workspace_root="/workspace/whd",
        )
        assert route["route"] == "WORKSPACE_DEFAULT"
        assert route["shared_zero_required"] is False
        assert route["workspace_canonical_sync_required"] is False
        assert route["retired_shared_zero_drift_observed"] is drift


def test_push_skill_is_workspace_delivery_alias_not_drive_authority():
    push = _read(".agents/skills/engineering/推推/SKILL.md")
    assert "顯式 delivery alias" in push
    assert "Git production X `cleanup/2d-3d-sync` 是唯一 CURRENT" in push
    assert "Google Drive 只存 data / mirror / backup" in push
    assert "因 Drive mount 不可見而回 blocker" in push
    assert "不得參與 CURRENT routing" in push
    assert "CREATE_DELIVERY_BRANCH" in push
    assert "MERGE_READBACK_VERIFIED" in push


def test_unpushed_workspace_is_never_git_delivery_content():
    ignore = _read(".gitignore").splitlines()
    assert ".unpushed/" in ignore
    push = _read(".agents/skills/engineering/推推/SKILL.md")
    assert "從 `.unpushed/docs/0` / `.unpushed/body/0` 取得 authoring authority" in push
    assert "以下全部禁止作 CURRENT 行為" in push


def test_workspace_canonical_sync_machine_is_retired_from_current_routing():
    contract = _json(".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json")
    assert contract["status"] == "HISTORICAL"
    assert contract["mode"] == "SUPERSEDED_DATA_ONLY"
    assert contract["activation"] == "NEVER_CURRENT"
    assert contract["current_routing_forbidden"] is True
    assert contract["authority"] is False
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    assert "legacy shared-zero helpers may remain only for historical data/recovery parsing" in root


def test_drive_unavailable_never_becomes_repository_content_blocker():
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    scheduler = _read(".agents/skills/engineering/排程模擬/SKILL.md")
    agents = _read("AGENTS.md")
    assert "Drive mount 不可見永遠不是 repository-content blocker" in root
    assert "Google Drive mount 不可見本身不是 blocker" in flow
    assert "Drive mount、mirror、舊 shared-zero drift 都不是 scheduler content-handoff 的判定條件" in scheduler
    assert "Drive mount、Drive mirror、舊 pointer、`.unpushed` 缺失都不是 blocker" in agents


def test_missing_workspace_hands_off_to_workspace_capable_runtime():
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    scheduler = _read(".agents/skills/engineering/排程模擬/SKILL.md")
    assert "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME" in root
    assert "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX" in flow
    assert "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX" in scheduler


def test_delivery_reservation_remains_delivery_only():
    payload = _json(".agents/contracts/WHD_PATH_RESERVATION_V1.json")
    assert payload["phase"] == "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN"
    assert payload["reservation_required_before"] == "CREATE_DELIVERY_BRANCH_OR_GIT_WRITE"
    assert payload["root_authoring_policy"] == "NO_PREWRITE_RESERVATION__RESERVE_ONLY_FOR_GIT_DELIVERY"


def test_terminal_authority_is_git_merge_and_flow_v2_finalize():
    push = _read(".agents/skills/engineering/推推/SKILL.md")
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    assert "MERGE_READBACK_VERIFIED → FINALIZE → DONE / RELEASED" in push
    assert "Flow v2 `FINALIZE → DONE`" in root
    assert "缺 mirror receipt 不得保持 Issue OPEN" in push


def test_current_docs_do_not_restore_legacy_drive_construction_root():
    joined = "\n".join(
        _read(p)
        for p in (
            "AGENTS.md",
            ".agents/skills/engineering/root-local-first/SKILL.md",
            ".agents/skills/engineering/flow-v2-execution/SKILL.md",
            ".agents/skills/engineering/排程模擬/SKILL.md",
            ".agents/skills/engineering/推推/SKILL.md",
        )
    )
    forbidden = (
        "唯一預設 root：`/Google Drive/WHD`",
        "所有修改與測試先在 `/Google Drive/WHD`",
        "Drive unavailable = blocked",
        "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME",
    )
    for marker in forbidden:
        assert marker not in joined
