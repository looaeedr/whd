import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
SUPERSEDED = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"


def _payload():
    return json.loads(CURRENT.read_text(encoding="utf-8"))


def _entries():
    return [
        ".git", ".agents", ".github", "AGENTS.md", "tools", "tests",
        "ae_engine", "gui_modules", ".unpushed",
    ]


def test_v2_is_only_current_work_root_contract():
    current = _payload()
    assert current["schema"] == "WHD_WORK_ROOT_HARD_GATE_V2"
    assert current["status"] == "CURRENT"
    assert current["default_work_root"]["library_path"] == "/Google Drive/WHD"
    assert current["default_work_root"]["drive_folder_id"] == "1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN"
    assert not SUPERSEDED.exists()


def test_interactive_and_remote_use_same_root_identity_but_different_read_transport():
    from tools.work_root_gate import (
        READ_MODE_GITHUB_REPO,
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )
    interactive = build_work_root_gate_evidence(
        gate_payload=_payload(), read_mode=READ_MODE_GOOGLE_DRIVE,
        execution_mode="INTERACTIVE", root_entries=_entries(),
    )
    assert interactive["schema"] == "WHD_WORK_ROOT_GATE_EVIDENCE_V2"
    assert interactive["source"].endswith("/.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert interactive["unpushed_root"] == "/Google Drive/WHD/.unpushed"

    remote = build_work_root_gate_evidence(
        gate_payload=_payload(), read_mode=READ_MODE_GITHUB_REPO,
        execution_mode="SCHEDULER_LANE", root_entries=_entries(),
    )
    assert remote["source"] == ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"

    with pytest.raises(ValueError, match="interactive mode"):
        build_work_root_gate_evidence(
            gate_payload=_payload(), read_mode=READ_MODE_GITHUB_REPO,
            execution_mode="INTERACTIVE", root_entries=_entries(),
        )


def test_root_gate_rejects_wrong_root_identity_and_legacy_control_layout():
    from tools.work_root_gate import validate_gate_payload, verify_root_entries
    payload = _payload()
    for bad in ("/mnt/data", "/WHD", "/", "GitHub repository checkout"):
        broken = json.loads(json.dumps(payload))
        broken["default_work_root"]["library_path"] = bad
        with pytest.raises(ValueError, match="work-root"):
            validate_gate_payload(broken)
    for legacy in ("source", "state", "work", "artifacts"):
        with pytest.raises(ValueError, match="LEGACY_CONTROL_ROOT_LAYOUT_FORBIDDEN"):
            verify_root_entries([*_entries(), legacy])


def test_agents_places_v2_work_root_then_shared_zero_gate_before_preflight():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    entry = text.index("ENTRY_ROUTER_FIRST_HARD_GATE_V1")
    work = text.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V2")
    shared = text.index("## -0.5. ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1")
    phase6 = text.index("# 0. 啟動硬閘門")
    assert entry < work < shared < phase6
    assert ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json" in text
    assert ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json" in text
    assert "/Google Drive/WHD/.unpushed/body/0" in text
    assert "/Google Drive/WHD/.unpushed/docs/0" in text


def test_flow_v2_startup_routes_content_work_through_shared_zero():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    section = text.split("## PROJECT_STARTUP_HARD_GATE_V1", 1)[1].split(
        "<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->", 1
    )[0]
    assert section.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V2") < section.index("ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1")
    assert "ZERO_INITIALIZED_OR_FRESH_READ" in section
    assert "只有 delivery 才取得 reservation" in section
    assert "/work/active" not in section


def test_startup_evidence_requires_v2_root_gate_before_ingress():
    from datetime import datetime, timezone
    from tools.execution_entry_contract import build_startup_evidence, validate_startup_evidence
    from tools.work_root_gate import READ_MODE_GOOGLE_DRIVE, build_work_root_gate_evidence

    gate = build_work_root_gate_evidence(
        gate_payload=_payload(), read_mode=READ_MODE_GOOGLE_DRIVE,
        execution_mode="INTERACTIVE", root_entries=_entries(),
    )
    evidence = build_startup_evidence(
        purpose="V2 root/shared-zero validation",
        invocation_identity="interactive:work0:shared-zero",
        execution_mode="INTERACTIVE", work_root_gate_evidence=gate,
        issued_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )
    validated = validate_startup_evidence(
        evidence, invocation_identity="interactive:work0:shared-zero",
        now=datetime(2026, 10, 2, 12, 1, tzinfo=timezone.utc),
    )
    assert validated["work_root_gate"]["schema"] == "WHD_WORK_ROOT_GATE_EVIDENCE_V2"
    assert "WHD_WORK_ROOT_HARD_GATE_V2" in validated["declaration"]


def test_work_root_paths_are_shared_zero_not_per_issue_workspaces():
    from tools.work_root_gate import UNPUSHED_ROOT, unpushed_zero_path, worker_candidate_path
    assert UNPUSHED_ROOT == "/Google Drive/WHD/.unpushed"
    assert unpushed_zero_path("body") == "/Google Drive/WHD/.unpushed/body/0"
    assert unpushed_zero_path("docs") == "/Google Drive/WHD/.unpushed/docs/0"
    candidate = worker_candidate_path(lane="docs", worker="work0", issue=1200)
    assert candidate == "/Google Drive/WHD/.unpushed/docs/workers/work0/issue-1200"
    assert "/work/active" not in candidate


def test_authority_map_declares_v2_and_shared_zero_current_owners():
    text = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    assert "contract=work-root-full-repo-gate role=CURRENT path=tools/work_root_gate.py" in text
    assert "contract=root-shared-unpushed-entry-gate role=CURRENT path=.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json" in text
    assert "contract=shared-unpushed-integration role=CURRENT path=tools/shared_unpushed_integration.py" in text
    assert "contract=push-delivery-skill role=CURRENT path=.agents/skills/engineering/推推/SKILL.md" in text


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
    assert len(bridged) >= 9
