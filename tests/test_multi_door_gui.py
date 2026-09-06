import tkinter as tk
import tkinter.font as tkfont

import gui


def make_app():
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    return root, app


def test_multi_door_gui_model_accepts_columns_and_derives_selected_cell():
    root, app = make_app()
    try:
        assert app.multi_door_enabled_var.get() is False
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.w_var.set("1100")
        app.h_var.set("1800")

        cells = app.get_door_layout_cells()
        assert len(cells) == 5
        assert cells[0].edges.right is False
        assert cells[0].edges.bottom is False
        assert cells[-1].edges.right is True
        assert cells[-1].edges.bottom is True

        app.door_layout_selected_var.set("1:0")
        selected = app.get_selected_door_layout_cell()
        assert (selected.column_index, selected.row_index) == (1, 0)
        assert selected.start_width == 500.0
        assert selected.start_height == 800.0
    finally:
        root.destroy()


def test_multi_door_controls_live_on_canvas_and_old_body_never_consumes_space():
    root, app = make_app()
    try:
        assert hasattr(app, "door_layout_body")
        assert not app.door_layout_body.winfo_ismapped()

        app.multi_door_enabled_var.set(True)
        app.toggle_multi_door_layout()
        root.update_idletasks()
        assert app.door_layout_body.winfo_manager() == ""
    finally:
        root.destroy()


def test_selected_multi_door_cell_keeps_whole_layout_visible_and_door_keeps_four_folds():
    from ae_engine.sheetmetal_part_adapters import build_door_result

    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x800")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.door_layout_selected_var.set("0:0")
        app.notebook.select(app.tab_door)
        root.update()

        app.draw_door(app.get_float_values())
        assert len(app.door_layout_cell_items) == 5
        selected = app.get_selected_door_layout_cell()
        result = build_door_result(
            w=selected.start_width, h=selected.start_height,
            t=2, fw=25, gap_w=3.5, gap_h=3.5,
            fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
            frame_edges=selected.edges,
        )
        assert round(result.width, 6) == 594.0
        assert round(result.height, 6) == 590.0
        assert result.topology.left_fold == 19.0
        assert result.topology.right_fold == 15.0
        assert result.topology.top_fold == 15.0
        assert result.topology.bottom_fold == 15.0

        app.select_door_layout_cell(1, 1)
        root.update_idletasks()
        assert len(app.door_layout_cell_items) == 5
        assert app.door_layout_selected_var.get() == "1:1"
    finally:
        root.destroy()


def test_multi_door_selected_cell_updates_left_result_dimensions():
    root, app = make_app()
    try:
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.door_layout_selected_var.set("0:0")
        app.update_calculations()
        assert app.result_door_w_var.get() == "594.00 mm"
        assert app.result_door_h_var.get() == "590.00 mm"
    finally:
        root.destroy()


def test_multi_door_export_writes_one_dxf_per_layout_cell(tmp_path):
    import ezdxf

    root, app = make_app()
    try:
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        names = app.export_multi_door_layout_dxfs(str(tmp_path), app.get_float_values(), draw_stock=False)
        assert names == [
            "door_c1_r1.dxf", "door_c1_r2.dxf", "door_c1_r3.dxf",
            "door_c2_r1.dxf", "door_c2_r2.dxf",
        ]
        for name in names:
            assert (tmp_path / name).exists()
            ezdxf.readfile(tmp_path / name)

        first = ezdxf.readfile(tmp_path / "door_c1_r1.dxf")
        cutting = list(first.modelspace().query('LWPOLYLINE[layer=="CUTTING"]'))[0]
        pts = list(cutting.get_points('xy'))
        assert round(max(p[0] for p in pts) - min(p[0] for p in pts), 6) == 594.0
        assert round(max(p[1] for p in pts) - min(p[1] for p in pts), 6) == 590.0
    finally:
        root.destroy()


def test_width_remainder_auto_completes_and_editing_auto_width_promotes_it():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [1000])])

        assert app.get_door_layout_columns() == [
            (400.0, [1000.0]),
            (600.0, [1000.0]),
        ]
        assert app.door_layout_columns[1]["width_auto"] is True

        app.door_layout_columns[1]["width_var"].set("400")
        app.commit_door_layout_width(1)
        assert app.get_door_layout_columns() == [
            (400.0, [1000.0]),
            (400.0, [1000.0]),
            (200.0, [1000.0]),
        ]
        assert app.door_layout_columns[1]["width_auto"] is False
        assert app.door_layout_columns[2]["width_auto"] is True
    finally:
        root.destroy()


