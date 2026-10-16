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
