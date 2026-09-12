import inspect
import os
import tkinter as tk
from tkinter import font as tkfont

import pytest

import fold_designer_bridge as bridge
import gui


pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Issue119 requires real Tk/Xvfb")


def _open_designer():
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.BoxCalculatorGUI(root)
    designer = app.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, app, designer


def _close(root):
    try:
        root.destroy()
    except Exception:
        pass


def _font_actual(widget):
    spec = str(widget.cget("font") or "TkDefaultFont")
    try:
        return tkfont.Font(root=widget, font=spec).actual()
    except tk.TclError:
        return tkfont.nametofont(spec, root=widget).actual()


def _green_geometry_bbox(canvas):
    items = []
    for item in canvas.find_all():
        for option in ("outline", "fill"):
            try:
                value = str(canvas.itemcget(item, option) or "").lower()
            except tk.TclError:
                continue
            if value == "#30d158":
                items.append(item)
                break
    boxes = [canvas.bbox(item) for item in items]
    boxes = [box for box in boxes if box is not None]
    assert boxes, "Corner Data must render authoritative CUTTING/material geometry"
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _show_corner_data_part(designer, root, part_key):
    bridge._phase6_show_corner_data(designer)
    bridge._phase6_select_corner_data_part(designer, part_key)
    root.update_idletasks()
    root.update()


def _show_box_body_corner_data(designer, root):
    _show_corner_data_part(designer, root, "box_body")


def test_red_119_1_selecting_real_part_leaves_corner_data_layout():
    root, _app, designer = _open_designer()
    try:
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks()
        root.update()
        assert designer.corner_data_panel.winfo_manager(), "precondition: Corner Data panel is visible"

        designer.activate_part("head")
        root.update_idletasks()
        root.update()

        assert designer._phase6_3d_display_mode == "single"
        assert designer.part_var.get() == "封頭"
        assert designer.corner_data_panel.winfo_manager() == "", (
            "Corner Data panel remained in layout after selecting a real part"
        )
        assert designer.fold_editor_host.winfo_manager(), "normal part Fold editor must return"
    finally:
        _close(root)


def test_red_119_2_first_vault_to_receiving_switch_refreshes_visible_boxbody_children():
    root, _app, designer = _open_designer()
    try:
        assert designer.baseline_model_var.get() == "金庫型"
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks()
        root.update()

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()

        expected = (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        authoritative = tuple(designer.designer_workspace.available_parts)
        for key in expected:
            assert key in authoritative, f"precondition: Receiving authoritative topology missing {key}"
            assert key in designer.corner_data_part_depths, (
                f"first live switch left visible Corner Data tree stale: {key} absent"
            )
            assert designer.corner_data_part_depths[key] == 1
            assert designer.corner_data_part_rows[key].winfo_manager()
    finally:
        _close(root)


def test_red_119_2b_family_switch_has_one_corner_data_refresh_owner():
    source = inspect.getsource(bridge._phase6_on_baseline_model_changed)
    assert source.count("_phase6_refresh_corner_data_parts_panel(self)") == 1, (
        "family transaction must refresh Corner Data exactly once after the authoritative commit"
    )


def test_red_119_3a_corner_data_operator_info_has_readable_emphasis():
    root, _app, designer = _open_designer()
    try:
        _show_box_body_corner_data(designer, root)

        label = designer.corner_data_info_label
        assert label.winfo_manager(), "Corner Data operator-info row must be visible"
        font_actual = _font_actual(label)
        assert abs(int(font_actual.get("size", 0) or 0)) >= 11, (
            f"Corner Data operator-info base font is too small: {font_actual}"
        )
        assert str(font_actual.get("weight") or "") == "bold", (
            f"Corner Data operator-info row is not visually legible enough: {font_actual}"
        )
    finally:
        _close(root)


def test_red_119_3b_corner_data_preview_uses_compact_dedicated_viewport():
    root, _app, designer = _open_designer()
    try:
        part_key = "door"
        assert part_key in tuple(designer.designer_workspace.available_parts)
        _show_corner_data_part(designer, root, part_key)

        canvas = designer.corner_data_canvas
        projection = bridge._phase6_corner_data_unfold_projection_for_key(designer, part_key)
        assert projection is not None
        bounds = tuple(float(v) for v in projection.render_data.material.bounds)
        material_w = max(1e-9, bounds[2] - bounds[0])
        material_h = max(1e-9, bounds[3] - bounds[1])

        cw = max(1, int(canvas.winfo_width()))
        ch = max(1, int(canvas.winfo_height()))
        left, top, right, bottom = _green_geometry_bbox(canvas)
        rendered_h = max(0, bottom - top)

        usable_w = max(1.0, float(cw) - 48.0 - 82.0)
        usable_h = max(1.0, float(ch) - 72.0 - 48.0)
        compact_scale = min(usable_w / material_w, usable_h / material_h)
        compact_expected_h = material_h * compact_scale
        ratio = rendered_h / max(1.0, compact_expected_h)
        print(
            "ISSUE119_PREVIEW_FIT",
            f"part={part_key}", f"canvas={cw}x{ch}", f"bbox={(left, top, right, bottom)}",
            f"compact_h={compact_expected_h:.1f}", f"fit_ratio={ratio:.3f}",
        )
        assert ratio >= 0.97, (
            "Corner Data unfolded material is still being shrunk by generic 2D annotation space: "
            f"rendered_h={rendered_h}, compact_expected_h={compact_expected_h:.1f}, ratio={ratio:.3f}"
        )
        assert right > left and cw > 1
    finally:
        _close(root)
