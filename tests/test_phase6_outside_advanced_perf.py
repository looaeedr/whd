import time
import tkinter as tk

import fold_designer_bridge as bridge


def _base_snapshot():
    settings = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 25.0,
        "draw_stock": False,
        "relief_top_secondary_x_factor": 0.5,
        "relief_top_secondary_depth_factor": 2.0,
        "relief_bottom_x_factor": 0.5,
        "relief_bottom_y_factor": 0.5,
        "notch_bottom_gap": 0.5, "notch_sub_x_half": 0.5, "notch_sub_y_factor": 2.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 3.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "hang_hole_r": 3.2, "hang_hole_x": 35.5, "hang_hole_y_up": 6.0,
        "sq_x_left": 3.0, "sq_width": 4.0, "sq_y_bottom": 18.0, "sq_height": 4.0,
        "bottom_hole_r": 2.5, "bottom_hole_y": 5.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 15.0, "door_fold_t": 15.0, "door_fold_b": 15.0,
        "base_plate_shrink_top": 55.0, "base_plate_shrink_bottom": 55.0,
        "base_plate_shrink_left": 55.0, "base_plate_shrink_right": 55.0,
        "base_plate_bend": 15.0,
        "indicator_box_fold": 49.0, "indicator_door_fold": 19.0,
    }
    return dict(
        model="金庫型", w=500, h=600, d=200, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=3,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        door_gap_w=3.5, door_gap_h=3.5,
        door_fold_l=19, door_fold_r=15, door_fold_t=15, door_fold_b=15,
        base_plate_shrink_top=55, base_plate_shrink_bottom=55,
        base_plate_shrink_left=55, base_plate_shrink_right=55, base_plate_bend=15,
        indicator_box_fold=49, indicator_door_fold=19,
        existing_parts=["box_body", "door", "base_plate"], active_part="box_body",
        part_dimensions={
            "box_body": {"width": 500, "height": 600},
            "door": {"width": 435, "height": 535},
            "base_plate": {"width": 390, "height": 490},
        },
        part_features={}, part_face_features={}, settings=settings,
    )


def test_box_body_engine_profile_keeps_bend_span_but_editor_shows_outside_whd():
    p = bridge.build_box_body_profile(_base_snapshot())
    by_key = {seg.get("phase6_key"): seg for seg in p}
    assert by_key["d_left"]["len"] == 196
    assert by_key["w"]["len"] == 496
    assert by_key["d_right"]["len"] == 196
    assert bridge.engine_segment_length_to_ui(by_key["d_left"]) == 200
    assert bridge.engine_segment_length_to_ui(by_key["w"]) == 500
    assert bridge.engine_segment_length_to_ui(by_key["d_right"]) == 200

    out = bridge.read_box_body_profile(p, _base_snapshot())
    assert out["w"] == 500
    assert out["d"] == 200


def test_regular_door_engine_profile_uses_finished_minus_2t_but_editor_shows_finished_outside_size():
    p = bridge.build_standard_part_profiles(_base_snapshot(), "door")
    assert p["X"][1]["len"] == 431
    assert p["Y"][1]["len"] == 531
    assert bridge.engine_segment_length_to_ui(p["X"][1]) == 435
    assert bridge.engine_segment_length_to_ui(p["Y"][1]) == 535


def test_base_plate_material_span_stays_raw_but_fold_editor_shows_topology_outside_size():
    p = bridge.build_standard_part_profiles(_base_snapshot(), "base_plate")
    assert p["X"][1]["len"] == 390
    assert p["Y"][1]["len"] == 490
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p["X"]] == [17, 394, 17]
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p["Y"]] == [17, 494, 17]


def _make_app(monkeypatch, on_settings_change=None):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root)
    app = bridge.Phase6FoldDesignerApp(
        win, _base_snapshot(),
        on_settings_change=on_settings_change,
    )
    win.update_idletasks()
    return root, win, app


