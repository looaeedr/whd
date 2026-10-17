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


def test_issue1816_material_cache_hit_returns_existing_2d_factory_result():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    class TestCache:
        def __init__(self):
            self.value=None
        def lookup(self, key):
            return SimpleNamespace(receipt=SimpleNamespace(hit=self.value is not None),
                                   result=self.value)
    class Spec:
        pass
    spec=Spec()
    calls=[]
    def build_part_render_data(item):
        calls.append(item)
        return {'real_material': object()}
    factory=SimpleNamespace(build_part_render_data=build_part_render_data)
    cache=TestCache()
    probe=Probe()
    try:
        probe.observe_manufacturing_cache(TestCache)
        probe.observe_material_factory(factory,'build_part_render_data')
        def acquire():
            found=cache.lookup('key')
            if found.result is None:
                cache.value=factory.build_part_render_data(spec)
            return cache.value
        first=acquire()
        assert acquire() is first
        assert len(calls) == 1
        assert probe.counts['manufacturing_cache_miss'] == 1
        assert probe.counts['manufacturing_cache_hit'] == 1
        assert probe.counts['material_factory_calls'] == 1
        assert probe.flat_material_builds['build_part_render_data:Spec'] == 1
        probe.reset()
        assert not probe.flat_material_builds
        assert acquire() is first
        assert probe.counts['manufacturing_cache_hit'] == 1
        assert probe.counts['material_factory_calls'] == 0
    finally:
        probe.stack.close()
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



def test_issue1816_supplemental_factory_does_not_pollute_prior_five_factory_totals():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    part_id = 'base_plate:fixing_plate:left'
    def real_builder(part, *, snapshot=None):
        return SimpleNamespace(part_id=part, geometry=object(), snapshot=snapshot)
    owner=SimpleNamespace(build_fixing_plate_source_render_data=real_builder)
    probe=Probe()
    try:
        probe.observe_supplemental_material_factory(
            owner,'build_fixing_plate_source_render_data','fixing_plate_source_flat',
            part_id=True)
        result=owner.build_fixing_plate_source_render_data(part_id, snapshot={'t':2})
        assert result.part_id == part_id and result.snapshot == {'t':2}
        assert probe.counts['supplemental_material_factory_calls'] == 1
        assert probe.supplemental_material_builds[
            'fixing_plate_source_flat:base_plate:fixing_plate:left'] == 1
        assert probe.counts['material_factory_calls'] == 0
        assert not probe.flat_material_builds
        probe.reset()
        assert not probe.supplemental_material_builds
        assert probe.counts['supplemental_material_factory_calls'] == 0
    finally:
        probe.stack.close()
    assert owner.build_fixing_plate_source_render_data is real_builder


def test_issue1816_supplemental_service_alias_success_and_failure_not_faked():
    from types import SimpleNamespace
    import pytest
    from tools.whd_performance_baseline import Probe
    class EndCapPartSpec:
        pass
    spec=EndCapPartSpec()
    result=object()
    def real_alias(value, context):
        if context == 'bad':
            raise ValueError('source relief invalid')
        return result
    owner=SimpleNamespace(build_part_render_data=real_alias)
    probe=Probe()
    try:
        probe.observe_supplemental_material_factory(
            owner,'build_part_render_data','service_relief_replay_material')
        assert owner.build_part_render_data(spec,'good') is result
        with pytest.raises(ValueError,match='source relief invalid'):
            owner.build_part_render_data(spec,'bad')
        assert probe.counts['supplemental_material_factory_calls'] == 1
        assert probe.supplemental_material_builds[
            'service_relief_replay_material:EndCapPartSpec'] == 1
        assert probe.milliseconds['supplemental_material_factory_calls'] >= 0
        assert probe.counts['material_factory_calls'] == 0
    finally:
        probe.stack.close()
    assert owner.build_part_render_data is real_alias


def test_issue1816_genuine_fixing_plate_factory_builds_real_material_unchanged():
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
        BASE_FIXING_PLATE_PREFIX,
    )
    from ae_engine import receiving_base_fixing_plate_geometry as module
    from tools.whd_performance_baseline import Probe
    key=BASE_FIXING_PLATE_PREFIX+'left'
    before=build_fixing_plate_source_render_data(key)
    probe=Probe()
    try:
        probe.observe_supplemental_material_factory(
            module,'build_fixing_plate_source_render_data',
            'fixing_plate_source_flat',part_id=True)
        after=module.build_fixing_plate_source_render_data(key)
        assert after.material.equals(before.material)
        assert after.material.area > 0
        assert after.scene is not None
        assert probe.supplemental_material_builds[
            f'fixing_plate_source_flat:{key}'] == 1
    finally:
        probe.stack.close()
    assert module.build_fixing_plate_source_render_data is build_fixing_plate_source_render_data


def test_issue1816_actual_primary_gui_owns_authoritative_render_method():
    import gui
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data,
    )
    assert gui.Phase6ApplicationHost._authoritative_render_data is _authoritative_render_data
    assert gui.Phase6PrimaryApplication._authoritative_render_data is _authoritative_render_data


def test_issue1816_primary_render_cache_receipt_tracks_exact_spec_context_key():
    from types import SimpleNamespace
    from tools.whd_performance_baseline import Probe
    class ExampleSpec:
        pass
    spec = ExampleSpec()
    ctx = SimpleNamespace(draw_stock=False)
    original_result = object()
    class TestPrimaryApplication:
        def __init__(self):
            self._authoritative_part_render_cache = {}
            self.builder_calls = 0
        def _authoritative_render_data(self, spec, context=None):
            key = (repr(spec), repr(context))
            cache = self._authoritative_part_render_cache
            if key not in cache:
                self.builder_calls += 1
                cache[key] = original_result
            return cache[key]
    app = TestPrimaryApplication()
    original = app._authoritative_render_data.__func__
    probe = Probe()
    try:
        probe.observe_primary_authoritative_render(app)
        assert app._authoritative_render_data(spec, ctx) is original_result
        assert app._authoritative_render_data(spec, ctx) is original_result
        assert app.builder_calls == 1
        assert probe.counts['authoritative_render_cache_miss'] == 1
        assert probe.counts['authoritative_render_cache_hit'] == 1
        assert probe.authoritative_cache_parts[
            'authoritative_render_cache_hit:ExampleSpec'] == 1
        assert probe.counts['material_factory_calls'] == 0
        probe.reset()
        assert not probe.authoritative_cache_parts
        assert app._authoritative_render_data(spec,ctx) is original_result
        assert probe.counts['authoritative_render_cache_hit'] == 1
    finally:
        probe.stack.close()
    assert app._authoritative_render_data.__func__ is original


