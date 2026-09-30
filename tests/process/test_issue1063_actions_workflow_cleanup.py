from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {
    "drive-source-snapshot-export.yml",
    "knowledge-governance-bootstrap.yml",
    "whd-product-regression.yml",
    "whd-control-plane-regression.yml",
    "whd-control-transaction-v2-request.yml",
    "whd-control-transaction-v2.yml",
    "whd-governance-single-authority-gate.yml",
    "whd-phase6-preflight.yml",
}

LEGACY_PRODUCT_WORKFLOWS = {
    "phase6-bridge-anti-regrowth.yml",
    "receiving-divider-broader-acceptance.yml",
    "receiving-fw-formed-occupation-red.yml",
    "receiving-ui-regression.yml",
}

def test_active_workflow_surface_is_exact_and_reusable() -> None:
    assert {p.name for p in WORKFLOWS.glob("*.yml")} == EXPECTED

def test_no_issue_scoped_branch_specific_or_retired_legacy_workflow_regrows() -> None:
    actual = {p.name for p in WORKFLOWS.glob("*.yml")}
    assert not any(name.startswith("qa-issue") or name.startswith("issue") for name in actual)
    forbidden = {
        "whd-control-transaction-v2-shadow.yml",
        "whd-control-transaction-v2-terminal-shadow.yml",
        "whd-remote-claim-activation.yml",
        "whd-remote-execution-guard.yml",
        "whd-remote-finalization.yml",
        "whd-remote-parent-branch-identity-repair.yml",
        "whd-scheduler-host-watchdog.yml",
        "whd-turn-exit-gate.yml",
        *LEGACY_PRODUCT_WORKFLOWS,
    }
    assert actual.isdisjoint(forbidden)

def test_product_ci_is_pr_verification_not_development_branch_automation() -> None:
    text = (WORKFLOWS / "whd-product-regression.yml").read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "cleanup/2d-3d-sync" in text
    assert "workflow_dispatch" not in text
    assert "work/receiving" not in text
    assert "fix/receiving" not in text
    assert "python tools/product_ci_regression.py" in text
    assert "run: pytest" not in text
    assert "xvfb-run -a pytest" not in text
    control = (WORKFLOWS / "whd-control-plane-regression.yml").read_text(encoding="utf-8")
    assert "'.github/workflows/**'" in control


def test_product_ci_preserves_all_retired_workflow_coverage() -> None:
    runner = (ROOT / "tools/product_ci_regression.py").read_text(encoding="utf-8")
    required = (
        "tests/process/test_issue533_c1_anti_regrowth.py",
        "tools/phase6_bridge_anti_regrowth_guard.py",
        "tests/test_dm1_divider_physical_contract.py",
        "tests/test_dm3_divider_canonical_relief_contract.py",
        "tests/test_dm4_divider_resolved_sinks.py",
        "tests/test_issue39_divider_relief.py",
        "tests/test_issue63_regression_red.py",
        "tests/test_issue71_divider_relief_components.py",
        "tests/test_issue74_divider_side_front_penetration.py",
        "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
        "tests/test_corner_parameter_lock.py",
        "tests/test_issue509_receiving_horizontal_marking.py",
        "tests/test_issue510_receiving_back_panel_modes.py",
        "test_saved_dxf_acceptance_passes_exact_roundtrip",
        "test_resolved_saved_dxf_acceptance_reopens_every_physical_part",
        "test_resolved_dxf_export_uses_exact_canonical_render_data_without_rebuilding",
        "test_2d_and_3d_equal_door_state_share_exact_render_data_object",
        "test_final_scene_assembly_uses_box_body_world_mesh_as_head_tail_mating_datum",
        "test_project_round_trip_preserves_verified_joint_relief_state",
        "test_p6fold_round_trip_preserves_receiving_bottom_wrap_linkage_and_reserves",
        "PHYSICAL_COLLISION_PLUS_TARGET_T_OVER_2",
        "PHYSICAL_PRIMARY_BOUNDARY_PLUS_SOURCE_COLLISION_SPAN",
    )
    for token in required:
        assert token in runner, token
    assert "PHASE6_BRIDGE_HISTORY_GUARD=DEFERRED_TO_PR_CI_NO_GIT_METADATA" in runner

def test_required_status_context_and_current_flow_v2_transports_remain() -> None:
    gate = (WORKFLOWS / "whd-governance-single-authority-gate.yml").read_text(encoding="utf-8")
    assert "Governance Mirror Hard Gate" in gate
    request = (WORKFLOWS / "whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "WHD｜Flow v2｜Push Transaction Request" in request
    for branch in ("coord/transaction-requests-work0", "coord/transaction-requests-work1", "coord/transaction-requests-work2", "coord/transaction-requests-work3"):
        assert branch in request
    preflight = (WORKFLOWS / "whd-phase6-preflight.yml").read_text(encoding="utf-8")
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1" in preflight

def test_remote_guard_registry_route_does_not_restore_deleted_workflow() -> None:
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(r for r in registry["routes"] if r["id"] == "remote-execution-guard")
    assert ".github/workflows/whd-remote-execution-guard.yml" not in route["file_globs"]
