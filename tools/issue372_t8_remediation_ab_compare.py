#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def phase(row, key):
    value = row.get(key)
    return value.get("outcome") if isinstance(value, dict) else None


def summarize(report):
    outcomes = {}
    failed = set()
    errors = set()
    for row in report.get("tests") or ():
        node = str(row.get("nodeid") or "")
        if not node:
            continue
        outcome = str(row.get("outcome") or "unknown")
        outcomes[node] = outcome
        if phase(row, "setup") == "failed" or phase(row, "teardown") == "failed":
            errors.add(node)
        elif phase(row, "call") == "failed" or outcome == "failed":
            failed.add(node)
    for row in report.get("collectors") or ():
        if str(row.get("outcome") or "") == "failed":
            errors.add("COLLECT::" + str(row.get("nodeid") or "<collection>"))
    return {
        "nodes": sorted(outcomes),
        "outcomes": outcomes,
        "failed": sorted(failed),
        "errors": sorted(errors),
    }


def compare_lane(name, baseline_report, candidate_report):
    baseline = summarize(baseline_report)
    candidate = summarize(candidate_report)
    bn = set(baseline["nodes"])
    cn = set(candidate["nodes"])
    baseline_bad = set(baseline["failed"]) | set(baseline["errors"])
    candidate_bad = set(candidate["failed"]) | set(candidate["errors"])
    new_bad = sorted(candidate_bad - baseline_bad)
    missing_nodes = sorted(bn - cn)
    extra_nodes = sorted(cn - bn)
    extra_bad = sorted(set(extra_nodes) & candidate_bad)
    improvements = sorted(
        n for n in bn & cn
        if baseline["outcomes"].get(n) == "failed"
        and candidate["outcomes"].get(n) in {"passed", "skipped"}
    )
    return {
        "lane": name,
        "baseline": baseline,
        "candidate": candidate,
        "missing_nodes": missing_nodes,
        "extra_nodes": extra_nodes,
        "extra_bad": extra_bad,
        "improvements": improvements,
        "new_failed": sorted(set(candidate["failed"]) - set(baseline["failed"]) - set(baseline["errors"])),
        "new_errors": sorted(set(candidate["errors"]) - set(baseline["errors"]) - set(baseline["failed"])),
        "new_bad": new_bad,
    }


def digest(path):
    return Path(path).read_text(encoding="utf-8").strip()


def protected(prefix, args):
    bb = digest(getattr(args, f"baseline_{prefix}_protected_before"))
    ba = digest(getattr(args, f"baseline_{prefix}_protected_after"))
    cb = digest(getattr(args, f"candidate_{prefix}_protected_before"))
    ca = digest(getattr(args, f"candidate_{prefix}_protected_after"))
    return {
        "baseline_runtime_drift": bb != ba,
        "candidate_runtime_drift": cb != ca,
        "source_drift": bb != cb,
    }


def main():
    parser = argparse.ArgumentParser()
    for lane in ("headless", "xvfb"):
        parser.add_argument(f"--baseline-{lane}", required=True)
        parser.add_argument(f"--candidate-{lane}", required=True)
        for side in ("baseline", "candidate"):
            for when in ("before", "after"):
                parser.add_argument(f"--{side}-{lane}-protected-{when}", required=True)
    parser.add_argument("--baseline-event-order", required=True)
    parser.add_argument("--candidate-event-order", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    headless = compare_lane("headless", load(args.baseline_headless), load(args.candidate_headless))
    xvfb = compare_lane("xvfb", load(args.baseline_xvfb), load(args.candidate_xvfb))
    protected_state = {
        "headless": protected("headless", args),
        "xvfb": protected("xvfb", args),
    }
    protected_drift = any(v for lane in protected_state.values() for v in lane.values())
    baseline_event = load(args.baseline_event_order)
    candidate_event = load(args.candidate_event_order)
    event_delta = baseline_event != candidate_event

    classifier = {
        "NEW_RELEVANT_HEADLESS": headless["new_bad"],
        "NEW_RELEVANT_XVFB": xvfb["new_bad"],
        "MISSING_BASELINE_HEADLESS_NODES": headless["missing_nodes"],
        "MISSING_BASELINE_XVFB_NODES": xvfb["missing_nodes"],
        "EXTRA_BAD_HEADLESS_NODES": headless["extra_bad"],
        "EXTRA_BAD_XVFB_NODES": xvfb["extra_bad"],
        "PROTECTED_DRIFT": 1 if protected_drift else 0,
        "UNEXPLAINED_EVENT_ORDER_DELTA": 1 if event_delta else 0,
    }
    decision = "GREEN" if (
        not classifier["NEW_RELEVANT_HEADLESS"]
        and not classifier["NEW_RELEVANT_XVFB"]
        and not classifier["MISSING_BASELINE_HEADLESS_NODES"]
        and not classifier["MISSING_BASELINE_XVFB_NODES"]
        and not classifier["EXTRA_BAD_HEADLESS_NODES"]
        and not classifier["EXTRA_BAD_XVFB_NODES"]
        and classifier["PROTECTED_DRIFT"] == 0
        and classifier["UNEXPLAINED_EVENT_ORDER_DELTA"] == 0
    ) else "RED"

    payload = {
        "schema": "WHD_ISSUE372_T8_REMEDIATION_AB_V1",
        "decision": decision,
        "headless": headless,
        "xvfb": xvfb,
        "protected": protected_state,
        "event_order": {"baseline": baseline_event, "candidate": candidate_event},
        "classifier": classifier,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": decision,
        "headless_baseline_nodes": len(headless["baseline"]["nodes"]),
        "headless_candidate_nodes": len(headless["candidate"]["nodes"]),
        "xvfb_baseline_nodes": len(xvfb["baseline"]["nodes"]),
        "xvfb_candidate_nodes": len(xvfb["candidate"]["nodes"]),
        "headless_improvements": headless["improvements"],
        "xvfb_improvements": xvfb["improvements"],
        **classifier,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    assert decision == "GREEN", classifier
    print("ISSUE372_T8_REMEDIATION_AB_DECISION=GREEN")


if __name__ == "__main__":
    main()
