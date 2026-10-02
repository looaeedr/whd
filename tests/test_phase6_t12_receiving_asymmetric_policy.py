# -*- coding: utf-8 -*-
"""T12 Contract Tests: Receiving is a formally asymmetric cabinet family."""
from __future__ import annotations

import os
import pytest

from ae_engine.cabinet_types import policy as cabinet_family_policy


def _pump(root):
    root.update_idletasks()
    root.update()


def _managed_symmetry_controls(root):
    """Return symmetry controls whose entire ancestor layout chain is active."""
    found = []

    def effectively_managed(widget):
        current = widget
        while current is not None and current is not root:
            try:
                if not current.winfo_manager():
                    return False
            except Exception:
                return False
            current = getattr(current, "master", None)
        return True

    def walk(widget):
        try:
            children = tuple(widget.winfo_children())
        except Exception:
            return
        for child in children:
            try:
                text = str(child.cget("text") or "")
            except Exception:
                text = ""
            if text == "對稱折彎" and effectively_managed(child):
                found.append(child)
            walk(child)
    walk(root)
    return found


def test_r07_receiving_family_forbids_generic_box_body_symmetry():
    assert cabinet_family_policy.box_body_symmetry_allowed("受電箱") is False
    assert cabinet_family_policy.box_body_symmetry_allowed("RECEIVING") is False
    assert cabinet_family_policy.box_body_symmetry_allowed("金庫型") is True


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_designer_forces_authoritative_symmetry_false_and_hides_control():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱"); _pump(root)
        designer = app.open_original_fold_designer(); _pump(root)
        assert designer.state.symmetric is False
        assert bool(designer.v_sy.get()) is False
        assert bool(designer.bend_ui.phase6_symmetry_var.get()) is False
        assert designer.bend_ui.phase6_symmetry_bar.winfo_manager() == ""
        assert _managed_symmetry_controls(designer.root) == []
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try: root.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_programmatic_symmetry_true_is_rejected_fail_closed():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱"); _pump(root)
        designer = app.open_original_fold_designer(); _pump(root)
        designer.v_sy.set(True)
        bridge._phase6_on_box_symmetry_changed(designer)
        _pump(root)
        assert designer.state.symmetric is False
        assert bool(designer.v_sy.get()) is False
        assert bool(designer.bend_ui.phase6_symmetry_var.get()) is False
        assert designer.bend_ui.phase6_symmetry_bar.winfo_manager() == ""
        assert _managed_symmetry_controls(designer.root) == []
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try: root.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_vault_symmetry_remains_functional_and_vault_to_receiving_hides_again():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer(); _pump(root)
        designer.baseline_model_var.set("金庫型"); _pump(root)
        designer.bend_ui._phase6_refresh_symmetry_bar(); _pump(root)
        assert designer.bend_ui.phase6_symmetry_bar.winfo_manager() != ""

        designer.v_sy.set(False); bridge._phase6_on_box_symmetry_changed(designer); _pump(root)
        assert designer.state.symmetric is False
        designer.v_sy.set(True); bridge._phase6_on_box_symmetry_changed(designer); _pump(root)
        assert designer.state.symmetric is True

        designer.baseline_model_var.set("受電箱"); _pump(root)
        designer.bend_ui._phase6_refresh_symmetry_bar(); _pump(root)
        assert designer.state.symmetric is False
        assert bool(designer.v_sy.get()) is False
        assert designer.bend_ui.phase6_symmetry_bar.winfo_manager() == ""
        assert _managed_symmetry_controls(designer.root) == []
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try: root.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_save_reload_cannot_revive_default_true_symmetry(tmp_path):
    import tkinter as tk
    import gui
    import phase6_project_file as project

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    root2 = None
    try:
        app.baseline_var.set("受電箱"); _pump(root)
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        path = tmp_path / "receiving-asymmetric.p6fold"
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-06T14:30:00+08:00",
            "snapshot": snapshot,
            "final_geometry": {},
        })
        loaded = project.read_project(path)["snapshot"]

        root2 = tk.Tk(); root2.withdraw(); app2 = gui.BoxCalculatorGUI(root2)
        app2._apply_phase6_project_snapshot(loaded); _pump(root2)
        designer2 = app2.open_original_fold_designer(); _pump(root2)
        assert designer2.state.symmetric is False
        assert bool(designer2.v_sy.get()) is False
        assert designer2.bend_ui.phase6_symmetry_bar.winfo_manager() == ""
        assert _managed_symmetry_controls(designer2.root) == []
    finally:
        try:
            if root2 is not None: root2.destroy()
        except Exception: pass
        try: root.destroy()
        except tk.TclError: pass