def test_issue1818_rapid_3d_switch_samples_keep_1bay_and_3bay_separate():
    """Do not treat failed or mismatched-Bay latency as a measured improvement."""
    from tools.whd_performance_baseline import summarize
    op = 'issue1818_rapid_2d_3d_final_state'
    rows = [
        dict(bays=1, worker_sample=0, operation=op, cache_state='display_only',
             status='ok', wall_ms=15),
        dict(bays=1, worker_sample=1, operation=op, cache_state='display_only',
             status='ok', wall_ms=25),
        dict(bays=1, worker_sample=2, operation=op, cache_state='display_only',
             status='failed', wall_ms=1),
        dict(bays=3, worker_sample=0, operation=op, cache_state='display_only',
             status='ok', wall_ms=70),
    ]
    summary = {(v['bays'], v['operation']): v for v in summarize(rows)}
    assert summary[1, op]['n'] == 2
    assert summary[1, op]['failed'] == 1
    assert summary[1, op]['median_ms'] == 20
    assert summary[3, op]['n'] == 1
    assert summary[3, op]['median_ms'] == 70


def test_issue1817_paired_true_tk_samples_are_separate_from_general_baseline():
    """Retain head-to-head sample identity and never treat failed rows as speed."""
    from tools.whd_performance_baseline import summarize
    rows = [
        dict(bays=3, operation='issue1817_bay0_cached', cache_state='warm',
             status='ok', wall_ms=11),
        dict(bays=3, operation='issue1817_bay0_cached', cache_state='warm',
             status='ok', wall_ms=13),
        dict(bays=3, operation='issue1817_bay0_forced_full_comparison',
             cache_state='warm', status='ok', wall_ms=101),
        dict(bays=3, operation='issue1817_bay0_forced_full_comparison',
             cache_state='warm', status='failed', wall_ms=1),
        dict(bays=1, operation='open_multi', cache_state='warm',
             status='ok', wall_ms=20),
    ]
    entries = {(r['bays'],r['operation']):r for r in summarize(rows)}
    assert entries[3,'issue1817_bay0_cached']['n'] == 2
    assert entries[3,'issue1817_bay0_cached']['median_ms'] == 12
    assert entries[3,'issue1817_bay0_forced_full_comparison']['n'] == 1
    assert entries[3,'issue1817_bay0_forced_full_comparison']['failed'] == 1
    assert entries[3,'issue1817_bay0_forced_full_comparison']['median_ms'] == 101
    assert entries[1,'open_multi']['n'] == 1


def test_issue1817_manufacturing_exact_state_undo_cache_is_bounded_and_fail_closed():
    from phase6_manufacturing_cache import ManufacturingCacheService, ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult, ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult, ManufacturingMutationResult,
        ManufacturingEffects,
    )
    def result(v):
        return ManufacturingResolveResult(
            geometry=v, diagnostics=ManufacturingDiagnosticsResult(),
            mutations=ManufacturingMutationResult(), effects=ManufacturingEffects(),
            cache=ManufacturingCacheReceipt(signature="", hit=False, stored=False))
    one = ManufacturingCacheService()
    a,b,c = (ManufacturingCacheKey(x*64) for x in "abc")
    one.store(a, result("original"))
    one.store(b, result("changed"))
    assert one.lookup(a).result is None, "non-Receiving single-entry behavior remains"
    service = ManufacturingCacheService(max_entries=2)
    first, second = result("3 bays"), result("4 bays")
    service.store(a, first)
    service.store(b, second)
    assert service.lookup(a).result is first
    assert service.lookup(b).result is second
    service.store(c, result("5 bays"))
    assert service.lookup(a).result is None, "bounded LRU evicts oldest exact state"
    assert service.lookup(c).result.geometry == "5 bays"
    service.clear()
    assert service.lookup(b).result is None
    assert service.lookup(c).result is None
    assert service.key is None and service.result is None


def test_issue1817_only_receiving_set_bay_opted_into_short_undo_history():
    from phase6_manufacturing_adapter import _cache_service_for_app
    from types import SimpleNamespace
    receiving = SimpleNamespace(_phase6_input_snapshot={
        "model":"受電箱", "active_mode":"set_bay"})
    vault = SimpleNamespace(_phase6_input_snapshot={"model":"金庫型"})
    quantity = SimpleNamespace(_phase6_input_snapshot={
        "model":"受電箱", "active_mode":"quantity"})
    assert _cache_service_for_app(receiving).max_entries == 2
    assert _cache_service_for_app(vault).max_entries == 1
    assert _cache_service_for_app(quantity).max_entries == 1
    receiving._phase6_input_snapshot["active_mode"] = "quantity"
    assert _cache_service_for_app(receiving).max_entries == 1


