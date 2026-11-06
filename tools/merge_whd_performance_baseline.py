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



def combine_isolated_sample_baselines(
    shards: Mapping[tuple[int, int], Mapping[str, object]],
    *,
    head_sha: str,
    samples: int = 3,
    cycles: int = 5,
) -> dict[str, object]:
    """Combine six independently measured workers, never a synthetic sample.

    Each sample comes from one isolated GitHub-hosted runner. Within-worker
    comparisons are authoritative; cross-runner latency variation is annotated.
    Older per-Bay aggregate inputs still use combine_baselines unchanged.
    """
    if samples < 1 or cycles < 1:
        raise ValueError("BASELINE_EXPECTATION_INVALID")
    expected = {(bay, sample) for bay in BAY_SCOPES for sample in range(samples)}
    if set(shards) != expected:
        raise ValueError("BASELINE_SAMPLE_SHARDS_INCOMPLETE")

    bay_results: dict[int, dict[str, object]] = {}
    sample_environments: dict[str, str] = {}
    for bay in BAY_SCOPES:
        all_rows: list[dict[str, object]] = []
        all_workers: list[dict[str, object]] = []
        first_metadata: dict[str, object] | None = None
        for sample in range(samples):
            source = shards[(bay, sample)]
            info = source.get("metadata")
            if (not isinstance(info, Mapping)
                    or info.get("source_sha") != head_sha
                    or info.get("bay_scope") != bay
                    or info.get("sample_index") != sample
                    or info.get("samples") != samples
                    or info.get("cycles") != cycles):
                raise ValueError("BASELINE_SAMPLE_SCOPE_OR_REVISION_MISMATCH")
            if first_metadata is None:
                first_metadata = deepcopy(dict(info))
            elif (info.get("harness_sha256") != first_metadata.get("harness_sha256")
                  or info.get("config_sha256") != first_metadata.get("config_sha256")):
                raise ValueError("BASELINE_HARNESS_OR_CONFIG_MISMATCH")

            workers = info.get("workers")
            if (not isinstance(workers, list) or len(workers) != 1
                    or not isinstance(workers[0], Mapping)
                    or workers[0].get("bays") != bay
                    or workers[0].get("sample") != sample
                    or workers[0].get("returncode") != 0):
                raise ValueError("BASELINE_SAMPLE_WORKER_INVALID")

            rows = source.get("rows")
            if (not isinstance(rows, list) or not rows
                    or any(
                        not isinstance(row, dict)
                        or row.get("bays") != bay
                        or row.get("worker_sample") != sample
                        or row.get("status") != "ok"
                        for row in rows
                    )):
                raise ValueError("BASELINE_SAMPLE_MEASUREMENTS_INVALID")
            if source.get("summary") != summarize(rows):
                raise ValueError("BASELINE_SAMPLE_SUMMARY_MISMATCH")
            all_workers.extend(deepcopy(workers))
            all_rows.extend(deepcopy(rows))
            sample_environments[f"{bay}-{sample}"] = (
                f"whd-issue1816-tk-baseline-b{bay}-s{sample}/environment.txt"
            )

        assert first_metadata is not None
        first_metadata["workers"] = all_workers
        first_metadata["sample_index"] = None
        bay_results[bay] = {
            "metadata": first_metadata,
            "summary": summarize(all_rows),
            "rows": all_rows,
        }
    combined = combine_baselines(
        bay_results, head_sha=head_sha, samples=samples, cycles=cycles,
    )
    combined["metadata"]["independent_sample_runners"] = True
    combined["metadata"]["sample_environment_files"] = sample_environments
    combined["metadata"]["environment_files"] = {
        str(bay): sample_environments[f"{bay}-0"] for bay in BAY_SCOPES
    }
    combined["metadata"]["comparison_note"] = (
        "Each original Tk worker sample ran on an isolated cloud runner; "
        "compare wall-time within a worker only, and account for CPU variance "
        "when comparing across samples or Bays."
    )
    return combined

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--isolated-samples", action="store_true",
                        help="Merge one genuine artifact per Bay/sample from separate runners")
    args = parser.parse_args()
    root = args.input_dir
    data = {}
    if args.isolated_samples:
        for bay in BAY_SCOPES:
            for sample in range(args.samples):
                name = f"whd-issue1816-tk-baseline-b{bay}-s{sample}"
                path = root / name / f"baseline-b{bay}-s{sample}.json"
                data[(bay, sample)] = json.loads(path.read_text(encoding="utf-8"))
        result = combine_isolated_sample_baselines(
            data, head_sha=args.head_sha, samples=args.samples, cycles=args.cycles,
        )
    else:
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
