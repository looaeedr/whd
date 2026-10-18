"""#1819 opt-in owner attribution: retainers first, not global slow tracing.

Only after the real GUI reaches a successful warm return-to-3D checkpoint,
begin one-frame tracemalloc; full-trace-from-process-start made real Tk geometry
calls exceed the GUI settle timeout and yielded zero owner checkpoints.
"""
from __future__ import annotations

from collections import Counter
import gc
import json
from pathlib import Path
import tracemalloc


_WATCHED = (
    "Figure", "Axes", "Axes3D", "FigureCanvasTkAgg", "LineCollection",
    "Poly3DCollection", "PhotoImage", "Toplevel",
    "ManufacturingResolveResult", "ResolvedManufacturingGeometry",
    "DrawingScene", "FinalSceneViewRequest", "ReceivingSettingsPreview2D",
)


def _len(value):
    try:
        return len(value)
    except (TypeError, ValueError):
        return None


def _cache_owners(owners):
    """Report concrete owner attributes without retaining live results."""
    result = {}
    for index, owner in enumerate(owners or ()):
        if owner is None:
            continue
        root = f"gui_owner_{index}:{type(owner).__name__}"
        attributes = vars(owner) if hasattr(owner, "__dict__") else {}
        for key, value in attributes.items():
            if key in (
                "_receiving_bay_preview_cache",
                "_authoritative_part_render_cache",
                "_phase6_manufacturing_cache_service",
                "_derived_cache_owner",
                "settings_panel",
                "_settings_page_cache",
                "_receiving_raw_inner_door_panel_history",
                "_receiving_raw_inner_door_frame_history",
                "_phase6_last_resolved_manufacturing_geometry",
                "_phase6_last_resolved_manufacturing_signature",
            ):
                if key == "settings_panel":
                    pages = getattr(value, "page_cache", {})
                    result[f"{root}.{key}.page_cache"] = _len(pages)
                    result[f"{root}.{key}.page_keys"] = tuple(str(k) for k in pages)
                    result[f"{root}.{key}.current_page"] = getattr(value, "current_page", None)
                elif key == "_phase6_manufacturing_cache_service":
                    result[f"{root}.{key}._entries"] = _len(getattr(value, "_entries", None))
                elif key == "_derived_cache_owner":
                    caches = getattr(value, "_caches", {})
                    for name, mapping in caches.items():
                        result[f"{root}.{key}._caches.{name}"] = _len(mapping)
                    for name in ("_receiving_exact_material_history",
                                 "_receiving_inner_door_panel_history"):
                        result[f"{root}.{key}.{name}"] = _len(getattr(value, name, None))
                elif key == "_phase6_last_resolved_manufacturing_geometry":
                    result[f"{root}.{key}"] = (type(value).__name__ if value is not None else None)
                else:
                    result[f"{root}.{key}"] = _len(value) if not isinstance(value, str) else value[:18]
    return result


def _tracked_type_counts():
    """Count real GC-tracked objects by fully qualified Python class."""
    counter = Counter(str(type(obj).__module__) + "." + str(type(obj).__name__) for obj in gc.get_objects())
    return dict(counter)


def _alive_object_counts():
    """Count surviving GC-tracked instances in the real process after GC."""
    counts = {key: 0 for key in _WATCHED}
    for obj in gc.get_objects():
        name = type(obj).__name__
        if name in counts:
            counts[name] += 1
    return {name: count for name, count in counts.items() if count}