def test_height_remainder_auto_completes_per_column_and_promotes_edited_auto_height():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(1000, [400])])

        assert app.get_door_layout_columns() == [(1000.0, [400.0, 600.0])]
        assert app.door_layout_columns[0]["height_auto"] == [False, True]

        app.door_layout_columns[0]["height_vars"][1].set("400")
        app.commit_door_layout_height(0, 1)
        assert app.get_door_layout_columns() == [(1000.0, [400.0, 400.0, 200.0])]
        assert app.door_layout_columns[0]["height_auto"] == [False, False, True]
    finally:
        root.destroy()


def test_removing_fixed_height_recomputes_remainder():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(1000, [400, 400])])
        assert app.get_door_layout_columns() == [(1000.0, [400.0, 400.0, 200.0])]

        app.remove_door_layout_height(0, 1)
        assert app.get_door_layout_columns() == [(1000.0, [400.0, 600.0])]
    finally:
        root.destroy()


def test_oversubscribed_layout_reports_excess_and_has_no_negative_auto_cell():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(700, [1000]), (400, [1000])])
        assert app.get_door_layout_columns() == [(700.0, [1000.0]), (400.0, [1000.0])]
        assert all(col["width_var"].get() != "-100" for col in app.door_layout_columns)
        app.refresh_door_layout_status()
        assert "超出 100" in app.door_layout_status_label.cget("text")
    finally:
        root.destroy()


def test_multi_door_canvas_shows_all_cells_without_preview_radiobuttons():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.toggle_multi_door_layout()
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update_idletasks()

        assert len(app.door_layout_cell_items) == 5
        preview_controls = [
            w for w in app.door_layout_body.winfo_children()
            if isinstance(w, tk.Radiobutton) and w.cget("text") == "預覽"
        ]
        # Search descendants too: there must be no per-cell Preview controls anywhere.
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        assert not [w for w in descendants(app.door_layout_body)
                    if isinstance(w, tk.Radiobutton) and w.cget("text") == "預覽"]

        before = tuple(app.canvas_door.find_withtag("door_layout_cell"))
        app.select_door_layout_cell(0, 1)
        root.update_idletasks()
        after = tuple(app.canvas_door.find_withtag("door_layout_cell"))
        assert len(before) == len(after) == 5
        assert app.door_layout_selected_var.get() == "0:1"
    finally:
        root.destroy()


def test_untouched_auto_remainders_stay_auto_on_focus_commit():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [400])])

        assert app.door_layout_columns[1]["width_auto"] is True
        assert app.door_layout_columns[0]["height_auto"] == [False, True]

        app.commit_door_layout_width(1)
        assert app.get_door_layout_columns() == [
            (400.0, [400.0, 600.0]),
            (600.0, [1000.0]),
        ]
        assert app.door_layout_columns[1]["width_auto"] is True

        app.commit_door_layout_height(0, 1)
        assert app.get_door_layout_columns()[0] == (400.0, [400.0, 600.0])
        assert app.door_layout_columns[0]["height_auto"] == [False, True]
    finally:
        root.destroy()


def test_multi_door_first_page_uses_canvas_entries_instead_of_layout_body():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.toggle_multi_door_layout()
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update_idletasks()

        # The old stacked editor panel must no longer consume vertical space.
        assert not hasattr(app, "door_layout_body") or not app.door_layout_body.winfo_ismapped()
        assert len(app.door_layout_width_entries) == 2
        assert len(app.door_layout_height_entries) == 5
        assert all(entry.winfo_ismapped() for entry in app.door_layout_width_entries.values())
        assert all(entry.winfo_ismapped() for entry in app.door_layout_height_entries.values())
    finally:
        root.destroy()


def test_multi_door_cells_only_allow_authoritative_derived_part_text_and_double_click_is_bound():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update_idletasks()

        # T16 intentionally projects authoritative divider/frame placement
        # information into the 2D layout.  Cell interiors may therefore contain
        # those derived-part annotations, but no unrelated metadata text.
        allowed_derived_tags = {"door_layout_divider", "door_layout_frame"}
        derived_text_items = []
        for key, bounds in app.door_layout_cell_bounds.items():
            x1, y1, x2, y2 = bounds
            for item in app.canvas_door.find_all():
                if app.canvas_door.type(item) != "text":
                    continue
                coords = app.canvas_door.coords(item)
                if len(coords) < 2:
                    continue
                x, y = coords[:2]
                if not (x1 < x < x2 and y1 < y < y2):
                    continue
                tags = set(app.canvas_door.gettags(item))
                assert tags & allowed_derived_tags, (
                    f"unowned metadata text leaked into cell {key}: tags={sorted(tags)}"
                )
                derived_text_items.append((item, tags))

        assert derived_text_items
        assert any("door_layout_divider" in tags for _item, tags in derived_text_items)

        # Interaction is canvas-level coordinate hit-testing; derived text must
        # never become the ownership seam for double-click selection.
        x1, y1, x2, y2 = app.door_layout_cell_bounds["0:0"]
        assert app._door_layout_cell_at_canvas_point((x1 + x2) / 2, (y1 + y2) / 2) == (0, 0)
    finally:
        root.destroy()


