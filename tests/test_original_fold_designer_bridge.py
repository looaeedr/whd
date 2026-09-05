import ast
import hashlib
import inspect
import tkinter as tk


def _safe_destroy(root):
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_original_renderer_source_is_unchanged_from_user_mainapp():
    import fold_designer_original as original

    text = open(original.__file__, encoding="utf-8").read()
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Renderer")
    source = ast.get_source_segment(text, node)
    digest = hashlib.sha256(source.encode()).hexdigest()
    assert digest == "98b8eb92e0c2e08cfd7e29291b429cf4735020b578b65fd4f34b15770917f1b5"


def test_phase6_box_body_data_maps_to_fixed_dwd_positions():
    from fold_designer_bridge import build_box_body_profile, engine_segment_length_to_ui

    profile = build_box_body_profile({
        "zl1": 15, "zl2": 20, "fw": 25,
        "d": 200, "w": 500,
        "zr2": 21, "zr1": 16,
    })
    assert [s["len"] for s in profile] == [15, 20, 25, 196, 496, 196, 25, 21, 16]
    assert [engine_segment_length_to_ui(s) for s in profile[3:6]] == [200, 500, 200]
    assert [s.get("core") for s in profile] == [None, None, None, "D", "W", "D", None, None, None]


def test_profile_round_trip_only_updates_phase6_data_fields():
    from fold_designer_bridge import build_box_body_profile, read_box_body_profile, ui_segment_length_to_engine

    snapshot = {
        "zl1": -15, "zl2": 20, "fw": 25,
        "d": 200, "w": 500,
        "zr2": 21, "zr1": -16,
        "z_comp": -10.0,
    }
    profile = build_box_body_profile(snapshot)
    profile[0]["len"] = 18
    profile[1]["len"] = 22
    profile[2]["len"] = 30
    profile[3]["len"] = ui_segment_length_to_engine(profile[3], 250)
    profile[4]["len"] = ui_segment_length_to_engine(profile[4], 600)
    profile[5]["len"] = ui_segment_length_to_engine(profile[5], 250)
    profile[6]["len"] = 30
    profile[7]["len"] = 23
    profile[8]["len"] = 19

    out = read_box_body_profile(profile, snapshot)
    assert out == {
        "zl1": -18, "zl2": 22, "fw": 30,
        "d": 250, "w": 600,
        "zr2": 23, "zr1": -19,
    }
    assert snapshot["z_comp"] == -10.0


def test_fixed_dwd_rows_cannot_be_removed():
    from fold_designer_bridge import can_remove_segment

    assert can_remove_segment({"len": 200, "core": "D"}) is False
    assert can_remove_segment({"len": 500, "core": "W"}) is False
    assert can_remove_segment({"len": 20}) is True


def test_bridge_does_not_define_or_override_renderer():
    import fold_designer_bridge as bridge

    tree = ast.parse(inspect.getsource(bridge))
    class_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert "Renderer" not in class_names


def test_added_outer_segments_do_not_move_dwd_or_break_known_value_mapping():
    from fold_designer_bridge import build_box_body_profile, read_box_body_profile

    snapshot = {"zl1": 15, "zl2": 20, "fw": 25, "d": 200, "w": 500, "zr2": 20, "zr1": 15}
    profile = build_box_body_profile(snapshot)
    profile.insert(0, {"len": 50, "angle": 90})
    profile.append({"len": 60})
    out = read_box_body_profile(profile, snapshot)
    assert out["d"] == 200
    assert out["w"] == 500
    assert out["zl1"] == 15
    assert [s.get("core") for s in profile if s.get("core")] == ["D", "W", "D"]


