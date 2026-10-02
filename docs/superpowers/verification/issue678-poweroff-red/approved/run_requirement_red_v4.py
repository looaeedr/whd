from __future__ import annotations
import hashlib
import json
import os
import subprocess
from pathlib import Path

TEST = Path(r"C:\Users\Public\test_whd_poweroff_requirement_red_v4.py")
FAKE = Path(r"C:\Users\Public\fake_token_only_poweroff_gate.py")
RAW = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v4_raw.txt")
ANTI_RAW = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v4_anti_false_green_raw.txt")
MANIFEST = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v4_manifest.json")

current_cases = [
    ("R0", "test_R0_poweroff_gate_production_owner_exists",
     "R0_POWER_OFF_GATE_OWNER: missing production owner tools/workstation_poweroff_gate.py"),
    ("R0A", "test_R0A_planned_handoff_evaluator_contract_exists",
     "R0A_PLANNED_HANDOFF_EVALUATOR: WHD_WORK_EXECUTOR_HANDOFF_V1 machine contract is absent from tools"),
    ("R1", "test_R1_local_durability_classifier_maps_machine_unavailable",
     "R1_LOCAL_DURABILITY: missing production owner tools/local_durability_gate.py"),
    ("R2", "test_R2_guard_exposes_distinct_planned_claim_handoff_action",
     "R2_PLANNED_HANDOFF: execution_claim_guard has no distinct claim-handoff action"),
    ("R3", "test_R3_guard_drain_is_behavioral",
     "R3_GUARD_DRAIN: missing production owner tools/workstation_poweroff_gate.py"),
    ("R4", "test_R4_scheduler_readiness_is_behavioral",
     "R4_SCHEDULER_READINESS: missing production owner tools/workstation_poweroff_gate.py"),
    ("R5", "test_R5_poweroff_truth_table_is_behavioral",
     "R5_POWER_OFF_TRISTATE: missing production owner tools/workstation_poweroff_gate.py"),
    ("R6", "test_R6_safe_receipt_invalidation_is_behavioral",
     "R6_SAFE_INVALIDATION: missing production owner tools/workstation_poweroff_gate.py"),
    ("R7", "test_R7_ha_projection_requires_current_request_bound_safe",
     "R7_HA_CURRENT_REQUEST_SAFE: no HA-facing bridge or poweroff-gate owner exists"),
    ("R8", "test_R8_timeout_is_fail_closed_not_shutdown_fallback",
     "R8_TIMEOUT_FAIL_CLOSED: no HA/poweroff machine owner exists to enforce timeout behavior"),
    ("R9", "test_R9_outage_recovery_distinguishes_unknown_local_state_and_mutation",
     "R9_OUTAGE_UNKNOWN_STATE: outage recovery cannot explicitly classify unknown local state/mutation"),
    ("R10", "test_R10_multi_slot_aggregation_is_behavioral",
     "R10_MULTI_SLOT_AGGREGATION: missing production owner tools/workstation_poweroff_gate.py"),
    ("R11", "test_R11_real_shutdown_integration_requires_end_to_end_acceptance_gate",
     "R11_REAL_SHUTDOWN_ACCEPTANCE: no HA/poweroff owner exists to gate real shutdown integration"),
]

anti_cases = [
    ("R3", "test_R3_guard_drain_is_behavioral", "expected result=NOT_SAFE"),
    ("R4", "test_R4_scheduler_readiness_is_behavioral", "expected result=NOT_SAFE"),
    ("R5", "test_R5_poweroff_truth_table_is_behavioral", "expected result=NOT_SAFE"),
    ("R6", "test_R6_safe_receipt_invalidation_is_behavioral", "assert True is False"),
    ("R10", "test_R10_multi_slot_aggregation_is_behavioral", "one NOT_SAFE slot must prevent aggregate SAFE"),
]

base_env = dict(os.environ)
base_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

def run_one(rid: str, fn: str, expected: str, *, override: bool):
    env = dict(base_env)
    if override:
        env["WHD_POWER_OFF_GATE_OVERRIDE"] = str(FAKE)
    else:
        env.pop("WHD_POWER_OFF_GATE_OVERRIDE", None)
    nodeid = f"{TEST}::{fn}"
    cmd = ["python", "-m", "pytest", "-q", "--tb=short", nodeid]
    p = subprocess.run(
        cmd, cwd=r"C:\Users\Public", env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=15,
    )
    return {
        "red_id": rid,
        "nodeid": nodeid,
        "command": (
            "$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; "
            + (f"$env:WHD_POWER_OFF_GATE_OVERRIDE='{FAKE}'; " if override else "")
            + "Set-Location C:\\Users\\Public; "
            + " ".join(cmd)
        ),
        "expected_failure_substring": expected,
        "exit_code": p.returncode,
        "expected_failure_observed": expected in p.stdout,
        "raw_output": p.stdout,
        "raw_output_sha256": hashlib.sha256(p.stdout.encode("utf-8")).hexdigest(),
    }

def render(records):
    parts = []
    for r in records:
        parts.append(
            f"===== {r['red_id']} =====\n"
            f"COMMAND: {r['command']}\n"
            f"EXPECTED_FAILURE_SUBSTRING: {r['expected_failure_substring']}\n"
            f"EXIT_CODE: {r['exit_code']}\n"
            f"EXPECTED_FAILURE_OBSERVED: {r['expected_failure_observed']}\n"
            f"{r['raw_output']}\n"
        )
    return "\n".join(parts)

current = [run_one(*case, override=False) for case in current_cases]
anti = [run_one(*case, override=True) for case in anti_cases]

RAW.write_text(render(current), encoding="utf-8")
ANTI_RAW.write_text(render(anti), encoding="utf-8")

for r in current + anti:
    del r["raw_output"]

manifest = {
    "schema": "WHD_REQUIREMENT_RED_PROBE_EVIDENCE_V2",
    "status": "PROBE_EXECUTED_DURABLE_ANCHOR_PENDING",
    "target_ref": "cleanup/2d-3d-sync",
    "target_sha": "87eb35b3f5ae5211673c941cb56c4c4343fa5405",
    "spec_version": "v1.3",
    "probe_path": str(TEST),
    "probe_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "runner_path": str(Path(__file__)),
    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "fake_token_only_gate_path": str(FAKE),
    "fake_token_only_gate_sha256": hashlib.sha256(FAKE.read_bytes()).hexdigest(),
    "raw_output_path": str(RAW),
    "raw_output_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
    "anti_false_green_raw_output_path": str(ANTI_RAW),
    "anti_false_green_raw_output_sha256": hashlib.sha256(ANTI_RAW.read_bytes()).hexdigest(),
    "all_current_cases_red": all(r["exit_code"] == 1 for r in current),
    "all_current_expected_failures_observed": all(r["expected_failure_observed"] for r in current),
    "anti_false_green_all_red": all(r["exit_code"] == 1 for r in anti),
    "anti_false_green_expected_failures_observed": all(r["expected_failure_observed"] for r in anti),
    "current_records": current,
    "anti_false_green_records": anti,
    "durable_anchor": "PENDING_USER_RED_APPROVAL_THEN_REPOSITORY_OWNED_EVIDENCE",
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    k: manifest[k] for k in (
        "schema","status","target_sha","spec_version",
        "probe_sha256","runner_sha256","fake_token_only_gate_sha256",
        "raw_output_sha256","anti_false_green_raw_output_sha256",
        "all_current_cases_red","all_current_expected_failures_observed",
        "anti_false_green_all_red","anti_false_green_expected_failures_observed",
    )
}, ensure_ascii=False, indent=2))
