import hashlib
import json
import os
import subprocess
from pathlib import Path

TEST = Path(r"C:\Users\Public\test_whd_poweroff_behavioral_red_v5.py")
FAKE_SAFE = Path(r"C:\Users\Public\fake_token_only_poweroff_gate.py")
FAKE_NOT_SAFE = Path(r"C:\Users\Public\fake_always_not_safe_poweroff_gate.py")
RAW = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v5_raw.txt")
ANTI_RAW = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v5_adversarial_raw.txt")
MANIFEST = Path(r"C:\Users\Public\whd_poweroff_requirement_red_v5_manifest.json")

# (case_id, nodeid function, adversarial fake, expected adversarial failure substring)
cases = [
    ("R3-PENDING", "test_R3_pending_guard_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R3-RECONCILE", "test_R3_reconcile_guard_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R3-AMBIGUOUS", "test_R3_ambiguous_guard_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R3-CONSUMED", "test_R3_consumed_guard_does_not_block_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R3-NONE", "test_R3_none_guard_does_not_block_safe", "NOT_SAFE", "expected result=SAFE"),

    ("R4-READY", "test_R4_ready_scheduler_allows_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R4-OWNER", "test_R4_owner_mismatch_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R4-UNVERIFIED", "test_R4_scheduler_unverified_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R4-DISABLED", "test_R4_scheduler_disabled_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R4-NEXT-ACTION", "test_R4_nonterminal_missing_next_action_blocks_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R4-HEAD", "test_R4_checkpoint_head_mismatch_blocks_safe", "SAFE", "expected result=NOT_SAFE"),

    ("R5-SAFE", "test_R5_all_safe_is_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R5-NOT-SAFE", "test_R5_local_mutation_is_not_safe", "SAFE", "expected result=NOT_SAFE"),
    ("R5-ERROR", "test_R5_machine_unreachable_is_error", "SAFE", "expected result=ERROR"),

    ("R6-REQUEST", "test_R6_request_id_change_invalidates_safe_receipt", "SAFE", "assert True is False"),
    ("R6-REVISION", "test_R6_evidence_revision_change_invalidates_safe_receipt", "SAFE", "assert True is False"),
    ("R6-RECEIPT", "test_R6_non_safe_receipt_is_invalid", "SAFE", "assert True is False"),
    ("R6-DIRTY", "test_R6_new_dirty_file_invalidates_safe_state", "SAFE", "expected result=NOT_SAFE"),
    ("R6-GUARD", "test_R6_new_pending_guard_invalidates_safe_state", "SAFE", "expected result=NOT_SAFE"),
    ("R6-OWNER", "test_R6_claim_owner_change_invalidates_safe_state", "SAFE", "expected result=NOT_SAFE"),
    ("R6-SCHEDULER", "test_R6_scheduler_disable_invalidates_safe_state", "SAFE", "expected result=NOT_SAFE"),
    ("R6-HEAD", "test_R6_remote_head_advance_invalidates_safe_state", "SAFE", "expected result=NOT_SAFE"),

    ("R10-ZERO", "test_R10_zero_slots_is_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R10-ONE", "test_R10_one_local_safe_slot_is_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R10-TWO", "test_R10_two_local_safe_slots_are_safe", "NOT_SAFE", "expected result=SAFE"),
    ("R10-NOT-SAFE", "test_R10_one_not_safe_slot_blocks_aggregate_safe", "SAFE", "one NOT_SAFE slot must prevent aggregate SAFE"),
    ("R10-ERROR", "test_R10_one_error_slot_makes_aggregate_error", "SAFE", "expected result=ERROR"),
    ("R10-NON-LOCAL", "test_R10_non_local_dependent_slot_does_not_block_shutdown", "NOT_SAFE", "expected result=SAFE"),
]

base_env = dict(os.environ)
base_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"


def run_one(case_id, fn, *, override=None, expected):
    env = dict(base_env)
    env.pop("WHD_POWER_OFF_GATE_OVERRIDE", None)
    if override == "SAFE":
        env["WHD_POWER_OFF_GATE_OVERRIDE"] = str(FAKE_SAFE)
    elif override == "NOT_SAFE":
        env["WHD_POWER_OFF_GATE_OVERRIDE"] = str(FAKE_NOT_SAFE)

    nodeid = f"{TEST}::{fn}"
    cmd = ["python", "-m", "pytest", "-q", "--tb=short", nodeid]
    p = subprocess.run(
        cmd, cwd=r"C:\Users\Public", env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=15,
    )
    return {
        "case_id": case_id,
        "nodeid": nodeid,
        "override": override,
        "command": (
            "$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; "
            + (
                f"$env:WHD_POWER_OFF_GATE_OVERRIDE='{FAKE_SAFE if override == 'SAFE' else FAKE_NOT_SAFE}'; "
                if override else ""
            )
            + "Set-Location C:\\Users\\Public; "
            + " ".join(cmd)
        ),
        "expected_failure_substring": expected,
        "exit_code": p.returncode,
        "expected_failure_observed": expected in p.stdout,
        "raw_output": p.stdout,
        "raw_output_sha256": hashlib.sha256(p.stdout.encode("utf-8")).hexdigest(),
    }


