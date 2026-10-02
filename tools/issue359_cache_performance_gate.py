#!/usr/bin/env python3
"""#359 T5 end-to-end cache-hit performance A/B gate.

The gate measures the whole hit path, not only cache lookup.  Miss-side phase
timings are reported for visibility but only the cache-hit end-to-end delta is
used as a hard performance threshold.
"""
from __future__ import annotations

from dataclasses import replace
from statistics import median
from time import perf_counter_ns
from types import SimpleNamespace

from shapely.geometry import box

from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_manufacturing_adapter import (
    _legacy_manufacturing_signature,
    apply_manufacturing_result,
    build_manufacturing_cache_key,
    build_manufacturing_request,
    resolve_manufacturing_for_app,
)
from phase6_manufacturing_cache import ManufacturingCacheKey, ManufacturingCacheService
from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveResult,
    manufacturing_request_fingerprint,
)


REQUIRED_METRICS = (
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
)


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Workspace:
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
    render = SimpleNamespace(
        scene=DrawingScene(),
        material=box(0, 0, 800, 400),
        fold_guides=(),
        metadata={},
    )
    app = SimpleNamespace(
        _phase6_input_snapshot={
            "model": "金庫型", "w": 800, "h": 1800, "d": 400, "t": 2.0,
        },
        _settings_values={"t": 2.0, "ui_text_size": "medium"},
        _phase6_box_whd={"w": 800, "h": 1800, "d": 400},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_assembly_type=SimpleNamespace(value="INSERT_OVERLAY"),
        assembly_ignore_fixed_corner_var=Var(False),
        assembly_relief_clearance_var=Var("0"),
        baseline_model_var=Var("金庫型"),
        _phase6_sync_revision=1,
        designer_workspace=Workspace(),
        state=SimpleNamespace(
            profiles_vault={"箱身": [{"len": 800.0, "core": True}]},
            profiles={"X": (), "Y": ()},
        ),
        _scene_query_callback=lambda key, payload: render,
    )
    return app


def _scene_payload(key):
    return {"part_key": key, "model": "金庫型"}


def _dims(key=None):
    return (800.0, 1800.0, 400.0)


def _render_provider(app):
    return lambda key, payload: app._scene_query_callback(key, payload)


def _sample_ns(fn, *, loops=400, rounds=7):
    samples = []
    for _ in range(rounds):
        start = perf_counter_ns()
        for _ in range(loops):
            fn()
        samples.append((perf_counter_ns() - start) / loops)
    return int(median(samples))


def _single_ns(fn, *, rounds=9):
    samples = []
    for _ in range(rounds):
        start = perf_counter_ns()
        fn()
        samples.append(perf_counter_ns() - start)
    return int(median(samples))


def _result(geometry, signature=""):
    return ManufacturingResolveResult(
        geometry=geometry,
        diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),
        effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(
            signature=signature,
            hit=False,
            stored=False,
        ),
    )


def collect_metrics():
    app = _app()
    signature = _legacy_manufacturing_signature(app)
    key = ManufacturingCacheKey(signature)
    geometry = object()
    result = _result(geometry, signature)

    service = ManufacturingCacheService()
    service.store(key, result)

    request = build_manufacturing_request(
        app,
        scene_payload_builder=_scene_payload,
        render_data_provider=_render_provider(app),
        finished_dimensions_provider=_dims,
    )

    # Historical Phase 1 shape: cheap signature + app-owned signature/result
    # comparison. This exists only inside the A/B harness.
    app._phase6_last_resolved_manufacturing_geometry = geometry
    app._phase6_last_resolved_manufacturing_signature = signature

    def phase1_hit():
        current = _legacy_manufacturing_signature(app)
        cached = app._phase6_last_resolved_manufacturing_geometry
        cached_signature = app._phase6_last_resolved_manufacturing_signature
        return cached if cached is not None and current == cached_signature else None

    def phase2_hit():
        return resolve_manufacturing_for_app(
            app,
            cache_service=service,
            scene_payload_builder=_scene_payload,
            render_data_provider=_render_provider(app),
            finished_dimensions_provider=_dims,
        )

    metrics = {
        "phase1_signature_build_ns": _sample_ns(
            lambda: _legacy_manufacturing_signature(app)
        ),
        "phase2_adapter_prescan_ns": _sample_ns(
            lambda: build_manufacturing_cache_key(app)
        ),
        "key_staging_ns": _sample_ns(
            lambda: ManufacturingCacheKey(signature)
        ),
        "freeze_canonicalization_ns": _sample_ns(
            lambda: manufacturing_request_fingerprint(request),
            loops=80,
        ),
        "full_dto_build_ns": _sample_ns(
            lambda: build_manufacturing_request(
                app,
                scene_payload_builder=_scene_payload,
                render_data_provider=_render_provider(app),
                finished_dimensions_provider=_dims,
            ),
            loops=80,
        ),
        "cache_lookup_ns": _sample_ns(lambda: service.lookup(key)),
        "unavoidable_apply_overhead_ns": _sample_ns(
            lambda: apply_manufacturing_result(app, result),
            loops=150,
        ),
        "phase1_hit_end_to_end_ns": _sample_ns(phase1_hit),
        "phase2_hit_end_to_end_ns": _sample_ns(phase2_hit),
    }

    miss_service = ManufacturingCacheService()

    def full_miss():
        miss_service.clear()
        return resolve_manufacturing_for_app(
            app,
            cache_service=miss_service,
            scene_payload_builder=_scene_payload,
            render_data_provider=_render_provider(app),
            finished_dimensions_provider=_dims,
        )

    metrics["miss_full_assembly_resolve_ns"] = _single_ns(full_miss, rounds=7)
    return metrics


def main() -> int:
    metrics = collect_metrics()
    missing = sorted(set(REQUIRED_METRICS) - set(metrics))
    assert not missing, f"MISSING_METRICS={missing}"

    baseline = max(1, metrics["phase1_hit_end_to_end_ns"])
    candidate = metrics["phase2_hit_end_to_end_ns"]
    ratio = candidate / baseline
    absolute_delta = candidate - baseline

    print("CACHE_PERFORMANCE_METRICS")
    for name in REQUIRED_METRICS:
        print(f"{name}={metrics[name]}")
    print(f"cache_hit_ratio={ratio:.4f}")
    print(f"cache_hit_absolute_delta_ns={absolute_delta}")

    # Wrapping the same cheap semantic signature in an immutable key and doing
    # one explicit service lookup may add small constant overhead. Fail only on
    # a material regression; the full DTO path is explicitly excluded from hit.
    allowed = max(int(baseline * 3.0), baseline + 75_000)
    assert candidate <= allowed, (
        "CACHE_HIT_PERFORMANCE_REGRESSION "
        f"baseline_ns={baseline} candidate_ns={candidate} "
        f"ratio={ratio:.4f} allowed_ns={allowed}"
    )
    print("PASS CACHE_HIT_END_TO_END_PERFORMANCE=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
