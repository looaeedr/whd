#!/usr/bin/env python3
"""#362 Phase 2 final A/B acceptance classifier."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE = "7a8b87f8cbb50a34c5038aa196fa137b301702a4"
CANDIDATE = "15630860b96fbd3045c6895c02fb6155c7d42e76"
EXPECTED_LABELS = {
    "baseline-headless",
    "candidate-headless",
    "baseline-xvfb",
    "candidate-xvfb",
}


def _load(root: Path) -> dict[str, dict]:
    found = {}
    for path in root.rglob("result.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        label = payload["label"]
        if label in found:
            raise RuntimeError(f"DUPLICATE_RESULT:{label}")
        found[label] = payload
    missing = sorted(EXPECTED_LABELS - set(found))
    extra = sorted(set(found) - EXPECTED_LABELS)
    if missing or extra:
        raise RuntimeError(f"RESULT_SET_MISMATCH missing={missing} extra={extra}")
    return found


def _nodes(payload: dict, field: str) -> set[str]:
    value = payload.get(field, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise RuntimeError(f"INVALID_{field.upper()}:{payload.get('label')}")
    return set(value)


def _assert_identity(label: str, payload: dict, sha: str) -> None:
    if payload.get("sha") != sha:
        raise RuntimeError(f"SHA_MISMATCH:{label}:{payload.get('sha')}:{sha}")
    if payload.get("protected_drift"):
        raise RuntimeError(f"PROTECTED_DRIFT:{label}")
    if payload.get("harness_error"):
        raise RuntimeError(f"HARNESS_ERROR:{label}:{payload['harness_error']}")
    if not isinstance(payload.get("collected"), int) or payload["collected"] <= 0:
        raise RuntimeError(f"INVALID_COLLECTION:{label}")


def classify(root: Path) -> dict:
    items = _load(root)
    for label in ("baseline-headless", "baseline-xvfb"):
        _assert_identity(label, items[label], BASELINE)
    for label in ("candidate-headless", "candidate-xvfb"):
        _assert_identity(label, items[label], CANDIDATE)

    out = {
        "baseline_sha": BASELINE,
        "candidate_sha": CANDIDATE,
        "modes": {},
        "decision": "GREEN",
    }

    for mode in ("headless", "xvfb"):
        base = items[f"baseline-{mode}"]
        cand = items[f"candidate-{mode}"]
        base_failed = _nodes(base, "failed_nodes")
        cand_failed = _nodes(cand, "failed_nodes")
        base_errors = _nodes(base, "error_nodes")
        cand_errors = _nodes(cand, "error_nodes")
        new_failed = sorted(cand_failed - base_failed)
        new_errors = sorted(cand_errors - base_errors)

        # Phase 2 adds tests; final candidate must not reduce the total executed
        # collection versus the fixed Phase 1 baseline.
        if cand["collected"] < base["collected"]:
            raise RuntimeError(
                f"COLLECTION_SHRINK:{mode}:baseline={base['collected']}:candidate={cand['collected']}"
            )
        if new_failed:
            raise RuntimeError(f"NEW_{mode.upper()}_FAILURES:{new_failed}")
        if new_errors:
            raise RuntimeError(f"NEW_{mode.upper()}_ERRORS:{new_errors}")

        out["modes"][mode] = {
            "baseline_collected": base["collected"],
            "candidate_collected": cand["collected"],
            "baseline_failed": sorted(base_failed),
            "candidate_failed": sorted(cand_failed),
            "baseline_errors": sorted(base_errors),
            "candidate_errors": sorted(cand_errors),
            "new_failures": new_failed,
            "new_errors": new_errors,
            "baseline_skipped": len(_nodes(base, "skipped_nodes")),
            "candidate_skipped": len(_nodes(cand, "skipped_nodes")),
        }

    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: issue362_phase2_final_acceptance.py <artifact-root> <out-json>")
    result = classify(Path(argv[1]))
    Path(argv[2]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("NEW_HEADLESS=[]")
    print("NEW_XVFB=[]")
    print("PROTECTED_DRIFT=0")
    print("ISSUE362_AB_DECISION=GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