def test_issue1817_undo_hit_restores_exact_world_collision_diagnostics(monkeypatch):
    from types import SimpleNamespace
    import phase6_manufacturing_adapter as adapter
    from phase6_manufacturing_cache import ManufacturingCacheService, ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult, ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult, ManufacturingMutationResult,
        ManufacturingEffects,
    )
    service=ManufacturingCacheService(max_entries=2)
    a,b = ManufacturingCacheKey("a"*64), ManufacturingCacheKey("b"*64)
    def result(geometry, probes):
        return ManufacturingResolveResult(
            geometry=geometry,
            diagnostics=ManufacturingDiagnosticsResult(
                interference_probe_parts=tuple(probes)),
            mutations=ManufacturingMutationResult(),
            effects=ManufacturingEffects(),
            cache=ManufacturingCacheReceipt(signature="",hit=False,stored=False))
    first=result(object(), ("3bay collision",))
    second=result(object(), ("4bay collision",))
    service.store(a,first)
    service.store(b,second)
    app=SimpleNamespace(
        _phase6_input_snapshot={"model":"受電箱","active_mode":"set_bay"},
        _phase6_last_interference_probe_parts=("4bay collision",),
        _phase6_last_relief_errors={"old": "stale"},
        _phase6_last_relief_solutions={"old": "stale"},
    )
    monkeypatch.setattr(adapter,"build_manufacturing_cache_key",lambda app:a)
    monkeypatch.setattr(adapter,"build_manufacturing_request",
                        lambda *args,**kwargs: (_ for _ in ()).throw(
                            AssertionError("exact cached undo may not rebuild")))
    got=adapter.resolve_manufacturing_for_app(app,cache_service=service)
    assert got is first.geometry
    assert app._phase6_last_interference_probe_parts==("3bay collision",)
    assert not app._phase6_last_relief_errors
    assert not app._phase6_last_relief_solutions
    assert app._phase6_last_resolved_manufacturing_signature==a.fingerprint


def test_issue1817_baseline_reload_evicts_current_and_previous_manufacturing():
    from types import SimpleNamespace
    from gui_modules.application.lifecycle import _reload_current_baseline_features
    from phase6_manufacturing_cache import ManufacturingCacheService,ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult,ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,ManufacturingMutationResult,
        ManufacturingEffects)
    service=ManufacturingCacheService(max_entries=2)
    result=ManufacturingResolveResult(
        geometry=object(),diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature="",hit=False,stored=False))
    a,b=(ManufacturingCacheKey(x*64) for x in "ab")
    service.store(a,result)
    service.store(b,result)
    owner=SimpleNamespace(_derived_cache_owner=None,
                          _phase6_manufacturing_cache_service=service)
    _reload_current_baseline_features(owner)
    assert service.lookup(a).result is None and service.lookup(b).result is None


def test_issue1817_receiving_undo_history_revokes_on_disk_baseline_change(tmp_path, monkeypatch):
    """Exact app dimensions cannot certify reused material after DXF source changes."""
    from types import SimpleNamespace
    from ae_engine import ae
    from phase6_manufacturing_adapter import _cache_service_for_app
    from phase6_manufacturing_cache import ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult,ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,ManufacturingMutationResult,
        ManufacturingEffects,
    )
    path=tmp_path/"箱身.dxf"
    path.write_text("old-source",encoding="utf-8")
    monkeypatch.setattr(
        ae,"baseline_part_path",
        lambda model,filename: str(path) if filename=="箱身.dxf" else None)
    app=SimpleNamespace(_phase6_input_snapshot={
        "model":"受電箱", "active_mode":"set_bay"})
    cache=_cache_service_for_app(app)
    result=ManufacturingResolveResult(
        geometry=object(),diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature="",hit=False,stored=False))
    a,b=(ManufacturingCacheKey(x*64) for x in "ab")
    cache.store(a,result);cache.store(b,result)
    assert cache.lookup(a).result is result
    # Same pathname, but modified file bytes/stat: neither old receipt is valid.
    path.write_text("new-source-content-with-different-length",encoding="utf-8")
    assert _cache_service_for_app(app) is cache
    assert cache.lookup(a).result is None
    assert cache.lookup(b).result is None
    cache.store(a,result)
    # Explicit source-reload generation matters even if file stat unchanged.
    ae.force_reload_baseline_dxf_sources()
    _cache_service_for_app(app)
    assert cache.lookup(a).result is None
    assert cache.max_entries == 2


def test_issue1817_receiving_source_stamp_unknown_fails_closed(monkeypatch):
    from types import SimpleNamespace
    from ae_engine import ae
    from phase6_manufacturing_adapter import _cache_service_for_app
    from phase6_manufacturing_cache import ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult,ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,ManufacturingMutationResult,
        ManufacturingEffects)
    app=SimpleNamespace(_phase6_input_snapshot={
        "model":"受電箱", "active_mode":"set_bay"})
    monkeypatch.setattr(ae,"baseline_part_path",
        lambda model,filename: "/inaccessible/source.dxf"
        if filename=="箱身.dxf" else None)
    monkeypatch.setattr(ae,"baseline_source_fingerprint",
        lambda path: (_ for _ in ()).throw(PermissionError("source missing")))
    cache=_cache_service_for_app(app)
    result=ManufacturingResolveResult(
        geometry=object(),diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(),effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature="",hit=False,stored=False))
    key=ManufacturingCacheKey("d"*64)
    cache.store(key,result)
    _cache_service_for_app(app)
    assert cache.lookup(key).result is None


def test_issue1817_fixing_plate_source_material_reuses_exact_immutable_wkb():
    """Only certified original CUTTING, never unfinished weld/fold metadata."""
    from ae_engine.receiving_base_fixing_plate_geometry import (
        BASE_FIXING_PLATE_PREFIX, LARGE_SOURCE, SMALL_SOURCE,
        _cached_source_flat_material_wkb, build_fixing_plate_source_render_data,
    )
    from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
    _cached_source_flat_material_wkb.cache_clear()
    left=build_fixing_plate_source_render_data(BASE_FIXING_PLATE_PREFIX+"left")
    right=build_fixing_plate_source_render_data(BASE_FIXING_PLATE_PREFIX+"right")
    assert _cached_source_flat_material_wkb.cache_info().misses==1
    assert _cached_source_flat_material_wkb.cache_info().hits==1
    assert left is not right and left.scene is not right.scene
    assert left.material is not right.material
    assert left.material.wkb==right.material.wkb
    assert material_polygon_from_final_scene(left.scene).wkb==left.material.wkb
    assert material_polygon_from_final_scene(right.scene).wkb==right.material.wkb
    assert left.metadata["stable_id"] != right.metadata["stable_id"]
    assert left.metadata["formed_geometry_verified"] is False
    assert right.metadata["weld_z_verified"] is False
    small=build_fixing_plate_source_render_data(
        BASE_FIXING_PLATE_PREFIX+"small_source",source_kind=SMALL_SOURCE)
    assert small.material.is_valid and small.material.is_simple
    assert _cached_source_flat_material_wkb.cache_info().misses==2
    assert material_polygon_from_final_scene(small.scene).wkb==small.material.wkb
    assert small.metadata["source_profile"]=="small"
    assert small.metadata["manufacturing_ready"] is False


