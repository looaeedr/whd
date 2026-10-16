from __future__ import annotations

import inspect
import tkinter as tk

import gui
import fold_designer_bridge as bridge
from phase6_settings_center import Phase6Settings


class _FakeSettingsService:
    def __init__(self, values):
        self.values = dict(values)

    def snapshot(self):
        return Phase6Settings(self.values)

    def update(self, updates):
        self.values.update(dict(updates))
        return self.snapshot()


def test_live_settings_only_sets_tk_vars_that_actually_change():
    interp = tk.Tcl()
    app = object.__new__(gui.BoxCalculatorGUI)
    initial = {
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "fw": 25.0,
        "base_plate_shrink_top": 10.0,
        "base_plate_shrink_bottom": 10.0,
        "base_plate_shrink_left": 10.0,
        "base_plate_shrink_right": 10.0,
    }
    app.settings_service = _FakeSettingsService(initial)
    app._settings_sync_guard = False
    app.endcap_fw_state = {
        "head": {"follow_box": True, "value": 25.0},
        "tail": {"follow_box": True, "value": 25.0},
    }
    app._sync_endcap_fw_controls = lambda: None
    app.update_calculations = lambda: None
    app.base_plate_all_same_var = tk.BooleanVar(master=interp, value=True)
    app.base_plate_shrink_same_var = tk.StringVar(master=interp, value="10")

    vars_by_key = {
        key: tk.StringVar(master=interp, value=str(int(value) if float(value).is_integer() else value))
        for key, value in initial.items()
        if key in {"w", "h", "d", "fw"}
    }
    app._setting_var_map = lambda: vars_by_key

    writes = {key: 0 for key in vars_by_key}
    for key, var in vars_by_key.items():
        var.trace_add("write", lambda *_args, k=key: writes.__setitem__(k, writes[k] + 1))

    incoming = dict(initial)
    incoming["w"] = 900.0
    gui.BoxCalculatorGUI._apply_fold_designer_live_settings(app, incoming, recalculate=False)

    assert writes == {"w": 1, "h": 0, "d": 0, "fw": 0}


def test_external_designer_apply_has_explicit_anti_echo_guard_contract():
    apply_src = inspect.getsource(bridge._phase6_apply_external_settings)
    from gui_modules.application import (
        command_router, fold_designer_composition_settings,
    )
    # The bridge delegates; guard ownership moved to the composition.
    apply_owner_src = inspect.getsource(
        fold_designer_composition_settings.apply_external_settings
    )
    execute_src = inspect.getsource(command_router.execute_fold_designer_update_reasons)
    wrapper_src = inspect.getsource(bridge._phase6_preview_aware_do_update)
    assert "_phase6_composition" in apply_src
    assert "_phase6_external_apply_guard" in apply_owner_src
    # T06 centralizes publish/anti-echo ownership in the orchestration executor;
    # compatibility wrappers must delegate instead of duplicating the guard.
    assert "_phase6_external_apply_guard" in execute_src
    assert 'not getattr(owner, "_phase6_external_apply_guard"' in execute_src
    assert "submit_update_intent" in wrapper_src


def test_live_snapshot_routes_final_recalculation_through_scheduler_not_direct_call():
    src = inspect.getsource(gui.BoxCalculatorGUI._apply_fold_designer_live_snapshot)
    assert "_phase6_update_scheduler" in src
    assert ".mark_dirty(" in src
    assert "self.update_calculations()" not in src


def test_main_input_traces_never_call_full_recalculation_directly():
    from gui_modules.application import state_sync
    bind_src = inspect.getsource(gui.BoxCalculatorGUI.bind_live_updates)
    total_src = inspect.getsource(gui.BoxCalculatorGUI._on_total_door_dimension_changed)
    setting_src = inspect.getsource(state_sync.on_main_setting_var_changed)
    assert 'trace_add("write", lambda *args: self.update_calculations())' not in bind_src
    assert 'self.update_calculations()' not in total_src
    assert '_phase6_update_scheduler' in setting_src
    assert '.mark_dirty(' in setting_src