def test_double_click_cell_opens_that_cells_hole_editor_and_uses_own_feature_list(monkeypatch):
    root, app = make_app()
    try:
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        captured = {}

        def fake_editor(part_key, title, surface, width, height, **kwargs):
            captured.update(
                part_key=part_key,
                title=title,
                width=width,
                height=height,
                feature_list=kwargs.get("feature_list_override"),
                indicator_state=kwargs.get("door_indicator_state"),
            )

        monkeypatch.setattr(app, "_open_unified_hole_editor", fake_editor)
        app.open_door_layout_cell_editor(0, 1)

        assert app.door_layout_selected_var.get() == "0:1"
        assert captured["part_key"] == "door"
        assert "C1-R2" in captured["title"]
        assert captured["feature_list"] is app.door_layout_features["0:1"]
        assert captured["indicator_state"] is app.door_layout_indicator_states["0:1"]
    finally:
        root.destroy()


def test_multi_door_overview_draws_only_each_cells_own_holes():
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.baseline_var.set("自訂")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.door_layout_features["0:0"] = [
            CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0))
        ]
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update_idletasks()

        assert app.canvas_door.find_withtag("door_layout_feature_0_0")
        assert not app.canvas_door.find_withtag("door_layout_feature_1_0")
    finally:
        root.destroy()



def test_multi_door_export_keeps_user_holes_owned_by_their_cell(tmp_path):
    import ezdxf
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    root, app = make_app()
    try:
        app.baseline_var.set("自訂")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.door_layout_features["0:0"] = [
            CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(35.0, 0.0))
        ]
        app.export_multi_door_layout_dxfs(str(tmp_path), app.get_float_values(), draw_stock=False)

        first = ezdxf.readfile(tmp_path / "door_c1_r1.dxf").modelspace()
        other = ezdxf.readfile(tmp_path / "door_c2_r1.dxf").modelspace()
        assert len(list(first.query('CIRCLE[layer=="CUTTING"]'))) == 1
        assert len(list(other.query('CIRCLE[layer=="CUTTING"]'))) == 0
    finally:
        root.destroy()


def test_multi_door_export_keeps_indicator_settings_owned_by_their_cell(tmp_path):
    import ezdxf

    root, app = make_app()
    try:
        app.baseline_var.set("自訂")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        state = app._door_layout_indicator_state_for_key("0:0")
        state.update(mode="indicator", enabled=True, box_enabled=False, layers=1,
                     groups=[1, 2, 2, 2, 2, 2], offset_x=0.0, offset_y=0.0)
        app.export_multi_door_layout_dxfs(str(tmp_path), app.get_float_values(), draw_stock=False)

        first = ezdxf.readfile(tmp_path / "door_c1_r1.dxf").modelspace()
        other = ezdxf.readfile(tmp_path / "door_c2_r1.dxf").modelspace()
        assert len(list(first.query('CIRCLE[layer=="CUTTING"]'))) > 0
        assert len(list(other.query('CIRCLE[layer=="CUTTING"]'))) == 0
    finally:
        root.destroy()


def test_single_door_hole_editor_receives_indicator_state_instead_of_door_page_controls(monkeypatch):
    root, app = make_app()
    try:
        captured = {}
        monkeypatch.setattr(app, "_open_unified_hole_editor", lambda *args, **kwargs: captured.update(kwargs))
        app.open_part_hole_editor("door")
        assert captured["door_indicator_state"]["enabled"] is app.is_door_indicator_var.get()
        assert "door_indicator_context" in captured
        # The old main-page indicator options remain hidden; editing belongs in the hole editor.
        assert not app.door_indicator_opts_frame.winfo_ismapped()
    finally:
        root.destroy()


def test_door_indicator_controls_are_inside_unified_hole_editor():
    root, app = make_app()
    try:
        app.open_part_hole_editor("door")
        root.update_idletasks()
        editor = app.last_unified_hole_editor

        texts = []
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except tk.TclError:
                    text = ""
                if text:
                    texts.append(str(text))
                walk(child)
        walk(editor)

        assert any("門指示燈" in text for text in texts)
        assert "直接指示燈" in texts
        assert "指示燈盒子" in texts
        assert not app.door_indicator_opts_frame.winfo_ismapped()
        editor.destroy()
    finally:
        root.destroy()


def test_door_page_top_only_shows_enable_multi_door_control():
    root, app = make_app()
    try:
        root.deiconify()
        app.notebook.select(app.tab_door)
        root.update()

        visible_checks = []
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Checkbutton) and child.winfo_ismapped():
                    visible_checks.append(child.cget("text"))
                walk(child)
        walk(app.tab_door)
        assert visible_checks == ["啟用多門配置"]
    finally:
        root.destroy()