current = [
    run_one(
        cid, fn,
        override=None,
        expected="missing production owner tools/workstation_poweroff_gate.py",
    )
    for cid, fn, _, _ in cases
]
adversarial = [
    run_one(cid, fn, override=fake, expected=expected)
    for cid, fn, fake, expected in cases
]


def render(records):
    parts = []
    for r in records:
        parts.append(
            f"===== {r['case_id']} =====\n"
            f"NODEID: {r['nodeid']}\n"
            f"OVERRIDE: {r['override']}\n"
            f"COMMAND: {r['command']}\n"
            f"EXPECTED_FAILURE_SUBSTRING: {r['expected_failure_substring']}\n"
            f"EXIT_CODE: {r['exit_code']}\n"
            f"EXPECTED_FAILURE_OBSERVED: {r['expected_failure_observed']}\n"
            f"{r['raw_output']}\n"
        )
    return "\n".join(parts)


RAW.write_text(render(current), encoding="utf-8")
ANTI_RAW.write_text(render(adversarial), encoding="utf-8")

for record in current + adversarial:
    del record["raw_output"]

manifest = {
    "schema": "WHD_REQUIREMENT_RED_PROBE_EVIDENCE_V3",
    "status": "PROBE_EXECUTED_DURABLE_ANCHOR_PENDING",
    "target_ref": "cleanup/2d-3d-sync",
    "target_sha": "87eb35b3f5ae5211673c941cb56c4c4343fa5405",
    "spec_version": "v1.4",
    "behavioral_case_count": len(cases),
    "probe_path": str(TEST),
    "probe_sha256": hashlib.sha256(TEST.read_bytes()).hexdigest(),
    "runner_path": str(Path(__file__)),
    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "fake_always_safe_path": str(FAKE_SAFE),
    "fake_always_safe_sha256": hashlib.sha256(FAKE_SAFE.read_bytes()).hexdigest(),
    "fake_always_not_safe_path": str(FAKE_NOT_SAFE),
    "fake_always_not_safe_sha256": hashlib.sha256(FAKE_NOT_SAFE.read_bytes()).hexdigest(),
    "current_raw_path": str(RAW),
    "current_raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
    "adversarial_raw_path": str(ANTI_RAW),
    "adversarial_raw_sha256": hashlib.sha256(ANTI_RAW.read_bytes()).hexdigest(),
    "all_current_behavioral_cases_red": all(r["exit_code"] == 1 for r in current),
    "all_current_expected_failures_observed": all(r["expected_failure_observed"] for r in current),
    "all_adversarial_cases_red": all(r["exit_code"] == 1 for r in adversarial),
    "all_adversarial_expected_failures_observed": all(r["expected_failure_observed"] for r in adversarial),
    "current_records": current,
    "adversarial_records": adversarial,
    "coverage": {
        "T3": 5,
        "T4": 6,
        "T5": 3,
        "T6": 8,
        "T10": 6,
    },
    "durable_anchor": "PENDING_USER_RED_APPROVAL_THEN_REPOSITORY_OWNED_EVIDENCE",
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "behavioral_case_count": manifest["behavioral_case_count"],
    "coverage": manifest["coverage"],
    "all_current_behavioral_cases_red": manifest["all_current_behavioral_cases_red"],
    "all_current_expected_failures_observed": manifest["all_current_expected_failures_observed"],
    "all_adversarial_cases_red": manifest["all_adversarial_cases_red"],
    "all_adversarial_expected_failures_observed": manifest["all_adversarial_expected_failures_observed"],
    "probe_sha256": manifest["probe_sha256"],
    "runner_sha256": manifest["runner_sha256"],
    "fake_always_safe_sha256": manifest["fake_always_safe_sha256"],
    "fake_always_not_safe_sha256": manifest["fake_always_not_safe_sha256"],
    "current_raw_sha256": manifest["current_raw_sha256"],
    "adversarial_raw_sha256": manifest["adversarial_raw_sha256"],
}, ensure_ascii=False, indent=2))
