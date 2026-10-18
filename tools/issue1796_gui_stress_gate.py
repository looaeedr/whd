"""#1796: strict validation of measured real-Tk GUI stress evidence.

Only validate counters emitted by tools/phase6_gui_perf_stress.py.
Do not conflate Linux Xvfb with Windows manual UAT or physical 3D collision.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

EXPECTED = (
    "whdt_burst_20_each",
    "fw_burst_20",
    "part_switch_cycle",
    "head_tail_10",
    "preview_toggle_5",
)
LIMITS = {
    "whdt_burst_20_each": {
        "calculation": 4, "manufacturing": 4, "scene_rebuild": 4,
        "render": 4, "publish": 4, "echo": 0, "dxf_disk_read": 0,
    },
    "fw_burst_20": {
        "calculation": 1, "manufacturing": 1, "scene_rebuild": 1,
        "render": 1, "echo": 0, "dxf_disk_read": 0,
    },
    "part_switch_cycle": {
        "calculation": 1, "manufacturing": 1, "scene_rebuild": 1,
        "render": 12, "echo": 0, "dxf_disk_read": 0,
    },
    "head_tail_10": {
        "calculation": 0, "manufacturing": 0, "scene_rebuild": 0,
        "render": 10, "echo": 0, "dxf_disk_read": 0,
    },
    "preview_toggle_5": {
        "calculation": 0, "manufacturing": 0, "scene_rebuild": 0,
        "render": 5, "echo": 0, "dxf_disk_read": 0,
    },
}


def validate(report: dict) -> dict:
    """Return explicit PASS/FAIL result; never infer an absent measurement as zero."""
    failures: list[str] = []
    observed = {}
    rows = report.get("gui_segments")
    if not isinstance(rows, list):
        rows = []
        failures.append("GUI_SEGMENTS_MISSING")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("segment"), str):
            failures.append("INVALID_GUI_SEGMENT")
            continue
        name = row["segment"]
        if name in observed:
            failures.append(f"DUPLICATE_SEGMENT:{name}")
            continue
        observed[name] = row
        if name not in LIMITS:
            failures.append(f"UNEXPECTED_SEGMENT:{name}")
            continue
        for key, maximum in LIMITS[name].items():
            value = row.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                failures.append(f"{name}:{key}:MISSING_OR_INVALID")
            elif value > maximum:
                failures.append(f"{name}:{key}:{value}_EXCEEDS_{maximum}")
        elapsed = row.get("wall_time")
        if (not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool)
                or not math.isfinite(elapsed) or elapsed <= 0):
            failures.append(f"{name}:INVALID_WALL_TIME")
    for name in EXPECTED:
        if name not in observed:
            failures.append(f"MISSING_SEGMENT:{name}")

    cache_rows = report.get("cache_segments")
    cache = {}
    if not isinstance(cache_rows, list):
        cache_rows = []
        failures.append("CACHE_SEGMENTS_MISSING")
    for row in cache_rows:
        if not isinstance(row, dict) or not isinstance(row.get("segment"), str):
            failures.append("INVALID_CACHE_SEGMENT")
            continue
        name = row["segment"]
        if name in cache:
            failures.append(f"DUPLICATE_CACHE_SEGMENT:{name}")
        else:
            cache[name] = row
    warm = cache.get("warm_cache_20")
    reload = cache.get("force_reload")
    if warm is None:
        failures.append("WARM_CACHE_MISSING")
    else:
        if warm.get("dxf_disk_read") != 1 or warm.get("additional_after_first") != 0:
            failures.append("CACHE_UNEXPECTED_REREAD")
    if reload is None:
        failures.append("FORCE_RELOAD_MISSING")
    elif reload.get("dxf_disk_read") != 1:
        failures.append("FORCE_RELOAD_NOT_EXERCISED")
    if set(cache) - {"warm_cache_20", "force_reload"}:
        failures.append("UNEXPECTED_CACHE_SEGMENTS")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "verified_segments": sorted(observed),
        "measurement_scope": (
            "Linux/Xvfb, real Tk event path and temporary DXF cache calls. "
            "Not Windows UAT, all-family parity, or full Save/Reload manufacturing certification."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = validate(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