def test_fixed_dwd_bending_ui_keeps_original_input_grid_and_disables_only_dwd_delete():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6BendingUI, build_box_body_profile

    root = tk.Tk(); root.withdraw()
    try:
        host = tk.Toplevel(root)
        state = original.AppState()
        state.struct_mode = "vault"
        state.active_bend = "箱身"
        state.profiles_vault["箱身"] = build_box_body_profile({
            "zl1": 15, "zl2": 20, "fw": 25, "d": 200, "w": 500, "zr2": 20, "zr1": 15,
        })
        ui = Phase6BendingUI(host, state, lambda: None)
        host.update_idletasks()

        segs = state.profiles_vault["箱身"]
        for index, seg in enumerate(segs):
            row = index + 1
            delete = ui.container.grid_slaves(row=row, column=6)[0]
            if seg.get("core"):
                assert str(delete.cget("state")) == "disabled"
                labels = [w.cget("text") for w in ui.container.grid_slaves(row=row, column=5)]
                assert any(str(seg["core"]) in str(label) and str(label).startswith("料 ") for label in labels)
            else:
                assert str(delete.cget("state")) != "disabled"
    finally:
        _safe_destroy(root)


def test_fixed_dwd_metadata_survives_original_save_cycle():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6BendingUI, build_box_body_profile

    root = tk.Tk(); root.withdraw()
    try:
        host = tk.Toplevel(root)
        state = original.AppState(); state.struct_mode = "vault"; state.active_bend = "箱身"
        state.profiles_vault["箱身"] = build_box_body_profile({
            "zl1": 15, "zl2": 20, "fw": 25, "d": 200, "w": 500, "zr2": 20, "zr1": 15,
        })
        ui = Phase6BendingUI(host, state, lambda: None)
        ui.controls[4]["len"].set("600")
        ui.save()
        assert [s.get("core") for s in state.profiles_vault["箱身"] if s.get("core")] == ["D", "W", "D"]
        assert state.profiles_vault["箱身"][4]["len"] == 596
        from fold_designer_bridge import engine_segment_length_to_ui
        assert engine_segment_length_to_ui(state.profiles_vault["箱身"][4]) == 600
    finally:
        _safe_destroy(root)


def test_phase6_app_uses_original_renderer_and_loads_phase6_box_data():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
        })
        win.update_idletasks()
        assert type(app.renderer) is original.Renderer
        assert app.state.struct_mode == "vault"
        assert [s["len"] for s in app.state.profiles_vault["箱身"]] == [15,20,25,196,496,196,25,20,15]
    finally:
        _safe_destroy(root)


def test_existing_designer_profile_keeps_extra_folds_when_phase6_values_reload():
    from fold_designer_bridge import build_box_body_profile, merge_box_body_profile

    snapshot = {"zl1": 15, "zl2": 20, "fw": 25, "d": 200, "w": 500, "zr2": 20, "zr1": 15}
    profile = build_box_body_profile(snapshot)
    profile.insert(0, {"len": 50, "angle": 90})
    profile.append({"len": 60})
    updated = dict(snapshot, d=250, w=600, fw=30)
    merged = merge_box_body_profile(profile, updated)
    assert merged[0]["len"] == 50
    assert merged[-1]["len"] == 60
    assert [s["len"] for s in merged if s.get("core") == "D"] == [246, 246]
    assert [s["len"] for s in merged if s.get("core") == "W"] == [596]
    assert [s["len"] for s in merged if s.get("phase6_key") in {"fw_left", "fw_right"}] == [30, 30]


def test_top_whd_and_fixed_dwd_rows_stay_data_synchronized_without_renderer_changes():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
        })
        app.activate_part("box_body")
        app.v_w.set("620")
        app.do_update()
        assert [s["len"] for s in app.state.profiles_vault["箱身"] if s.get("core") == "W"] == [616]

        from fold_designer_bridge import ui_segment_length_to_engine
        seg = app.state.profiles_vault["箱身"][4]
        seg["len"] = ui_segment_length_to_engine(seg, 640)
        app.do_update()
        assert app.v_w.get() == "640"

        app.v_d.set("250")
        app.do_update()
        assert [s["len"] for s in app.state.profiles_vault["箱身"] if s.get("core") == "D"] == [246, 246]
    finally:
        _safe_destroy(root)