def test_issue1817_fixing_plate_source_cache_cannot_bypass_part_authorization():
    import pytest
    from ae_engine.receiving_base_fixing_plate_geometry import (
        BASE_FIXING_PLATE_PREFIX,
        _cached_source_flat_material_wkb, build_fixing_plate_source_render_data,
    )
    _cached_source_flat_material_wkb.cache_clear()
    with pytest.raises(ValueError,match="unknown physical large"):
        build_fixing_plate_source_render_data(BASE_FIXING_PLATE_PREFIX+"unverified")
    assert _cached_source_flat_material_wkb.cache_info().currsize==0


def test_issue1817_original_fixing_plate_contours_not_retraced_for_sibling_part(monkeypatch):
    """Real large left/right source scenes stay separate without repeated trig arcs."""
    from ae_engine import receiving_base_fixing_plate_geometry as source
    from ae_engine.receiving_base_fixing_plate import BASE_FIXING_PLATE_PREFIX
    invocations = []
    original_arc = source._arc
    def actual_arc(*args, **kwargs):
        invocations.append((args,kwargs))
        return original_arc(*args,**kwargs)
    monkeypatch.setattr(source, "_arc", actual_arc)
    source._outline.cache_clear()
    source._slot.cache_clear()
    try:
        left = source.build_fixing_plate_source_render_data(
            BASE_FIXING_PLATE_PREFIX+"left")
        after_left = len(invocations)
        assert after_left > 0, "RED signal: first material source must generate real arc points"
        right = source.build_fixing_plate_source_render_data(
            BASE_FIXING_PLATE_PREFIX+"right")
        assert len(invocations) == after_left, (
            "uncached repeated source-only curved contours rebuild for each sibling")
        assert left.scene is not right.scene
        assert left.scene.primitives == right.scene.primitives
        assert left.scene.primitives is not right.scene.primitives
        assert left.material is not right.material
        assert left.material.equals(right.material)
        assert left.metadata["stable_id"] != right.metadata["stable_id"]
        right.scene.primitives.pop()
        assert len(left.scene.primitives) > len(right.scene.primitives)
    finally:
        source._outline.cache_clear()
        source._slot.cache_clear()


def test_issue1817_source_contour_cache_key_includes_original_physical_pattern():
    from dataclasses import replace
    from ae_engine import receiving_base_fixing_plate_geometry as source
    source._outline.cache_clear()
    source._slot.cache_clear()
    try:
        original = source.source_pattern(source.LARGE_SOURCE)
        outline = source._outline(original)
        assert source._outline(original) is outline
        changed = replace(original, width=original.width+1)
        assert source._outline(changed) is not outline
        assert source._outline(changed) != outline
        small = source.source_pattern(source.SMALL_SOURCE)
        assert source._outline(small) != outline
        assert source._slot(*original.slot_centers[0],
                            original.slot_length, original.slot_width) == (
               source._slot(*original.slot_centers[0],
                            original.slot_length, original.slot_width))
    finally:
        source._outline.cache_clear()
        source._slot.cache_clear()


def test_issue1817_cached_contours_keep_source_flat_small_dxf_roundtrip(tmp_path):
    from ae_engine import receiving_base_fixing_plate_geometry as source
    from ae_engine.receiving_base_fixing_plate import BASE_FIXING_PLATE_PREFIX
    source._outline.cache_clear()
    source._slot.cache_clear()
    try:
        small=source.build_fixing_plate_source_render_data(
            BASE_FIXING_PLATE_PREFIX+"small_source",
            source_kind=source.SMALL_SOURCE)
        assert small.material.is_valid and small.material.area > 0
        assert {p.layer for p in small.scene.primitives} == {
            "CUTTING", "MARKING"}
        output=source.save_independent_source_flat_dxf(
            BASE_FIXING_PLATE_PREFIX+"small_source",tmp_path/"small.dxf")
        assert output == str(tmp_path/"small.dxf")
        assert (tmp_path/"small.dxf").is_file()
    finally:
        source._outline.cache_clear()
        source._slot.cache_clear()


def test_issue1817_real_multipart_query_uses_authoritative_partspec_cache(monkeypatch):
    """RED: multipart Receiving BoxBody must not bypass the existing 2D/3D cache."""
    from dataclasses import replace
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from ae_engine import manufacturing_api
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data, _query_fold_designer_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner
    from phase6_box_body_structure import BoxBodyStructureType

    spec=BoxBodyPartSpec(
        width=800.0,height=1600.0,depth=350.0,thickness=2.0,
        frame_width=29.0,model_name="受電箱",
        structure_state={
            "active_type":BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
        })
    context=ManufacturingContext(draw_stock=False)
    calls=[]
    def actual_factory(s,c):
        calls.append((repr(s),repr(c)))
        return object()
    monkeypatch.setattr(
        manufacturing_api,"build_box_body_structure_render_data",actual_factory)
    class ActualQueryOwner:
        def __init__(self):
            self.spec=spec
            self._derived_cache_owner=Phase6DerivedCacheOwner()
            self._authoritative_part_render_cache=(
                self._derived_cache_owner.cache("authoritative_render"))
        def _fold_designer_part_spec_from_payload(self, part_key, payload):
            assert part_key == "box_body"
            return self.spec,context
        def _authoritative_render_data(self,s,c=None):
            return _authoritative_render_data(self,s,c)
    owner=ActualQueryOwner()
    first=_query_fold_designer_render_data(owner,"box_body",{})
    second=_query_fold_designer_render_data(owner,"box_body",{})
    assert second is first
    assert len(calls)==1, "multipart query bypasses authoritative PartSpec cache"
    assert (repr(spec),repr(context)) in owner._authoritative_part_render_cache
    # Exact changed source dimensions invalidate by typed PartSpec signature.
    owner.spec=replace(spec,width=820)
    changed=_query_fold_designer_render_data(owner,"box_body",{})
    assert changed is not first and len(calls)==2
    # A real geometry invalidation must still force a subsequent build.
    assert owner._derived_cache_owner.invalidate(
        "geometry",changed_keys=("w",))
    again=_query_fold_designer_render_data(owner,"box_body",{})
    assert again is not changed and len(calls)==3
    assert calls[-1][0]==repr(owner.spec)


