"""Audit WHD pytest lane collection coverage without executing test bodies."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.test_lane_policy import LANE_EXPRESSIONS, XVFB_UI_EXPRESSION


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_LANES = {
    **LANE_EXPRESSIONS,
    "xvfb_ui": XVFB_UI_EXPRESSION,
}


def _nodeids(output: str) -> set[str]:
    return {
        line.strip()
        for line in output.splitlines()
        if line.startswith("tests/") and "::" in line
    }


def collect(marker_expression: str | None = None) -> tuple[set[str], str]:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"]
    if marker_expression:
        cmd.extend(["-m", marker_expression])
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"collection failed rc={proc.returncode}:\n{proc.stdout}")
    if "PytestUnknownMarkWarning" in proc.stdout:
        raise RuntimeError(f"unknown pytest marker warning detected:\n{proc.stdout}")
    return _nodeids(proc.stdout), proc.stdout


def audit() -> dict[str, object]:
    full, _ = collect()
    lane_nodes: dict[str, set[str]] = {}
    for lane, expression in EXECUTION_LANES.items():
        nodes, _ = collect(expression)
        if not nodes:
            raise RuntimeError(f"required lane collected zero tests: {lane} ({expression})")
        lane_nodes[lane] = nodes

    owners: dict[str, list[str]] = {}
    for lane, nodes in lane_nodes.items():
        for node in nodes:
            owners.setdefault(node, []).append(lane)

    overlap = {node: lanes for node, lanes in owners.items() if len(lanes) != 1}
    union = set(owners)
    missing = sorted(full - union)
    extra = sorted(union - full)
    if overlap or missing or extra:
        raise RuntimeError(
            json.dumps(
                {"overlap": overlap, "missing": missing, "extra": extra},
                ensure_ascii=False,
                indent=2,
            )
        )

    return {
        "full_count": len(full),
        "union_count": len(union),
        "lane_counts": {lane: len(nodes) for lane, nodes in sorted(lane_nodes.items())},
        "lane_expressions": dict(sorted(EXECUTION_LANES.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
