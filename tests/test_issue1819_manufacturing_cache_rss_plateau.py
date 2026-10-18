"""#1819 Linux cache-residency plateau and retired-result reclamation.

This observes one process, not Windows operator RSS. Complementary to the
real manufacturing/DXF cached-vs-cold test and the production GUI profiler.
"""
from __future__ import annotations

from dataclasses import replace
import gc
import weakref

from phase6_manufacturing_cache import ManufacturingCacheKey, ManufacturingCacheService
from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveResult,
)
from tools.whd_performance_baseline import rss_bytes

MIB = 1024 * 1024


def _large_complete_result(index: int) -> ManufacturingResolveResult:
    # Allocate a distinct, concrete 1-MiB geometry-like result for every
    # edit; an unbounded history would keep hundreds of MiB live.
    payload = bytes([index % 251]) * MIB
    return ManufacturingResolveResult(
        geometry=payload,
        diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),
        effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature=f"{index:064x}"),
    )


def test_issue1819_repeated_large_result_churn_reclaims_evictions_and_bounds_rss(record_property):
    cache = ManufacturingCacheService(max_entries=2)
    references = []
    checkpoints = []
    for batch in range(12):
        for index in range(batch * 32, (batch + 1) * 32):
            result = _large_complete_result(index)
            references.append(weakref.ref(result))
            key = ManufacturingCacheKey(f"{index:064x}")
            cache.store(key, result)
            assert len(cache._entries) <= 2
            assert cache.lookup(key).result is result
        del result
        gc.collect()
        # Only two most recent complete results are allowed to survive:
        # this detects invisible strong references even if dict size is 2.
        assert all(ref() is None for ref in references[:-2])
        assert all(ref() is not None for ref in references[-2:])
        observed = rss_bytes()
        if observed is not None:
            checkpoints.append(int(observed))
    assert len(references) == 384
    assert len(cache._entries) == 2
    assert len(checkpoints) in (0, 12)
    if checkpoints:
        # Ignore the initial allocator warmup. A leaking ~1MiB per edit
        # would grow at least 256 MiB across these subsequent 9 batches.
        # An 32-MiB RSS envelope tolerates malloc/OS allocator behavior.
        plateau = checkpoints[3:]
        growth = max(plateau) - min(plateau)
        record_property("issue1819_rss_checkpoints_bytes", ",".join(map(str, checkpoints)))
        record_property("issue1819_rss_post_warmup_spread_bytes", growth)
        assert growth <= 32 * MIB, (
            "RSS kept growing while the two-result manufacturing cache was "
            f"churned: post-warmup range {growth} bytes"
        )
    cache.clear()
    gc.collect()
    assert all(ref() is None for ref in references)
