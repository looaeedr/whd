import tkinter as tk

import pytest

import gui
import fold_designer_bridge as bridge


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


def test_box_body_corner_data_uses_direct_whd_face_dimensions():
    root, app = make_app()
    designer = None
    try:
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        assert bridge._phase6_select_corner_data_part(designer, "box_body") == "box_body"
        root.update_idletasks(); root.update()

        projection = bridge._phase6_corner_data_unfold_projection(designer)
        assert projection is not None
        assert projection.part_key == "box_body"
        contexts = projection.render_data.box_body_face_contexts
        assert {
            key: (float(ctx.outer_width), float(ctx.outer_height))
            for key, ctx in contexts.items()
        } == {
            "left": (200.0, 600.0),
            "back": (500.0, 600.0),
            "right": (200.0, 600.0),
        }
        assert not hasattr(app, "notebook")
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
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


def test_box_body_corner_data_keeps_original_unfolded_structural_geometry():
    root, app = make_app()
    designer = None
    try:
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        bridge._phase6_select_corner_data_part(designer, "box_body")
        projection = bridge._phase6_corner_data_unfold_projection(designer)

        assert projection is not None
        render_data = projection.render_data
        bend_primitives = [
            primitive for primitive in render_data.scene.primitives
            if getattr(primitive, "layer", None) == "BEND"
        ]
        minx, _miny, maxx, _maxy = map(float, render_data.material.bounds)
        assert bend_primitives
        assert (maxx - minx) > 500 + 200 + 200  # full unfolded blank includes folds/flanges
        assert designer.corner_data_canvas is not None
        assert not hasattr(app, "notebook")
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_box_body_face_contexts_are_projected_onto_authoritative_unfolded_strip():
    root, app = make_app()
    designer = None
    try:
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("200")
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        bridge._phase6_select_corner_data_part(designer, "box_body")
        projection = bridge._phase6_corner_data_unfold_projection(designer)

        assert projection is not None
        render_data = projection.render_data
        contexts = render_data.box_body_face_contexts
        assert set(contexts) == {"left", "back", "right"}
        minx, miny, maxx, maxy = map(float, render_data.material.bounds)
        assert maxx > minx and maxy > miny
        for face in ("left", "back", "right"):
            ctx = contexts[face]
            assert ctx.unfolded_max_x > ctx.unfolded_min_x
            assert ctx.unfolded_height > 0
            assert ctx.outer_width > 0 and ctx.outer_height == pytest.approx(600.0)
        # Face ownership is metadata on the same authoritative aggregate blank;
        # the 2D view must not substitute a face-only material polygon.
        assert (maxx - minx) > sum(ctx.outer_width for ctx in contexts.values())
        assert projection.part_key == "box_body"
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_unified_editor_does_not_draw_finished_boundary_text_label():
    import inspect

    source = inspect.getsource(gui.BoxCalculatorGUI._open_unified_hole_editor)
    assert 'text="Finished Boundary"' not in source