def test_issue1817_receiving_unchanged_exact_partspec_reuses_material_across_whd_edit(monkeypatch):
    """RED: only source-certified identical physical PartSpec survives W/H/D invalidation.

    Raw 2D material reuse must not bypass a new full manufacturing resolver,
    assembly offset projection, collision or relief computation.
    """
    from dataclasses import replace
    from types import SimpleNamespace

    import phase6_manufacturing_adapter
    from ae_engine import manufacturing_api
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner
    from phase6_box_body_structure import BoxBodyStructureType

    source_generation = ["verified-source-A"]
    monkeypatch.setattr(
        phase6_manufacturing_adapter,
        "_receiving_baseline_source_stamp",
        lambda model, **kwargs: tuple(source_generation) if (
            model == "受電箱" and kwargs["include_physical_panels"]
        ) else None,
    )
    calls = []
    def build(s, c):
        calls.append((repr(s), repr(c)))
        return object()
    monkeypatch.setattr(
        manufacturing_api, "build_box_body_structure_render_data", build,
    )
    spec = BoxBodyPartSpec(
        width=800.0, height=1600.0, depth=350.0, thickness=2.0,
        frame_width=29.0, model_name="受電箱",
        structure_state={
            "active_type": BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
        },
    )
    ctx = ManufacturingContext(draw_stock=False)
    derived = Phase6DerivedCacheOwner()
    app = SimpleNamespace(
        _derived_cache_owner=derived,
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"},
    )
    original = _authoritative_render_data(app, spec, ctx)
    assert _authoritative_render_data(app, spec, ctx) is original
    assert len(calls) == 1
    derived.invalidate("display")
    assert _authoritative_render_data(app, spec, ctx) is original
    assert len(calls) == 1, "display-only edits must not retire geometry material"

    # The original authoritative cache is still invalidated. Only an exact,
    # independently witnessed raw render may be returned from bounded history.
    derived.invalidate("geometry", changed_keys=("w",))
    assert derived.cache("authoritative_render") == {}
    assert _authoritative_render_data(app, spec, ctx) is original
    assert len(calls) == 1

    different = _authoritative_render_data(app, replace(spec, width=820), ctx)
    assert different is not original and len(calls) == 2
    derived.invalidate("geometry", changed_keys=("h", "d"))
    assert _authoritative_render_data(app, spec, ctx) is original
    assert len(calls) == 2

    # DXF source generation changes and unknown geometry edits must not reuse
    # the old physical material, even if the nominal Spec/Context is unchanged.
    source_generation[:] = ["verified-source-B"]
    assert _authoritative_render_data(app, spec, ctx) is not original
    assert len(calls) == 3
    derived.invalidate("geometry", changed_keys=("unknown_joint",))
    _authoritative_render_data(app, spec, ctx)
    assert len(calls) == 4
    derived.invalidate("baseline", changed_keys=("source_reload",))
    _authoritative_render_data(app, spec, ctx)
    assert len(calls) == 5


def test_issue1817_cross_edit_retention_is_never_used_outside_receiving_set_bay(monkeypatch):
    from types import SimpleNamespace
    import phase6_manufacturing_adapter
    from ae_engine import manufacturing_api
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner
    from phase6_box_body_structure import BoxBodyStructureType

    monkeypatch.setattr(
        phase6_manufacturing_adapter,
        "_receiving_baseline_source_stamp",
        lambda _model, **kwargs: (("source", "verified"),) if (
            kwargs["include_physical_panels"]
        ) else None,
    )
    calls = []
    monkeypatch.setattr(
        manufacturing_api, "build_box_body_structure_render_data",
        lambda _s, _c: calls.append(1) or object(),
    )
    spec = BoxBodyPartSpec(
        width=800, height=1600, depth=350, thickness=2,
        frame_width=29, model_name="受電箱",
        structure_state={"active_type": BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value},
    )
    ctx = ManufacturingContext(draw_stock=False)
    derived = Phase6DerivedCacheOwner()
    app = SimpleNamespace(
        _derived_cache_owner=derived,
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "quantity"},
    )
    _authoritative_render_data(app, spec, ctx)
    derived.invalidate("geometry", changed_keys=("w",))
    _authoritative_render_data(app, spec, ctx)
    assert len(calls) == 2, "quantity mode is not certified for cross-edit reuse"


def test_issue1817_exact_material_witness_covers_all_physical_panel_sources(
    monkeypatch, tmp_path,
):
    """A dedicated left/right/rear DXF mutation retires raw material reuse."""
    from ae_engine import ae
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.receiving_panel_baselines import ROLE_FILES
    from phase6_manufacturing_adapter import _receiving_baseline_source_stamp

    root = tmp_path / "基準檔" / "受電箱"
    root.mkdir(parents=True)
    for role, name in ROLE_FILES.items():
        (root / name).write_bytes(("DXF witness:" + role).encode("utf-8"))
    # Standard legacy files may be absent, but the physical sources are
    # mandatory for the three-piece Receiving material factory.
    monkeypatch.setattr(ae, "baseline_part_path", lambda _model, _name: None)
    monkeypatch.setattr(
        ae, "baseline_source_fingerprint",
        lambda p: (str(p), p.stat().st_size, p.stat().st_mtime_ns, "parser-v1"),
    )
    ctx = ManufacturingContext(draw_stock=False, resource_root=tmp_path)
    before = _receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )
    assert before is not None
    assert {row[0] for row in before if len(row) == 3} == set(ROLE_FILES)

    (root / ROLE_FILES["right_side"]).write_bytes(b"DXF modified witness with different size")
    after = _receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )
    assert after is not None and after != before
    (root / ROLE_FILES["back"]).unlink()
    assert _receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    ) is None


