import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge
import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#162 viewport contracts require real Tk/Xvfb"
)


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


def _show_part(designer, root, part_key):
    bridge._phase6_show_corner_data(designer)
    resolved = bridge._phase6_select_corner_data_part(designer, part_key)
    root.update_idletasks()
    root.update()
    assert resolved == part_key
    return designer.corner_data_canvas


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
    assert boxes, "authoritative CUTTING/material geometry must be visible"
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _largest_green_outline_bbox(canvas):
    """Return the largest single CUTTING outline, excluding dimension overlays."""
    boxes = []
    for item in canvas.find_all():
        try:
            outline = str(canvas.itemcget(item, "outline") or "").lower()
        except tk.TclError:
            continue
        if outline != "#30d158":
            continue
        box = canvas.bbox(item)
        if box is None:
            continue
        area = max(0, box[2] - box[0]) * max(0, box[3] - box[1])
        boxes.append((area, box))
    assert boxes, "authoritative CUTTING material outline must be visible"
    return max(boxes, key=lambda row: row[0])[1]


def _bbox_size(box):
    return max(0, box[2] - box[0]), max(0, box[3] - box[1])


def _material_fingerprint(render_data):
    material = getattr(render_data, "material", None)
    assert material is not None and not material.is_empty
    return bytes(material.wkb)


def test_red_162_canvas_uses_black_background():
    root, _app, designer = _open_designer()
    try:
        canvas = _show_part(designer, root, "door")
        assert str(canvas.cget("background")).lower() == "#000000", (
            "#162 requires the unfold workspace to use the same black drawing background"
        )
    finally:
        _close(root)


def test_red_162_initial_fit_is_materially_larger_than_previous_corner_data_fit():
    root, _app, designer = _open_designer()
    try:
        canvas = _show_part(designer, root, "door")
        projection = bridge._phase6_corner_data_unfold_projection_for_key(designer, "door")
        assert projection is not None
        minx, miny, maxx, maxy = map(float, projection.render_data.material.bounds)
        world_w = max(1e-9, maxx - minx)
        world_h = max(1e-9, maxy - miny)
        cw = max(1, int(canvas.winfo_width()))
        ch = max(1, int(canvas.winfo_height()))
        left, top, right, bottom = _largest_green_outline_bbox(canvas)
        rendered_w, rendered_h = _bbox_size((left, top, right, bottom))
        rendered_scale = min(rendered_w / world_w, rendered_h / world_h)

        # Exact current/pre-#162 Corner Data fit envelope. #162 must make the
        # actual material outline visibly larger, not merely enlarge annotations.
        legacy_scale = min(
            max(1.0, float(cw) - 48.0 - 82.0) / world_w,
            max(1.0, float(ch) - 64.0 - 48.0) / world_h,
        )
        assert rendered_scale >= legacy_scale * 1.04, (
            f"initial unfold material did not grow enough: rendered={rendered_scale:.4f}, "
            f"legacy={legacy_scale:.4f}"
        )
        assert left >= 0 and top >= 0 and right <= cw and bottom <= ch
    finally:
        _close(root)


def test_red_162_mouse_wheel_zooms_receiving_parent_and_physical_child_without_geometry_feedback():
    root, _app, designer = _open_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()
        assert "box_body:back" in tuple(designer.designer_workspace.available_parts)

        for part_key in ("box_body", "box_body:back"):
            canvas = _show_part(designer, root, part_key)
            assert canvas.bind("<MouseWheel>"), "#162 requires Windows/macOS wheel binding"
            assert canvas.bind("<Button-4>"), "#162 requires Linux wheel-up binding"
            assert canvas.bind("<Button-5>"), "#162 requires Linux wheel-down binding"

            before_projection = bridge._phase6_corner_data_unfold_projection_for_key(
                designer, part_key
            )
            assert before_projection is not None
            before_material = _material_fingerprint(before_projection.render_data)
            before_box = _green_geometry_bbox(canvas)
            before_w, before_h = _bbox_size(before_box)

            canvas.event_generate(
                "<MouseWheel>", delta=120,
                x=max(1, int(canvas.winfo_width() / 2)),
                y=max(1, int(canvas.winfo_height() / 2)),
            )
            root.update_idletasks()
            root.update()

            after_box = _green_geometry_bbox(canvas)
            after_w, after_h = _bbox_size(after_box)
            assert after_w > before_w * 1.03 or after_h > before_h * 1.03, (
                f"wheel-up did not zoom {part_key}: before={before_box}, after={after_box}"
            )

            after_projection = bridge._phase6_corner_data_unfold_projection_for_key(
                designer, part_key
            )
            assert after_projection is not None
            assert after_projection.part_key == part_key
            assert _material_fingerprint(after_projection.render_data) == before_material, (
                "viewport zoom must never feed back into authoritative manufacturing geometry"
            )
    finally:
        _close(root)
