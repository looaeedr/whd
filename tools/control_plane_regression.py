"""Canonical Root/CI control-plane regression runner for WHD.

Both the root-local-first workspace and GitHub Actions call this exact module;
the test list must not be duplicated in workflow YAML.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "python tools/control_plane_regression.py"

COMPILE_PATHS = (
    "tools/scheduler_runtime_liveness.py",
    "tools/scheduler_host_watchdog.py",
    "tools/scheduler_entrypoint_observation.py",
    "tools/scheduler_ready_ingress.py",
    "tools/control_transaction.py",
    "tools/control_transaction_production_executor.py",
    "tools/control_transaction_request_ingress.py",
    "tools/flow_v2_pre_merge_recovery.py",
    "tools/control_transaction_request_builder.py",
    "tools/flow_v2_merge_precheck.py",
    "tools/execution_invocation_exit.py",
    "tools/execution_scheduler_view.py",
    "tools/flow_v2_compact_context.py",
    "tools/execution_entry_contract.py",
    "tools/execution_path_reservation.py",
    "tools/work_root_gate.py",
    "tools/workspace_canonical_sync.py",
    "tools/change_test_profile.py",
    "tools/post_integration_durability.py",
    "tools/shared_unpushed_integration.py",
    "tools/phase6_remote_preflight.py",
    "tools/phase6_preflight_push_request.py",
    "tools/production_x_post_merge_finalize.py",
    "tools/control_plane_regression.py",
)

STATIC_PYTEST_PATHS = (
    "tests/process/test_flow_v2_execution_invocation_exit.py",
    "tests/process/test_flow_v2_execution_scheduler_view.py",
    "tests/process/test_flow_v2_compact_context.py",
    "tests/process/test_issue1078_scheduler_ready_ingress.py",
    "tests/process/test_issue1078_scheduler_entrypoint_observation.py",
    "tests/process/test_issue1081_a40_host_identity.py",
    "tests/process/test_flow_v2_merge_precheck.py",
    "tests/process/test_flow_v2_sync_target.py",
    "tests/process/test_flow_v2_atomic_control_transaction.py",
    "tests/process/test_flow_v2_path_reservation.py",
    "tests/process/test_issue865_scheduler_stop_hardening.py",
    "tests/process/test_scheduler_no_work_census_contract.py",
    "tests/process/test_issue892_flow_v2_production_transaction.py",
    "tests/process/test_issue899_push_transaction_ingress.py",
    "tests/process/test_issue961_work_root_hard_gate.py",
    "tests/process/test_change_test_profile.py",
    "tests/process/test_issue696_startup_authorization_purpose.py",
    "tests/process/test_issue721_task_start_authority_declaration.py",
    "tests/process/test_issue724_report_handler_identity_prefix.py",
    "tests/process/test_issue886_flow_v2_entrypoint_cutover.py",
    "tests/process/test_issue952_governance_ancestry_reconcile.py",
    "tests/process/test_issue975_flow_v2_closure_stability.py",
    "tests/process/test_governance_single_authority.py",
    "tests/process/test_root_local_first_entry_hard_gate.py",
    "tests/process/test_issue1022_root_ci_parity.py",
    "tests/process/test_issue1032_flow_v2_semantic_doc_cutover.py",
    "tests/process/test_checkpoint_resume_contract.py",
    "tests/process/test_continuous_execution_durable_contract.py",
    "tests/process/test_issue1046_flow_v2_anti_regrowth_v2.py",
    "tests/process/test_issue1049_flow_v2_anti_regrowth_v3.py",
    "tests/process/test_issue1056_flow_v2_anti_regrowth_v4.py",
    "tests/process/test_issue1045_post_integration_durability.py",
    "tests/process/test_shared_unpushed_integration.py",
    "tests/process/test_shared_unpushed_anti_regrowth.py",
    "tests/process/test_issue1059_flow_v2_anti_regrowth_v5.py",
    "tests/process/test_issue1183_scheduler_phase6_push_preflight.py",
    "tests/process/test_issue1186_scheduler_preflight_continuation.py",
    "tests/process/test_issue1191_workspace_canonical_sync.py",
    "tests/process/test_issue1194_workspace_first_content_flow.py",
    "tests/process/test_issue1196_scheduler_host_lifecycle_gap.py",
    "tests/process/test_issue1063_actions_workflow_cleanup.py",
    "tests/process/test_issue1265_codex_git_connector_routing.py",
    "tests/process/test_issue1282_post_merge_finalize.py",
    "tests/process/test_issue1429_pre_merge_recovery.py",
    "tests/process/test_issue1412_postmerge_recovery_backlog.py",
    "tests/test_execution_work_slot_autoincrement.py",
    "tests/test_dm5_deep_module_writeback_contract.py",
    "tests/test_issue443_t1_dead_glue.py",
    "tests/test_issue_closure_completion_skill_contract.py",
    "tests/test_phase6_skill_preflight_gate.py",
    "tests/test_remote_qa_monitoring_skill_contract.py",
    "tests/test_to_tickets_red_first_contract.py",
    "tests/knowledge",
)

FLOW_V2_PYTEST_PATHS = tuple(
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests/process").glob("test_flow_v2_*.py")
    )
)
PRODUCT_PROCESS_TESTS = frozenset({
    "test_issue423_phase5_t2_assembly_panel.py", "test_issue424_phase5_t3_box_piece_panel.py",
    "test_issue425_phase5_t4_final_scene_visibility.py", "test_issue426_phase5_t5_bridge_compression.py",
})
CURRENT_PROCESS_PATHS = tuple(sorted(
    path.relative_to(ROOT).as_posix()
    for path in (ROOT / "tests/process").glob("test_*.py")
    if path.name not in PRODUCT_PROCESS_TESTS
))
PYTEST_PATHS = tuple(dict.fromkeys((*CURRENT_PROCESS_PATHS, *STATIC_PYTEST_PATHS,
    "tests/test_root_entry_router_hard_gate.py", "tests/governance",
    "tests/test_writing_skill_contract.py")))


def run() -> int:
    for rel in COMPILE_PATHS:
        py_compile.compile(str(ROOT / rel), doraise=True)
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *PYTEST_PATHS], cwd=ROOT)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