def test_door_canvas_double_click_fallback_does_not_reopen_multi_door_editor(monkeypatch):
    root, app = make_app()
    try:
        calls = []
        monkeypatch.setattr(app, "open_part_hole_editor", lambda key: calls.append(key))
        app.multi_door_enabled_var.set(True)
        result = app.on_door_canvas_double_click(None)
        assert result == "break"
        assert calls == []

        app.multi_door_enabled_var.set(False)
        result = app.on_door_canvas_double_click(None)
        assert result == "break"
        assert calls == ["door"]
    finally:
        root.destroy()


def test_deleting_layout_column_or_row_keeps_remaining_feature_ownership_aligned():
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [400, 400]), (300, [1000])])
        # Auto remainder creates column 3. Attach sentinel objects to data ownership.
        f_left_bottom = object()
        f_right = object()
        app.door_layout_features["0:1"] = [f_left_bottom]
        app.door_layout_features["1:0"] = [f_right]
        app.door_layout_indicator_states["1:0"] = {"enabled": False, "sentinel": "right"}

        app.remove_door_layout_height(0, 0)
        assert app.door_layout_features["0:0"] == [f_left_bottom]

        app.remove_door_layout_column(0)
        assert app.door_layout_features["0:0"] == [f_right]
        assert app.door_layout_indicator_states["0:0"]["sentinel"] == "right"
    finally:
        root.destroy()



def test_real_double_click_in_cell_center_opens_editor_once(monkeypatch):
    """Regression: an unfilled Canvas rectangle only hits on its outline, so center double-click must be tested."""
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update()

        calls = []
        monkeypatch.setattr(app, "open_door_layout_cell_editor", lambda c, r: calls.append((c, r)))
        x1, y1, x2, y2 = app.door_layout_cell_bounds["0:0"]
        x = int((x1 + x2) / 2)
        y = int((y1 + y2) / 2)

        for _ in range(2):
            app.canvas_door.event_generate("<ButtonPress-1>", x=x, y=y)
            app.canvas_door.event_generate("<ButtonRelease-1>", x=x, y=y)
            root.update()

        assert calls == [(0, 0)]
    finally:
        root.destroy()


def test_layout_dimension_entries_match_editor_sized_inputs():
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.notebook.select(app.tab_door)
        root.update()
        app.draw_door(app.get_float_values())
        root.update()

        entries = list(app.door_layout_width_entries.values()) + list(app.door_layout_height_entries.values())
        assert entries
        for entry in entries:
            actual_font = tkfont.Font(root=root, font=entry.cget("font"))
            assert abs(int(actual_font.cget("size"))) >= 12
            assert int(entry.cget("width")) >= 8
    finally:
        root.destroy()


def test_multi_door_uses_manual_double_click_detection_not_tk_double_binding(monkeypatch):
    """Windows/Tk may not deliver <Double-Button-1> reliably; multi-door must count two Button-1 presses itself."""
    from types import SimpleNamespace

    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.notebook.select(app.tab_door)
        app.toggle_multi_door_layout()
        root.update()
        app.draw_door(app.get_float_values())
        root.update()

        # Multi-door must not depend on Tk's OS-specific Double event.
        assert app.canvas_door.bind("<Double-Button-1>") == ""

        calls = []
        monkeypatch.setattr(app, "open_door_layout_cell_editor", lambda c, r: calls.append((c, r)))
        x1, y1, x2, y2 = app.door_layout_cell_bounds["0:0"]
        x = int((x1 + x2) / 2)
        y = int((y1 + y2) / 2)

        app.on_door_canvas_press(SimpleNamespace(x=x, y=y, time=1000))
        assert calls == []
        app.on_door_canvas_press(SimpleNamespace(x=x, y=y, time=1250))
        assert calls == [(0, 0)]
    finally:
        root.destroy()


def test_multi_door_single_click_selection_does_not_recalculate_or_redraw(monkeypatch):
    """Single-click selection must stay lightweight so a second click can become a double-click."""
    root, app = make_app()
    try:
        root.deiconify()
        root.geometry("1200x900")
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])
        app.notebook.select(app.tab_door)
        app.toggle_multi_door_layout()
        root.update()
        app.draw_door(app.get_float_values())
        root.update()

        # Selection alone must never trigger full calculations or rebuild the Canvas/Entry widgets.
        monkeypatch.setattr(app, "update_calculations", lambda: (_ for _ in ()).throw(AssertionError("recalculated")))
        monkeypatch.setattr(app, "draw_door_layout_overview", lambda: (_ for _ in ()).throw(AssertionError("redrawn")))

        app.select_door_layout_cell(1, 0)

        assert app.door_layout_selected_var.get() == "1:0"
        selected_rect = app.door_layout_cell_items["1:0"]
        unselected_rect = app.door_layout_cell_items["0:0"]
        assert int(float(app.canvas_door.itemcget(selected_rect, "width"))) == 3
        assert int(float(app.canvas_door.itemcget(unselected_rect, "width"))) == 2
    finally:
        root.destroy()


