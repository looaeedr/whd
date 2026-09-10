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


def test_corner_data_box_body_lists_physical_children_and_draws_selected_piece():
    import fold_designer_bridge as bridge

    tk, root, app = _open_receiving_app()
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks(); root.update()

        keys = tuple(bridge._phase6_corner_data_part_keys(designer))
        for key in ("box_body:left_side", "box_body:back", "box_body:right_side"):
            assert key in keys

        assert bridge._phase6_select_corner_data_part(designer, "box_body:right_side") == "box_body:right_side"
        projection = bridge._phase6_corner_data_unfold_projection(designer)
        assert projection is not None
        assert projection.part_key == "box_body:right_side"
        assert projection.render_data is not None
        assert designer._phase6_corner_data_selected_part_key == "box_body:right_side"
        assert not hasattr(app, "notebook")
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


def test_box_body_physical_child_has_same_authoritative_material_in_3d_and_corner_data_2d():
    import fold_designer_bridge as bridge

    tk, root, app = _open_receiving_app()
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.activate_part("box_body:back")
        root.update_idletasks(); root.update()
        active_before = designer.designer_workspace.active_part
        expected = bridge._phase6_query_final_render_data(designer)

        bridge._phase6_show_corner_data(designer)
        assert bridge._phase6_select_corner_data_part(designer, "box_body:back") == "box_body:back"
        root.update_idletasks(); root.update()
        projection = bridge._phase6_corner_data_unfold_projection(designer)

        assert active_before == "box_body:back"
        assert designer.designer_workspace.active_part == active_before
        assert projection is not None
        assert projection.part_key == "box_body:back"
        assert projection.render_data.material.equals(expected.material)
        assert not hasattr(bridge, "_phase6_return_to_2d_corner")
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
