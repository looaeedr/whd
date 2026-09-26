"""Deliberately wrong anti-false-green fixture.
Contains the expected vocabulary but implements the wrong behavior: always SAFE / always valid.
Keywords:
WHD_POWER_OFF_GATE_V1
PENDING_GUARD_TRANSACTION GUARD_RECONCILIATION_REQUIRED GUARD_AMBIGUOUS
CLAIM_OWNER_NOT_SCHEDULER SCHEDULER_ENABLEMENT_UNVERIFIED CHECKPOINT_HEAD_MISMATCH
SAFE NOT_SAFE ERROR
poweroff_request_id evidence_revision active_slots
LOCAL_MUTATION_IN_PROGRESS LOCAL_MACHINE_UNREACHABLE
"""
import argparse
import json

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)
e = sub.add_parser("evaluate")
e.add_argument("--snapshot", required=True)
v = sub.add_parser("validate-safe")
v.add_argument("--receipt", required=True)
v.add_argument("--request-id", required=True)
v.add_argument("--evidence-revision", required=True)
a = p.parse_args()

if a.cmd == "evaluate":
    snap = json.load(open(a.snapshot, "r", encoding="utf-8"))
    print(json.dumps({
        "schema": "WHD_POWER_OFF_GATE_V1",
        "result": "SAFE",
        "reason": "FAKE_ALWAYS_SAFE",
        "poweroff_request_id": snap.get("poweroff_request_id"),
        "evidence_revision": snap.get("evidence_revision"),
        "active_slots": [s.get("slot_id") for s in snap.get("slots", [])],
    }))
else:
    print(json.dumps({
        "schema": "WHD_POWER_OFF_SAFE_VALIDATION_V1",
        "valid": True,
        "reason": "VALID",
    }))
