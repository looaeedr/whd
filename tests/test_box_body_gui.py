import tkinter as tk

import gui
from ae_engine.sheetmetal_features import box_body_face_contexts_from_strip


def make_app():
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    return root, app


def test_box_body_owns_three_independent_face_feature_stores():
    root, app = make_app()
    try:
        assert set(app.box_body_face_features) == {"left", "back", "right"}
        assert app.box_body_face_features["left"] is not app.box_body_face_features["back"]
        assert app.box_body_face_features["right"] is not app.box_body_face_features["back"]
    finally:
        root.destroy()


def test_box_body_overview_uses_direct_whd_face_dimensions():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x800")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        app.notebook.select(app.tab_z)
        root.update()
        app.draw_box_body(app.get_float_values())
        assert set(app.box_body_face_bounds) == {"left", "back", "right"}
        assert app.last_box_body_face_overview["dimensions"] == {
            "left": (200.0, 600.0),
            "back": (500.0, 600.0),
            "right": (200.0, 600.0),
        }
    finally:
        root.destroy()


def test_box_body_face_editor_receives_direct_whd_reference_guide_and_baseline_status(monkeypatch):
    root, app = make_app()
    captured = {}
    try:
        # T11 known-family selection owns the canonical preset.  Select the
        # family first, then exercise this test's actual seam: current WHD edits
        # must flow directly into the Box Body face editor.
        app.baseline_var.set("金庫型")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")

        def fake_open(part_key, title, surface, width, height, **kwargs):
            captured.update(
                part_key=part_key, title=title, width=width, height=height,
                surface=surface,
                reference_guide=kwargs["reference_guide"],
                feature_list_override=kwargs["feature_list_override"],
                baseline_status_text=kwargs["baseline_status_text"],
            )

        monkeypatch.setattr(app, "_open_unified_hole_editor", fake_open)
        app.open_box_body_face_editor("back")

        assert captured["part_key"] == "box_body_back"
        assert captured["width"] == 500.0
        assert captured["height"] == 600.0
        assert tuple(round(v, 6) for v in captured["surface"].polygon.bounds) == (2.0, 2.0, 498.0, 598.0)
        guide = captured["reference_guide"]
        assert guide.min_point.x == 0.0 and guide.min_point.y == 0.0
        assert guide.max_point.x == 500.0 and guide.max_point.y == 600.0
        assert captured["feature_list_override"] is app.box_body_face_features["back"]
        assert captured["baseline_status_text"] == "基準檔：金庫型/箱身.dxf（固定特徵映射）"
    finally:
        root.destroy()


def test_box_body_manual_second_click_opens_hit_face_without_full_recalculation(monkeypatch):
    root, app = make_app()
    opened = []
    recalcs = []
    try:
        app.box_body_face_bounds = {
            "left": (10, 10, 110, 210),
            "back": (110, 10, 360, 210),
            "right": (360, 10, 460, 210),
        }
        monkeypatch.setattr(app, "open_box_body_face_editor", lambda face: opened.append(face))
        monkeypatch.setattr(app, "update_calculations", lambda *a, **k: recalcs.append(True))

        class Event:
            x = 200
            y = 100
            time = 1000

        assert app.on_box_body_canvas_press(Event()) == "break"
        Event.time = 1300
        assert app.on_box_body_canvas_press(Event()) == "break"
        assert opened == ["back"]
        assert recalcs == []
    finally:
        root.destroy()


def test_selected_export_passes_three_face_stores_to_single_box_body_export(monkeypatch, tmp_path):
    root, app = make_app()
    captured = {}
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

        def fake_export(spec, filepath, context):
            captured["spec"] = spec
            captured["filepath"] = filepath
            captured["context"] = context
            return type("ExportResult", (), {"output_path": filepath})()
        monkeypatch.setattr(app, "_export_authoritative_part", fake_export)
        app.export_selected_dxf()
        assert dict(captured["spec"].face_features) == {
            key: tuple(value) for key, value in app.box_body_face_features.items()
        }
        assert tuple(captured["spec"].face_features["back"]) == ("BACK_SENTINEL",)
    finally:
        root.destroy()


