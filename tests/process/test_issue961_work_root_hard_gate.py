import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
SUPERSEDED = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"


def _payload():
    return json.loads(CURRENT.read_text(encoding="utf-8"))


def _entries():
    return [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"]


def test_v2_current_work_root_is_executor_local_policy_not_fixed_path():
    current = _payload()
    assert current["schema"] == "WHD_WORK_ROOT_HARD_GATE_V2"
    assert current["status"] == "CURRENT"
    root = current["default_work_root"]
    assert root["provider"] == "executor_local_workspace"
    assert root["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert root["production_branch"] == "cleanup/2d-3d-sync"
    assert root["authority"] is False
    assert "library_path" not in root
    assert "canonical_drive_overlay" not in current
    assert "unpushed" not in current
    assert current["drive_mirror"]["role"] == "MIRROR_BACKUP_ONLY"
    assert current["drive_mirror"]["authority"] is False
    assert current["drive_mirror"]["routing_forbidden"] is True
    assert not SUPERSEDED.exists()


def test_interactive_uses_own_workspace_and_remote_reads_repository_contract():
    from tools.work_root_gate import (
        READ_MODE_GITHUB_REPO,
        READ_MODE_WORKSPACE,
        build_work_root_gate_evidence,
    )

    interactive = build_work_root_gate_evidence(
        gate_payload=_payload(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=_entries(),
        workspace_root="/tmp/runtime-whd",
        production_head_sha="a" * 40,
    )
    assert interactive["workspace_root"] == "/tmp/runtime-whd"
    assert interactive["production_branch"] == "cleanup/2d-3d-sync"
    assert interactive["shared_zero_required"] is False

    remote = build_work_root_gate_evidence(
        gate_payload=_payload(),
        read_mode=READ_MODE_GITHUB_REPO,
        execution_mode="SCHEDULER_LANE",
        root_entries=_entries(),
    )
    assert remote["source"] == ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"

    with pytest.raises(ValueError, match="interactive mode"):
        build_work_root_gate_evidence(
            gate_payload=_payload(),
            read_mode=READ_MODE_GITHUB_REPO,
            execution_mode="INTERACTIVE",
            root_entries=_entries(),
            workspace_root="/tmp/runtime-whd",
        )


def test_work_root_contract_rejects_regrowth_to_fixed_drive_or_codex_root():
    from tools.work_root_gate import validate_gate_payload

    payload = _payload()
    for bad in (
        {"provider": "google_drive", "path_policy": "EXECUTOR_LOCAL_REPO_WORKSPACE"},
        {"provider": "executor_local_workspace", "path_policy": "/workspace/whd"},
        {"provider": "executor_local_workspace", "path_policy": "/Google Drive/WHD"},
    ):
        broken = json.loads(json.dumps(payload))
        broken["default_work_root"].update(bad)
        with pytest.raises(ValueError, match="work-root"):
            validate_gate_payload(broken)


def test_agents_places_workspace_gate_then_retired_shared_zero_compatibility_before_preflight():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    entry = text.index("ENTRY_ROUTER_FIRST_HARD_GATE_V1")
    work = text.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V2")
    shared = text.index("## -0.5. ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1")
    phase6 = text.index("# 0. 啟動硬閘門")
    assert entry < work < shared < phase6
    assert "executor 自己的 repo workspace" in text
    assert "cleanup/2d-3d-sync" in text
    assert "shared_zero_drift_present=false → WORKSPACE_DEFAULT" in text
    assert "shared_zero_drift_present=true → WORKSPACE_DEFAULT" in text


def test_flow_v2_startup_defaults_to_workspace_and_drive_cannot_change_route():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    section = text.split("## PROJECT_STARTUP_HARD_GATE_V1", 1)[1].split(
        "<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->", 1
    )[0]
    assert "executor 自己的 repo workspace" in section
    assert "WORKSPACE_DEFAULT" in section
    assert "Drive/shared-zero 不得改變 route" in section
    assert "普通 startup 不要求 Drive mount/shared-0" in section


def test_startup_evidence_accepts_executor_local_workspace_gate():
    from datetime import datetime, timezone
    from tools.execution_entry_contract import build_startup_evidence, validate_startup_evidence
    from tools.work_root_gate import READ_MODE_WORKSPACE, build_work_root_gate_evidence

    gate = build_work_root_gate_evidence(
        gate_payload=_payload(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=_entries(),
        workspace_root="/mnt/data/chatgpt-whd",
        production_head_sha="b" * 40,
    )
    evidence = build_startup_evidence(
        purpose="workspace-first validation",
        invocation_identity="interactive:work0:workspace",
        execution_mode="INTERACTIVE",
        work_root_gate_evidence=gate,
        issued_at=datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc),
    )
    validated = validate_startup_evidence(
        evidence,
        invocation_identity="interactive:work0:workspace",
        now=datetime(2026, 10, 5, 0, 1, tzinfo=timezone.utc),
    )
    assert validated["work_root_gate"]["workspace_root"] == "/mnt/data/chatgpt-whd"
    assert "executor-local repo workspace" in validated["declaration"]


def test_shared_zero_work_root_helpers_are_hard_retired():
    from tools.work_root_gate import unpushed_zero_path, worker_candidate_path

    contract = _payload()
    assert "unpushed" not in contract
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        unpushed_zero_path("body")
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        worker_candidate_path(lane="docs", worker="work0", issue=1200)


def test_authority_map_still_points_to_single_current_machine_owners():
    text = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(
        encoding="utf-8"
    )
    assert "contract=work-root-full-repo-gate role=CURRENT path=tools/work_root_gate.py" in text
    assert "contract=root-shared-unpushed-entry-gate role=CURRENT path=.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json" in text
    assert "contract=shared-unpushed-integration role=HISTORICAL path=tools/shared_unpushed_integration.py" in text


def test_every_flow_v2_execution_bridge_routes_through_canonical_flow_startup():
    skill_root = ROOT / ".agents/skills/engineering"
    bridged = []
    for path in skill_root.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        if "FLOW_V2_EXECUTION_BRIDGE_V1" not in text:
            continue
        bridged.append(path)
        assert "flow-v2-execution" in text, path
        assert (
            "whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md" in text
            or "PROJECT_STARTUP_HARD_GATE_V1" in text
        ), path
    assert len(bridged) >= 8