def test_phase6_endcap_values_are_loaded_into_original_head_tail_profiles_without_renderer_changes():
    from fold_designer_bridge import build_endcap_profile

    profile = build_endcap_profile({"ytop1": 16, "d": 200, "ybottom1": 15})
    assert [s["len"] for s in profile] == [16, 200, 15]
    assert len(profile) == 3


def test_part_selection_preserves_existing_order_and_prefers_previous_active_part():
    from fold_designer_bridge import normalize_part_selection

    parts, active = normalize_part_selection(
        ["box_body", "door", "indicator_box"], "indicator_box"
    )
    assert parts == ["box_body", "door", "indicator_box"]
    assert active == "indicator_box"


def test_part_selection_defaults_to_one_box_body_only_when_nothing_exists():
    from fold_designer_bridge import normalize_part_selection

    parts, active = normalize_part_selection([], None)
    assert parts == ["box_body"]
    assert active == "box_body"


def test_part_selection_falls_back_to_first_existing_when_previous_part_is_missing():
    from fold_designer_bridge import normalize_part_selection

    parts, active = normalize_part_selection(["door", "base_plate"], "indicator_box")
    assert parts == ["door", "base_plate"]
    assert active == "door"


def test_phase6_features_project_to_original_renderer_holes_without_mutating_sources():
    from ae_engine.sheetmetal_features import CircleFeature, RectFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from fold_designer_bridge import project_features_to_original_holes

    features = [
        CircleFeature(20.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(30.0, 40.0)),
        RectFeature(50.0, 25.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(80.0, 90.0)),
    ]
    before = list(features)
    holes = project_features_to_original_holes(features, 200.0, 150.0)

    assert holes == [
        {"type": "圓孔", "name": "孔1", "x": 30, "y": 40, "d1": 20, "d2": 0},
        {"type": "方孔", "name": "孔2", "x": 80, "y": 90, "d1": 50, "d2": 25},
    ]
    assert features == before


def test_profile_features_are_preserved_but_not_faked_as_circle_or_rect_preview_holes():
    from ae_engine.sheetmetal_features import ProfileFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from fold_designer_bridge import project_features_to_original_holes

    profile = ProfileFeature(
        (Vec2(-5.0, -5.0), Vec2(5.0, -5.0), Vec2(0.0, 5.0)),
        FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        Vec2(50.0, 50.0),
    )
    assert project_features_to_original_holes([profile], 100.0, 100.0) == []


def test_original_designer_hole_module_is_hidden_but_original_holes_state_still_exists(monkeypatch):
    import tkinter as tk
    import fold_designer_bridge as bridge

    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda features, width, height: [])
    Phase6FoldDesignerApp = bridge.Phase6FoldDesignerApp
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "existing_parts": ["box_body"], "active_part": "box_body",
            "part_features": {"box_body": []},
        })
        win.update_idletasks()
        assert len(app.main_nb.tabs()) == 1
        assert app.main_nb.winfo_manager() == ""
        assert hasattr(app, "holes_ui")
        assert isinstance(app.state.holes, dict)
    finally:
        _safe_destroy(root)


