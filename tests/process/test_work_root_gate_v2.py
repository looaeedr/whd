import json
from pathlib import Path

import pytest

from tools.work_root_gate import (
    DEFAULT_WORKSPACE_POLICY,
    DRIVE_MIRROR_ROOT,
    EVIDENCE_SCHEMA,
    READ_MODE_GOOGLE_DRIVE,
    READ_MODE_WORKSPACE,
    build_work_root_gate_evidence,
    unpushed_zero_path,
    verify_root_entries,
    worker_candidate_path,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
ROOT_ENTRIES = [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"]


def gate():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_executor_local_workspace_identity_is_current_root():
    ev = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/tmp/chatgpt-whd",
        production_head_sha="a" * 40,
    )
    assert ev["schema"] == EVIDENCE_SCHEMA
    assert ev["workspace_policy"] == DEFAULT_WORKSPACE_POLICY
    assert ev["workspace_root"] == "/tmp/chatgpt-whd"
    assert ev["production_branch"] == "cleanup/2d-3d-sync"
    assert ev["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert ev["drive_mirror_root"] == DRIVE_MIRROR_ROOT
    assert ev["shared_zero_required"] is False


def test_interactive_workspace_root_is_required_but_not_globally_fixed():
    with pytest.raises(ValueError, match="workspace_root"):
        build_work_root_gate_evidence(
            gate_payload=gate(),
            read_mode=READ_MODE_WORKSPACE,
            execution_mode="INTERACTIVE",
            root_entries=ROOT_ENTRIES,
        )
    a = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/workspace/whd",
    )
    b = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/mnt/data/whd",
    )
    assert a["workspace_root"] != b["workspace_root"]


def test_legacy_control_root_layout_is_fail_closed():
    with pytest.raises(ValueError, match="LEGACY_CONTROL_ROOT_LAYOUT_FORBIDDEN"):
        verify_root_entries(ROOT_ENTRIES + ["source"])


def test_drive_read_mode_and_shared_zero_helpers_are_hard_retired():
    with pytest.raises(ValueError, match="DRIVE_WORK_ROOT_RETIRED"):
        build_work_root_gate_evidence(
            gate_payload=gate(),
            read_mode=READ_MODE_GOOGLE_DRIVE,
            execution_mode="INTERACTIVE",
            root_entries=ROOT_ENTRIES,
            workspace_root="/workspace/whd",
        )
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        unpushed_zero_path("body")
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        worker_candidate_path(lane="docs", worker="work0", issue=1200)


def test_current_work_root_contract_contains_no_drive_overlay_or_unpushed_route():
    payload = gate()
    assert "canonical_drive_overlay" not in payload
    assert "unpushed" not in payload
    assert "CONDITIONAL_SHARED_ZERO_DRIFT_CHECK" not in payload["required_sequence"]
    assert "ROOT_SHARED_UNPUSHED_GATE_READ" not in payload["required_sequence"]
