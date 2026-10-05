import pytest
from tools.work_root_gate import (
    CANONICAL_DRIVE_ROOT,
    DEFAULT_DRIVE_FOLDER_ID,
    DEFAULT_WORKSPACE_POLICY,
    EVIDENCE_SCHEMA,
    GATE_SCHEMA,
    READ_MODE_WORKSPACE,
    UNPUSHED_ROOT,
    build_work_root_gate_evidence,
    unpushed_zero_path,
    verify_root_entries,
    worker_candidate_path,
)

ROOT_ENTRIES = [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"]


def gate():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[2] / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text())


def test_executor_local_workspace_identity_is_not_fixed_to_codex_path():
    ev = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/tmp/chatgpt-whd",
        production_head_sha="a" * 40,
    )
    assert ev["schema"] == EVIDENCE_SCHEMA
    assert ev["workspace_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert ev["workspace_root"] == "/tmp/chatgpt-whd"
    assert ev["production_branch"] == "cleanup/2d-3d-sync"
    assert ev["production_head_sha"] == "a" * 40
    assert ev["shared_zero_required"] is False


def test_interactive_workspace_root_is_required_but_not_globally_fixed():
    with pytest.raises(ValueError, match="workspace_root"):
        build_work_root_gate_evidence(
            gate_payload=gate(),
            read_mode=READ_MODE_WORKSPACE,
            execution_mode="INTERACTIVE",
            root_entries=ROOT_ENTRIES,
        )
    codex = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/workspace/whd",
    )
    chatgpt = build_work_root_gate_evidence(
        gate_payload=gate(),
        read_mode=READ_MODE_WORKSPACE,
        execution_mode="INTERACTIVE",
        root_entries=ROOT_ENTRIES,
        workspace_root="/mnt/data/whd",
    )
    assert codex["workspace_root"] != chatgpt["workspace_root"]


def test_legacy_control_root_layout_is_fail_closed():
    with pytest.raises(ValueError, match="LEGACY_CONTROL_ROOT_LAYOUT_FORBIDDEN"):
        verify_root_entries(ROOT_ENTRIES + ["source"])


def test_historical_shared_zero_paths_have_no_current_routing_authority():
    assert unpushed_zero_path("body") == "/Google Drive/WHD/.unpushed/body/0"
    assert unpushed_zero_path("docs") == "/Google Drive/WHD/.unpushed/docs/0"
    assert worker_candidate_path(lane="docs", worker="work0", issue=1200).startswith(
        "/Google Drive/WHD/.unpushed/docs/workers/work0/"
    )