def test_designer_part_selector_opens_on_previous_active_part_and_can_add_missing_known_part(monkeypatch):
    import tkinter as tk
    import fold_designer_original as original
    import fold_designer_bridge as bridge

    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda features, width, height: [])
    Phase6FoldDesignerApp = bridge.Phase6FoldDesignerApp
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "ytop1": 25, "ybottom1": 25,
            "existing_parts": ["box_body", "door", "indicator_box"],
            "active_part": "indicator_box",
            "part_features": {"box_body": [], "door": [], "indicator_box": []},
        })
        win.update_idletasks()
        assert type(app.renderer) is original.Renderer
        # Phase6 no longer opens on a blank/home state. The assembly view is
        # backed by the real box-body part so geometry is immediately available.
        assert app.active_part_key == "box_body"
        assert app.part_var.get() == "組合體"
        assert all(not button.instate(["disabled"]) for button in app.part_buttons.values())
        app.activate_part("indicator_box")
        assert app.active_part_key == "indicator_box"
        assert app.part_var.get() == "指示燈盒"
        assert not hasattr(app, "part_cb")
        # Fixed part choices are exposed through one Menubutton/Menu, not one
        # Tk button per part. Availability is owned by the workspace.
        assert app.part_buttons == {}
        assert "indicator_box" in app.available_parts
        assert "base_plate" not in app.available_parts

        app.add_part("base_plate")
        assert "base_plate" in app.available_parts
        assert app.active_part_key == "base_plate"
        assert app.part_var.get() == "底板"
        assert str(app.remove_part_button.cget("state")) == "normal"
    finally:
        _safe_destroy(root)


def test_box_body_face_features_project_to_matching_original_renderer_faces():
    import tkinter as tk
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from fold_designer_bridge import Phase6FoldDesignerApp

    left = CircleFeature(10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(20.0, 30.0))
    back = CircleFeature(12.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40.0, 50.0))
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "existing_parts": ["box_body"], "active_part": "box_body",
            "part_features": {"box_body": []},
            "part_face_features": {"box_body": {"left": [left], "back": [back], "right": []}},
        })
        assert app.state.holes["左面"][0]["x"] == 20
        assert app.state.holes["正面"][0]["x"] == 40
        assert app._phase6_part_face_features["box_body"]["left"][0] == left
    finally:
        _safe_destroy(root)


def test_stored_added_part_profile_is_reused_on_next_designer_open():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    stored = {
        "X": [{"len": 33, "angle": -90}, {"len": 400, "angle": -90}, {"len": 34}],
        "Y": [{"len": 35, "angle": -90}, {"len": 500, "angle": -90}, {"len": 36}],
    }
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "未知類型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "existing_parts": ["box_body", "door"], "active_part": "door",
            "part_features": {"box_body": [], "door": []},
            "part_profiles": {"door": stored},
        })
        app.activate_part("door")
        assert [s["len"] for s in app.state.profiles["X"]] == [33, 400, 34]
        assert [s["len"] for s in app.state.profiles["Y"]] == [35, 500, 36]
    finally:
        _safe_destroy(root)


def test_export_from_standard_part_does_not_replace_cabinet_whd_with_part_preview_size():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "ytop1": 25, "ybottom1": 25,
            "existing_parts": ["box_body", "indicator_box"], "active_part": "indicator_box",
            "part_dimensions": {"indicator_box": {"width": 326, "height": 445}},
            "part_features": {"box_body": [], "indicator_box": []},
        })
        out = app.export_phase6_snapshot()
        assert out["w"] == 500
        assert out["h"] == 600
        assert out["d"] == 200
    finally:
        _safe_destroy(root)


def test_door_fold_edits_return_to_phase6_snapshot_without_changing_renderer_class():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "ytop1": 25, "ybottom1": 25,
            "door_fold_l": 19, "door_fold_r": 15, "door_fold_t": 15, "door_fold_b": 15,
            "existing_parts": ["box_body", "door"], "active_part": "door",
            "part_dimensions": {"door": {"width": 400, "height": 500}},
            "part_features": {"box_body": [], "door": []},
        })
        assert type(app.renderer) is original.Renderer
        app.activate_part("door")
        app.state.symmetric = False; app.v_sy.set(False)
        app.bend_ui.controls[0]["len"].set("23")
        app.bend_ui.controls[-1]["len"].set("24")
        app.bend_ui.save()
        app.state.active_bend = "Y"
        app.bend_ui.nb.select(1)
        app.bend_ui.render()
        app.bend_ui.controls[0]["len"].set("25")
        app.bend_ui.controls[-1]["len"].set("26")
        app.bend_ui.save()
        out = app.export_phase6_snapshot()
        # Editor cells are operator outside dimensions; persisted door_fold_*
        # values are canonical material lengths. Each outer segment has one
        # adjacent bend, so T=2 subtracts exactly 2 mm on save.
        assert out["door_fold_l"] == 21
        assert out["door_fold_r"] == 22
        assert out["door_fold_b"] == 23
        assert out["door_fold_t"] == 24
    finally:
        _safe_destroy(root)


