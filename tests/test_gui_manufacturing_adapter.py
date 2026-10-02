import inspect
import tkinter as tk

import gui


def make_app():
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    return root, app


def test_gui_builds_box_body_and_endcap_specs_from_existing_state():
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec

    root, app = make_app()
    try:
        # T11: explicit known-family selection reapplies the canonical preset.
        # Select the family first, then exercise this test's actual seam:
        # manufacturing specs must consume the current edited GUI state.
        app.baseline_var.set("金庫型")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        app.t_var.set("2")
        val = app.get_float_values()

        body = app._box_body_part_spec(val)
        head = app._end_cap_part_spec(val, is_tail=False)
        tail = app._end_cap_part_spec(val, is_tail=True)

        assert isinstance(body, BoxBodyPartSpec)
        assert (body.width, body.height, body.depth, body.thickness) == (500, 600, 200, 2)
        assert body.model_name == "金庫型"
        assert body.face_features == {key: tuple(value) for key, value in app.box_body_face_features.items()}

        assert isinstance(head, EndCapPartSpec) and isinstance(tail, EndCapPartSpec)
        assert (head.width, head.height, head.depth) == (500, 600, 200)
        assert head.is_tail is False and tail.is_tail is True
        assert head.holes == tuple(app.head_holes)
        assert tail.holes == tuple(app.tail_holes)
        assert head.fold_left == val["yl1"]
        assert head.box_fold_left == val["zl1"]
    finally:
        root.destroy()


def test_gui_builds_single_and_multidoor_specs_with_existing_feature_ownership():
    from ae_engine.contracts import DoorPartSpec

    root, app = make_app()
    try:
        # T11 family selection is the reset seam; per-test runtime edits come
        # after it so this test remains about DoorPartSpec ownership/contents.
        app.baseline_var.set("金庫型")
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.t_var.set("2")
        val = app.get_float_values()
        app.surface_features["door"].append("SINGLE")

        single = app._single_door_part_spec(val, indicator_hole=(100, 120), door_indicator=(2, 3))
        assert isinstance(single, DoorPartSpec)
        assert single.features == ("SINGLE",)
        assert single.indicator_hole == (100, 120)
        assert single.door_indicator == (2, 3)
        assert single.model_name == "金庫型"
        assert single.feature_space == "legacy_unfolded"

        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [1000])])
        cell = app.get_door_layout_cells()[0]
        key = app._door_layout_cell_key(cell)
        app.door_layout_features[key] = []
        app.door_layout_features[key].append("CELL")
        state = app._door_layout_indicator_state_for_key(key)
        state["mode"] = "indicator"
        state["layers"] = 1
        state["groups"] = [2, 2, 2, 2, 2, 2]

        multi = app._door_layout_part_spec(cell, val)
        assert isinstance(multi, DoorPartSpec)
        assert (multi.width, multi.height) == (cell.start_width, cell.start_height)
        assert multi.frame_edges == cell.edges
        assert multi.features == ("CELL",)
        assert multi.door_indicator == (2,)
        assert multi.feature_space == "legacy_unfolded"
        indicator_door = app._indicator_door_part_spec(val, (2,), features=("IND",))
        assert indicator_door.feature_space == "legacy_unfolded"
    finally:
        root.destroy()


def test_gui_export_paths_use_manufacturing_api_not_direct_ae_exporters():
    methods = (
        gui.BoxCalculatorGUI.export_multi_door_layout_dxfs,
        gui.BoxCalculatorGUI.export_multi_door_indicator_box_parts,
        gui.BoxCalculatorGUI.export_selected_dxf,
    )
    source = "\n".join(inspect.getsource(method) for method in methods)
    assert "ae.export_" not in source
    assert "_export_authoritative_part" in source
    helper_source = inspect.getsource(gui.BoxCalculatorGUI._export_authoritative_part)
    assert "manufacturing_api.save_part_render_data_dxf" in helper_source
    assert "manufacturing_api.generate_box_body_structure_parts" in helper_source


def test_selected_box_body_export_routes_exact_spec_through_api(monkeypatch, tmp_path):
    root, app = make_app()
    calls = []
    try:
        app.export_z_var.set(True)
        app.export_head_var.set(False)
        app.export_tail_var.set(False)
        app.export_door_var.set(False)
        app.export_base_plate_var.set(False)
        app.export_ib_var.set(False)
        app.export_ib_door_var.set(False)
        app.box_body_face_features["back"].append("BACK_SENTINEL")

        monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *a, **k: None)
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *a, **k: None)
        monkeypatch.setattr(
            app, "_export_authoritative_part",
            lambda spec, path, context=None: calls.append((spec, path, context)),
        )

        app.export_selected_dxf()
        assert len(calls) == 1
        spec, path, context = calls[0]
        assert spec.face_features["back"] == ("BACK_SENTINEL",)
        assert path.endswith("box_body_z.dxf")
        assert context.draw_stock == app.draw_stock_var.get()
    finally:
        root.destroy()
