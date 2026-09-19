#!/usr/bin/env python3
"""#365 T1 task-scoped A/B classifier.

Compares existing workspace/navigation regression outcomes between the immutable
Phase 3 root baseline and one candidate.  The classifier is intentionally
fail-closed: assigned node sets, per-node outcomes, error sets, and protected
config/DXF digests must match exactly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _test_phase_outcome(row: dict, phase: str) -> str | None:
    value = row.get(phase)
    return value.get("outcome") if isinstance(value, dict) else None


def summarize(report: dict) -> dict:
    tests = list(report.get("tests") or ())
    outcomes: dict[str, str] = {}
    failed: set[str] = set()
    errors: set[str] = set()
    skipped: set[str] = set()

    for row in tests:
        nodeid = str(row.get("nodeid") or "")
        if not nodeid:
            continue
        outcome = str(row.get("outcome") or "unknown")
        outcomes[nodeid] = outcome
        call_outcome = _test_phase_outcome(row, "call")
        setup_outcome = _test_phase_outcome(row, "setup")
        teardown_outcome = _test_phase_outcome(row, "teardown")
        if outcome == "skipped":
            skipped.add(nodeid)
        if call_outcome == "failed":
            failed.add(nodeid)
        elif setup_outcome == "failed" or teardown_outcome == "failed":
            errors.add(nodeid)
        elif outcome == "failed":
            # Older pytest-json-report may omit phase detail.
            failed.add(nodeid)

    for row in list(report.get("collectors") or ()):
        if str(row.get("outcome") or "") == "failed":
            nodeid = str(row.get("nodeid") or "<collection>")
            errors.add(f"COLLECT::{nodeid}")

    return {
        "nodes": sorted(outcomes),
        "outcomes": outcomes,
        "failed": sorted(failed),
        "errors": sorted(errors),
        "skipped": sorted(skipped),
        "summary": dict(report.get("summary") or {}),
        "exitcode": report.get("exitcode"),
    }


def read_digest(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def compare_lane(name: str, baseline: dict, candidate: dict) -> dict:
    base = summarize(baseline)
    cand = summarize(candidate)
    base_nodes = set(base["nodes"])
    cand_nodes = set(cand["nodes"])
    missing = sorted(base_nodes - cand_nodes)
    extra = sorted(cand_nodes - base_nodes)
    changed = sorted(
        node for node in base_nodes & cand_nodes
        if base["outcomes"].get(node) != cand["outcomes"].get(node)
    )
    new_failed = sorted(set(cand["failed"]) - set(base["failed"]))
    new_errors = sorted(set(cand["errors"]) - set(base["errors"]))
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
        "new_failed": new_failed,
        "new_errors": new_errors,
        "exact_outcome_parity": not missing and not extra and not changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-headless", type=Path, required=True)
    parser.add_argument("--candidate-headless", type=Path, required=True)
    parser.add_argument("--baseline-xvfb", type=Path, required=True)
    parser.add_argument("--candidate-xvfb", type=Path, required=True)
    parser.add_argument("--baseline-protected-before", type=Path, required=True)
    parser.add_argument("--baseline-protected-after", type=Path, required=True)
    parser.add_argument("--candidate-protected-before", type=Path, required=True)
    parser.add_argument("--candidate-protected-after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    headless = compare_lane(
        "headless", _load(args.baseline_headless), _load(args.candidate_headless)
    )
    xvfb = compare_lane(
        "xvfb", _load(args.baseline_xvfb), _load(args.candidate_xvfb)
    )

    baseline_before = read_digest(args.baseline_protected_before)
    baseline_after = read_digest(args.baseline_protected_after)
    candidate_before = read_digest(args.candidate_protected_before)
    candidate_after = read_digest(args.candidate_protected_after)

    protected = {
        "baseline_before": baseline_before,
        "baseline_after": baseline_after,
        "candidate_before": candidate_before,
        "candidate_after": candidate_after,
        "baseline_runtime_drift": baseline_before != baseline_after,
        "candidate_runtime_drift": candidate_before != candidate_after,
        "source_drift": baseline_before != candidate_before,
    }
    protected_drift = any((
        protected["baseline_runtime_drift"],
        protected["candidate_runtime_drift"],
        protected["source_drift"],
    ))

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
        "schema": "WHD_ISSUE365_T1_AB_V1",
        "decision": decision,
        "headless": headless,
        "xvfb": xvfb,
        "protected": protected,
        "classifier": {
            "NEW_RELEVANT_HEADLESS": new_headless,
            "NEW_RELEVANT_XVFB": new_xvfb,
            "NEW_RELEVANT_ERRORS": new_errors,
            "PROTECTED_DRIFT": 1 if protected_drift else 0,
            "UNEXPLAINED_TASK_DELTA": 1 if unexplained else 0,
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
    print("ISSUE365_T1_AB_DECISION=GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