def test_vault_endcap_xy_profiles_match_authoritative_phase6_bend_chain():
    from fold_designer_bridge import build_endcap_xy_profiles

    profiles = build_endcap_xy_profiles({
        "w": 500, "d": 150, "t": 2, "fw": 25,
        "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
    })
    assert [s["len"] for s in profiles["X"]] == [15, 492, 15]
    assert [s.get("phase6_key") for s in profiles["X"]] == ["yl1", "endcap_w_core", "yr1"]
    assert [s["len"] for s in profiles["Y"]] == [16, 25, 144, 15]
    assert [s.get("phase6_key") for s in profiles["Y"]] == [
        "ytop1", "fw", "endcap_d_core", "ybottom1",
    ]
    # top edge has two bends: ytop1 <-> FW and FW <-> D-3T.
    assert len(profiles["Y"]) == 4


def test_vault_endcap_xy_profiles_round_trip_derived_global_wd():
    from fold_designer_bridge import build_endcap_xy_profiles, read_endcap_xy_profiles

    snapshot = {
        "w": 500, "d": 150, "t": 2, "fw": 25,
        "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
    }
    profiles = build_endcap_xy_profiles(snapshot)
    profiles["X"][1]["len"] = 592   # W => 600
    profiles["Y"][2]["len"] = 194   # D => 200
    profiles["Y"][1]["len"] = 30
    out = read_endcap_xy_profiles(profiles, snapshot)
    assert out == {
        "w": 600, "d": 200, "fw": 30,
        "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
    }


def test_plus_minus_90_is_inverted_only_at_ui_boundary():
    from fold_designer_bridge import engine_angle_to_ui, ui_angle_to_engine

    assert engine_angle_to_ui(90) == -90
    assert engine_angle_to_ui(-90) == 90
    assert ui_angle_to_engine(90) == -90
    assert ui_angle_to_engine(-90) == 90
    assert engine_angle_to_ui(45) == 45
    assert ui_angle_to_engine(135) == 135


def test_endcap_operator_length_is_outside_dimension_while_engine_keeps_bend_line_span():
    from fold_designer_bridge import build_endcap_xy_profiles, engine_segment_length_to_ui

    profiles = build_endcap_xy_profiles({
        "w": 400, "d": 150, "t": 2, "fw": 25,
        "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
    })
    # Engine/manufacturing-side profile keeps real BEND-line spans.
    assert profiles["X"][1]["len"] == 392
    assert profiles["Y"][2]["len"] == 144
    # Operator edits outside dimensions: +1T at each 90-degree end.
    assert engine_segment_length_to_ui(profiles["X"][1]) == 396
    assert engine_segment_length_to_ui(profiles["Y"][2]) == 148



def test_bending_ui_displays_inverted_90_but_stores_original_engine_sign():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6BendingUI

    root = tk.Tk(); root.withdraw()
    try:
        host = tk.Toplevel(root)
        state = original.AppState()
        state.struct_mode = "standard"
        state.active_bend = "X"
        state.symmetric = False
        state.profiles["X"] = [
            {"len": 20, "angle": -90},
            {"len": 500, "angle": 90},
            {"len": 20},
        ]
        ui = Phase6BendingUI(host, state, lambda: None)
        assert ui.controls[0]["angle"].get() == "90"
        assert ui.controls[1]["angle"].get() == "-90"

        ui.controls[0]["angle"].set("-90")
        ui.save()
        assert state.profiles["X"][0]["angle"] == 90
    finally:
        _safe_destroy(root)