def test_external_guard_runtime_suppresses_echo_without_dropping_scene_refresh():
    # #1792: assert real publish/render callbacks, not inspect.getsource().
    from types import SimpleNamespace
    from gui_modules.application import command_router

    calls = []
    owner = SimpleNamespace(
        _phase6_sync_ready=True,
        _phase6_initializing=False,
        _phase6_external_apply_guard=True,
        _phase6_defer_input_publish=False,
        _live_sync_callback=lambda payload=None: None,
    )

    def run():
        command_router.execute_fold_designer_update_reasons(
            owner,
            {"display", "camera"},
            full_update=lambda: calls.append("full"),
            render_committed=lambda: calls.append("scene"),
            publish_if_changed=lambda: calls.append("echo"),
        )

    run()
    assert calls == ["scene"]  # external apply updates scene, not host echo
    owner._phase6_external_apply_guard = False
    calls.clear()
    run()
    assert calls == ["echo", "scene"]  # genuine local edit still publishes


def test_issue1794_identical_authoritative_part_presence_keeps_derived_cache(
    record_property,
):
    """Exercise the real MainGUI presence handler; first authority commit still invalidates."""
    from types import SimpleNamespace
    from time import perf_counter_ns

    from gui_modules.application.lifecycle import _apply_existing_parts_from_fold_workspace
    from phase6_workspace_controller import Phase6WorkspaceController

    class Flag:
        def __init__(self):
            self.values = []

        def set(self, value):
            self.values.append(bool(value))

    workspace = Phase6WorkspaceController(
        default_existing_parts={"box_body", "head", "door"}
    )
    cache = gui._Phase6DerivedCacheOwner()
    refreshed = []
    host = SimpleNamespace(
        workspace_controller=workspace,
        _derived_cache_owner=cache,
        is_indicator_box_var=Flag(),
        is_door_indicator_var=Flag(),
        _phase6_refresh_presence_ui=lambda parts: refreshed.append(frozenset(parts)),
        _manual_corner_part_override=None,
    )
    before = cache.metrics_snapshot()
    first = _apply_existing_parts_from_fold_workspace(host, ("door", "head"))
    assert first == {"box_body", "head", "door"}
    assert workspace.has_authoritative_workspace
    assert all(cache.metrics_snapshot()[p] == before[p] + 1 for p in cache.PRODUCTS)

    for product in cache.PRODUCTS:
        cache.cache(product)["physical-sentinel"] = product
    stable_metrics = cache.metrics_snapshot()
    wall_ms = []
    for _ in range(5):
        start = perf_counter_ns()
        identical = _apply_existing_parts_from_fold_workspace(
            host, ("head", "door", "box_body")
        )
        wall_ms.append((perf_counter_ns() - start) / 1_000_000)
        assert identical == first
        assert cache.metrics_snapshot() == stable_metrics, (
            "equivalent authoritative presence cleared derived geometry cache"
        )
        assert all(
            cache.cache(p).get("physical-sentinel") == p
            for p in cache.PRODUCTS
        )

    # A real physical-part removal still invalidates every dependent
    # product exactly once; the absent door cannot survive in cached scene.
    without_door = _apply_existing_parts_from_fold_workspace(host, ("head",))
    assert without_door == {"box_body", "head"}
    assert all(
        cache.metrics_snapshot()[p] == stable_metrics[p] + 1
        for p in cache.PRODUCTS
    )
    assert all(not cache.cache(p) for p in cache.PRODUCTS)
    assert refreshed[-1] == frozenset(without_door)
    record_property("issue1794_noop_authoritative_presence_wall_ms", repr(wall_ms))


