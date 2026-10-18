"""Opt-in diagnostic of Python heap retention versus process RSS in WHD Tk runs.

This deliberately changes allocator timing: do NOT use memory-traced wall times
as an ordinary latency baseline. It never changes manufacturing or GUI data.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path
import tracemalloc


class PythonMemoryAttributionProbe:
    def __init__(self, *, cycles: int, rss_reader):
        if cycles < 4:
            raise ValueError("diagnostic requires at least 4 return-to-3D cycles")
        self.rss_reader = rss_reader
        self.cycles = cycles
        self.warm_at = max(3, min(10, cycles // 3))
        self.count = 0
        self.checkpoints = {}
        self.snapshots = {}
        self._owns_tracer = not tracemalloc.is_tracing()
        if self._owns_tracer:
            tracemalloc.start(5)

    def capture(self, row):
        if row.get("operation") != "return_3d" or row.get("status") != "ok":
            return
        self.count += 1
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        row["python_memory_probe"] = {
            "return_3d_cycle": self.count,
            "python_heap_traced_bytes_after_gc": int(current),
            "python_heap_traced_peak_bytes": int(peak),
            "rss_bytes_after_forced_gc": self.rss_reader(),
            "gc_tracked_object_count": len(gc.get_objects()),
            "diagnostic_only_not_comparable_latency": True,
        }
        if self.count in (self.warm_at, self.cycles):
            self.checkpoints[self.count] = dict(row["python_memory_probe"])
            self.snapshots[self.count] = tracemalloc.take_snapshot()

    def finalize(self, path):
        target = Path(path)
        report = {
            "kind": "PYTHON_TRACEMALLOC_GC_DIAGNOSTIC_NOT_GUI_LATENCY_BASELINE",
            "cycles_seen": self.count,
            "expected_cycles": self.cycles,
            "warm_cycle": self.warm_at,
            "checkpoints": self.checkpoints,
            "complete": self.count == self.cycles and len(self.snapshots) == 2,
            "windows_uat": "PENDING",
        }
        if len(self.snapshots) == 2:
            earlier, later = self.snapshots[self.warm_at], self.snapshots[self.cycles]
            diff = later.compare_to(earlier, "filename")
            report["tracemalloc_delta_total_bytes"] = sum(s.size_diff for s in diff)
            report["top_python_heap_file_growth"] = [
                {"file": str(stat.traceback[0].filename),
                 "size_diff_bytes": stat.size_diff,
                 "count_diff": stat.count_diff}
                for stat in sorted(diff, key=lambda s: s.size_diff, reverse=True)[:30]
            ]
            a, b = self.checkpoints[self.warm_at], self.checkpoints[self.cycles]
            for field in (
                "python_heap_traced_bytes_after_gc",
                "rss_bytes_after_forced_gc",
                "gc_tracked_object_count",
            ):
                if a[field] is not None and b[field] is not None:
                    report[field + "_delta"] = b[field] - a[field]
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._owns_tracer:
            tracemalloc.stop()
        return report
