from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.test_lane_policy import LANE_EXPRESSIONS, XVFB_UI_EXPRESSION


def _collect(expr: str | None) -> set[str]:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"]
    if expr:
        cmd.extend(["-m", expr])
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"pytest collection failed for expression {expr!r} with rc={proc.returncode}\n{proc.stdout}"
        )
    return {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }


def build_audit() -> dict[str, object]:
    full = _collect(None)
    lane_nodes = {lane: _collect(expr) for lane, expr in LANE_EXPRESSIONS.items()}
    lane_nodes["xvfb_ui"] = _collect(XVFB_UI_EXPRESSION)
    union: set[str] = set()
    for nodes in lane_nodes.values():
        union.update(nodes)
    return {
        "full_count": len(full),
        "union_count": len(union),
        "missing_from_union": sorted(full - union),
        "extra_in_union": sorted(union - full),
        "lanes": {name: len(nodes) for name, nodes in lane_nodes.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit pytest taxonomy lane collection coverage")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = build_audit()
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if result["missing_from_union"] or result["extra_in_union"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
