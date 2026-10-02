from __future__ import annotations

import os

import pytest


def _values(app):
    return tuple(float(var.get()) for var in (app.w_var, app.h_var, app.d_var, app.t_var, app.fw_z_var))


def _pump(root):
    root.update_idletasks()
    root.update()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_known_family_switch_always_applies_target_defaults_not_last_runtime_edits():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        vault_defaults = (
            float(app.settings_service.snapshot()["w"]),
            float(app.settings_service.snapshot()["h"]),
            float(app.settings_service.snapshot()["d"]),
            float(app.settings_service.snapshot()["t"]),
            float(app.settings_service.snapshot()["fw"]),
        )

        app.baseline_var.set("受電箱"); _pump(root)
        assert _values(app) == (800.0, 1600.0, 350.0, 2.0, 29.0)
        app.w_var.set("830"); app.h_var.set("1650"); app.d_var.set("355"); app.fw_z_var.set("30")
        _pump(root)

        app.baseline_var.set("金庫型"); _pump(root)
        assert _values(app) == vault_defaults
        app.w_var.set("450"); app.h_var.set("650"); app.d_var.set("260"); app.fw_z_var.set("27")
        _pump(root)

        app.baseline_var.set("受電箱"); _pump(root)
        assert _values(app) == (800.0, 1600.0, 350.0, 2.0, 29.0)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_switching_into_custom_carries_current_dimensions_but_custom_to_known_resets_target():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱"); _pump(root)
        app.w_var.set("820"); app.h_var.set("1700"); app.d_var.set("360"); app.t_var.set("2.5"); app.fw_z_var.set("31")
        _pump(root)
        before_custom = _values(app)

        app.baseline_var.set("自訂"); _pump(root)
        assert _values(app) == before_custom

        app.w_var.set("900"); app.h_var.set("1800"); app.d_var.set("380"); app.t_var.set("3"); app.fw_z_var.set("33")
        _pump(root)
        app.baseline_var.set("受電箱"); _pump(root)
        assert _values(app) == (800.0, 1600.0, 350.0, 2.0, 29.0)

        app.w_var.set("840"); app.h_var.set("1660"); app.d_var.set("358"); app.t_var.set("2.2"); app.fw_z_var.set("30")
        _pump(root)
        app.baseline_var.set("金庫型"); _pump(root)
        vault_defaults = _values(app)
        app.w_var.set("455"); app.h_var.set("655"); app.d_var.set("265"); app.t_var.set("2.4"); app.fw_z_var.set("28")
        _pump(root)
        before_custom = _values(app)

        app.baseline_var.set("自訂"); _pump(root)
        assert _values(app) == before_custom

        app.baseline_var.set("金庫型"); _pump(root)
        assert _values(app) == vault_defaults
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_fold_designer_known_models_reset_presets_while_custom_carries_current_values():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        _pump(root)

        designer.baseline_model_var.set("受電箱"); _pump(root)
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t", "fw")) == (
            800.0, 1600.0, 350.0, 2.0, 29.0
        )

        designer._phase6_input_snapshot.update({"w": 820.0, "h": 1700.0, "d": 360.0, "t": 2.5, "fw": 31.0})
        designer._settings_values.update({"w": 820.0, "h": 1700.0, "d": 360.0, "t": 2.5, "fw": 31.0})
        designer.state.w = 820; designer.state.h = 1700; designer.state.d = 360
        designer.v_w.set("820"); designer.v_h.set("1700"); designer.v_d.set("360")

        designer.baseline_model_var.set("自訂"); _pump(root)
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t", "fw")) == (
            820.0, 1700.0, 360.0, 2.5, 31.0
        )

        designer.baseline_model_var.set("金庫型"); _pump(root)
        vault_settings = app._cabinet_family_defaults["金庫型"]["settings"]
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t", "fw")) == tuple(
            float(vault_settings[k]) for k in ("w", "h", "d", "t", "fw")
        )

        designer.baseline_model_var.set("受電箱"); _pump(root)
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t", "fw")) == (
            800.0, 1600.0, 350.0, 2.0, 29.0
        )
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_fold_designer_receiving_to_vault_restores_vault_structure_preset_even_when_opened_from_receiving():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        vault_structure = app._cabinet_family_defaults["金庫型"]["box_body_structure"]
        app.baseline_var.set("受電箱"); _pump(root)
        assert app.workspace_controller.box_body_structure_state()["active_type"] != vault_structure["active_type"]

        assert "_runtime_family_presets" not in app._compose_phase6_project_snapshot_from_main_gui()
        designer = app.open_original_fold_designer(); _pump(root)
        assert "_runtime_family_presets" in designer._phase6_input_snapshot
        assert designer.designer_workspace.box_body_structure_state()["active_type"] != vault_structure["active_type"]

        designer.baseline_model_var.set("金庫型"); _pump(root)
        assert designer.designer_workspace.box_body_structure_state() == vault_structure
        assert designer._phase6_input_snapshot["box_body_structure"] == vault_structure
        assert bool(designer._phase6_input_snapshot.get("multi_door_enabled", False)) is False
        assert designer._phase6_input_snapshot.get("door_layout_columns") == []
        assert designer._phase6_input_snapshot.get("inner_doors") == []
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