def test_bending_ui_shows_outside_core_length_but_stores_bend_line_length():
    import tkinter as tk
    import fold_designer_original as original
    from fold_designer_bridge import Phase6BendingUI, build_endcap_xy_profiles

    root = tk.Tk(); root.withdraw()
    try:
        host = tk.Toplevel(root)
        state = original.AppState()
        state.struct_mode = "standard"
        state.active_bend = "X"
        state.symmetric = False
        state.profiles = build_endcap_xy_profiles({
            "w": 400, "d": 150, "t": 2, "fw": 25,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
        })
        ui = Phase6BendingUI(host, state, lambda: None)
        assert ui.controls[1]["len"].get() == "396"
        assert state.profiles["X"][1]["len"] == 392

        ui.controls[1]["len"].set("496")
        ui.save()
        assert state.profiles["X"][1]["len"] == 492
    finally:
        _safe_destroy(root)


def test_head_uses_real_xy_profiles_and_global_whd_in_original_renderer_mode():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["box_body", "head", "tail"], "active_part": "head",
            "part_features": {"box_body": [], "head": [], "tail": []},
        })
        win.update_idletasks()
        assert app.active_part_key == "box_body"
        app.activate_part("head")
        assert app.active_part_key == "head"
        assert app.state.struct_mode == "standard"
        assert [s["len"] for s in app.state.profiles["X"]] == [15, 492, 15]
        assert [s["len"] for s in app.state.profiles["Y"]] == [16, 25, 144, 15]
        assert app.v_w.get() == "500"
        assert app.v_h.get() == "600"
        assert app.v_d.get() == "150"
    finally:
        _safe_destroy(root)


def test_switching_to_local_part_does_not_replace_global_whd_fields():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["box_body", "door"], "active_part": "box_body",
            "part_dimensions": {"door": {"width": 400, "height": 500}},
            "part_features": {"box_body": [], "door": []},
        })
        app.activate_part("door")
        assert app.v_w.get() == "500"
        assert app.v_h.get() == "600"
        assert app.v_d.get() == "150"
    finally:
        _safe_destroy(root)


def test_head_preview_never_falls_back_to_legacy_renderer_without_final_scene_provider():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["head"], "active_part": "head",
            "part_features": {"head": []},
        })
        app.activate_part("head")
        app.do_update()
        assert len(app.renderer.ax3d.collections) == 0
        assert "provider is not connected" in str(app.final_scene_view.cutting_mesh_error)
    finally:
        _safe_destroy(root)


def test_box_body_shows_only_box_body_fold_tab_not_nested_head_tail_tabs():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["box_body", "head", "tail"], "active_part": "box_body",
            "part_features": {"box_body": [], "head": [], "tail": []},
        })
        win.update_idletasks()
        app.activate_part("box_body")
        assert app.state.struct_mode == "vault"  # renderer internals stay unchanged
        assert app.bend_ui.tabs == ["X"]
        assert len(app.bend_ui.nb.tabs()) == 1
    finally:
        _safe_destroy(root)


def test_original_structure_mode_radio_buttons_are_hidden_by_bridge():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["box_body"], "active_part": "box_body",
            "part_features": {"box_body": []},
        })
        win.update_idletasks()
        texts = []
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if child.winfo_manager():
                        texts.append(str(child.cget("text")))
                except tk.TclError:
                    pass
                walk(child)
        walk(app.left)
        assert "標準十字型" not in texts
        assert "金庫型(三件)" not in texts
    finally:
        _safe_destroy(root)


def test_global_wd_updates_head_derived_cores_and_head_core_can_update_global_wd():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["head", "tail"], "active_part": "head",
            "part_features": {"head": [], "tail": []},
        })
        app.activate_part("head")
        app.v_w.set("600")
        app.v_d.set("200")
        app.do_update()
        assert app.state.profiles["X"][1]["len"] == 592
        assert app.state.profiles["Y"][2]["len"] == 194

        app.state.profiles["X"][1]["len"] = 692
        app.state.profiles["Y"][2]["len"] = 244
        app.do_update()
        assert app.v_w.get() == "700"
        assert app.v_d.get() == "250"
    finally:
        _safe_destroy(root)


