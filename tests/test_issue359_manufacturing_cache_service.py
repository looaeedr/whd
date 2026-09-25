from types import SimpleNamespace

import pytest

from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveResult,
)


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeWorkspace:
    available_parts = ("box_body",)
    active_part = "box_body"

    def profiles_for(self, key, default):
        return default

    def features_for(self, key):
        return ()

    def face_features_for(self, key):
        return {}

    def box_body_structure_state(self):
        return {"piece_count": 1}


def _app():
    return SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 800, "h": 1800, "d": 400, "t": 2.0},
        _settings_values={"t": 2.0, "ui_text_size": "medium"},
        _phase6_box_whd={"w": 800, "h": 1800, "d": 400},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_assembly_type=SimpleNamespace(value="INSERT_OVERLAY"),
        assembly_ignore_fixed_corner_var=FakeVar(False),
        assembly_relief_clearance_var=FakeVar("0"),
        baseline_model_var=FakeVar("金庫型"),
        _phase6_sync_revision=1,
        designer_workspace=FakeWorkspace(),
        state=SimpleNamespace(
            profiles_vault={"箱身": [{"len": 100.0, "core": True}]},
            profiles={"X": (), "Y": ()},
        ),
    )


def _result(geometry):
    return ManufacturingResolveResult(
        geometry=geometry,
        diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),
        effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature="", hit=False, stored=False),
    )


def test_issue359_explicit_cache_service_hit_miss_and_receipt():
    from phase6_manufacturing_cache import (
        ManufacturingCacheKey,
        ManufacturingCacheService,
    )

    service = ManufacturingCacheService()
    key_a = ManufacturingCacheKey("a" * 64)
    key_b = ManufacturingCacheKey("b" * 64)
    geometry = object()
    result = _result(geometry)

    miss = service.lookup(key_a)
    assert miss.result is None
    assert miss.receipt.hit is False
    assert miss.receipt.signature == key_a.fingerprint

    stored = service.store(key_a, result)
    assert stored.stored is True
    assert stored.signature == key_a.fingerprint

    hit = service.lookup(key_a)
    assert hit.result is result
    assert hit.receipt.hit is True
    assert hit.receipt.signature == key_a.fingerprint

    changed = service.lookup(key_b)
    assert changed.result is None
    assert changed.receipt.hit is False


def test_issue359_cache_key_is_semantic_and_ignores_ui_only_state():
    from phase6_manufacturing_adapter import build_manufacturing_cache_key

    a = _app()
    b = _app()
    assert build_manufacturing_cache_key(a) == build_manufacturing_cache_key(b)

    b._settings_values["ui_text_size"] = "large"
    assert build_manufacturing_cache_key(a) == build_manufacturing_cache_key(b)

    b._settings_values["t"] = 2.5
    assert build_manufacturing_cache_key(a) != build_manufacturing_cache_key(b)


def test_issue359_key_has_no_app_object_identity():
    from phase6_manufacturing_adapter import build_manufacturing_cache_key

    a = _app()
    b = _app()
    assert a is not b
    assert id(a) != id(b)
    assert build_manufacturing_cache_key(a).fingerprint == build_manufacturing_cache_key(b).fingerprint


def test_issue359_cache_hit_returns_before_full_dto_build(monkeypatch):
    import phase6_manufacturing_adapter as adapter
    from phase6_manufacturing_cache import ManufacturingCacheService

    app = _app()
    service = ManufacturingCacheService()
    key = adapter.build_manufacturing_cache_key(app)
    geometry = object()
    service.store(key, _result(geometry))

    monkeypatch.setattr(
        adapter,
        "build_manufacturing_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit must not build full immutable request")
        ),
    )

    got = adapter.resolve_manufacturing_for_app(app, cache_service=service)
    assert got is geometry


def test_issue359_legacy_last_result_fields_are_not_cache_authority(monkeypatch):
    import phase6_manufacturing_adapter as adapter
    from phase6_manufacturing_cache import ManufacturingCacheService

    app = _app()
    app._phase6_last_resolved_manufacturing_geometry = object()
    app._phase6_last_resolved_manufacturing_signature = adapter._legacy_manufacturing_signature(app)

    service = ManufacturingCacheService()
    built = []

    class DummyRequest:
        source_fingerprint = "request"

    monkeypatch.setattr(
        adapter,
        "build_manufacturing_request",
        lambda *args, **kwargs: built.append(True) or DummyRequest(),
    )

    new_geometry = object()
    monkeypatch.setattr(
        adapter,
        "apply_manufacturing_result",
        lambda app, result: result.geometry,
    )

    import phase6_manufacturing_service as service_module
    monkeypatch.setattr(
        service_module,
        "resolve",
        lambda request: _result(new_geometry),
    )

    got = adapter.resolve_manufacturing_for_app(app, cache_service=service)
    assert built == [True]
    assert got is new_geometry


def test_issue359_cache_service_rejects_non_result_storage():
    from phase6_manufacturing_cache import (
        ManufacturingCacheKey,
        ManufacturingCacheService,
    )

    service = ManufacturingCacheService()
    with pytest.raises(TypeError):
        service.store(ManufacturingCacheKey("a" * 64), object())


def test_issue359_performance_gate_reports_required_end_to_end_phases():
    from tools.issue359_cache_performance_gate import REQUIRED_METRICS

    assert {
        "phase1_signature_build_ns",
        "phase2_adapter_prescan_ns",
        "key_staging_ns",
        "freeze_canonicalization_ns",
        "full_dto_build_ns",
        "cache_lookup_ns",
        "unavoidable_apply_overhead_ns",
        "miss_full_assembly_resolve_ns",
        "phase1_hit_end_to_end_ns",
        "phase2_hit_end_to_end_ns",
    } <= set(REQUIRED_METRICS)


