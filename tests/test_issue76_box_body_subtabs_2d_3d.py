from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")


def _tab_labels(notebook):
    return tuple(notebook.tab(tab_id, "text").strip() for tab_id in notebook.tabs())


def _select_tab_by_label(notebook, label):
    for tab_id in notebook.tabs():
        if notebook.tab(tab_id, "text").strip() == label:
            notebook.select(tab_id)
            notebook.event_generate("<<NotebookTabChanged>>")
            return tab_id
    raise AssertionError(f"missing tab: {label}; have={_tab_labels(notebook)!r}")


def _open_receiving_app():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    root.update_idletasks(); root.update()
    return tk, root, app


def test_designer_box_body_stays_one_top_level_part_but_has_switchable_physical_subtabs():
    import fold_designer_bridge as bridge

    tk, root, app = _open_receiving_app()
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bundle = bridge._phase6_query_assembly_render_data(designer)
        root.update_idletasks(); root.update()

        labels = tuple(
            designer.part_choice_menu.entrycget(i, "label")
            for i in range(designer.part_choice_menu.index("end") + 1)
        )
        assert labels.count("箱身") == 1
        assert "左側板" not in labels and "後面板" not in labels and "右側板" not in labels

        # Enter one physical child: the logical top-level label remains 箱身,
        # while the child selector exposes all manufacturing identities.
        designer.activate_part("box_body:back")
        root.update_idletasks(); root.update()
        assert designer.part_var.get() == "箱身"
        assert _tab_labels(designer.box_body_piece_selector) == ("左側板", "後面板", "右側板")
        assert designer.box_body_piece_selector.winfo_manager() != ""

        _select_tab_by_label(designer.box_body_piece_selector, "左側板")
        root.update_idletasks(); root.update()
        assert designer.designer_workspace.active_part == "box_body:left_side"
        assert designer.part_var.get() == "箱身"

        aggregate = next(part for part in bundle.assembly_parts if part.part_key == "box_body").render_data
        expected = next(piece.render_data for piece in aggregate.pieces if piece.role == "left_side")
        actual = bridge._phase6_query_final_render_data(designer)
        assert actual.material.equals(expected.material)
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_main_2d_box_body_has_matching_physical_subtabs_and_draws_only_selected_piece():
    tk, root, app = _open_receiving_app()
    try:
        app.notebook.select(app.tab_z)
        app.draw_preview()
        root.update_idletasks(); root.update()

        assert _tab_labels(app.box_body_piece_tabs) == ("左側板", "後面板", "右側板")
        assert app.box_body_piece_tabs.winfo_manager() != ""

        _select_tab_by_label(app.box_body_piece_tabs, "右側板")
        root.update_idletasks(); root.update()

        assert app.box_body_piece_2d_selected_var.get() == "box_body:right_side"
        assert app.last_box_body_face_overview["mode"] == "physical_piece"
        assert app.last_box_body_face_overview["piece_key"] == "box_body:right_side"
        assert app.last_box_body_face_overview["role"] == "right_side"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_box_body_physical_subtab_round_trips_between_3d_and_2d():
    import fold_designer_bridge as bridge

    tk, root, app = _open_receiving_app()
    designer = None
    try:
        # 2D -> 3D: choose right side in 2D; opening Designer must remember it.
        app.notebook.select(app.tab_z)
        app.draw_preview()
        root.update_idletasks(); root.update()
        _select_tab_by_label(app.box_body_piece_tabs, "右側板")
        root.update_idletasks(); root.update()

        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["box_body_active_piece"] == "box_body:right_side"

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        assert designer._phase6_box_body_active_piece_key == "box_body:right_side"

        # Invoke the single top-level 箱身 entry: it must enter the remembered child,
        # not collapse back to the aggregate editor.
        box_index = next(
            i for i in range(designer.part_choice_menu.index("end") + 1)
            if designer.part_choice_menu.entrycget(i, "label") == "箱身"
        )
        designer.part_choice_menu.invoke(box_index)
        root.update_idletasks(); root.update()
        assert designer.designer_workspace.active_part == "box_body:right_side"

        # 3D -> 2D: switch to back and return; main 2D must render back.
        _select_tab_by_label(designer.box_body_piece_selector, "後面板")
        root.update_idletasks(); root.update()
        assert designer.designer_workspace.active_part == "box_body:back"

        assert bridge._phase6_return_to_2d_corner(designer) is True
        designer = None
        root.update_idletasks(); root.update()
        assert app.root.nametowidget(app.notebook.select()) == app.tab_z
        assert app.box_body_piece_2d_selected_var.get() == "box_body:back"
        assert app.last_box_body_face_overview["mode"] == "physical_piece"
        assert app.last_box_body_face_overview["piece_key"] == "box_body:back"
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
