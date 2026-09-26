"""Deliberately wrong behavioral sentinel: always NOT_SAFE / always invalid."""
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
        "result": "NOT_SAFE",
        "reason": "FAKE_ALWAYS_NOT_SAFE",
        "poweroff_request_id": snap.get("poweroff_request_id"),
        "evidence_revision": snap.get("evidence_revision"),
        "active_slots": [s.get("slot_id") for s in snap.get("slots", []) if s.get("local_dependent")],
    }))
else:
    print(json.dumps({
        "schema": "WHD_POWER_OFF_SAFE_VALIDATION_V1",
        "valid": False,
        "reason": "FAKE_ALWAYS_INVALID",
    }))