def test_multi_door_editor_does_not_open_duplicate_window_when_clicks_are_queued(monkeypatch):
    """Rapid queued clicks must not create multiple Door editor windows."""
    root, app = make_app()
    created = []
    try:
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([
            (600, [600, 500, 700]),
            (500, [800, 1000]),
        ])

        def fake_open(*args, **kwargs):
            win = tk.Toplevel(root)
            app.last_unified_hole_editor = win
            created.append(win)

        monkeypatch.setattr(app, "_open_unified_hole_editor", fake_open)
        app.open_door_layout_cell_editor(0, 0)
        app.open_door_layout_cell_editor(0, 0)

        assert len(created) == 1
    finally:
        for win in created:
            if win.winfo_exists():
                win.destroy()
        root.destroy()


def test_indicator_box_and_small_door_are_same_level_workspace_parts():
    """Indicator components are first-level physical workspace parts, not notebook children."""
    root, app = make_app()
    try:
        app.is_indicator_box_var.set(True)
        app.on_indicator_box_toggle()
        existing = app._phase6_current_existing_parts()
        assert {"indicator_box", "indicator_door"} <= existing
        assert str(app.tab_indicator_box) not in app.notebook.tabs()
        assert str(app.tab_indicator_door) not in app.notebook.tabs()
    finally:
        root.destroy()


def test_single_door_indicator_box_toggle_does_not_change_multi_door_cell_modes():
    """Legacy single-door mode and per-cell multi-door modes are independent state domains."""
    root, app = make_app()
    try:
        app.is_door_indicator_var.set(True)
        app.door_layout_indicator_states[(0, 0)] = {
            "mode": "indicator", "enabled": True, "box_enabled": False,
            "layers": 1, "groups": [2] * 6,
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        }
        app.is_indicator_box_var.set(True)
        app.on_indicator_box_toggle()
        root.update()

        assert app.is_indicator_box_var.get() is True
        assert app.is_door_indicator_var.get() is False
        assert app.door_layout_indicator_states[(0, 0)]["mode"] == "indicator"
        assert {"indicator_box", "indicator_door"} <= app._phase6_current_existing_parts()
        assert str(app.tab_indicator_box) not in app.notebook.tabs()
        assert str(app.tab_indicator_door) not in app.notebook.tabs()
    finally:
        root.destroy()


def test_direct_door_indicator_removes_indicator_box_presence_from_saved_snapshot():
    root, app = make_app()
    try:
        app._apply_existing_parts_from_fold_workspace({
            "box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door"
        })
        assert app.workspace_controller.has_authoritative_workspace is True
        assert {"indicator_box", "indicator_door"} <= app._phase6_current_existing_parts()

        app.is_door_indicator_var.set(True)
        app.on_door_indicator_toggle()

        assert app.is_indicator_box_var.get() is False
        assert "indicator_box" not in app._phase6_current_existing_parts()
        assert "indicator_door" not in app._phase6_current_existing_parts()
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        assert "indicator_box" not in snapshot["existing_parts"]
        assert "indicator_door" not in snapshot["existing_parts"]
    finally:
        root.destroy()


def test_single_door_indicator_enable_removes_separate_indicator_box_presence():
    root, app = make_app()
    try:
        app._apply_existing_parts_from_fold_workspace({
            "box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door"
        })
        app.is_door_indicator_var.set(True)
        app.on_door_indicator_toggle()
        root.update()

        assert app.is_door_indicator_var.get() is True
        assert app.is_indicator_box_var.get() is False
        existing = app._phase6_current_existing_parts()
        assert "indicator_box" not in existing
        assert "indicator_door" not in existing
    finally:
        root.destroy()


