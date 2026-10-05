from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str):
    return json.loads(_read(path))


def test_shared_zero_contract_is_historical_metadata_only():
    contract = _json(".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json")
    assert contract["status"] == "HISTORICAL"
    assert contract["role"] == "SUPERSEDED_DATA_ONLY"
    assert contract["activation"] == "NEVER_CURRENT"
    assert contract["current_routing_forbidden"] is True
    assert contract["authority"] is False
    assert contract["current_route"] == "WORKSPACE_DEFAULT"


def test_work_root_contract_has_no_drive_or_shared_zero_execution_overlay():
    contract = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert contract["default_work_root"]["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "canonical_drive_overlay" not in contract
    assert "unpushed" not in contract
    mirror = contract["drive_mirror"]
    assert mirror["library_path"] == "/Google Drive/WHD/WHD_MIRROR/CURRENT"
    assert mirror["role"] == "MIRROR_BACKUP_ONLY"
    assert mirror["authority"] is False
    assert mirror["routing_forbidden"] is True


def test_current_router_never_selects_drive_or_shared_zero():
    from tools.root_local_first_gate import select_repository_content_route
    for drift in (False, True):
        route = select_repository_content_route(
            shared_zero_drift_present=drift, workspace_root="/workspace/whd"
        )
        assert route["route"] == "WORKSPACE_DEFAULT"
        assert route["shared_zero_required"] is False
        assert route["workspace_canonical_sync_required"] is False


def test_current_shared_zero_machine_apis_are_fail_closed():
    import tools.shared_unpushed_integration as shared
    import tools.workspace_canonical_sync as sync
    try:
        shared.classify_lane(path="AGENTS.md", ownership="governance")
    except shared.UnpushedIntegrationError as exc:
        assert "SHARED_ZERO_ROUTING_RETIRED" in str(exc)
    else:
        raise AssertionError("shared-zero CURRENT API unexpectedly remained executable")
    try:
        sync.status()
    except sync.WorkspaceCanonicalSyncError as exc:
        assert "WORKSPACE_CANONICAL_SYNC_RETIRED" in str(exc)
    else:
        raise AssertionError("workspace canonical sync CURRENT API unexpectedly remained executable")


def test_drive_unavailable_never_becomes_repository_content_blocker():
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    scheduler = _read(".agents/skills/engineering/排程模擬/SKILL.md")
    agents = _read("AGENTS.md")
    assert "Drive mount 不可見永遠不是 repository-content blocker" in root
    assert "Google Drive mount 不可見本身不是 blocker" in flow
    assert "Drive mount、mirror、舊 shared-zero drift 都不是 scheduler content-handoff 的判定條件" in scheduler
    assert "Drive mount、Drive mirror、舊 pointer、`.unpushed` 缺失都不是 blocker" in agents


def test_current_docs_do_not_restore_legacy_drive_construction_root():
    joined = "\n".join(_read(p) for p in (
        "AGENTS.md",
        ".agents/skills/engineering/root-local-first/SKILL.md",
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        ".agents/skills/engineering/排程模擬/SKILL.md",
        ".agents/skills/engineering/推推/SKILL.md",
    ))
    forbidden = (
        "唯一預設 root：`/Google Drive/WHD`",
        "所有修改與測試先在 `/Google Drive/WHD`",
        "Drive unavailable = blocked",
        "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME",
    )
    for marker in forbidden:
        assert marker not in joined