def test_legacy_relief_and_notch_are_hidden_from_live_settings_panel(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        # RELIEF / NOTCH are legacy compatibility inputs only. They must not
        # reappear as a second left-side ownership surface now that the
        # parameter lock controls the live settings panel.
        assert not hasattr(app, "left_advanced_settings_frame")
        assert not hasattr(app, "left_advanced_vars")
        assert app.advanced_settings_visible is True
        assert app.advanced_toggle_button is None
        app._render_settings_context("global")
        page = app.settings_panel.page_cache["global"]
        assert "relief_top_secondary_x_factor" not in page["setting_vars"]
        assert "notch_bottom_gap" not in page["setting_vars"]
    finally:
        root.destroy()


def test_settings_typing_coalesces_expensive_live_callback_until_user_pauses(monkeypatch):
    calls = []
    root, win, app = _make_app(monkeypatch, on_settings_change=lambda values: calls.append(dict(values)))
    try:
        calls.clear()
        var = app.left_global_vars["w"]
        var.set("6")
        var.set("64")
        var.set("640")
        # Value state is immediate, expensive callback is delayed/coalesced.
        assert app._settings_values["w"] == 640.0
        assert calls == []
        time.sleep(0.18)
        root.update()
        assert len(calls) == 1
        assert calls[0]["w"] == 640.0
    finally:
        root.destroy()


def test_settings_focusout_flushes_pending_value_immediately(monkeypatch):
    calls = []
    root, win, app = _make_app(monkeypatch, on_settings_change=lambda values: calls.append(dict(values)))
    try:
        calls.clear()
        var = app.left_global_vars["w"]
        var.set("650")
        assert calls == []
        app.flush_pending_settings()
        root.update_idletasks()
        assert len(calls) == 1
        assert calls[0]["w"] == 650.0
    finally:
        root.destroy()


def test_box_body_every_fold_editor_segment_uses_adjacent_bend_count_for_outside_dimension():
    snap = _base_snapshot()
    p = bridge.build_box_body_profile(snap)
    assert [seg["len"] for seg in p] == [15, 20, 25, 196, 496, 196, 25, 20, 15]
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p] == [17, 24, 29, 200, 500, 200, 29, 24, 17]
    # Reverse conversion must restore the exact material segment lengths.
    outside = [17, 24, 29, 200, 500, 200, 29, 24, 17]
    assert [bridge.ui_segment_length_to_engine(seg, value) for seg, value in zip(p, outside)] == [15, 20, 25, 196, 496, 196, 25, 20, 15]


def test_three_segment_fold_profiles_apply_1t_to_outer_segments_and_2t_to_middle_segment():
    snap = _base_snapshot()
    p = bridge.build_standard_part_profiles(snap, "door")["X"]
    # Material/profile lengths stay authoritative.
    assert [seg["len"] for seg in p] == [19, 431, 15]
    # Operator sees outside dimensions: one adjacent bend on outer segments,
    # two adjacent bends on the middle segment.
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p] == [21, 435, 17]


def test_four_segment_endcap_y_profile_applies_topology_based_outside_compensation():
    snap = _base_snapshot()
    p = bridge.build_endcap_xy_profiles(snap)["Y"]
    assert [seg["len"] for seg in p] == [16, 25, 194, 15]
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p] == [18, 29, 198, 17]


def test_3d_preview_can_be_disabled_so_updates_skip_renderer(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        calls = []
        monkeypatch.setattr(app.renderer, "render", lambda: calls.append("render"))
        app.set_3d_preview_enabled(False)
        calls.clear()
        app.do_update()
        assert calls == []
        assert app.preview_3d_enabled is False
        app.set_3d_preview_enabled(True)
        assert app.preview_3d_enabled is True
        assert calls == ["render"]
    finally:
        root.destroy()


def test_user_box_body_example_matches_material_to_outside_definition_exactly():
    snap = _base_snapshot()
    snap.update({"w": 400, "d": 200, "t": 2, "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15})
    p = bridge.build_box_body_profile(snap)
    assert [seg["len"] for seg in p] == [15, 20, 25, 196, 396, 196, 25, 20, 15]
    assert [bridge.engine_segment_length_to_ui(seg) for seg in p] == [17, 24, 29, 200, 400, 200, 29, 24, 17]
