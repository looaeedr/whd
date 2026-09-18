# -*- coding: utf-8 -*-
import os
import tkinter as tk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="Issue187 requires real Tk/Xvfb"
)


def _open_designer(app_setup=None):
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.BoxCalculatorGUI(root)
    if app_setup is not None:
        app_setup(app)
    designer = app.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, app, designer


def _pump(root, cycles=3):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _close(root):
    try:
        root.destroy()
    except Exception:
        pass


def _descendant_texts(widget):
    rows = []
    for child in widget.winfo_children():
        try:
            text = str(child.cget("text") or "")
        except Exception:
            text = ""
        if text:
            rows.append(text)
        rows.extend(_descendant_texts(child))
    return rows


def test_issue187_output_surface_remains_formal_after_top_toolbar_migration():
    root, _app, designer = _open_designer()
    try:
        assert hasattr(designer, "output_controls_frame"), (
            "#187 RED: 3D workspace has no formal operator Output surface"
        )
        frame = designer.output_controls_frame
        _pump(root)
        assert frame.winfo_ismapped(), "3D Output surface must be mapped"
        assert frame.master is designer.top_command_row, (
            "T2 moves Output into the one-row top command surface without changing its owners"
        )
        assert hasattr(designer, "output_draw_stock_check")
        assert hasattr(designer, "output_export_checks")
        assert hasattr(designer, "output_export_button")
        assert str(designer.output_export_button.cget("text")) == "輸出選取的 DXF 檔案"

        top_text = "\n".join(_descendant_texts(designer.top_command_row))
        assert "輸出 STOCK" in top_text
        assert "輸出選取的 DXF 檔案" in top_text
    finally:
        _close(root)


def test_issue187_red_export_selection_is_independent_of_presence_and_3d_visibility():
    root, app, designer = _open_designer()
    try:
        assert hasattr(designer, "output_export_vars"), (
            "#187 RED: 3D has no independent DXF export-selection state"
        )
        assert hasattr(designer, "output_export_checks")
        assert "head" in designer.output_export_vars
        assert "head" in set(designer.designer_workspace.available_parts)

        export_var = designer.output_export_vars["head"]
        check = designer.output_export_checks["head"]
        visibility_var = designer.assembly_part_visible_vars["head"]
        visible_before = bool(visibility_var.get())
        parts_before = tuple(designer.designer_workspace.available_parts)

        if not bool(export_var.get()):
            check.invoke()
            _pump(root)
        check.invoke()
        _pump(root)

        assert bool(export_var.get()) is False
        assert bool(app.export_head_var.get()) is False, (
            "3D export selection must project to the existing export owner"
        )
        assert bool(visibility_var.get()) is visible_before, (
            "DXF export selection must not mutate 3D visibility"
        )
        assert tuple(designer.designer_workspace.available_parts) == parts_before, (
            "DXF export selection must not mutate physical part presence"
        )
    finally:
        _close(root)


def test_issue187_red_stock_reuses_existing_setting_and_batch_action_delegates():
    calls = []

    def setup(app):
        app.export_selected_dxf = lambda: calls.append("export") or ["sentinel.dxf"]

    root, app, designer = _open_designer(setup)
    try:
        assert hasattr(designer, "output_draw_stock_var"), (
            "#187 RED: 3D has no operator-facing STOCK control"
        )
        assert hasattr(designer, "output_draw_stock_check")
        assert hasattr(designer, "output_export_button"), (
            "#187 RED: 3D has no batch DXF export action"
        )

        before = bool(designer.output_draw_stock_var.get())
        designer.output_draw_stock_check.invoke()
        _pump(root)
        after = bool(designer.output_draw_stock_var.get())
        assert after is (not before)
        assert bool(designer._settings_values["draw_stock"]) is after, (
            "STOCK control must reuse the existing draw_stock settings owner"
        )
        assert bool(app.draw_stock_var.get()) is after, (
            "3D STOCK state must stay synchronized with the existing host setting"
        )

        designer.output_export_button.invoke()
        _pump(root)
        assert calls == ["export"], (
            "3D batch action must delegate to the existing export_selected_dxf path"
        )
    finally:
        _close(root)


def test_issue187_presence_refresh_never_rewrites_export_intention():
    root, app, designer = _open_designer()
    try:
        export_var = designer.output_export_vars["head"]
        export_var.set(False)
        _pump(root)
        assert bool(app.export_head_var.get()) is False

        current = tuple(app._phase6_current_existing_parts())
        without_head = tuple(key for key in current if key != "head")
        app._apply_existing_parts_from_fold_workspace(without_head)
        _pump(root)
        assert bool(export_var.get()) is False
        assert bool(app.export_head_var.get()) is False

        restored = tuple(dict.fromkeys((*without_head, "head")))
        app._apply_existing_parts_from_fold_workspace(restored)
        _pump(root)
        assert bool(export_var.get()) is False, (
            "physical presence restoration must not silently re-enable DXF export"
        )
    finally:
        _close(root)


@pytest.mark.parametrize("ui_text_size", ("small", "medium", "large"))
def test_issue187_output_surface_stays_mapped_and_reachable_at_all_text_scales(ui_text_size):
    root, _app, designer = _open_designer()
    try:
        designer.apply_external_settings({"ui_text_size": ui_text_size})
        _pump(root, cycles=5)

        frame = designer.output_controls_frame
        button = designer.output_export_button
        assert frame.winfo_ismapped(), f"Output surface hidden at {ui_text_size}"
        assert button.winfo_ismapped(), f"DXF export action hidden at {ui_text_size}"
        assert frame.winfo_width() > 1 and frame.winfo_height() > 1
        assert button.winfo_width() > 1 and button.winfo_height() > 1
        assert frame.winfo_rootx() >= designer.top_command_row.winfo_rootx()
        assert frame.winfo_rooty() >= designer.top_command_row.winfo_rooty()
    finally:
        _close(root)