def test_multi_door_editor_indicator_commit_does_not_toggle_single_door_global_mode(monkeypatch):
    root, app = make_app()
    captured = {}
    try:
        app.w_var.set("1100")
        app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app.is_indicator_box_var.set(True)
        app.on_indicator_box_toggle()

        def fake_open(*args, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(app, "_open_unified_hole_editor", fake_open)
        app.open_door_layout_cell_editor(0, 0)
        commit = captured["door_indicator_commit"]
        commit({
            "mode": "indicator", "layers": 1, "groups": [2] * 6,
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })

        assert app.is_indicator_box_var.get() is True
        assert app._door_layout_indicator_state_for_key("0:0")["mode"] == "indicator"
        assert {"indicator_box", "indicator_door"} <= app._phase6_current_existing_parts()
        assert str(app.tab_indicator_box) not in app.notebook.tabs()
    finally:
        root.destroy()


def test_multi_door_cells_own_mutually_exclusive_indicator_modes_independently():
    root, app = make_app()
    try:
        app._apply_multi_door_indicator_state("0:0", {
            "mode": "indicator_box", "layers": 1, "groups": [2]*6,
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })
        app._apply_multi_door_indicator_state("1:0", {
            "mode": "indicator", "layers": 1, "groups": [1,2,2,2,2,2],
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })
        left = app._door_layout_indicator_state_for_key("0:0")
        right = app._door_layout_indicator_state_for_key("1:0")
        assert left["mode"] == "indicator_box"
        assert left["enabled"] is False
        assert left["box_enabled"] is True
        assert right["mode"] == "indicator"
        assert right["enabled"] is True
        assert right["box_enabled"] is False
        # Per-cell mode must not toggle the legacy single-door global mode.
        assert app.is_indicator_box_var.get() is False
    finally:
        root.destroy()


def test_door_hole_editor_offers_none_direct_indicator_and_indicator_box_modes():
    root, app = make_app()
    try:
        app.open_part_hole_editor("door")
        root.update_idletasks()
        editor = app.last_unified_hole_editor
        texts = []
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except tk.TclError:
                    text = ""
                if text:
                    texts.append(str(text))
                walk(child)
        walk(editor)
        assert "不使用" in texts
        assert "直接指示燈" in texts
        assert "指示燈盒子" in texts
        editor.destroy()
    finally:
        root.destroy()


def test_indicator_box_mode_draws_centered_opening_only_on_own_multi_door_cell():
    from ae_engine.sheetmetal_features import ResolvedRect
    root, app = make_app()
    try:
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        cells = app.get_door_layout_cells()
        first = cells[0]
        first_key = app._door_layout_cell_key(first)
        app._apply_multi_door_indicator_state(first_key, {
            "mode": "indicator_box", "layers": 1, "groups": [1,2,2,2,2,2],
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })
        first_result = app._door_layout_cell_result(first)
        first_features = app._door_layout_cell_resolved_features(first, first_result, first_key)
        other = cells[-1]
        other_result = app._door_layout_cell_result(other)
        other_features = app._door_layout_cell_resolved_features(other, other_result, app._door_layout_cell_key(other))
        openings = [f for f in first_features if isinstance(f, ResolvedRect) and f.source_type == "indicator_box_opening"]
        assert len(openings) == 1
        assert (openings[0].width, openings[0].height) == (226.0, 345.0)
        assert not [f for f in other_features if getattr(f, "source_type", None) == "indicator_box_opening"]
    finally:
        root.destroy()


def test_box_distance_checkbox_draws_enclosure_reference_frame_in_door_editor():
    root, app = make_app()
    try:
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app.open_door_layout_cell_editor(0, 0)  # missing right and bottom frame edges
        root.update_idletasks()
        editor = app.last_unified_hole_editor
        checkbox = None
        def walk(widget):
            nonlocal checkbox
            for child in widget.winfo_children():
                if isinstance(child, tk.Checkbutton) and child.cget("text") == "箱體定位距離":
                    checkbox = child
                walk(child)
        walk(editor)
        assert checkbox is not None
        checkbox.invoke()
        root.update_idletasks()
        assert hasattr(app, "last_hole_editor_canvas")
        assert app.last_hole_editor_canvas.find_withtag("door_enclosure_reference")
        editor.destroy()
    finally:
        root.destroy()


def test_hole_editor_insert_button_stays_visible_at_minimum_window_height():
    root, app = make_app()
    try:
        root.deiconify(); root.geometry("900x700+0+0"); root.update()
        app.open_part_hole_editor("door")
        editor = app.last_unified_hole_editor
        editor.geometry("760x560+20+20")
        root.update()
        insert = None
        def walk(widget):
            nonlocal insert
            for child in widget.winfo_children():
                try:
                    if child.cget("text") == "插入":
                        insert = child
                except tk.TclError:
                    pass
                walk(child)
        walk(editor)
        assert insert is not None
        assert insert.winfo_ismapped() == 1
        assert insert.winfo_rooty() + insert.winfo_height() <= editor.winfo_rooty() + editor.winfo_height()
        editor.destroy()
    finally:
        root.destroy()


def test_coordinate_reference_confirm_button_is_on_the_right_of_cancel():
    root, app = make_app()
    try:
        app.open_part_hole_editor("door")
        editor = app.last_unified_hole_editor
        buttons = {}
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Button):
                    try:
                        text = child.cget("text")
                    except tk.TclError:
                        text = ""
                    if text in {"確定", "取消"} and child.winfo_manager() == "grid":
                        buttons[text] = child
                walk(child)
        walk(editor)
        assert buttons["確定"].grid_info()["column"] > buttons["取消"].grid_info()["column"]
        editor.destroy()
    finally:
        root.destroy()