def test_issue1817_complete_undo_cache_tracks_dedicated_three_piece_dxfs(monkeypatch):
    """RED: exact 3->4->3 global receipts cannot hide physical source changes.

    This exercises the real manufacturing cache-service entry, separately from
    the raw PartSpec render-material cache established in PR #1849.
    """
    from types import SimpleNamespace
    import phase6_manufacturing_adapter as adapter
    from phase6_manufacturing_cache import ManufacturingCacheKey
    from phase6_manufacturing_contracts import (
        ManufacturingResolveResult, ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult, ManufacturingMutationResult,
        ManufacturingEffects,
    )
    from phase6_box_body_structure import BoxBodyStructureType
    active_type = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    generation = ["physical-source-A"]
    witnesses = []
    def stamp(model, *, context=None, include_physical_panels=False):
        witnesses.append((model, include_physical_panels))
        return ("standard-source", tuple(generation)) if include_physical_panels else ("standard-source",)
    monkeypatch.setattr(adapter, "_receiving_baseline_source_stamp", stamp)
    app = SimpleNamespace(
        _phase6_input_snapshot={
            "model":"受電箱","active_mode":"set_bay",
            "box_body_structure":{"active_type": active_type},
        },
        designer_workspace=SimpleNamespace(
            box_body_structure_state=lambda: {"active_type": active_type},
        ),
    )
    cache = adapter._cache_service_for_app(app)
    assert witnesses[-1] == ("受電箱", True), (
        "multipart manufacturing undo must witness dedicated left/right/rear DXFs"
    )
    result = ManufacturingResolveResult(
        geometry=object(), diagnostics=ManufacturingDiagnosticsResult(),
        mutations=ManufacturingMutationResult(), effects=ManufacturingEffects(),
        cache=ManufacturingCacheReceipt(signature="", hit=False, stored=False),
    )
    first, second = (ManufacturingCacheKey(c * 64) for c in "ab")
    cache.store(first, result)
    cache.store(second, result)
    assert cache.lookup(first).result is result
    generation[:] = ["physical-source-B"]
    assert adapter._cache_service_for_app(app) is cache
    assert cache.lookup(first).result is None
    assert cache.lookup(second).result is None
    assert cache.max_entries == 2


def test_issue1817_integral_undo_does_not_require_dedicated_three_piece_sources(monkeypatch):
    from types import SimpleNamespace
    import phase6_manufacturing_adapter as adapter
    from phase6_box_body_structure import BoxBodyStructureType
    witnesses = []
    def stamp(model, *, context=None, include_physical_panels=False):
        witnesses.append(include_physical_panels)
        return ("standard-source",)
    monkeypatch.setattr(adapter, "_receiving_baseline_source_stamp", stamp)
    app = SimpleNamespace(
        _phase6_input_snapshot={"model":"受電箱", "active_mode":"set_bay"},
        designer_workspace=SimpleNamespace(
            box_body_structure_state=lambda: {
                "active_type": BoxBodyStructureType.INTEGRAL.value,
            },
        ),
    )
    assert adapter._cache_service_for_app(app).max_entries == 2
    assert witnesses == [False]


def test_issue1817_modal_dimension_stage_does_not_calculate_until_explicit_boundary():
    """RED: modal dimension edits coalesce, but save/export flush is authoritative."""
    from types import SimpleNamespace
    from gui_modules.application.command_router import _Phase6UpdateScheduler

    calls = []
    owner = SimpleNamespace(root=None)
    scheduler = _Phase6UpdateScheduler(owner, executor=lambda reasons: calls.append(frozenset(reasons)))
    scheduler.stage("geometry")  # no idle timer or manufacturing during a modal edit
    scheduler.stage("geometry")  # second confirmation replaces the first
    assert not scheduler.dirty
    assert scheduler.staged == {"geometry"}
    assert scheduler._after_job is None
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 0
    assert not calls
    # Save/Export must explicitly flush the *last* edited state without
    # waiting for the multi-settings window to close.
    assert scheduler.flush_now() is True
    assert calls == [frozenset({"geometry"})]
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 1
    assert not scheduler.staged and not scheduler.dirty
    assert scheduler.flush_now() is False  # close after save cannot solve again

    scheduler.stage("geometry")
    scheduler.submit("annotation", immediate=True)
    assert calls[-1] == frozenset({"geometry", "annotation"})
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 2
    assert not scheduler.staged
    scheduler.stage("geometry")
    scheduler.cancel_pending()
    assert scheduler.staged == set()  # cancelled editor must not leak an update


def test_issue1817_modal_dimension_stages_real_scheduler_boundary_not_eager_commit():
    """Check the production UI callback seam, not a shadow duplicate handler."""
    import inspect
    from gui_modules.application.fold_designer_composition_receiving import (
        open_receiving_multi_settings,
        _restore_receiving_assembly_after_modal,
    )
    body = inspect.getsource(open_receiving_multi_settings)
    dimension_only = body.split("def dimension_group(", 1)[1].split(
        "def single_size_quantity(", 1
    )[0]
    assert 'scheduler.stage("geometry")' in dimension_only
    assert 'submit_update_intent("geometry", commit=True)' not in dimension_only
    close = inspect.getsource(_restore_receiving_assembly_after_modal)
    assert "scheduler.flush_now()" in close
    assert 'getattr(scheduler, "staged", ())' in close


