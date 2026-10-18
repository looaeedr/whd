"""#1819 diagnostic isolation: real tracemalloc and explicit GC, opt in only."""
import json
import tracemalloc

from tools.issue1819_python_memory_probe import PythonMemoryAttributionProbe


def test_issue1819_python_memory_attribution_checkpoints_and_summary(tmp_path):
    old_tracing = tracemalloc.is_tracing()
    probe = PythonMemoryAttributionProbe(cycles=6, rss_reader=lambda: 987654321)
    allocated = []
    for cycle in range(1, 7):
        allocated.append(bytes([cycle]) * 1024)
        row = {"operation": "return_3d", "status": "ok"}
        probe.capture(row)
        assert row["python_memory_probe"]["return_3d_cycle"] == cycle
        assert row["python_memory_probe"]["rss_bytes_after_forced_gc"] == 987654321
        assert row["python_memory_probe"]["gc_tracked_object_count"] > 0
    target = tmp_path / "snapshot.json"
    result = probe.finalize(target)
    assert result["complete"]
    assert result["cycles_seen"] == 6
    assert result["warm_cycle"] == 3
    assert set(result["checkpoints"]) == {3, 6}
    assert "top_python_heap_file_growth" in result
    assert "rss_bytes_after_forced_gc_delta" in result
    assert json.loads(target.read_text())["kind"].startswith("PYTHON_TRACEMALLOC")
    if not old_tracing:
        assert not tracemalloc.is_tracing()


def test_issue1819_diagnostic_probe_does_not_capture_unrelated_operations(tmp_path):
    probe = PythonMemoryAttributionProbe(cycles=5, rss_reader=lambda: 99)
    for kind in ("open_multi", "open_true_2d", "return_3d"):
        row = {"operation": kind, "status": "failed" if kind == "return_3d" else "ok"}
        probe.capture(row)
        assert "python_memory_probe" not in row
    result = probe.finalize(tmp_path / "incomplete.json")
    assert result["complete"] is False
    assert result["cycles_seen"] == 0