def test_multi_door_indicator_box_mode_passes_own_centered_cutout_to_door_export(monkeypatch, tmp_path):
    root, app = make_app()
    captured = {}
    try:
        app.baseline_var.set("自訂")
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app._apply_multi_door_indicator_state("0:0", {
            "mode": "indicator_box", "layers": 1, "groups": [1,2,2,2,2,2],
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })
        def fake_export(spec, filepath, context):
            captured[str(filepath)] = spec
        monkeypatch.setattr(app, "_export_authoritative_part", fake_export)
        app.export_multi_door_layout_dxfs(str(tmp_path), app.get_float_values(), draw_stock=False)
        first = captured[str(tmp_path / "door_c1_r1.dxf")]
        other = captured[str(tmp_path / "door_c2_r1.dxf")]
        assert first.indicator_hole == (226.0, 345.0)
        assert first.door_indicator is None
        assert other.indicator_hole is None
    finally:
        root.destroy()


def test_multi_door_indicator_box_parts_export_once_per_box_mode_cell(monkeypatch, tmp_path):
    root, app = make_app()
    calls = {"box": [], "door": []}
    try:
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app._apply_multi_door_indicator_state("0:0", {
            "mode": "indicator_box", "layers": 1, "groups": [1,2,2,2,2,2],
            "offset_x": 0, "offset_y": 0, "is_box_dist": False,
        })
        app._apply_multi_door_indicator_state("1:1", {
            "mode": "indicator_box", "layers": 2, "groups": [2,3,2,2,2,2],
            "offset_x": 0, "offset_y": 0, "is_box_dist": False,
        })
        from ae_engine.contracts import DoorPartSpec, IndicatorBoxPartSpec
        def fake_export(spec, filepath, context):
            if isinstance(spec, IndicatorBoxPartSpec):
                calls["box"].append((filepath, spec.layer_groups))
            elif isinstance(spec, DoorPartSpec):
                calls["door"].append((filepath, spec))
            else:
                raise AssertionError(type(spec))
        monkeypatch.setattr(app, "_export_authoritative_part", fake_export)
        val = app.get_float_values()
        box_names = app.export_multi_door_indicator_box_parts(str(tmp_path), val, draw_stock=False, export_box=True, export_door=True)
        assert box_names == [
            "indicator_box_c1_r1.dxf", "indicator_door_c1_r1.dxf",
            "indicator_box_c2_r2.dxf", "indicator_door_c2_r2.dxf",
        ]
        assert [groups for _fp, groups in calls["box"]] == [(1,), (2, 3)]
        assert len(calls["door"]) == 2
        assert all(spec.model_name is None for _fp, spec in calls["door"])
    finally:
        root.destroy()


def test_indicator_box_and_small_door_are_shared_workspace_parts_and_still_in_door_editor():
    root, app = make_app()
    try:
        app.is_indicator_box_var.set(True)
        app.on_indicator_box_toggle()
        assert {"indicator_box", "indicator_door"} <= app._phase6_current_existing_parts()

        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app._apply_multi_door_indicator_state("0:0", {
            "mode": "indicator_box", "layers": 1, "groups": [2,2,2,2,2,2],
            "offset_x": 0, "offset_y": 0, "is_box_dist": False,
        })
        app.open_door_layout_cell_editor(0, 0)
        editor = app.last_unified_hole_editor
        texts = []
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except tk.TclError:
                    text = ""
                if text:
                    texts.append(text)
                walk(child)
        walk(editor)
        assert "指示燈盒子" in texts
        assert "編輯盒子" not in texts
        assert "編輯小門" not in texts
        editor.destroy()
    finally:
        root.destroy()


def test_multi_door_export_uses_selected_door_baseline_when_available(monkeypatch, tmp_path):
    root, app = make_app()
    captured = []
    try:
        app.baseline_var.set("金庫型")
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        monkeypatch.setattr(app, "_export_authoritative_part", lambda spec, fp, ctx: captured.append((fp, spec)))
        app.export_multi_door_layout_dxfs(str(tmp_path), app.get_float_values(), draw_stock=False)
        assert len(captured) == 5
        assert all(spec.model_name == "金庫型" for _fp, spec in captured)
        assert all(spec.frame_edges is not None for _fp, spec in captured)
    finally:
        root.destroy()


def test_multi_door_editor_shows_explicit_baseline_source_status(monkeypatch):
    root, app = make_app()
    try:
        app.baseline_var.set("金庫型")
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        monkeypatch.setattr(gui.ae, "has_baseline_part", lambda model, filename: True)
        monkeypatch.setattr(gui.ae, "baseline_source_label", lambda model, filename: "基準檔：金庫型/門.dxf")
        app.open_door_layout_cell_editor(0, 0)
        editor = app.last_unified_hole_editor
        labels = []
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton)):
                    try: labels.append(child.cget("text"))
                    except tk.TclError: pass
                walk(child)
        walk(editor)
        assert "基準檔：金庫型/門.dxf" in labels
        editor.destroy()
    finally:
        root.destroy()


