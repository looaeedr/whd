# -*- coding: utf-8 -*-
"""Real Tk regression for Receiving BasePlate shrink and closable parameters."""
import tkinter as tk

import gui
import fold_designer_bridge as bridge


def _open_receiving():
    root = tk.Tk()
    root.withdraw()
    box = gui.BoxCalculatorGUI(root)
    box.baseline_var.set("受電箱")
    root.update()
    designer = box.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, designer


def _close(root, designer):
    try:
        designer.root.destroy()
    finally:
        root.destroy()


def test_receiving_base_has_no_edge_shrink_even_when_unlocked():
    root, designer = _open_receiving()
    try:
        designer.activate_part("base_plate")
        root.update()
        assert designer.base_plate_edge_shrink_widgets == {}
        assert designer.base_plate_edge_shrink_vars == {}
        assert all(not host.winfo_children()
                   for host in designer.drawing_edge_hosts.values())
        before = dict(designer._settings_values)
        assert bridge._phase6_commit_base_plate_edge_shrink(
            designer, "TOP", "99"
        ) is False
        assert designer._settings_values == before

        designer.parameter_lock_button.invoke()
        root.update()
        assert designer._phase6_parameters_unlocked is True
        assert designer.base_plate_edge_shrink_widgets == {}
        close = designer.settings_center._phase6_close_parameters_button
        assert close.winfo_ismapped(), "The user needs an actual reachable close"
        assert close.cget("text") == "收合參數"
        close.invoke()
        root.update()
        assert designer._phase6_parameters_unlocked is False
        assert designer.settings_center.winfo_manager() == ""
        assert designer.base_plate_edge_shrink_widgets == {}
        assert "鎖定" in designer.parameter_lock_button.cget("text")
    finally:
        _close(root, designer)


def test_assembly_diagnostic_panel_has_its_own_reachable_close():
    root, designer = _open_receiving()
    try:
        assert designer._phase6_3d_display_mode == "assembly"
        designer.parameter_lock_button.invoke()
        root.update()
        assert designer._phase6_parameters_unlocked is True
        diagnostics = designer.assembly_diagnostics_frame
        assert diagnostics.winfo_ismapped()
        close = diagnostics._phase6_close_parameters_button
        assert close.winfo_ismapped()
        close.invoke()
        root.update()
        assert designer._phase6_parameters_unlocked is False
        assert diagnostics.winfo_manager() == ""
        assert "鎖定" in designer.parameter_lock_button.cget("text")
        # No separate independent panel-lock state; re-open and close again.
        designer.parameter_lock_button.invoke()
        root.update()
        assert close.winfo_ismapped()
        close.invoke()
        root.update()
        assert not designer._phase6_parameters_unlocked
    finally:
        _close(root, designer)