def test_issue1794_same_presence_but_changed_geometry_revision_invalidates():
    """A changed Designer payload is not an equivalent presence-only repeat."""
    from types import SimpleNamespace
    from gui_modules.application.lifecycle import _apply_existing_parts_from_fold_workspace
    from phase6_workspace_controller import Phase6WorkspaceController

    class Flag:
        def set(self, _value):
            pass

    owner = gui._Phase6DerivedCacheOwner()
    host = SimpleNamespace(
        workspace_controller=Phase6WorkspaceController(),
        _derived_cache_owner=owner,
        is_indicator_box_var=Flag(),
        is_door_indicator_var=Flag(),
        _manual_corner_part_override=None,
    )
    parts = ("box_body", "head", "door")
    _apply_existing_parts_from_fold_workspace(host, parts, state_fingerprint="geometry-A")
    first = owner.metrics_snapshot()
    for product in owner.PRODUCTS:
        owner.cache(product)["old"] = True

    # Same geometry revision is an actual no-op.
    _apply_existing_parts_from_fold_workspace(host, parts, state_fingerprint="geometry-A")
    assert owner.metrics_snapshot() == first
    assert all(owner.cache(product) for product in owner.PRODUCTS)

    # New PartSpec/Joint/holes revision with same presence must clear the
    # old material and 3D rendering, never return stale cached geometry.
    _apply_existing_parts_from_fold_workspace(host, parts, state_fingerprint="geometry-B")
    assert all(owner.metrics_snapshot()[p] == first[p] + 1 for p in owner.PRODUCTS)
    assert all(not owner.cache(p) for p in owner.PRODUCTS)

    for product in owner.PRODUCTS:
        owner.cache(product)["previous-project"] = True
    before_reload = owner.metrics_snapshot()
    _apply_existing_parts_from_fold_workspace(
        host, parts, state_fingerprint="geometry-B", force_invalidate=True
    )
    assert all(owner.metrics_snapshot()[p] == before_reload[p] + 1 for p in owner.PRODUCTS)
    assert all(not owner.cache(p) for p in owner.PRODUCTS)


def test_issue1794_changed_keys_precise_display_noop_but_unknown_geometry_fails_closed():
    owner = gui._Phase6DerivedCacheOwner()
    for name in owner.PRODUCTS:
        owner.cache(name)["sentinel"] = name
    before = owner.metrics_snapshot()
    assert owner.invalidate("geometry", changed_keys={"camera", "ui_text_size"}) == ()
    assert owner.metrics_snapshot() == before
    assert all(owner.cache(p)["sentinel"] == p for p in owner.PRODUCTS)

    # Physical dimensions remain real geometry dependencies.
    assert set(owner.invalidate("geometry", changed_keys={"w", "h", "d", "t", "fw"})) == set(owner.PRODUCTS)
    assert all(not owner.cache(p) for p in owner.PRODUCTS)
    for name in owner.PRODUCTS:
        owner.cache(name)["sentinel"] = name
    assert set(owner.invalidate("geometry", changed_keys={"unrecognized_joint_key"})) == set(owner.PRODUCTS)
    assert all(not owner.cache(p) for p in owner.PRODUCTS)