def test_head_xy_edits_export_authoritative_endcap_values_without_box_body_overwrite():
    import tkinter as tk
    from fold_designer_bridge import Phase6FoldDesignerApp

    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 150, "t": 2,
            "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
            "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
            "existing_parts": ["box_body", "head", "tail"], "active_part": "head",
            "part_features": {"box_body": [], "head": [], "tail": []},
        })
        app.activate_part("head")
        app.state.symmetric = False
        app.v_sy.set(False)

        # Edit through the same BendingUI StringVars the user edits in the 3D window.
        assert app.state.active_bend == "X"
        for ctrl, value in zip(app.bend_ui.controls, (18, 596, 19)):
            ctrl["len"].set(str(value))
        app.bend_ui.save()

        app.state.active_bend = "Y"
        app.bend_ui.render()
        for ctrl, value in zip(app.bend_ui.controls, (17, 30, 198, 16)):
            ctrl["len"].set(str(value))
        app.bend_ui.save()

        out = app.export_phase6_snapshot()
        assert out["w"] == 600
        assert out["d"] == 200
        assert out["fw"] == 25
        assert out["endcap_fw"]["head"] == {"follow_box": False, "value": 26.0}
        assert out["endcap_fw"]["tail"] == {"follow_box": False, "value": 26.0}
        assert out["yl1"] == 16
        assert out["yr1"] == 17
        assert out["ytop1"] == 15
        assert out["ybottom1"] == 14
    finally:
        _safe_destroy(root)


def test_phase6_hides_legacy_module_notebook_and_mounts_fold_editor_directly(monkeypatch):
    import tkinter as tk
    import fold_designer_bridge as bridge

    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda features, width, height: [])
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        app = bridge.Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "existing_parts": ["box_body"], "active_part": "box_body",
            "part_features": {"box_body": []},
        })
        win.update_idletasks()

        assert app.main_nb.winfo_manager() == ""
        assert app.bend_ui.nb.master is app.fold_editor_host
        assert app.fold_editor_host.winfo_manager() == ""
        app.activate_part("box_body")
        win.update_idletasks()
        assert app.fold_editor_host.winfo_manager() == "pack"
    finally:
        _safe_destroy(root)


def test_phase6_part_picker_uses_one_menubutton_menu_without_combobox(monkeypatch):
    import tkinter as tk
    from tkinter import ttk
    import fold_designer_bridge as bridge

    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda features, width, height: [])
    root = tk.Tk(); root.withdraw()
    try:
        win = tk.Toplevel(root)
        parts = list(bridge.KNOWN_PARTS)
        app = bridge.Phase6FoldDesignerApp(win, {
            "model": "金庫型", "w": 500, "h": 600, "d": 200,
            "t": 2.0, "zl1": 15, "zl2": 20, "fw": 25, "zr2": 20, "zr1": 15,
            "ytop1": 25, "ybottom1": 25,
            "existing_parts": parts, "active_part": "indicator_box",
            "part_features": {key: [] for key in parts},
        })
        win.update_idletasks()
        assert not hasattr(app, "part_cb")
        assert app.part_buttons == {}
        assert tuple(app.available_parts) == tuple(parts)
        assert isinstance(app.part_choice_button, ttk.Menubutton)
        assert not any(isinstance(child, ttk.Combobox) for child in app.part_selector.winfo_children())
        app.activate_part("indicator_box")
        assert app.part_var.get() == bridge.PART_LABELS["indicator_box"]
        assert app.active_part_key == "indicator_box"
        app.activate_part("door")
        assert app.part_var.get() == bridge.PART_LABELS["door"]
        assert app.active_part_key == "door"
    finally:
        _safe_destroy(root)
