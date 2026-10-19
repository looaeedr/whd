"""Issue #1819: explicit manufacturing-result cache bounds and cold/hot parity.

These tests cover the cache service's result ownership, not end-to-end DXF
output or process RSS. Those require separate manufacturing/UI acceptance.
"""
from phase6_manufacturing_cache import ManufacturingCacheKey, ManufacturingCacheService
from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveResult,
)


def _result(number):
    return ManufacturingResolveResult(
        geometry=("CUTTING", "MARKING", number),
        diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),
        effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature=f"{number:064x}"),
    )


def _key(number):
    return ManufacturingCacheKey(f"{number:064x}")


def test_issue1819_hot_and_cold_complete_manufacturing_results_are_identical():
    service = ManufacturingCacheService(max_entries=2)
    calls = 0

    def resolve(number, *, use_cache):
        nonlocal calls
        key = _key(number)
        if use_cache:
            cached = service.lookup(key)
            if cached.result is not None:
                assert cached.receipt.hit
                return cached.result
        calls += 1
        result = _result(number)
        if use_cache:
            service.store(key, result)
        return result

    cold = resolve(11, use_cache=False)
    first = resolve(11, use_cache=True)
    warm = resolve(11, use_cache=True)
    assert cold == first == warm
    assert warm is first
    assert calls == 2  # The hot read avoided one resolver invocation.


def test_issue1819_long_repeated_edits_keep_result_history_bounded_and_precise():
    service = ManufacturingCacheService(max_entries=2)
    for number in range(512):
        key = _key(number)
        assert service.lookup(key).result is None
        service.store(key, _result(number))
        assert len(service._entries) <= 2
        assert service.lookup(key).result == _result(number)
        if number > 1:
            assert service.lookup(_key(number - 2)).result is None

    # The most recent two exact fingerprints survive; a different parameter
    # must never return the old manufactured geometry.
    assert service.lookup(_key(511)).result.geometry[-1] == 511
    assert service.lookup(_key(510)).result.geometry[-1] == 510
    service.clear()
    assert not service._entries
    assert service.lookup(_key(511)).result is None
