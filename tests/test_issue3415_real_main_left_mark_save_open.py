"""#3415 actual Main Save As -> *new root* Open -> real Designer DXF.

Do not forge a saved snapshot or overwrite missing physical source. Select
the legacy unconfigured Receiving mode through its existing GUI transaction,
then commit LEFT_FLAT_SIDE using the actual settings Apply button. Draw a
real manual MARKING line with the actual Hole Editor button and Tk canvas.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from phase6_project_file import read_project
from tests.test_issue1502_receiving_gui_base_bridge import (
    _open_legacy_unconfigured_base_settings,
)

ROOT = Path(__file__).resolve().parents[1]
LEFT = {
    "pattern": RECEIVING_BASE_PATTERN_LEFT,
    "height": 340.0,
    "shrink_top": 20.0,
    "shrink_bottom": 20.0,
    "shrink_left": 45.0,
    "shrink_right": 45.0,
    "bend": 20.0,
}


def _actual_editor_confirm(editor):
    def descendants(w):
        for child in w.winfo_children():
            yield child
            yield from descendants(child)
    buttons = [
        item for item in descendants(editor)
        if isinstance(item, tk.Button) and item.cget("text") == "確定全部"
    ]
    assert len(buttons) == 1
    buttons[0].invoke()


def _real_part(host):
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    designer = host.fold_designer_app
    designer.activate_part("base_plate")
    designer.root.update_idletasks()
    designer.root.update()
    payload = build_scene_payload_for_app(designer, "base_plate")
    spec, ctx = host._fold_designer_part_spec_from_payload("base_plate", payload)
    return spec, ctx


def _dxf_entities(path):
    drawing = ezdxf.readfile(path)
    assert drawing.header["$INSUNITS"] == 4
    entities = tuple(sorted(
        (e.dxftype(), e.dxf.layer, tuple(round(float(v), 6) for v in (
            (e.dxf.center.x, e.dxf.center.y, e.dxf.radius)
            if e.dxftype() == "CIRCLE"
            else tuple(coordinate for x, y in e.get_points("xy")
                       for coordinate in (x, y))
            if e.dxftype() == "LWPOLYLINE"
            else ()
        )))
        for e in drawing.modelspace()
        if e.dxftype() in ("CIRCLE", "LWPOLYLINE")
    ))
    assert any(layer == "MARKING" for _, layer, _ in entities)
    # Finite BEND is a DXF LINE, not necessarily a LWPOLYLINE.
    assert any(item.dxf.layer == "BEND" for item in drawing.modelspace())
    assert any(item.dxf.layer == "CUTTING" for item in drawing.modelspace())
    return entities


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"),
                    reason="requires native Tk or Xvfb display")
def test_real_main_left_committed_mark_saveas_new_root_open_designer_export(
    tmp_path, monkeypatch,
):
    import gui
    from gui_modules.application.physical_part_hole_editor import (
        open_workspace_sheet_editor,
    )

    path = tmp_path / "real-main-left-marked.p6fold"
    first = tmp_path / "before-main-reopen.dxf"
    second = tmp_path / "after-main-reopen.dxf"
    saved_marks = None
    source_sig = None

    for roundtrip in (0, 1):
        root = tk.Tk()
        # A real operator's Main window is visible. With withdraw(), the
        # nested editor canvas stays 1x1, so no genuine mouse hit is possible.
        root.geometry("1400x900+0+0")
        root.update_idletasks()
        root.update()
        host = None
        try:
            host = gui.BoxCalculatorGUI(root)
            if roundtrip == 0:
                host.baseline_var.set("受電箱")
                root.update()
                designer = host.open_original_fold_designer()
                root.update()
                # Supported Receiving manual BasePlate settings mode; selects
                # the mode, not a fabricated BasePlate profile or saved state.
                _open_legacy_unconfigured_base_settings(designer)
                root.update()
                panel = designer.settings_panel
                panel.invalidate_context("base_plate")
                rendered = panel.render_context("base_plate")
                fields = rendered["extension_state"]["receiving_base_plate_vars"]
                for key, value in LEFT.items():
                    fields[key].set(str(value))
                rendered["extension_state"]["receiving_base_plate_apply_button"].invoke()
                assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT
                spec, ctx = _real_part(host)
                assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                assert spec.corner_policy is None
                assert spec.receiving_nfb_depth_pair_mm is None
                assert not spec.seam_positions

                open_workspace_sheet_editor(host, "base_plate")
                editor = host.last_unified_hole_editor
                root.update_idletasks()
                root.update()
                assert editor.winfo_exists() and editor._manual_marking_controls
                canvas = host.last_hole_editor_canvas
                drawing_button = editor._manual_marking_controls[0]
                # Use the *actual* Tk renderer's established transform;
                # never guess pixel layout or manufacture a Feature in test.
                bound = dict(zip(
                    editor._manual_marking_place.__code__.co_freevars,
                    (cell.cell_contents
                     for cell in editor._manual_marking_place.__closure__),
                ))
                state = bound["s"]
                assert canvas.winfo_width() > 100 and canvas.winfo_height() > 100, (
                    "GUI_CANVAS_NOT_LAID_OUT"
                )
                from ae_engine.sheetmetal_features import Vec2
                cx, cy = state.canvas_view.transform.world_to_canvas(
                    Vec2(state.live_context.width / 2, state.live_context.height / 2)
                )
                drawing_button.invoke()
                assert state.manual_mark_mode[0], "GUI_MARK_DRAW_MODE_NOT_ENTERED"
                canvas.event_generate(
                    "<Button-1>", x=round(cx), y=round(cy),
                )
                root.update()
                assert len(tuple(item for item in state.live_context.feature_list
                                 if api.is_manual_mark(item))) == 1, (
                    "GUI_CANVAS_MARK_NOT_INSERTED: " +
                    editor._manual_marking_controls[2].cget("text")
                )
                assert editor._manual_marking_controls[2].cget("text") == ""
                _actual_editor_confirm(editor)
                root.update()
                assert not editor.winfo_exists()
                saved_marks = tuple(
                    item for item in designer.designer_workspace.features_for("base_plate")
                    if api.is_manual_mark(item)
                )
                assert len(saved_marks) == 1
                first_spec, first_ctx = _real_part(host)
                assert any(api.is_manual_mark(item) for item in first_spec.features)
                assert first_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                source_sig = (
                    first_spec.model_name, first_spec.width, first_spec.height,
                    first_spec.receiving_bend_pattern, first_spec.bend,
                )
                host._export_authoritative_part(first_spec, first, first_ctx)
                assert first.is_file() and first.stat().st_size > 0
                expected_entities = _dxf_entities(first)
                assert api.verify_saved_part_render_data_dxf(
                    host._authoritative_render_data(first_spec, first_ctx), first
                ).ok

                monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
                host.project_save_as_button.invoke()
                assert path.is_file()
                saved = read_project(path)["snapshot"]
                assert saved["receiving_base_plate"] == LEFT
                assert tuple(item for item in saved["part_features"]["base_plate"]
                             if api.is_manual_mark(item)) == saved_marks
                assert tuple(item for item in saved["workspace"]["part_features"]["base_plate"]
                             if api.is_manual_mark(item)) == saved_marks
            else:
                monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
                host.project_open_button.invoke()
                root.update()
                assert host.project_controller.project_path == str(path)
                assert tuple(
                    item for item in host.surface_features["base_plate"]
                    if api.is_manual_mark(item)
                ) == saved_marks
                # This must come from the committed .p6fold -> live Designer
                # hydration. Passing a manually patched payload is forbidden.
                designer = host.open_original_fold_designer()
                root.update()
                assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT
                reopened_spec, reopened_ctx = _real_part(host)
                assert reopened_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                assert reopened_spec.corner_policy is None
                assert not reopened_spec.seam_positions
                assert reopened_spec.receiving_nfb_depth_pair_mm is None
                assert tuple(item for item in reopened_spec.features
                             if api.is_manual_mark(item)) == saved_marks
                assert (
                    reopened_spec.model_name, reopened_spec.width,
                    reopened_spec.height, reopened_spec.receiving_bend_pattern,
                    reopened_spec.bend
                ) == source_sig
                host._export_authoritative_part(reopened_spec, second, reopened_ctx)
                assert second.is_file() and second.stat().st_size > 0
                assert first.read_bytes() == second.read_bytes(), (
                    "RELOADED_MAIN_DXF_BYTES_DRIFT"
                )
                assert _dxf_entities(second) == expected_entities
                assert api.verify_saved_part_render_data_dxf(
                    host._authoritative_render_data(reopened_spec, reopened_ctx), second
                ).ok
        finally:
            if host is not None and host.fold_designer_window is not None:
                try:
                    host.fold_designer_window.destroy()
                except tk.TclError:
                    pass
            root.destroy()
