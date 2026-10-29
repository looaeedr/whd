"""Exact canonical per-file profiling; never expand partial ::node selections.

This is a timing experiment, NOT an alternative acceptance gate. The workflow
still has to pass its own complete file inventory and reject any non-green case.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

from tools.product_ci_regression import (
    PYTEST_PATHS, ROOT, _pytest_command, _tracked_invariants,
    _run_bridge_guard, _source_authority_scan,
)


def file_inventory() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Canonical whole-file ownership, preserving each *existing* selector."""
    if len(set(PYTEST_PATHS)) != len(PYTEST_PATHS):
        raise ValueError("duplicate canonical selector")
    grouped: dict[str, list[str]] = {}
    for selector in PYTEST_PATHS:
        filename = selector.split("::", 1)[0]
        if not filename.startswith("tests/") or not filename.endswith(".py"):
            raise ValueError(f"invalid canonical selector: {selector}")
        if not (ROOT / filename).is_file():
            raise ValueError(f"missing canonical test file: {filename}")
        grouped.setdefault(filename, []).append(selector)
    inventory = tuple((path, tuple(selectors)) for path, selectors in grouped.items())
    if sum(len(selectors) for _, selectors in inventory) != len(PYTEST_PATHS):
        raise ValueError("file inventory dropped canonical selectors")
    return inventory


def matrix_batch(batch: int) -> list[int]:
    if batch not in (0, 1):
        raise ValueError("invalid batch")
    inventory = file_inventory()
    split = (len(inventory) + 1) // 2
    return list(range(0, split)) if batch == 0 else list(range(split, len(inventory)))


def run_file(index: int, output: Path) -> int:
    inventory = file_inventory()
    if not (0 <= index < len(inventory)):
        raise ValueError(f"invalid file index: {index}")
    filename, selectors = inventory[index]
    before = _tracked_invariants()
    _source_authority_scan()
    _run_bridge_guard()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = output.with_suffix(".xml")
    print(f"WHD_FILE_PROFILE_START index={index} path={filename} selectors={len(selectors)}", flush=True)
    start = time.perf_counter()
    try:
        rc = subprocess.call(_pytest_command(report, selectors), cwd=ROOT, timeout=900)
    except subprocess.TimeoutExpired:
        rc = 124
    duration = round(time.perf_counter() - start, 3)
    cases = []
    if report.is_file():
        cases = ET.parse(report).getroot().findall(".//testcase")
    status = "success" if (
        rc == 0 and cases and all(
            not any(case.find(tag) is not None for tag in ("skipped", "error", "failure"))
            for case in cases
        )
    ) else "failure"
    after = _tracked_invariants()
    if before != after:
        status = "failure"
        print("WHD_FILE_PROFILE_TRACKED_INVARIANTS_CHANGED", flush=True)
    data = {
        "index": index, "file": filename, "selectors": list(selectors),
        "test_cases": len(cases), "elapsed_seconds": duration,
        "status": status, "pytest_return_code": rc,
        "tested_sha": os.environ.get("GITHUB_SHA", ""),
    }
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WHD_FILE_PROFILE_{status.upper()} index={index} file={filename} "
          f"cases={len(cases)} seconds={duration}", flush=True)
    return 0 if status == "success" else 1


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _span(first: str | None, last: str | None) -> float | None:
    a, b = _time(first), _time(last)
    return round((b - a).total_seconds(), 3) if a and b else None


def _all_jobs(repository: str, run_id: int, token: str) -> list[dict]:
    if not token:
        raise ValueError("GitHub API token required to produce the timing summary")
    jobs: list[dict] = []
    page = 1
    while True:
        url = (f"https://api.github.com/repos/{repository}/actions/runs/"
               f"{run_id}/jobs?per_page=100&page={page}")
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.load(response)
        part = payload.get("jobs", [])
        jobs.extend(part)
        if len(part) < 100:
            break
        page += 1
    return jobs