def test_known_family_selection_applies_canonical_stripfold_parameters_without_parsing_box_body_baseline(monkeypatch):
    root, app = make_app()
    try:
        class Data:
            pass
        endcap = Data()
        endcap.params = {"yl1": 20, "yr1": 20, "ytop1": 40, "ybottom1": 20, "fw": 25}
        door = Data()
        door.params = {"door_fold_l": 19, "door_fold_r": 15, "door_fold_t": 15, "door_fold_b": 15}
        monkeypatch.setattr(gui.ae, "get_stretched_end_cap_data", lambda *a, **k: endcap)
        monkeypatch.setattr(gui.ae, "get_stretched_door_data", lambda *a, **k: door)
        monkeypatch.setattr(gui.ae, "get_stretched_box_body_data", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not parse structural box body from baseline")))

        # Seed stale runtime edits, then explicitly select the known Vault
        # family.  T11 requires the target family's canonical preset to win.
        app.zl1_var.set("11")
        app.zl2_var.set("22")
        app.zr1_var.set("13")
        app.zr2_var.set("24")
        app.z_comp_var.set("5")
        app.baseline_var.set("金庫型")

        assert app.zl1_var.get() == "15"
        assert app.zl2_var.get() == "20"
        assert app.zr1_var.get() == "15"
        assert app.zr2_var.get() == "20"
        assert app.z_comp_var.get() == "2"
    finally:
        root.destroy()


def test_box_body_main_preview_keeps_original_unfolded_structural_geometry(monkeypatch):
    root, app = make_app()
    captured = {}
    try:
        root.deiconify()
        root.geometry("1200x800")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        app.notebook.select(app.tab_z)
        root.update()

        real_authoritative = app._authoritative_render_data
        def capture_authoritative(spec, context):
            render_data = real_authoritative(spec, context)
            captured["render_data"] = render_data
            return render_data
        monkeypatch.setattr(app, "_authoritative_render_data", capture_authoritative)

        app.draw_box_body(app.get_float_values())

        render_data = captured["render_data"]
        bend_primitives = [
            primitive for primitive in render_data.scene.primitives
            if getattr(primitive, "layer", None) == "BEND"
        ]
        bend_items = [
            item for item in app.canvas_z.find_all()
            if app.canvas_z.type(item) == "line"
            and app.canvas_z.itemcget(item, "fill") == "#0a84ff"
        ]
        minx, _miny, maxx, _maxy = map(float, render_data.material.bounds)
        assert bend_primitives
        assert len(bend_items) >= len(bend_primitives)
        assert (maxx - minx) > 500 + 200 + 200  # full unfolded blank includes folds/flanges
    finally:
        root.destroy()


def test_box_body_face_hit_zones_are_projected_onto_unfolded_strip_not_replacing_it():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x800")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        app.notebook.select(app.tab_z)
        root.update()
        val = app.get_float_values()
        app.draw_box_body(val)

        result = gui.build_box_body_result(
            w=val['w'], h=val['h'], d=val['d'], t=val['t'], fw=val['fw'],
            zl1=val['zl1'], zl2=val['zl2'], zr1=val['zr1'], zr2=val['zr2'],
            z_comp=val['z_comp'],
        )
        contexts = box_body_face_contexts_from_strip(
            result.topology, w=val['w'], h=val['h'], d=val['d'], t=val['t']
        )
        meta = app.last_box_body_face_overview
        assert meta["mode"] == "unfolded_with_face_hit_zones"
        assert meta["unfolded_size"] == (result.width, result.height)
        for face in ("left", "back", "right"):
            x1, y1, x2, y2 = app.box_body_face_bounds[face]
            p1 = meta["transform"].canvas_to_world(x1, y2)
            p2 = meta["transform"].canvas_to_world(x2, y1)
            wx1, wy1 = p1.x, p1.y
            wx2, wy2 = p2.x, p2.y
            ctx = contexts[face]
            assert abs(wx1 - ctx.unfolded_min_x) < 1e-5
            assert abs(wx2 - ctx.unfolded_max_x) < 1e-5
            assert abs(wy1 - 0.0) < 1e-5
            assert abs(wy2 - result.height) < 1e-5
    finally:
        root.destroy()


def test_unified_editor_does_not_draw_finished_boundary_text_label():
    import inspect

    source = inspect.getsource(gui.BoxCalculatorGUI._open_unified_hole_editor)
    assert 'text="Finished Boundary"' not in source
