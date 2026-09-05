from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_topology_change_rebuilds_all_assembly_info_rows():
    """金庫型→受電箱後，資訊列必須跟最新 authoritative part topology 一致。"""
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        wanted = tuple(designer.designer_workspace.available_parts)
        assert any(key.startswith("box_body:divider:") for key in wanted)
        assert any(key.startswith("inner_door:") for key in wanted)
        assert tuple(designer.assembly_part_visible_vars) == wanted
        assert tuple(designer.assembly_part_corner_vars) == wanted
        assert tuple(designer.assembly_part_blank_vars) == wanted
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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_default_layout_materializes_two_door_parts():
    """Receiving 預設 1×2 門格必須是兩個 formal Fold Designer parts。"""
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        door_keys = tuple(
            key for key in designer.designer_workspace.available_parts
            if key.startswith("door_c")
        )
        assert door_keys == ("door_c1_r1", "door_c1_r2")
        assert "door" not in designer.designer_workspace.available_parts
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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_second_topology_change_rebuilds_without_stale_rows():
    """Receiving 門格再次改變後，資訊列不得殘留/重複舊 derived part。"""
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        before = tuple(designer.designer_workspace.available_parts)
        assert sum(key.startswith("box_body:divider:") for key in before) == 1

        designer._phase6_input_snapshot["door_layout_columns"] = [[800.0, [700.0, 500.0, 400.0]]]
        designer._settings_values["door_layout_columns"] = [[800.0, [700.0, 500.0, 400.0]]]
        bridge._phase6_refresh_profiles_from_settings(designer)
        root.update_idletasks(); root.update()

        wanted = tuple(designer.designer_workspace.available_parts)
        current = tuple(designer.assembly_part_visible_vars)
        assert sum(key.startswith("box_body:divider:") for key in wanted) == 2
        assert current == wanted
        assert len(current) == len(set(current))
        assert tuple(designer.assembly_part_corner_vars) == wanted
        assert tuple(designer.assembly_part_blank_vars) == wanted
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


def test_part_label_localizes_dynamic_receiving_and_box_piece_keys():
    import fold_designer_bridge as bridge

    receiving = {"model": "受電箱", "door_layout_columns": [[800.0, [1100.0, 500.0]]]}
    assert bridge._phase6_part_label("door_c1_r1", snapshot=receiving) == "上門"
    assert bridge._phase6_part_label("door_c1_r2", snapshot=receiving) == "下門"
    assert bridge._phase6_part_label("door_c2_r3", snapshot={"model": "金庫型"}) == "第2欄第3門"
    assert bridge._phase6_part_label("box_body:left_side") == "左側板"
    assert bridge._phase6_part_label("box_body:back") == "後面板"
    assert bridge._phase6_part_label("box_body:right_side") == "右側板"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_assembly_rows_have_formed_blank_corner_contract_and_no_raw_keys():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()
        bridge._phase6_query_assembly_render_data(designer)

        wanted = tuple(designer.designer_workspace.available_parts)
        assert tuple(designer.assembly_part_formed_vars) == wanted
        assert tuple(designer.assembly_part_blank_vars) == wanted
        assert tuple(designer.assembly_part_corner_vars) == wanted
        operator_text = "\n".join(
            [bridge._phase6_part_label(key, snapshot=designer._phase6_input_snapshot) for key in wanted]
            + [var.get() for var in designer.assembly_part_formed_vars.values()]
            + [var.get() for var in designer.assembly_part_blank_vars.values()]
            + [var.get() for var in designer.assembly_part_corner_vars.values()]
        )
        for token in ("box_body_left_side", "box_body_back", "box_body_right_side", "door_c1_r1", "door_c1_r2"):
            assert token not in operator_text
        assert all(var.get().startswith("成形尺寸：") for var in designer.assembly_part_formed_vars.values())
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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_three_piece_body_has_three_independent_piece_info_subrows():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()
        bridge._phase6_query_assembly_render_data(designer)
        keys = tuple(designer.assembly_box_body_piece_formed_vars)
        assert keys == ("box_body:left_side", "box_body:back", "box_body:right_side")
        text = "\n".join(
            [designer.assembly_box_body_piece_labels[k] for k in keys]
            + [designer.assembly_box_body_piece_formed_vars[k].get() for k in keys]
            + [designer.assembly_box_body_piece_blank_vars[k].get() for k in keys]
            + [designer.assembly_box_body_piece_corner_vars[k].get() for k in keys]
        )
        assert "左側板" in text and "後面板" in text and "右側板" in text
        assert "box_body_" not in text
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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_formal_door_parts_activate_with_independent_cell_dimensions():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        dims = dict(designer._phase6_input_snapshot.get("part_dimensions") or {})
        assert "door" not in dims
        assert tuple(k for k in dims if k.startswith("door_c")) == ("door_c1_r1", "door_c1_r2")
        assert dims["door_c1_r1"]["height"] != dims["door_c1_r2"]["height"]

        designer.activate_part("door_c1_r1")
        root.update_idletasks(); root.update()
        r1 = bridge._phase6_query_final_render_data(designer)
        r1_blank = bridge._phase6_current_unfolded_size(designer, "door_c1_r1")
        assert designer.designer_workspace.active_part == "door_c1_r1"

        designer.activate_part("door_c1_r2")
        root.update_idletasks(); root.update()
        r2 = bridge._phase6_query_final_render_data(designer)
        r2_blank = bridge._phase6_current_unfolded_size(designer, "door_c1_r2")
        assert designer.designer_workspace.active_part == "door_c1_r2"

        assert r1 is not None and r2 is not None
        assert r1_blank is not None and r2_blank is not None
        assert r1_blank != r2_blank
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
