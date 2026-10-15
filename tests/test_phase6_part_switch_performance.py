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


def test_issue1793_part_switches_coalesce_scheduler_flushes(monkeypatch, record_property):
    """Record route attempts separately from effective flushes for 12 real Tk switches."""
    root, win, app = _make_app(monkeypatch)
    try:
        scheduler = app._phase6_update_scheduler
        original_submit = scheduler.submit
        original_flush = scheduler.flush_now
        original_render = app.renderer.render
        reasons, attempts, renders = [], [], []

        def observed_submit(reason="geometry", *, immediate=False, debounce_ms=None):
            reasons.append((str(reason), bool(immediate)))
            return original_submit(
                reason, immediate=immediate, debounce_ms=debounce_ms
            )

        def observed_flush():
            attempts.append(tuple(sorted(scheduler.dirty)))
            return original_flush()

        def observed_render(*args, **kwargs):
            renders.append(1)
            return original_render(*args, **kwargs)

        scheduler.submit = observed_submit
        scheduler.flush_now = observed_flush
        app.renderer.render = observed_render
        rows = []
        for part in ("door", "head", "tail", "box_body") * 3:
            before = scheduler.metrics_snapshot()
            prev_attempts, prev_render = len(attempts), len(renders)
            start = time.perf_counter()
            app.activate_part(part)
            _drain(root, 0.2)
            after = scheduler.metrics_snapshot()
            rows.append({
                "part": part,
                "attempts": len(attempts) - prev_attempts,
                "flush": after["flushes"] - before["flushes"],
                "solve": after["calculation_flushes"] - before["calculation_flushes"],
                "display": after["display_flushes"] - before["display_flushes"],
                "render": len(renders) - prev_render,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            })
        record_property("issue1793_switch_metrics", repr(rows))
        record_property("issue1793_submit_reasons", repr(reasons))
        record_property("issue1793_flush_dirty", repr(attempts))

        assert all(row["solve"] == 0 for row in rows), (rows, reasons)
        assert all(row["flush"] <= 1 for row in rows), (rows, reasons)
        assert all(row["attempts"] <= 1 for row in rows), (rows, attempts)
        assert all(row["render"] <= 1 for row in rows), (rows, reasons)
        assert scheduler.dirty == set(), (rows, reasons)
        assert scheduler._after_job is None, (rows, reasons)
    finally:
        root.destroy()


def test_issue1796_combined_whdt_twenty_input_burst_commits_latest_without_dxf_reread(
    monkeypatch, record_property,
):
    """One real Tk transaction: 20 updates each W/H/D/T, one committed final state."""
    from ae_engine import ae

    root, win, app = _make_app(monkeypatch)
    try:
        reads = []
        original_readfile = ae.ezdxf.readfile

        def readfile(*args, **kwargs):
            reads.append(str(args[0]))
            return original_readfile(*args, **kwargs)

        monkeypatch.setattr(ae.ezdxf, "readfile", readfile)
        scheduler = app._phase6_update_scheduler
        baseline = scheduler.metrics_snapshot()
        final = {}
        started = time.perf_counter()
        for key, increment in (("w", 1.0), ("h", 1.0), ("d", 1.0), ("t", 0.01)):
            initial = float(app._settings_values[key])
            for i in range(1, 21):
                value = round(initial + increment * i, 3)
                app.left_global_vars[key].set(str(value))
            final[key] = value

        # Save/Export must not observe pending text-entry state.
        app.flush_pending_settings()
        _drain(root, 0.2)
        after = scheduler.metrics_snapshot()
        deltas = {key: after[key] - baseline[key] for key in baseline}
        record_property("issue1796_whdt_burst_scheduler", repr(deltas))
        record_property("issue1796_whdt_burst_wall_ms", round((time.perf_counter() - started) * 1000, 2))
        record_property("issue1796_whdt_burst_dxf_reads", repr(reads))

        for key, expected in final.items():
            assert float(app._settings_values[key]) == expected
            assert float(app.left_global_vars[key].get()) == expected
        assert deltas["calculation_flushes"] <= 1, deltas
        assert len(reads) == 0, reads
        assert scheduler.dirty == set()
        assert scheduler._after_job is None
    finally:
        root.destroy()


def test_issue1796_combined_five_3d_toggles_with_part_switches_have_no_offscreen_render(
    monkeypatch, record_property,
):
    """Real Tk display navigation cannot trigger an offscreen full resolve."""
    root, win, app = _make_app(monkeypatch)
    try:
        scheduler = app._phase6_update_scheduler
        original_render = app.renderer.render
        renders = []

        def tracked_render(*args, **kwargs):
            renders.append(1)
            return original_render(*args, **kwargs)

        app.renderer.render = tracked_render
        rows = []
        for index, part in enumerate(("door", "head", "tail", "box_body", "door")):
            app.set_3d_preview_enabled(False)
            _drain(root, 0.1)
            before = scheduler.metrics_snapshot()
            offscreen_before = len(renders)
            started = time.perf_counter()
            app.activate_part(part)
            _drain(root, 0.2)
            after = scheduler.metrics_snapshot()
            row = {
                "part": part,
                "solve": after["calculation_flushes"] - before["calculation_flushes"],
                "render_off": len(renders) - offscreen_before,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            rows.append(row)
            assert row["solve"] == 0, rows
            assert row["render_off"] == 0, rows
            app.set_3d_preview_enabled(True)
            _drain(root, 0.1)
        record_property("issue1796_toggle_switch_metrics", repr(rows))
        assert scheduler.dirty == set()
        assert scheduler._after_job is None
    finally:
        root.destroy()