def test_issue1794_real_main_gui_render_cache_hit_scene_sha_and_no_dxf_reread(
    monkeypatch, record_property,
):
    """Check real GUI/cache/geometry authority, not only an isolated fake owner."""
    import hashlib
    import os
    import time

    from ae_engine import ae

    if not os.environ.get("DISPLAY"):
        import pytest
        pytest.skip("real Tk/MainGUI source-integrity proof requires Xvfb")

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        parts = tuple(app.workspace_controller.current_existing_parts())
        app._apply_existing_parts_from_fold_workspace(parts)
        owner = app._derived_cache_owner

        values = app.get_float_values()
        spec = app._end_cap_part_spec(values, is_tail=False)
        context = app._manufacturing_context(draw_stock=False)
        initial = app._authoritative_render_data(spec, context)
        scene_sha = hashlib.sha256(repr(initial.scene).encode("utf-8")).hexdigest()
        material_sha = hashlib.sha256(initial.material.wkb).hexdigest()
        before = owner.metrics_snapshot()

        # Count real parser calls after the first verified manufacturing build.
        reads = []
        original_read = ae.ezdxf.readfile

        def recorded_read(*args, **kwargs):
            reads.append(str(args[0]))
            return original_read(*args, **kwargs)

        monkeypatch.setattr(ae.ezdxf, "readfile", recorded_read)
        latencies = []
        for _ in range(5):
            started = time.perf_counter_ns()
            app._apply_existing_parts_from_fold_workspace(reversed(parts))
            actual = app._authoritative_render_data(spec, context)
            latencies.append(round((time.perf_counter_ns() - started) / 1e6, 3))
            assert actual is initial, "equivalent GUI part state must hit actual RenderData cache"
            assert hashlib.sha256(repr(actual.scene).encode("utf-8")).hexdigest() == scene_sha
            assert hashlib.sha256(actual.material.wkb).hexdigest() == material_sha
            assert owner.metrics_snapshot() == before
        assert not reads, "equivalent derived state must not reparse original DXF"

        if "door" in parts:
            changed = tuple(key for key in parts if key != "door")
        else:
            changed = tuple(parts) + ("door",)
        app._apply_existing_parts_from_fold_workspace(changed)
        rebuilt = app._authoritative_render_data(spec, context)
        assert rebuilt is not initial
        assert all(owner.metrics_snapshot()[p] == before[p] + 1 for p in owner.PRODUCTS)
        assert not reads, "physical presence invalidation must not clear DXF source"
        record_property("issue1794_real_main_gui_noop_wall_ms", repr(latencies))
        record_property("issue1794_real_main_gui_scene_sha256", scene_sha)
        record_property("issue1794_real_main_gui_material_sha256", material_sha)
        record_property("issue1794_real_main_gui_baseline_dxf_reads", len(reads))
    finally:
        root.destroy()


def test_baseline_report_excludes_failed_samples_and_keeps_cache_groups():
    from tools.whd_performance_baseline import summarize
    rows = [dict(bays=1, operation='open', cache_state='warm', status='ok', wall_ms=x)
            for x in range(1, 21)]
    rows += [dict(bays=1, operation='open', cache_state='warm', status='failed', wall_ms=9999),
             dict(bays=1, operation='open', cache_state='first_entry', status='ok', wall_ms=100)]
    report = {r['cache_state']: r for r in summarize(rows)}
    assert report['warm']['n'] == 20
    assert report['warm']['failed'] == 1
    assert report['warm']['median_ms'] == 10.5
    assert report['warm']['p95_ms'] == 19
    assert report['first_entry']['median_ms'] == 100


def test_baseline_probe_preserves_result_exception_and_restores_callable():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    import pytest
    def operation(key):
        if key == 'bad':
            raise ValueError('real error')
        return key
    owner = SimpleNamespace(operation=operation)
    probe = Probe()
    try:
        probe.wrap(owner, 'operation', 'actual', part_arg=0)
        assert owner.operation('head') == 'head'
        with pytest.raises(ValueError, match='real error'):
            owner.operation('bad')
        assert probe.counts['actual'] == 2
        assert probe.parts == {'head': 1, 'bad': 1}
    finally:
        probe.stack.close()
    assert owner.operation is operation


def test_baseline_settle_waits_for_pending_debounce_and_rejects_timeout():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import settle
    import pytest
    scheduler = SimpleNamespace(dirty={'geometry'}, _after_job='job', _flushing=False)
    calls = []
    def update():
        calls.append(1)
        if len(calls) == 3:
            scheduler.dirty.clear()
            scheduler._after_job = None
    root = SimpleNamespace(update_idletasks=lambda: None, update=update)
    settle(root, [SimpleNamespace(_phase6_update_scheduler=scheduler)])
    assert len(calls) >= 4
    scheduler.dirty.add('geometry')
    with pytest.raises(TimeoutError):
        settle(root, [SimpleNamespace(_phase6_update_scheduler=scheduler)], timeout=.005)


