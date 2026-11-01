#!/usr/bin/env python3
"""Combine independently measured Tk Bay scopes; never synthesize timings.

1-Bay and 3-Bay samples must remain on separate runners. Merge is a strict
evidence validator, not a performance measurement or a manufacturing gate.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Mapping
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.whd_performance_baseline import memory_trends, summarize

BAY_SCOPES = (3, 1)


def combine_baselines(
    scopes: Mapping[int, Mapping[str, object]],
    *,
    head_sha: str,
    samples: int = 3,
    cycles: int = 5,
) -> dict[str, object]:
    """Accept exactly six real workers; refuse partial or cross-revision evidence."""
    if set(scopes) != set(BAY_SCOPES):
        raise ValueError("BASELINE_BAY_SCOPES_INCOMPLETE")
    if not head_sha or samples < 1 or cycles < 1:
        raise ValueError("BASELINE_EXPECTATION_INVALID")

    rows: list[dict[str, object]] = []
    workers: list[dict[str, object]] = []
    pending: set[str] = set()
    metadata = None
    for bay in BAY_SCOPES:
        result = scopes[bay]
        info = result.get("metadata")
        if not isinstance(info, Mapping):
            raise ValueError("BASELINE_METADATA_MISSING")
        if (info.get("source_sha") != head_sha
                or info.get("bay_scope") != bay
                or info.get("samples") != samples
                or info.get("cycles") != cycles):
            raise ValueError("BASELINE_SCOPE_OR_REVISION_MISMATCH")
        if metadata is None:
            metadata = deepcopy(dict(info))
        elif (info.get("harness_sha256") != metadata.get("harness_sha256")
              or info.get("config_sha256") != metadata.get("config_sha256")):
            raise ValueError("BASELINE_HARNESS_OR_CONFIG_MISMATCH")
        scope_workers = result.get("metadata", {}).get("workers")
        if (not isinstance(scope_workers, list)
                or len(scope_workers) != samples
                or {w.get("sample") for w in scope_workers if isinstance(w, Mapping)}
                   != set(range(samples))
                or any(not isinstance(w, Mapping) or w.get("bays") != bay
                       or w.get("returncode") != 0 for w in scope_workers)):
            raise ValueError("BASELINE_WORKERS_INCOMPLETE")
        scope_rows = result.get("rows")
        if (not isinstance(scope_rows, list) or not scope_rows
                or any(not isinstance(row, dict) or row.get("bays") != bay
                       or row.get("status") != "ok" for row in scope_rows)):
            raise ValueError("BASELINE_MEASUREMENTS_INCOMPLETE")
        if result.get("summary") != summarize(scope_rows):
            raise ValueError("BASELINE_SCOPE_SUMMARY_MISMATCH")
        workers.extend(deepcopy(scope_workers))
        rows.extend(deepcopy(scope_rows))
        pending.update(str(item) for item in (info.get("pending") or ()))

    assert metadata is not None
    metadata["workers"] = workers
    metadata["pending"] = sorted(pending)
    metadata["bay_scope"] = None
    metadata["independent_runners"] = True
    metadata["environment_files"] = {
        "3": "b3/environment.txt", "1": "b1/environment.txt",
    }
    metadata["comparison_note"] = (
        "Bay scopes ran on independent cloud runners; cross-Bay timing "
        "differences also include runner variation."
    )
    return {
        "metadata": metadata,
        "summary": summarize(rows),
        "memory_trends": memory_trends(rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()
    root = args.input_dir
    data = {}
    for bay in BAY_SCOPES:
        path = root / f"b{bay}" / f"baseline-b{bay}.json"
        data[bay] = json.loads(path.read_text(encoding="utf-8"))
    result = combine_baselines(
        data, head_sha=args.head_sha, samples=args.samples, cycles=args.cycles,
    )
    (root / "baseline.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(
        "BASELINE_PARALLEL_EVIDENCE_VERIFIED"
        f" workers={len(result['metadata']['workers'])}"
        f" rows={len(result['rows'])} scopes=3,1",
        flush=True,
    )


if __name__ == "__main__":
    main()
