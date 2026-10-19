"""#1819: actual manufacturing resolve + reopened DXF cache parity.

A service-level fake cannot establish whether cache reuse changes a real
manufacturing result or an exported DXF. Use the same live Project/GUI request
for the uncached manufacturing solver and for a cached complete result.
Linux CI timings/RSS are observational, not a Windows performance SLA.
"""
import gc
import hashlib
import os
import statistics
import time


def test_issue1819_real_manufacturing_cached_uncached_dxf_parity(
    tmp_path, monkeypatch, record_property,
):
    assert os.environ.get("DISPLAY"), "real Tk manufacturing acceptance requires Xvfb"
    import tkinter as tk
    import gui
    import phase6_manufacturing_service as manufacturing_service
    from ae_engine import manufacturing_api as api
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
    from phase6_manufacturing_cache import ManufacturingCacheKey, ManufacturingCacheService
    from phase6_manufacturing_contracts import manufacturing_request_fingerprint
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project
    from phase6_receiving_modes import fresh_receiving_mode
    from tools.whd_performance_baseline import rss_bytes

    captured = []
    original_resolve = manufacturing_service.resolve

    def capture(request):
        captured.append(request)
        return original_resolve(request)

    monkeypatch.setattr(manufacturing_service, "resolve", capture)
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        snapshot = fresh_receiving_mode(
            "quantity", {"w": 800, "h": 1600, "d": 350, "t": 2}
        )
        # Physical W800/T2 Receiving plate; match the CURRENT #1502
        # source-profile fixture, never weaken the DXF manufacturing guard.
        snapshot["receiving_base_plate"] = {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 350.0,
            "shrink_top": 55.0,
            "shrink_bottom": 55.0,
            "shrink_left": 85.0,
            "shrink_right": 85.0,
            "bend": 20.0,
        }
        # Quantity's real Base Plate authority is the common physical box;
        # the root receiving_base_plate is a transient assembly projection.
        # Commit the existing #1502 source using the same transaction route
        # as the live GUI, then test the *real* cached/uncached DXF parity.
        from ae_engine.receiving_quantity_box import update_common_box
        snapshot = update_common_box(
            snapshot, {"receiving_base_plate": snapshot["receiving_base_plate"]},
        )
        assert snapshot["receiving_quantity_box"]["receiving_base_plate"] == (
            snapshot["receiving_base_plate"]
        )
        project = write_project(
            tmp_path / "real-parity.p6fold",
            {"schema": PROJECT_SCHEMA_V2, "snapshot": snapshot},
        )
        host.load_phase6_project(project)
        root.update()
        assert captured, "the test must use an actual manufacturing request"
        request = captured[-1]

        started = time.perf_counter_ns()
        without_cache = original_resolve.__wrapped__(request)
        uncached_ms = (time.perf_counter_ns() - started) / 1e6
        started = time.perf_counter_ns()
        freshly_resolved = original_resolve(request)
        warm_solve_ms = (time.perf_counter_ns() - started) / 1e6
        assert freshly_resolved == without_cache

        # Consume a real complete manufacturing result via the production
        # ManufacturingCacheService, not a synthetic mock geometry object.
        key = ManufacturingCacheKey(manufacturing_request_fingerprint(request))
        cache = ManufacturingCacheService(max_entries=2)
        assert cache.lookup(key).result is None
        cache.store(key, freshly_resolved)
        hits = 0
        hit_ms = []
        rss_before = rss_bytes()
        for _ in range(80):
            start = time.perf_counter_ns()
            receipt = cache.lookup(key)
            hit_ms.append((time.perf_counter_ns() - start) / 1e6)
            assert receipt.receipt.hit and receipt.result is freshly_resolved
            assert receipt.result == without_cache
            hits += 1
        gc.collect()
        rss_after = rss_bytes()
        assert len(cache._entries) == 1
        wrong_key = ManufacturingCacheKey(
            hashlib.sha256((key.fingerprint + ":changed").encode()).hexdigest()
        )
        assert cache.lookup(wrong_key).result is None

        cold_dir = tmp_path / "uncached-dxf"
        hot_dir = tmp_path / "cached-dxf"
        cold_files = api.save_resolved_manufacturing_geometry_dxf(
            without_cache.geometry, cold_dir, overwrite=True
        )
        hot_files = api.save_resolved_manufacturing_geometry_dxf(
            receipt.result.geometry, hot_dir, overwrite=True
        )
        assert cold_files and set(cold_files) == set(hot_files)
        cold_check = api.verify_saved_resolved_manufacturing_geometry_dxf(
            without_cache.geometry, cold_dir
        )
        hot_check = api.verify_saved_resolved_manufacturing_geometry_dxf(
            receipt.result.geometry, hot_dir
        )
        assert cold_check.ok and not cold_check.issues
        assert hot_check.ok and not hot_check.issues
        assert set(cold_check.part_results) == set(hot_check.part_results)

        record_property("issue1819_real_mfg_cache_hit_rate", hits / 80)
        record_property("issue1819_real_mfg_cache_hits", hits)
        record_property("issue1819_real_mfg_uncached_solve_ms", round(uncached_ms, 3))
        record_property("issue1819_real_mfg_repeat_solve_ms", round(warm_solve_ms, 3))
        record_property("issue1819_real_mfg_hit_median_ms", round(statistics.median(hit_ms), 5))
        record_property("issue1819_real_mfg_dxf_part_count", len(cold_files))
        record_property("issue1819_real_mfg_rss_before_bytes", rss_before)
        record_property("issue1819_real_mfg_rss_after_bytes", rss_after)
    finally:
        root.destroy()