def _peak_running(rows: list[dict]) -> int:
    events = []
    for row in rows:
        if row.get("start") and row.get("end"):
            events.extend(((row["start"], 1), (row["end"], -1)))
    simultaneous = peak = 0
    for _, change in sorted(events, key=lambda event: (event[0], event[1])):
        simultaneous += change
        peak = max(peak, simultaneous)
    return peak


def summarize(repository: str, run_id: int, token: str, dest: Path) -> int:
    inventory = file_inventory()
    jobs = _all_jobs(repository, run_id, token)
    by_index: dict[int, dict] = {}
    for job in jobs:
        name = job.get("name", "")
        if not name.startswith(("Profile A (", "Profile B (")):
            continue
        try:
            index = int(name.split("(", 1)[1].split(")", 1)[0])
        except ValueError as exc:
            raise ValueError(f"bad job name: {name}") from exc
        if index in by_index:
            raise ValueError(f"duplicate profiling job: {index}")
        by_index[index] = job

    rows = []
    for index, (filename, selectors) in enumerate(inventory):
        job = by_index.get(index, {})
        steps = [s for s in job.get("steps", [])
                 if s.get("name") == "Run exact file selectors"]
        if len(steps) > 1:
            raise ValueError(f"duplicate timing steps for file {index}")
        step = steps[0] if steps else {}
        rows.append({
            "index": index, "file": filename, "selector_count": len(selectors),
            "status": job.get("conclusion") or job.get("status") or "missing",
            "test_step_seconds": _span(step.get("started_at"), step.get("completed_at")),
            "runner_queue_seconds": _span(job.get("created_at"), job.get("started_at")),
            "job_seconds": _span(job.get("started_at"), job.get("completed_at")),
            "start": job.get("started_at"), "end": job.get("completed_at"),
            "job_url": job.get("html_url", ""),
        })
    dest.mkdir(parents=True, exist_ok=True)
    csv_path = dest / "per-file-timings.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    measured = [r for r in rows if r["test_step_seconds"] is not None]
    failed = [r for r in rows if r["status"] != "success"
              or r["test_step_seconds"] is None]
    sorted_rows = sorted(measured, key=lambda r: r["test_step_seconds"], reverse=True)
    peak = _peak_running(rows)
    summary = [
        "# WHD per-file CI timing profile",
        "",
        f"- Run: {run_id}; canonical file groups: {len(inventory)}",
        f"- Exact canonical selectors: {len(PYTEST_PATHS)}",
        f"- Timed files: {len(measured)}; non-green/missing: {len(failed)}",
        f"- Observed peak overlapping runner jobs: {peak}",
        "- Two 152-job matrices, each max-parallel=15 (configured cap 30).",
        "- test_step_seconds is GitHub's actual test-step wall-clock (seconds); "
        "queue and job total are separate columns. No file is expanded to "
        "unselected pytest nodes.",
        "",
        "## Slowest 30 files",
        "",
        "| File | Test step (s) | Queue (s) | Result |",
        "|---|---:|---:|---|",
    ]
    for row in sorted_rows[:30]:
        summary.append(f"| \`{row['file']}\` | {row['test_step_seconds']} | "
                       f"{row['runner_queue_seconds']} | {row['status']} |")
    (dest / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"WHD_FILE_PROFILE_SUMMARY files={len(inventory)} measured={len(measured)} "
          f"non_green={len(failed)} peak_running={peak} csv={csv_path}", flush=True)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    command = parser.add_subparsers(dest="command", required=True)
    matrices = command.add_parser("matrix")
    matrices.add_argument("--batch", type=int, choices=(0, 1), required=True)
    runner = command.add_parser("run")
    runner.add_argument("--index", type=int, required=True)
    runner.add_argument("--output", type=Path, required=True)
    summary = command.add_parser("summary")
    summary.add_argument("--repo", required=True)
    summary.add_argument("--run-id", required=True, type=int)
    summary.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "matrix":
        print(json.dumps(matrix_batch(args.batch), separators=(",", ":")))
        return 0
    if args.command == "run":
        return run_file(args.index, args.output)
    return summarize(args.repo, args.run_id, os.environ.get("GH_TOKEN", ""), args.out)


if __name__ == "__main__":
    raise SystemExit(main())