def test_issue1817_receiving_projected_whd_tk_trace_cannot_echo_full_solve(monkeypatch):
    """RED: canonical Receiving W/H/D projection is not a second operator edit."""
    from types import SimpleNamespace
    import fold_designer_bridge as bridge
    calls = []
    monkeypatch.setattr(
        bridge, "queue_fold_designer_update",
        lambda owner, *, executor: calls.append(owner) or True,
    )
    host = SimpleNamespace(_phase6_receiving_set_bay_guard=True)
    assert bridge._phase6_queue_update(host) is False
    assert calls == []
    host._phase6_receiving_set_bay_guard = False
    assert bridge._phase6_queue_update(host) is True
    assert calls == [host], "genuine operator Tk edits still queue one update"


def test_issue1817_receiving_raw_endcap_preserves_only_witnessed_exact_material(monkeypatch):
    """Reuse only unchanged source-verified raw EndCap, never finished relief."""
    from dataclasses import replace
    from types import SimpleNamespace
    from ae_engine import manufacturing_api
    from ae_engine.contracts import (
        BoxBodyPartSpec, EndCapPartSpec, EndCapAssemblyReliefRequest,
        ManufacturingContext,
    )
    import phase6_manufacturing_adapter as adapter
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner

    version = ["source-A"]
    def witness(model, **kwargs):
        assert model == "受電箱"
        assert kwargs["include_physical_panels"] is False
        return (("箱身.dxf", ("body", version[0])),
                ("封頭尾.dxf", ("endcap", version[0])),
                ("門.dxf", ("door", version[0])))
    monkeypatch.setattr(adapter, "_receiving_baseline_source_stamp", witness)
    calls = []
    monkeypatch.setattr(
        manufacturing_api, "build_part_render_data",
        lambda spec, ctx: calls.append((spec, ctx)) or object())
    owner = Phase6DerivedCacheOwner()
    app = SimpleNamespace(_derived_cache_owner=owner,
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"})
    spec = EndCapPartSpec(width=800, depth=350, thickness=2,
                          frame_width=29, model_name="受電箱")
    context = ManufacturingContext(draw_stock=False)
    head = _authoritative_render_data(app, spec, context)
    assert _authoritative_render_data(app, spec, context) is head
    assert len(calls) == 1

    owner.invalidate("geometry", changed_keys=("w", "h", "d"))
    assert owner.cache("authoritative_render") == {}
    assert _authoritative_render_data(app, spec, context) is head
    assert len(calls) == 1  # untouched raw 2D material was not rebuilt
    tail = _authoritative_render_data(app, replace(spec, is_tail=True), context)
    assert tail is not head and len(calls) == 2
    resized = _authoritative_render_data(app, replace(spec, width=810), context)
    assert resized is not head and len(calls) == 3

    # A committed relief cut is a different material authority and cannot be
    # carried across even an unrelated W/H/D edit.
    committed = replace(
        spec, resolved_assembly_relief_cuts=(((0, 0), (4, 0), (4, 4)),))
    first_committed = _authoritative_render_data(app, committed, context)
    owner.invalidate("geometry", changed_keys=("w",))
    assert _authoritative_render_data(app, committed, context) is not first_committed

    # A nested assembly relief request is never cross-transaction material.
    nested = replace(spec, assembly_relief=EndCapAssemblyReliefRequest(
        BoxBodyPartSpec(width=800, height=1600, depth=350, thickness=2,
                        frame_width=29, model_name="受電箱")))
    nested_first = _authoritative_render_data(app, nested, context)
    owner.invalidate("geometry", changed_keys=("w",))
    assert _authoritative_render_data(app, nested, context) is not nested_first
    # Source replacement and unknown dependency both force fresh raw input.
    version[:] = ["source-B"]
    assert _authoritative_render_data(app, spec, context) is not head
    owner.invalidate("geometry", changed_keys=("joint_unknown",))
    fresh = _authoritative_render_data(app, spec, context)
    assert fresh is not head


def test_issue1817_receiving_endcap_missing_dxf_source_never_reuses_old_material(monkeypatch):
    from types import SimpleNamespace
    from ae_engine import manufacturing_api
    from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
    import phase6_manufacturing_adapter as adapter
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _authoritative_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner

    monkeypatch.setattr(adapter, "_receiving_baseline_source_stamp",
                        lambda _model, **_kw: (("箱身.dxf", ("a",)),
                                                ("封頭尾.dxf", None),
                                                ("門.dxf", None)))
    calls = []
    monkeypatch.setattr(manufacturing_api, "build_part_render_data",
                        lambda _spec, _ctx: calls.append(1) or object())
    owner = Phase6DerivedCacheOwner()
    app = SimpleNamespace(_derived_cache_owner=owner,
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"})
    spec = EndCapPartSpec(width=800, depth=350, thickness=2,
                          frame_width=29, model_name="受電箱")
    ctx = ManufacturingContext(draw_stock=False)
    a = _authoritative_render_data(app, spec, ctx)
    owner.invalidate("geometry", changed_keys=("w",))
    b = _authoritative_render_data(app, spec, ctx)
    assert a is not b and len(calls) == 2


def test_issue1817_exact_receiving_inner_door_panel_reuses_only_frozen_inputs(monkeypatch):
    """W/H/D of an unrelated Bay must not rematerialize an identical panel."""
    from dataclasses import replace
    from types import SimpleNamespace
    from ae_engine import manufacturing_api
    from ae_engine.inner_door_panels import InnerDoorPanelPart
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _query_fold_designer_render_data,
    )
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner
    from ae_engine.cabinet_types import policy as family

    panel = InnerDoorPanelPart(
        stable_id="inner_door:test:panel", inner_door_id="test",
        cell_key="upper", width=685, height=1040, thickness=2,
    )
    current = [panel]
    monkeypatch.setattr(family, "derive_inner_door_panels",
                        lambda _data: tuple(current))
    calls = []
    monkeypatch.setattr(
        manufacturing_api, "build_inner_door_panel_render_data",
        lambda part, *, features=(): calls.append((part, features)) or object())
    derived = Phase6DerivedCacheOwner()
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"},
        _derived_cache_owner=derived,
    )
    def render(features=()):
        return _query_fold_designer_render_data(
            app, "inner_door:test:panel",
            {"model": "受電箱", "features": features})

    first = render()
    assert render() is first and len(calls) == 1
    derived.invalidate("geometry", changed_keys=("w", "h", "d"))
    assert render() is first and len(calls) == 1
    # Any change to physical PartSpec or authored opening must miss.
    current[:] = [replace(panel, width=686)]
    resized = render()
    assert resized is not first and len(calls) == 2
    current[:] = [panel]
    changed_holes = render(({"kind": "圓孔", "x": 16, "y": 8, "d1": 6},))
    assert changed_holes is not first and len(calls) == 3
    assert render(({"kind": "圓孔", "x": 16, "y": 8, "d1": 6},)) is changed_holes
    another_hole = render(({"kind": "圓孔", "x": 18, "y": 8, "d1": 6},))
    assert another_hole is not changed_holes and len(calls) == 4
    # Unknown feature representations fail closed, rather than repr-hashing.
    opaque = object()
    unknown = render((opaque,))
    derived.invalidate("geometry", changed_keys=("w",))
    assert render((opaque,)) is not unknown
    derived.invalidate("geometry", changed_keys=("joint_unknown",))
    assert render() is not first
    derived.invalidate("baseline", changed_keys=("source_reload",))
    again = render()
    assert again is not first

    # Product cache history may not leak to other family or quantity mode.
    app._phase6_input_snapshot["active_mode"] = "quantity"
    assert render() is not again
    assert render() is not again
    app._phase6_input_snapshot["active_mode"] = "set_bay"
    app._phase6_input_snapshot["model"] = "金庫型"
    assert render() is not again


