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
    "tools/continuity_controller.py",
    "tools/scheduler_runtime_liveness.py",
    "tools/scheduler_host_watchdog.py",
    "tools/scheduled_resume_executor.py",
    "tools/scheduled_resume_runtime.py",
    "tools/control_transaction.py",
    "tools/control_transaction_production_executor.py",
    "tools/control_transaction_request_ingress.py",
    "tools/control_transaction_request_builder.py",
    "tools/flow_v2_merge_precheck.py",
    "tools/execution_invocation_exit.py",
    "tools/execution_scheduler_view.py",
    "tools/execution_entry_contract.py",
    "tools/execution_path_reservation.py",
    "tools/work_root_gate.py",
    "tools/change_test_profile.py",
    "tools/post_integration_durability.py",
    "tools/control_plane_regression.py",
)

PYTEST_PATHS = (
    "tests/process/test_flow_v2_execution_invocation_exit.py",
    "tests/process/test_flow_v2_execution_scheduler_view.py",
    "tests/process/test_flow_v2_merge_precheck.py",
    "tests/process/test_flow_v2_sync_target.py",
    "tests/process/test_flow_v2_atomic_control_transaction.py",
    "tests/process/test_flow_v2_path_reservation.py",
    "tests/process/test_issue865_scheduler_stop_hardening.py",
    "tests/process/test_issue851_recurring_lifecycle_turn_exit.py",
    "tests/process/test_issue769_terminal_scheduler_census_exit_gate.py",
    "tests/process/test_issue787_turn_exit_blocker_authority.py",
    "tests/process/test_scheduler_no_work_census_contract.py",
    "tests/process/test_issue892_flow_v2_production_transaction.py",
    "tests/process/test_issue899_push_transaction_ingress.py",
    "tests/process/test_issue961_work_root_hard_gate.py",
    "tests/process/test_change_test_profile.py",
    "tests/process/test_issue945_scheduler_host_watchdog.py",
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
    "tests/process/test_issue1045_post_integration_durability.py",
    "tests/knowledge",
)


def run() -> int:
    for rel in COMPILE_PATHS:
        py_compile.compile(str(ROOT / rel), doraise=True)
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *PYTEST_PATHS], cwd=ROOT)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