class PythonMemoryAttributionProbe:
    def __init__(self, *, cycles: int, rss_reader, owners=None):
        if cycles < 4:
            raise ValueError("diagnostic requires at least 4 return-to-3D cycles")
        self.rss_reader = rss_reader
        self.cycles = cycles
        # Compare the same alternating 800/820 Bay width. Prior 3-vs-8
        # snapshots compared DIFFERENT physical geometry states.
        candidate = max(3, min(10, cycles // 3))
        if candidate % 2 != cycles % 2:
            candidate += 1
        self.warm_at = min(candidate, cycles - 2)
        self.count = 0
        self.checkpoints = {}
        self.snapshots = {}
        self.owners = owners
        self._owns_tracer = False

    def capture(self, row):
        if row.get("operation") != "return_3d" or row.get("status") != "ok":
            return
        self.count += 1
        # No tracing and no forced GC during expensive first GUI operations.
        if self.count not in (self.warm_at, self.cycles):
            return
        gc.collect()
        if self.count == self.warm_at and not tracemalloc.is_tracing():
            # 1 frame, beginning only at warm state; do not pay the 5-frame
            # allocation tax for startup and first full manufacturing solves.
            tracemalloc.start(1)
            self._owns_tracer = True
        current, peak = tracemalloc.get_traced_memory()
        row["python_memory_probe"] = {
            "return_3d_cycle": self.count,
            "python_heap_traced_bytes_after_gc": int(current),
            "python_heap_traced_peak_bytes": int(peak),
            "rss_bytes_after_forced_gc": self.rss_reader(),
            "gc_tracked_object_count": len(gc.get_objects()),
            "surviving_object_counts": _alive_object_counts(),
            "gc_live_objects_by_qualified_type": _tracked_type_counts(),
            "actual_gui_owner_cache_entries": _cache_owners(self.owners),
            "diagnostic_only_not_comparable_latency": True,
        }
        self.checkpoints[self.count] = dict(row["python_memory_probe"])
        if tracemalloc.is_tracing():
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
            a, b = self.snapshots[self.warm_at], self.snapshots[self.cycles]
            diff = b.compare_to(a, "filename")
            report["tracemalloc_delta_total_bytes"] = sum(s.size_diff for s in diff)
            report["top_python_heap_file_growth"] = [
                {"file": str(stat.traceback[0].filename),
                 "size_diff_bytes": stat.size_diff,
                 "count_diff": stat.count_diff}
                for stat in sorted(diff, key=lambda s: s.size_diff, reverse=True)[:30]
            ]
            first, last = self.checkpoints[self.warm_at], self.checkpoints[self.cycles]
            for field in ("python_heap_traced_bytes_after_gc",
                          "rss_bytes_after_forced_gc", "gc_tracked_object_count"):
                if first[field] is not None and last[field] is not None:
                    report[field + "_delta"] = last[field] - first[field]
            counts_first = first["gc_live_objects_by_qualified_type"]
            counts_last = last["gc_live_objects_by_qualified_type"]
            type_delta = {
                key: counts_last.get(key, 0) - counts_first.get(key, 0)
                for key in set(counts_first) | set(counts_last)
            }
            report["top_still_alive_gc_types"] = [
                {"type": key, "warm_count": counts_first.get(key, 0),
                 "final_count": counts_last.get(key, 0), "delta": delta}
                for key, delta in sorted(type_delta.items(), key=lambda pair: pair[1], reverse=True)
                if delta
            ][:60]
            report["top_alive_allocation_lines"] = [
                {"file": str(stat.traceback[0].filename),
                 "lineno": stat.traceback[0].lineno,
                 "size_diff_bytes": stat.size_diff, "count_diff": stat.count_diff}
                for stat in b.compare_to(a, "lineno")[:45]
            ]
            key = "gui_owner_1:Phase6FoldDesignerApp._phase6_last_resolved_manufacturing_signature"
            report["same_source_geometry_signature"] = (
                first["actual_gui_owner_cache_entries"].get(key)
                == last["actual_gui_owner_cache_entries"].get(key)
            )
            report["surviving_object_count_delta"] = {
                k: last["surviving_object_counts"].get(k, 0) - first["surviving_object_counts"].get(k, 0)
                for k in _WATCHED
            }
            report["actual_gui_owner_cache_entry_delta"] = {
                k: (last["actual_gui_owner_cache_entries"][k] - value)
                for k, value in first["actual_gui_owner_cache_entries"].items()
                if isinstance(value, int)
                and isinstance(last["actual_gui_owner_cache_entries"].get(k), int)
            }
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._owns_tracer:
            tracemalloc.stop()
        return report