def test_baseline_rss_sampler_window_excludes_outside_and_never_fakes_peak():
    from tools.whd_performance_baseline import RSSSampler
    values = iter([100, 150, 135])
    stamps = iter([1.0, 2.0, 3.0])
    sampler = RSSSampler(50, reader=lambda: next(values),
                         clock=lambda: next(stamps))
    for _ in range(3):
        sampler._capture()
    assert sampler.window(1.5, 2.5) == {
        'rss_peak_sampled_bytes': 150,
        'rss_samples_in_operation': 1,
        'rss_sample_error': None,
    }
    assert sampler.window(4, 5)['rss_peak_sampled_bytes'] is None
    assert sampler.window(4, 5)['rss_samples_in_operation'] == 0


def test_baseline_rss_sampler_bounds_and_unavailable_reader():
    import pytest
    from tools.whd_performance_baseline import RSSSampler
    with pytest.raises(ValueError):
        RSSSampler(0)
    with pytest.raises(ValueError):
        RSSSampler(1001)
    sampler = RSSSampler(50, reader=lambda: None)
    sampler._capture()
    assert sampler.window(0, float('inf'))['rss_peak_sampled_bytes'] is None


def test_baseline_memory_trends_never_mix_workers_or_claim_leaks():
    from tools.whd_performance_baseline import memory_trends
    def row(bays, worker, rss, operation='return_3d', status='ok'):
        return dict(bays=bays, worker_sample=worker, operation=operation,
                    status=status, rss_after=rss)
    measurements = [
        row(1, 0, 100), row(1, 1, 600), row(1, 0, 120),
        row(1, 0, 800, operation='open_multi'),
        row(1, 0, 900, status='failed'),
        row(3, 0, 200), row(3, 0, 180),
    ]
    trends = memory_trends(measurements)
    assert len(trends) == 3
    one = next(t for t in trends if t['bays'] == 1 and t['worker_sample'] == 0)
    assert one['completed_cycles'] == 2
    assert one['delta_bytes'] == 20
    assert one['max_checkpoint_rss_bytes'] == 120
    assert one['interpretation'].endswith('not_leak_proof')
    assert next(t for t in trends if t['bays'] == 3)['delta_bytes'] == -20


def test_issue1816_world_skin_keys_exclude_box_body_aggregate():
    from tools.whd_performance_baseline import physical_world_skin_keys
    from pytest import raises
    world = {'world_triangles_by_part': {
        'box_body': [('aggregate',)],
        'box_body:left': [('left',)],
        'box_body:right': [('right',)],
        'head': [('head',)],
        'tail': [],
    }}
    assert physical_world_skin_keys(world) == ('box_body:left','box_body:right','head')
    assert physical_world_skin_keys({'world_triangles_by_part': {'box_body': [(1,)]}}) == ('box_body',)
    with raises(ValueError):
        physical_world_skin_keys({'unrelated': {'box_body': []}})


def test_issue1816_world_skin_observer_counts_real_return_and_restores():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    import pytest
    def actual_world_skin(*args, **kwargs):
        if args and args[0] == 'bad':
            raise RuntimeError('actual world failure')
        return {'world_triangles_by_part': {
            'box_body': [(1,)], 'box_body:left': [(2,)],
            'box_body:back': [(3,)], 'door': [(4,)], 'tail': []}}
    service = SimpleNamespace(build=actual_world_skin)
    probe = Probe()
    try:
        probe.observe_world_skin(service, 'build')
        expected = actual_world_skin()
        assert service.build() == expected
        assert probe.counts['world_skin_builds'] == 1
        assert probe.world_skin_parts == {'box_body:left': 1, 'box_body:back': 1, 'door': 1}
        assert sum(probe.world_skin_parts.values()) == 3
        with pytest.raises(RuntimeError, match='actual world failure'):
            service.build('bad')
        assert probe.counts['world_skin_builds'] == 1
        probe.reset()
        assert sum(probe.world_skin_parts.values()) == 0
        assert probe.counts['world_skin_builds'] == 0
        assert service.build() == expected
        assert probe.counts['world_skin_builds'] == 1
    finally:
        probe.stack.close()
    assert service.build is actual_world_skin