def test_issue1817_real_inner_door_panel_cache_matches_fresh_manufacturing_material():
    """A cache hit reuses the exact 2D drawing, metadata and fold topology."""
    from ae_engine.inner_door_panels import InnerDoorPanelPart
    from ae_engine import manufacturing_api
    from types import SimpleNamespace
    from gui_modules.application import fold_designer_manufacturing_projection as projection
    from gui_modules.application.state_sync import Phase6DerivedCacheOwner
    from ae_engine.cabinet_types import policy as family

    panel = InnerDoorPanelPart(
        stable_id="inner_door:parity:panel", inner_door_id="parity",
        cell_key="upper", width=689, height=1040, thickness=2)
    actual = manufacturing_api.build_inner_door_panel_render_data(panel)
    cached = {
        "model": "受電箱", "active_mode": "set_bay",
        "features": (),
    }
    # Use a pure panel selection seam, not a fake geometry factory.
    existing = family.derive_inner_door_panels
    try:
        family.derive_inner_door_panels = lambda _source: (panel,)
        owner = SimpleNamespace(
            _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"},
            _derived_cache_owner=Phase6DerivedCacheOwner(),
        )
        a = projection._query_fold_designer_render_data(
            owner, "inner_door:parity:panel", cached)
        owner._derived_cache_owner.invalidate(
            "geometry", changed_keys=("w",))
        b = projection._query_fold_designer_render_data(
            owner, "inner_door:parity:panel", cached)
    finally:
        family.derive_inner_door_panels = existing
    assert a is b
    assert a.material.equals(actual.material)
    assert a.scene.primitives == actual.scene.primitives
    assert a.fold_guides == actual.fold_guides
    assert a.unfolded_topology == actual.unfolded_topology
    assert a.metadata == actual.metadata


def test_issue1818_navigation_only_sync_rejects_real_or_unknown_changes():
    from copy import deepcopy
    from phase6_sync_envelope import navigation_only_change
    old = {'model': '受電箱', 'active_part': 'box_body', 'w': 800,
           'workspace': {'active_part': 'box_body', 'existing_parts': ['box_body', 'head'],
                         'part_features': {}, 'part_profiles': {}}, 'revision': 1}
    new = deepcopy(old)
    new.update(active_part='head', revision=2, delta={'active_part': 'head'})
    new['workspace']['active_part'] = 'head'
    assert navigation_only_change(old, new)
    for mutate in (lambda p: p.update(w=820),
                   lambda p: p['workspace']['part_features'].update(head=[{'x': 1}]),
                   lambda p: p['workspace']['part_profiles'].update(head={'X': [1]}),
                   lambda p: p.update(unknown_geometry_rule=True),
                   lambda p: p.pop('w'),
                   lambda p: p['workspace'].update(existing_parts=['head'])):
        changed = deepcopy(new)
        mutate(changed)
        assert not navigation_only_change(old, changed)
    assert not navigation_only_change(None, new)
    assert not navigation_only_change(old, old)


def test_issue1818_navigation_sync_preserves_committed_selection_without_geometry_work():
    from copy import deepcopy
    from types import SimpleNamespace
    from gui_modules.application.lifecycle import _apply_fold_designer_live_snapshot
    old = {'origin': 'fold_designer', 'revision': 1, 'fingerprint': 'old',
           'model': '受電箱', 'active_part': 'box_body',
           'workspace': {'active_part': 'box_body', 'existing_parts': ['box_body', 'head']}}
    new = deepcopy(old)
    new.update(revision=2, fingerprint='new', active_part='head')
    new['workspace']['active_part'] = 'head'
    selected, committed = [], []
    host = SimpleNamespace(
        _phase6_last_fold_designer_live_payload=old,
        _phase6_last_fold_designer_revision=1,
        _phase6_last_fold_designer_fingerprint='old',
        workspace_controller=SimpleNamespace(set_active_part=selected.append),
        project_controller=SimpleNamespace(capture_committed=committed.append),
        _compose_phase6_project_snapshot_from_main_gui=lambda: {'active_part': selected[-1]},
        _sync_fold_designer_manual_corner_context=lambda key: None,
    )
    # No geometry/state setters or Scheduler on this host: using any would fail.
    assert _apply_fold_designer_live_snapshot(host, new)
    assert selected == ['head']
    assert committed == [{'active_part': 'head'}]
    assert host._phase6_last_fold_designer_revision == 2
    assert host._phase6_last_fold_designer_live_payload == new
    assert not _apply_fold_designer_live_snapshot(host, old)
