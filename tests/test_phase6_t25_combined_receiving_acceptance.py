from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)


def _pump(root):
    root.update_idletasks()
    root.update()


def _selector_entries(designer):
    menu = designer.part_choice_menu
    end = menu.index("end")
    result = {}
    for index in range((end if end is not None else -1) + 1):
        try:
            result[str(menu.entrycget(index, "value"))] = index
        except Exception:
            pass
    return result


def test_combined_receiving_operator_path_from_live_family_switch():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from ae_engine.assembly_placement import resolve_assembly_placement

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        _pump(root)

        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        _pump(root)

        # Exact user lifecycle seam: designer is already open before switching.
        designer.baseline_model_var.set("受電箱")
        _pump(root)

        snap = designer._phase6_input_snapshot
        assert str(snap.get("model")) == "受電箱"
        assert tuple(float(snap[k]) for k in ("w", "h", "d", "t", "fw")) == pytest.approx(
            (800.0, 1600.0, 350.0, 2.0, 29.0)
        )

        # Receiving physical box-body sections.
        designer.activate_part("box_body")
        bridge._phase6_invalidate_settings_page(designer, "box_body")
        bridge._phase6_render_settings_context(designer, "box_body")
        _pump(root)
        assert tuple(designer.box_body_piece_input_sections) == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )

        # Door/Base topology + operator selector semantics + callbacks.
        entries = _selector_entries(designer)
        expected = {
            "上門": "door_c1_r1",
            "下門": "door_c1_r2",
            "上門底板": "base_plate_c1_r1",
            "下門底板": "base_plate_c1_r2",
        }
        for label, stable_id in expected.items():
            assert label in entries, f"missing selector label {label!r}: {tuple(entries)}"
            designer.part_choice_menu.invoke(entries[label])
            _pump(root)
            assert designer.active_part_key == stable_id

        parts = tuple(str(key) for key in designer.available_parts)
        assert "door" not in parts and "base_plate" not in parts
        assert all(stable_id in parts for stable_id in expected.values())

        dims = bridge._phase6_recalculate_part_dimensions(designer)
        assert dims["base_plate_c1_r1"] == {"width": 690.0, "height": 990.0}
        assert dims["base_plate_c1_r2"] == {"width": 690.0, "height": 390.0}

        upper = resolve_assembly_placement(snap, "base_plate_c1_r1")
        lower = resolve_assembly_placement(snap, "base_plate_c1_r2")
        assert upper.world_offset == pytest.approx((0.0, 250.0, 0.0))
        assert lower.world_offset == pytest.approx((0.0, -550.0, 0.0))
        assert upper.placement_kind == lower.placement_kind == "receiving_base_plate"

        # Medium + unlock UI remains usable on real Head drawing.
        designer.activate_part("head")
        designer.ui_text_size_var.set("中")
        _pump(root)
        if not bool(getattr(designer, "_phase6_parameters_unlocked", False)):
            designer.parameter_lock_button.invoke()
        _pump(root)

        panel = designer.settings_panel
        assert panel.settings_scroll_canvas is not None
        assert panel.settings_scrollbar is not None
        assert panel.settings_scrollbar.winfo_manager()
        assert panel.settings_scroll_canvas.bbox("all") is not None

        hosts = designer.drawing_edge_hosts
        renderer = designer.renderer.canvas.get_tk_widget()
        assert renderer.winfo_height() >= 80
        for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            host = getattr(hosts, edge.lower())
            parent = host.master
            assert host.winfo_viewable() == 1
            x, y, w, h = host.winfo_x(), host.winfo_y(), host.winfo_width(), host.winfo_height()
            assert x >= 0 and y >= 0
            assert x + w <= parent.winfo_width() + 1
            assert y + h <= parent.winfo_height() + 1
            assert int(designer.endcap_joint_widgets[edge].cget("width")) <= 5
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
