"""Workspace-only admission and completion through the public governance seams."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_startup_and_test_profile_never_nominate_drive_or_shared_zero():
    from tools.execution_entry_contract import build_startup_declaration
    from tools.change_test_profile import build_test_profile

    declaration = build_startup_declaration(purpose="workspace governance repair")
    assert "fallback" not in declaration
    profile = build_test_profile(task="repair", changed_files=["gui.py"], explicit_type="BUGFIX")
    assert profile["workspace_root"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert profile["workspace_unpushed_root"] is None
    assert profile["exact_commands"] == ["python tools/product_ci_regression.py"]


def test_drive_transport_cannot_produce_current_workspace_admission():
    from tools.work_root_gate import build_work_root_gate_evidence

    payload = json.loads((ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json").read_text())
    with pytest.raises(ValueError, match="DRIVE_WORK_ROOT_RETIRED"):
        build_work_root_gate_evidence(
            gate_payload=payload, read_mode="GOOGLE_DRIVE_CANONICAL",
            execution_mode="INTERACTIVE", root_entries=payload["required_root_entries"],
        )


def _workspace_gate(**overrides):
    from tools.root_local_first_gate import (
        build_entry_router_evidence, build_gate_evidence, build_remote_connection_authority,
    )

    args = dict(
        execution_mode="INTERACTIVE", repository_content_implementation=True,
        entry_router_evidence=build_entry_router_evidence(
            workspace_root="/workspace/whd", fresh_reads=[
                ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
                ".agents/skills/engineering/root-local-first/SKILL.md",
            ],
        ),
        source_evidence={"status": "EXACT_SOURCE_CURRENT", "source_sha": "a" * 40},
        workspace_mutations_complete=True, workspace_tests_green=True,
        diff_digest="d" * 64, expected_test_commands=["python tools/control_plane_regression.py"],
        workspace_delivery_authority=build_remote_connection_authority(
            kind="WORKSPACE_DELIVERY", target="GITHUB", user_explicit=True,
        ),
        path_reservation_evidence={
            "schema": "WHD_PATH_RESERVATION_EVIDENCE_V1", "phase": "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN",
            "issue": 1, "generation": 1, "target_branch": "cleanup/2d-3d-sync", "base_sha": "a" * 40,
            "write_paths": ["AGENTS.md"], "delete_paths": [], "reservation_state": "ACTIVE",
            "record_fingerprint": "f" * 64,
        },
    )
    args.update(overrides)
    return build_gate_evidence(**args)


def _test_receipt():
    return dict(schema="WHD_TEST_EXECUTION_RECEIPT_V1", status="GREEN", source_sha="a" * 40,
                issue=1, generation=1, manifest_digest="d" * 64,
                exact_commands=["python tools/control_plane_regression.py"])


def test_boolean_green_cannot_unlock_workspace_delivery():
    with pytest.raises(ValueError, match="test.*receipt|WHD_TEST_EXECUTION_RECEIPT"):
        _workspace_gate()


@pytest.mark.parametrize("field,value", [
    ("source_sha", "b" * 40), ("issue", 2), ("status", "RED"),
    ("manifest_digest", "e" * 64), ("exact_commands", ["true"]),
])
def test_workspace_receipt_must_bind_the_tested_candidate(field, value):
    receipt = _test_receipt()
    receipt[field] = value
    with pytest.raises(ValueError):
        _workspace_gate(test_receipt=receipt)


def test_verified_workspace_receipt_unlocks_exact_diff_without_shared_zero():
    gate = _workspace_gate(test_receipt=_test_receipt())
    assert gate["git_write_unlocked"] is True
    assert gate["route"] == "WORKSPACE_DEFAULT"
    assert gate["test_receipt"] == _test_receipt()


def test_receipt_commands_accept_a_single_pass_iterable():
    gate = _workspace_gate(
        test_receipt=_test_receipt(),
        expected_test_commands=iter(["python tools/control_plane_regression.py"]),
    )
    assert gate["git_write_unlocked"] is True


def test_terminal_workspace_does_not_require_a_retired_lane_receipt():
    from tools.post_integration_durability import classify_post_integration_durability

    record = dict(issue=1, generation=1, state="DONE", lease=None, next_action=None,
                  target_sha="a" * 40, mutation_scope={"reservation_state": "RELEASED"},
                  closure={"issue_closed": True, "merged_sha": "a" * 40})
    result = classify_post_integration_durability(execution_record=record, root_sync_receipt=None,
                                                lane_delivery_receipt=None)
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    record["closure"]["issue_closed"] = False
    assert classify_post_integration_durability(execution_record=record, root_sync_receipt=None,
                                              lane_delivery_receipt=None)["state"] == "NOT_TERMINAL"


def test_skill_audit_accepts_existing_declared_contracts():
    proc = subprocess.run([sys.executable, "tools/knowledge_authority_skill_gap_audit.py"],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKILL_AUTHORITY_GAPS 0" in proc.stdout


def test_canonical_runner_covers_workspace_admission_and_repair():
    from tools.control_plane_regression import PYTEST_PATHS

    for path in ("tests/process/test_workspace_entry_drive_independence.py",
                 "tests/process/test_work_root_gate_v2.py",
                 "tests/process/test_issue1250_codex_liveness_v3.py",
                 "tests/process/test_workspace_only_governance_repair.py",
                 "tests/test_root_entry_router_hard_gate.py"):
        assert path in PYTEST_PATHS