def test_component_feature_ownership_reindexes_with_deleted_column():
    root, app = make_app()
    try:
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [1800]), (500, [1800])])
        app.door_layout_columns[0]["width_auto"] = False
        app.door_layout_indicator_box_features["1:0"] = ["BOX_FEATURE"]
        app.door_layout_indicator_door_features["1:0"] = ["DOOR_FEATURE"]
        app.remove_door_layout_column(0)
        assert app.door_layout_indicator_box_features == {"0:0": ["BOX_FEATURE"]}
        assert app.door_layout_indicator_door_features == {"0:0": ["DOOR_FEATURE"]}
    finally:
        root.destroy()


def test_multi_door_indicator_component_exports_use_each_cells_own_features(monkeypatch, tmp_path):
    root, app = make_app()
    calls = {"box": [], "door": []}
    try:
        app.w_var.set("1100"); app.h_var.set("1800")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(600, [600, 500, 700]), (500, [800, 1000])])
        app._apply_multi_door_indicator_state("0:0", {
            "mode": "indicator_box", "layers": 1, "groups": [2,2,2,2,2,2],
            "offset_x": 0, "offset_y": 0, "is_box_dist": False,
        })
        box_feature = object(); door_feature = object()
        app.door_layout_indicator_box_features["0:0"] = [box_feature]
        app.door_layout_indicator_door_features["0:0"] = [door_feature]
        from ae_engine.contracts import DoorPartSpec, IndicatorBoxPartSpec
        def fake_export(spec, filepath, context):
            if isinstance(spec, IndicatorBoxPartSpec):
                calls["box"].append(list(spec.features))
            elif isinstance(spec, DoorPartSpec):
                calls["door"].append(list(spec.features))
        monkeypatch.setattr(app, "_export_authoritative_part", fake_export)
        app.export_multi_door_indicator_box_parts(str(tmp_path), app.get_float_values(), export_box=True, export_door=True)
        assert calls["box"] == [[box_feature]]
        assert calls["door"] == [[door_feature]]
    finally:
        root.destroy()


def test_multi_door_width_commit_rejects_value_that_exceeds_total_w(monkeypatch):
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [1000])])
        warnings = []
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda title, text: warnings.append((title, text)))

        app.door_layout_columns[0]["width_var"].set("1100")
        assert app.commit_door_layout_width(0) is False
        assert app.door_layout_columns[0]["width_var"].get() == "400"
        assert warnings and "W" in warnings[-1][1]
        assert app.get_door_layout_columns() == [(400.0, [1000.0]), (600.0, [1000.0])]
    finally:
        root.destroy()


def test_multi_door_width_commit_rejects_fixed_sum_over_total_w(monkeypatch):
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [1000])])
        app.door_layout_columns[1]["width_var"].set("700")
        warnings = []
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda title, text: warnings.append((title, text)))

        assert app.commit_door_layout_width(1) is False
        assert app.door_layout_columns[1]["width_var"].get() == "600"
        assert warnings and "1000" in warnings[-1][1]
    finally:
        root.destroy()


def test_multi_door_height_commit_rejects_value_or_stack_over_total_h(monkeypatch):
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(1000, [400])])
        warnings = []
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda title, text: warnings.append((title, text)))

        app.door_layout_columns[0]["height_vars"][0].set("1100")
        assert app.commit_door_layout_height(0, 0) is False
        assert app.door_layout_columns[0]["height_vars"][0].get() == "400"

        app.door_layout_columns[0]["height_vars"][1].set("700")
        assert app.commit_door_layout_height(0, 1) is False
        assert app.door_layout_columns[0]["height_vars"][1].get() == "600"
        assert warnings and "H" in warnings[-1][1]
    finally:
        root.destroy()


def test_multi_door_commit_rejects_non_numeric_and_non_positive_values(monkeypatch):
    root, app = make_app()
    try:
        app.w_var.set("1000")
        app.h_var.set("1000")
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(400, [400])])
        warnings = []
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda title, text: warnings.append((title, text)))

        app.door_layout_columns[0]["width_var"].set("abc")
        assert app.commit_door_layout_width(0) is False
        assert app.door_layout_columns[0]["width_var"].get() == "400"

        app.door_layout_columns[0]["height_vars"][0].set("0")
        assert app.commit_door_layout_height(0, 0) is False
        assert app.door_layout_columns[0]["height_vars"][0].get() == "400"
        assert len(warnings) == 2
    finally:
        root.destroy()