def test_issue1816_kernel_peak_rss_parsing_does_not_fake_missing_data():
    from tools.whd_performance_baseline import linux_vmhwm_bytes
    assert linux_vmhwm_bytes('Name: python\nVmHWM:\t182340 kB\nVmRSS:\t162000 kB\n') == 182340 * 1024
    assert linux_vmhwm_bytes('VmRSS: 100 kB\n') is None
    assert linux_vmhwm_bytes('VmHWM: invalid kB\n') is None
    assert linux_vmhwm_bytes('VmHWM: 123 MB\n') is None


def test_issue1816_linux_kernel_hwm_is_an_os_peak_not_sampled_rss():
    import sys
    import pytest
    from tools.whd_performance_baseline import rss_highwater_bytes, rss_bytes
    if not sys.platform.startswith('linux'):
        pytest.skip('linux proc VmHWM only')
    peak = rss_highwater_bytes()
    assert peak is not None and peak > 0
    assert peak >= rss_bytes() * .90  # independent consecutive reads can change


def test_issue1816_observe_real_cache_receipt_hits_and_misses():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    class RealLikeCache:
        def lookup(self, key):
            return SimpleNamespace(receipt=SimpleNamespace(hit=(key == 'known')))
    service=RealLikeCache()
    original=RealLikeCache.lookup
    probe=Probe()
    try:
        probe.observe_manufacturing_cache(RealLikeCache)
        assert service.lookup('unknown').receipt.hit is False
        assert service.lookup('known').receipt.hit is True
        assert probe.counts['manufacturing_cache_hit'] == 1
        assert probe.counts['manufacturing_cache_miss'] == 1
        probe.reset()
        assert probe.counts['manufacturing_cache_hit'] == 0
    finally:
        probe.stack.close()
    assert RealLikeCache.lookup is original


def test_issue1816_render_material_cache_and_build_count_are_independent():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    cache={}
    class Spec:
        pass
    spec=Spec()
    context=SimpleNamespace(draw_stock=False)
    def build_part_render_data(spec, ctx):
        return dict(material='real_created')
    factory=SimpleNamespace(build_part_render_data=build_part_render_data)
    def authoritative(spec, context=None):
        key=(repr(spec),repr(context))
        if key not in cache:
            cache[key]=factory.build_part_render_data(spec,context)
        return cache[key]
    designer=SimpleNamespace(_authoritative_part_render_cache=cache,
                             _authoritative_render_data=authoritative)
    probe=Probe()
    try:
        probe.observe_material_factory(factory,'build_part_render_data')
        probe.observe_authoritative_render(designer)
        first=designer._authoritative_render_data(spec,context)
        second=designer._authoritative_render_data(spec,context)
        assert first is second
        assert probe.counts['authoritative_render_cache_miss'] == 1
        assert probe.counts['authoritative_render_cache_hit'] == 1
        assert probe.counts['material_factory_calls'] == 1
        assert probe.flat_material_builds['build_part_render_data:Spec'] == 1
        probe.reset()
        assert not probe.flat_material_builds
        assert designer._authoritative_render_data(spec,context) is first
        assert probe.counts['authoritative_render_cache_hit'] == 1
        assert probe.counts['material_factory_calls'] == 0
    finally:
        probe.stack.close()
    assert designer._authoritative_render_data is authoritative
    assert factory.build_part_render_data is build_part_render_data


def test_issue1816_material_factory_errors_are_not_counted_as_success():
    from types import SimpleNamespace
    import pytest
    from tools.whd_performance_baseline import Probe
    def failing(_spec):
        raise ValueError('real solver failure')
    factory=SimpleNamespace(build_part_render_data=failing)
    probe=Probe()
    try:
        probe.observe_material_factory(factory,'build_part_render_data')
        with pytest.raises(ValueError,match='real solver failure'):
            factory.build_part_render_data(object())
        assert probe.counts['material_factory_calls'] == 0
        assert probe.milliseconds['material_factory_calls'] >= 0
    finally:
        probe.stack.close()
    assert factory.build_part_render_data is failing
