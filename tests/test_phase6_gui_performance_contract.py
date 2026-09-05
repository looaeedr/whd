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
    execute_src = inspect.getsource(bridge._phase6_execute_update_intents)
    wrapper_src = inspect.getsource(bridge._phase6_preview_aware_do_update)
    assert "_phase6_external_apply_guard" in apply_src
    # T06 centralizes publish/anti-echo ownership in the orchestration executor;
    # compatibility wrappers must delegate instead of duplicating the guard.
    assert "_phase6_external_apply_guard" in execute_src
    assert "not getattr(self, \"_phase6_external_apply_guard\"" in execute_src
    assert "submit_update_intent" in wrapper_src


def test_live_snapshot_routes_final_recalculation_through_scheduler_not_direct_call():
    src = inspect.getsource(gui.BoxCalculatorGUI._apply_fold_designer_live_snapshot)
    assert "_phase6_update_scheduler" in src
    assert ".mark_dirty(" in src
    assert "self.update_calculations()" not in src


def test_main_input_traces_never_call_full_recalculation_directly():
    bind_src = inspect.getsource(gui.BoxCalculatorGUI.bind_live_updates)
    total_src = inspect.getsource(gui.BoxCalculatorGUI._on_total_door_dimension_changed)
    setting_src = inspect.getsource(gui.BoxCalculatorGUI._on_main_setting_var_changed)

    assert 'trace_add("write", lambda *args: self.update_calculations())' not in bind_src
    assert 'self.update_calculations()' not in total_src
    assert '_phase6_update_scheduler' in setting_src
    assert '.mark_dirty(' in setting_src
