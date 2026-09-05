import time
import tkinter as tk

import fold_designer_bridge as bridge


def _snapshot():
    settings = {
        'w':500.0,'h':600.0,'d':200.0,'t':2.0,'fw':25.0,'draw_stock':False,
        'relief_top_secondary_x_factor':0.5,'relief_top_secondary_depth_factor':2.0,
        'relief_bottom_x_factor':0.5,'relief_bottom_y_factor':0.5,
        'notch_bottom_gap':0.5,'notch_sub_x_half':0.5,'notch_sub_y_factor':2.0,
        'zl1':15.0,'zl2':20.0,'zr1':15.0,'zr2':20.0,'z_comp':3.0,
        'yl1':15.0,'yr1':15.0,'ytop1':16.0,'ybottom1':15.0,
        'hang_hole_r':3.2,'hang_hole_x':35.5,'hang_hole_y_up':6.0,
        'sq_x_left':3.0,'sq_width':4.0,'sq_y_bottom':18.0,'sq_height':4.0,
        'bottom_hole_r':2.5,'bottom_hole_y':5.0,
        'door_gap_w':3.5,'door_gap_h':3.5,
        'door_fold_l':19.0,'door_fold_r':15.0,'door_fold_t':15.0,'door_fold_b':15.0,
        'base_plate_shrink_top':55.0,'base_plate_shrink_bottom':55.0,
        'base_plate_shrink_left':55.0,'base_plate_shrink_right':55.0,'base_plate_bend':15.0,
        'indicator_box_fold':49.0,'indicator_door_fold':19.0,
    }
    return dict(
        model='金庫型', w=500, h=600, d=200, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=3,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        door_gap_w=3.5, door_gap_h=3.5,
        door_fold_l=19, door_fold_r=15, door_fold_t=15, door_fold_b=15,
        base_plate_shrink_top=55, base_plate_shrink_bottom=55,
        base_plate_shrink_left=55, base_plate_shrink_right=55, base_plate_bend=15,
        indicator_box_fold=49, indicator_door_fold=19,
        existing_parts=['box_body','head','tail','door','base_plate','indicator_box','indicator_door'],
        active_part='box_body', part_dimensions={}, part_features={}, part_face_features={}, settings=settings,
    )


def _make_app(monkeypatch):
    monkeypatch.setattr(bridge, 'project_features_to_original_holes', lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _snapshot())
    # Flush all startup-generated notebook/after events before counting a switch.
    end = time.perf_counter() + 0.35
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.005)
    return root, win, app


def _drain(root, seconds=0.45):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.005)


def test_equivalent_part_switch_skips_full_update_but_renders_committed_view_once(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        counts = {'update': 0, 'renderer': 0, 'holes': 0, 'rebuild': 0}

        original_update = app.do_update
        def counted_update(*args, **kwargs):
            counts['update'] += 1
            return original_update(*args, **kwargs)
        app.do_update = counted_update

        original_renderer = app.renderer.render
        def counted_renderer(*args, **kwargs):
            counts['renderer'] += 1
            return original_renderer(*args, **kwargs)
        app.renderer.render = counted_renderer

        original_holes = app.holes_ui.render
        def counted_holes(*args, **kwargs):
            counts['holes'] += 1
            return original_holes(*args, **kwargs)
        app.holes_ui.render = counted_holes

        original_rebuild = app.bend_ui.rebuild_tabs
        def counted_rebuild(*args, **kwargs):
            counts['rebuild'] += 1
            return original_rebuild(*args, **kwargs)
        app.bend_ui.rebuild_tabs = counted_rebuild

        app.activate_part('door')
        _drain(root)

        # Deep-module orchestration owns the new contract: a pure active-view
        # switch must not enter the legacy full-update executor.
        assert counts['update'] == 0
        assert counts['renderer'] == 1
        assert counts['holes'] == 0
        assert counts['rebuild'] <= 1
    finally:
        root.destroy()


def test_preview_off_part_switch_never_renders_3d_even_after_queued_events(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        app.set_3d_preview_enabled(False)
        _drain(root, 0.15)
        calls = []
        original_renderer = app.renderer.render
        app.renderer.render = lambda *a, **k: (calls.append(1), original_renderer(*a, **k))[1]
        app.activate_part('head')
        _drain(root)
        assert calls == []
    finally:
        root.destroy()


def test_switching_back_to_box_body_is_display_only_and_does_not_schedule_full_update(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        app.activate_part('head')
        _drain(root)
        counts = {'update': 0, 'renderer': 0}
        original_update = app.do_update
        def counted_update(*args, **kwargs):
            counts['update'] += 1
            return original_update(*args, **kwargs)
        app.do_update = counted_update
        original_renderer = app.renderer.render
        def counted_renderer(*args, **kwargs):
            counts['renderer'] += 1
            return original_renderer(*args, **kwargs)
        app.renderer.render = counted_renderer

        app.activate_part('box_body')
        _drain(root)

        assert counts == {'update': 0, 'renderer': 1}
    finally:
        root.destroy()
