#!/usr/bin/env python3
"""#368 T4 task-scoped A/B classifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def phase_outcome(row: dict, phase: str):
    value = row.get(phase)
    return value.get("outcome") if isinstance(value, dict) else None


def summarize(report: dict) -> dict:
    outcomes = {}
    failed = set()
    errors = set()
    skipped = set()
    for row in report.get("tests") or ():
        node = str(row.get("nodeid") or "")
        if not node:
            continue
        outcome = str(row.get("outcome") or "unknown")
        outcomes[node] = outcome
        if outcome == "skipped":
            skipped.add(node)
        if phase_outcome(row, "call") == "failed":
            failed.add(node)
        elif phase_outcome(row, "setup") == "failed" or phase_outcome(row, "teardown") == "failed":
            errors.add(node)
        elif outcome == "failed":
            failed.add(node)
    for row in report.get("collectors") or ():
        if str(row.get("outcome") or "") == "failed":
            errors.add("COLLECT::" + str(row.get("nodeid") or "<collection>"))
    return {
        "nodes": sorted(outcomes),
        "outcomes": outcomes,
        "failed": sorted(failed),
        "errors": sorted(errors),
        "skipped": sorted(skipped),
        "summary": dict(report.get("summary") or {}),
        "exitcode": report.get("exitcode"),
    }


def compare_lane(name: str, baseline: dict, candidate: dict) -> dict:
    base = summarize(baseline)
    cand = summarize(candidate)
    bnodes = set(base["nodes"])
    cnodes = set(cand["nodes"])
    missing = sorted(bnodes - cnodes)
    extra = sorted(cnodes - bnodes)
    changed = sorted(
        node for node in bnodes & cnodes
        if base["outcomes"].get(node) != cand["outcomes"].get(node)
    )
    return {
        "lane": name,
        "baseline": base,
        "candidate": cand,
        "missing_nodes": missing,
        "extra_nodes": extra,
        "changed_outcomes": [
            {
                "node": node,
                "baseline": base["outcomes"].get(node),
                "candidate": cand["outcomes"].get(node),
            }
            for node in changed
        ],
        "new_failed": sorted(set(cand["failed"]) - set(base["failed"])),
        "new_errors": sorted(set(cand["errors"]) - set(base["errors"])),
        "exact_outcome_parity": not missing and not extra and not changed,
    }


def digest(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def protected_lane(prefix: str, args) -> dict:
    bb = digest(getattr(args, f"baseline_{prefix}_protected_before"))
    ba = digest(getattr(args, f"baseline_{prefix}_protected_after"))
    cb = digest(getattr(args, f"candidate_{prefix}_protected_before"))
    ca = digest(getattr(args, f"candidate_{prefix}_protected_after"))
    return {
        "baseline_before": bb,
        "baseline_after": ba,
        "candidate_before": cb,
        "candidate_after": ca,
        "baseline_runtime_drift": bb != ba,
        "candidate_runtime_drift": cb != ca,
        "source_drift": bb != cb,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    for lane in ("headless", "xvfb"):
        p.add_argument(f"--baseline-{lane}", type=Path, required=True)
        p.add_argument(f"--candidate-{lane}", type=Path, required=True)
        p.add_argument(f"--baseline-{lane}-protected-before", type=Path, required=True)
        p.add_argument(f"--baseline-{lane}-protected-after", type=Path, required=True)
        p.add_argument(f"--candidate-{lane}-protected-before", type=Path, required=True)
        p.add_argument(f"--candidate-{lane}-protected-after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    headless = compare_lane("headless", load(args.baseline_headless), load(args.candidate_headless))
    xvfb = compare_lane("xvfb", load(args.baseline_xvfb), load(args.candidate_xvfb))
    protected = {
        "headless": protected_lane("headless", args),
        "xvfb": protected_lane("xvfb", args),
    }
    protected_drift = any(
        lane[key]
        for lane in protected.values()
        for key in ("baseline_runtime_drift", "candidate_runtime_drift", "source_drift")
    )

    new_headless = headless["new_failed"]
    new_xvfb = xvfb["new_failed"]
    new_errors = sorted(set(headless["new_errors"]) | set(xvfb["new_errors"]))
    unexplained = not (
        headless["exact_outcome_parity"] and xvfb["exact_outcome_parity"]
    )
    decision = "GREEN" if (
        not new_headless
        and not new_xvfb
        and not new_errors
        and not protected_drift
        and not unexplained
    ) else "RED"

    payload = {
        "schema": "WHD_ISSUE368_T4_AB_V1",
        "decision": decision,
        "headless": headless,
        "xvfb": xvfb,
        "protected": protected,
        "classifier": {
            "NEW_RELEVANT_HEADLESS": new_headless,
            "NEW_RELEVANT_XVFB": new_xvfb,
            "NEW_RELEVANT_ERRORS": new_errors,
            "PROTECTED_DRIFT": 1 if protected_drift else 0,
            "UNEXPLAINED_DIAGNOSTIC_DELTA": 1 if unexplained else 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": decision,
        "headless_nodes": len(headless["baseline"]["nodes"]),
        "headless_failed_baseline": len(headless["baseline"]["failed"]),
        "headless_failed_candidate": len(headless["candidate"]["failed"]),
        "xvfb_nodes": len(xvfb["baseline"]["nodes"]),
        "xvfb_failed_baseline": len(xvfb["baseline"]["failed"]),
        "xvfb_failed_candidate": len(xvfb["candidate"]["failed"]),
        **payload["classifier"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    assert decision == "GREEN", payload["classifier"]
    print("ISSUE368_T4_AB_DECISION=GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
