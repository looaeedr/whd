from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")


def _render_box_body_settings(designer, root, bridge):
    designer.activate_part("box_body")
    bridge._phase6_invalidate_settings_page(designer, "box_body")
    bridge._phase6_render_settings_context(designer, "box_body")
    root.update_idletasks()
    root.update()
    return dict(designer.box_body_piece_input_sections)


def _resolved_piece_keys(designer, bridge):
    data = bridge._phase6_query_final_render_data(designer)
    return tuple(f"box_body:{piece.role}" for piece in tuple(data.pieces))


def test_r11_two_piece_and_three_piece_sections_follow_physical_piece_ids_and_replace_stale_sections():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.structure_type_var.set("二件式（W 二分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        sections = _render_box_body_settings(designer, root, bridge)
        assert tuple(sections) == ("box_body:left", "box_body:right")
        assert tuple(sections) == _resolved_piece_keys(designer, bridge)
        assert all(getattr(widget, "_phase6_part_key", None) == key for key, widget in sections.items())

        left_var = designer.box_body_piece_input_vars["box_body:left"]["width"]
        left_entry = designer.box_body_piece_input_entries["box_body:left"]["width"]
        total_w = bridge._phase6_box_structure_w(designer)
        left_var.set(str(int(total_w / 2.0 - 20.0)))
        left_entry.event_generate("<Return>")
        root.update_idletasks(); root.update()
        state = bridge._phase6_box_structure_state(designer)
        cfg = state["configs"]["two_piece_w_split"]
        assert cfg["left_w"] == pytest.approx(total_w / 2.0 - 20.0)
        assert cfg["right_w"] == pytest.approx(total_w / 2.0 + 20.0)

        old_sections = tuple(sections.values())
        designer.structure_type_var.set("三件式（W 三分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        sections = _render_box_body_settings(designer, root, bridge)
        assert tuple(sections) == ("box_body:left", "box_body:middle", "box_body:right")
        assert tuple(sections) == _resolved_piece_keys(designer, bridge)
        assert len(designer.box_body_piece_input_host.winfo_children()) == 3
        assert all(not bool(widget.winfo_exists()) for widget in old_sections)
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


def test_r11_receiving_three_piece_side_back_sections_bind_real_piece_stable_ids():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        sections = _render_box_body_settings(designer, root, bridge)
        assert tuple(sections) == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        assert tuple(sections) == _resolved_piece_keys(designer, bridge)
        assert all(getattr(widget, "_phase6_part_key", None) == key for key, widget in sections.items())

        assert "rear_bend" in designer.box_body_piece_input_vars["box_body:left_side"]
        assert "width_comp_t" in designer.box_body_piece_input_vars["box_body:back"]
        assert "rear_bend" in designer.box_body_piece_input_vars["box_body:right_side"]
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


def test_r11_save_reload_rebuilds_sections_from_authoritative_physical_piece_state(tmp_path):
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    root2 = None
    designer2 = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.structure_type_var.set("三件式（W 三分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        _render_box_body_settings(designer, root, bridge)

        assert bridge._phase6_publish_live_state(designer, force=True) is True
        root.update_idletasks(); root.update()
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        path = tmp_path / "t14-child-sections.p6fold"
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-06T16:40:00+08:00",
            "snapshot": snapshot,
            "final_geometry": {},
        })
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

    root2 = tk.Tk()
    root2.withdraw()
    app2 = gui.BoxCalculatorGUI(root2)
    try:
        designer2 = app2.load_phase6_project(path, open_designer=True)
        root2.update_idletasks(); root2.update()
        sections = _render_box_body_settings(designer2, root2, bridge)
        assert tuple(sections) == ("box_body:left", "box_body:middle", "box_body:right")
        assert tuple(sections) == _resolved_piece_keys(designer2, bridge)
        assert designer2.designer_workspace.box_body_structure_state()["active_type"] == "three_piece_w_split"
    finally:
        try:
            if designer2 is not None:
                designer2.root.destroy()
        except Exception:
            pass
        try:
            root2.destroy()
        except Exception:
            pass
