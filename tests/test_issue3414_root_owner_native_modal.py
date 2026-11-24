"""Existing shared native modal with owner/mark atomic recovery, no release."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.operator_manual_marking import is_manual_round_mark
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3415_primary_marking_menu_roundtrip import LEFT, _actual_editor_confirm

FIXTURE = Path(__file__).parent / "fixtures/issue1503_legacy_receiving_without_nfb_base.p6fold"
KEY = api.ROOT_MARKING_STORE_KEY
OWNER_KEY = api.ROOT_PHYSICAL_OCCUPANCY_KEY


def test_established_ordinary_left_cursor_first_confirm_and_replacement_isolated(tmp_path, monkeypatch):
    from gui import Phase6PrimaryApplication

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu
        key = "base_plate"

        def current():
            return {**app._phase6_input_snapshot, **app.designer_workspace.snapshot()}

        def open_path(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            menu.invoke(0)
            root.update()
            assert host.project_controller.project_path == str(path)

        def save_path(name):
            path = tmp_path / f"{name}.p6fold"
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
            menu.invoke(2)
            root.update()
            return path, read_project(path)["snapshot"]

        def edit():
            app.activate_part(key)
            root.update()
            editor = host.open_part_hole_editor(key)
            root.update()
            assert editor is not None
            callback = editor._manual_marking_place
            state = dict(zip(callback.__code__.co_freevars, (c.cell_contents for c in callback.__closure__)))["s"]
            assert set(state.manual_marking_draft.allowed_tools) == {"line","circle","cross","l","pair_l","quad_l"}
            assert hasattr(editor, "_manual_round_marking_controls")
            return editor, state

        def click(editor, state, length, x_shift=0):
            state.manual_mark_length.set(str(length))
            state.manual_mark_angle.set("37")
            x, y = state.canvas_view.transform.world_to_canvas(
                Vec2(state.live_context.width / 2 + x_shift, state.live_context.height / 2),
            )
            editor._manual_marking_controls[0].invoke()
            canvas = host.last_hole_editor_canvas
            canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            root.update()
            assert any(api.is_manual_mark(f) for f in state.live_context.feature_list)
            return tuple(state.live_context.feature_list)

        open_path(FIXTURE)
        panel = app.settings_panel
        panel.invalidate_context(key)
        state = panel.render_context(key)["extension_state"]
        for k, v in LEFT.items():
            state["receiving_base_plate_vars"][k].set(str(v))
        state["receiving_base_plate_apply_button"].invoke()
        root.update()
        assert key not in app.designer_workspace.available_parts
        app.add_part(key)
        root.update()
        _, established = save_path("old-stock")
        # Represent the same real authored LEFT project immediately before the
        # ownership schema existed; no stock, folds, placement or holes altered.
        established.pop(OWNER_KEY, None)
        if isinstance(established.get("workspace"), dict):
            established["workspace"].pop(OWNER_KEY, None)
        legacy = write_project(tmp_path / "legacy-left.p6fold", {"schema": PROJECT_SCHEMA, "snapshot": established})
        open_path(legacy)

        editor, state = edit()
        assert not api.resolve_workspace_physical_root_owner(current(), key)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        assert not current().get(KEY) and not api.resolve_workspace_physical_root_owner(current(), key)

        editor, state = edit()
        click(editor, state, 9)
        state.cancel_all_btn.invoke()
        root.update()
        assert not editor.winfo_exists()
        assert not current().get(KEY) and not api.resolve_workspace_physical_root_owner(current(), key)

        editor, state = edit()
        chosen = click(editor, state, 12)
        assert not current().get(KEY) and not api.resolve_workspace_physical_root_owner(current(), key)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        owner = api.resolve_workspace_physical_root_owner(current(), key)
        assert owner and api.read_workspace_marking_owner_record(current(), owner)["features"] == chosen
        assert not any(api.is_manual_mark(f) for f in app.designer_workspace.features_for(key))

        marked_file, marked = save_path("confirmed")
        assert marked[KEY]["records"][owner]["features"] == chosen
        open_path(marked_file)
        import ezdxf
        from ae_engine.manufacturing_export import resolved_physical_render_parts

        def read_export_source():
            return current(), app._phase6_resolve_manufacturing_geometry()

        normal = dict(resolved_physical_render_parts(read_export_source()[1]))[key]
        baseline_path = tmp_path / "approved-unmarked.dxf"
        marked_dxf = tmp_path / "confirmed-owner-only.dxf"
        api.save_part_render_data_dxf(normal, baseline_path, verify_reopen=True)
        from gui_modules.project.export_actions import export_selected_dxf
        from gui_modules.editors.hole_editor import messagebox
        output_dir = tmp_path / "operator-normal-DXF"
        output_dir.mkdir()
        failures = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: failures.append((title, text)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
        for k in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{k}_var").set(k == "base_plate")
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(output_dir))
        export_selected_dxf(host)
        assert not failures, failures
        marked_dxf, = output_dir.glob("*.dxf")
        original_dxf, selected_dxf = map(ezdxf.readfile, (baseline_path, marked_dxf))
        assert original_dxf.header["$INSUNITS"] == selected_dxf.header["$INSUNITS"] == 4

        def cut_and_bend(doc):
            facts = []
            for entity in doc.modelspace():
                if entity.dxf.layer not in {"CUTTING", "BEND"}:
                    continue
                values = {k: v for k, v in entity.dxfattribs().items() if k not in {"owner", "handle"}}
                if entity.dxftype() == "LWPOLYLINE":
                    values["vertices"] = tuple(tuple(point) for point in entity.get_points("xyseb"))
                facts.append((entity.dxftype(), values))
            return facts

        assert cut_and_bend(original_dxf) == cut_and_bend(selected_dxf)
        ink, = tuple(row for row in selected_dxf.modelspace() if row.dxf.layer == "MARKING")
        assert ink.dxftype() == "LWPOLYLINE"
        assert tuple(tuple(point) for point in ink.get_points("xy")) == tuple((p.x, p.y) for p in chosen[0].points)
        previous_bytes = marked_dxf.read_bytes()
        editor, state = edit()
        assert tuple(state.live_context.feature_list) == chosen
        round_button, diameter = editor._manual_round_marking_controls
        diameter.set("8")
        round_button.invoke()
        x, y = state.canvas_view.transform.world_to_canvas(
            Vec2(state.live_context.width / 2 + 30, state.live_context.height / 2),
        )
        host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        edited = tuple(state.live_context.feature_list)
        assert len(edited) == 2 and any(is_manual_round_mark(f) for f in edited)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        assert api.read_workspace_marking_owner_record(current(), owner)["features"] == edited
        editor, state = edit()
        state.manual_group_tools["l"].invoke()
        x, y = state.canvas_view.transform.world_to_canvas(
            Vec2(state.live_context.width / 2 + 80, state.live_context.height / 2),
        )
        host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        grouped = tuple(state.live_context.feature_list)
        assert len(grouped) == 3 and any(api.is_manual_group(row) for row in grouped)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        _, copy_snapshot = save_path("owned-saved-group")
        from ae_engine.operator_manual_marking_copy import _saved_source_features
        assert _saved_source_features(copy_snapshot) == grouped
        editor, state = edit()
        state.selected_catalog_text.set("＋ 自訂圓孔")
        state.var_d.set("6")
        state.var_blind.set(False)
        state.insert_btn.invoke()
        x, y = state.canvas_view.transform.world_to_canvas(
            Vec2(state.live_context.width / 2 - 55, state.live_context.height / 2),
        )
        host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        assert len(state.live_context.feature_list) == 4
        with_hole = click(editor, state, 11, x_shift=-25)
        assert len(with_hole) == 5
        retained = tuple(row for row in with_hole if api.is_manual_mark(row))
        hole, = tuple(row for row in with_hole if not api.is_manual_mark(row))
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        mixed_path, mixed = save_path("same-confirm-hole-and-mark")
        assert mixed[KEY]["records"][owner]["features"] == retained
        assert tuple(mixed["part_features"][key]) == (hole,)
        open_path(mixed_path)
        editor, state = edit()
        assert len(state.live_context.feature_list) == 5
        abandoned = click(editor, state, 8, x_shift=-30)
        assert len(abandoned) == 6

        assert app.remove_part(key)
        app.add_part(key)
        root.update()
        replaced = api.resolve_workspace_physical_root_owner(current(), key)
        assert replaced and replaced != owner
        errors = []
        from gui_modules.editors.hole_editor import messagebox
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: errors.append(text))
        _actual_editor_confirm(editor)
        root.update()
        assert errors == ["ROOT_MARKING_OWNER_STALE"]
        assert editor.winfo_exists()
        state.cancel_all_btn.invoke()
        root.update()
        editor, state = edit()
        assert tuple(state.live_context.feature_list) == (hole,)
        assert api.read_workspace_marking_owner_record(current(), owner)["features"] == retained
        with pytest.raises(ValueError, match="PERSISTED_RECORD_REQUIRED"):
            api.save_confirmed_workspace_owner_marking_dxf(
                key, marked_dxf, read_current=read_export_source, overwrite=True,
            )
        assert marked_dxf.read_bytes() == previous_bytes
        state.cancel_all_btn.invoke()
        root.update()

    finally:
        root.destroy()


@pytest.mark.parametrize(("key", "full_tools"), (("head", False), ("tail", False),
                                                   ("head", True), ("tail", True)))
def test_same_existing_editor_and_export_ordinary_signed_endcap(tmp_path, monkeypatch, key, full_tools):
    import ezdxf
    from gui import Phase6PrimaryApplication
    from gui_modules.editors.hole_editor import messagebox
    from gui_modules.project.export_actions import export_selected_dxf
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
    from tests.test_issue3414_scoped_marking_proto import _real_source, _resize, _raw_write

    source = _resize(_real_source(), 1)
    source["existing_parts"] = ["box_body", "base_plate", key]
    original = _raw_write(tmp_path / f"genuine-{key}.p6fold", source)
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        failures = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: failures.append((title, text)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
        menu = app.project_file_menu
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(original))
        menu.invoke(0)
        root.update()
        app.activate_part(key)
        root.update()
        assert not api.resolve_workspace_physical_root_owner(current_workspace_marking_source(app), key)
        reference = tmp_path / "original-unmarked-export"
        reference.mkdir()
        for k in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{k}_var").set(k == key)
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(reference))
        export_selected_dxf(host)
        assert not failures, failures
        unmarked, = reference.glob("*.dxf")
        editor = host.open_part_hole_editor(key)
        root.update()
        assert editor is not None and hasattr(editor, "_manual_marking_controls"), failures
        callback = editor._manual_marking_place
        state = dict(zip(callback.__code__.co_freevars, (c.cell_contents for c in callback.__closure__)))["s"]
        assert set(state.manual_marking_draft.allowed_tools) == {"line", "circle", "cross", "l", "pair_l", "quad_l"}
        assert state.manual_marking_draft.output_capability == "verified_normal"
        original_bytes = unmarked.read_bytes()
        from ae_engine.sheetmetal_drawing import CirclePrimitive
        hole = next((row for row in state.manual_marking_draft.context.render_data.scene.primitives
                     if isinstance(row, CirclePrimitive) and row.layer == "CUTTING"), None)
        if key == "head":
            assert hole is not None
        if hole is not None:
            hx, hy = state.canvas_view.transform.world_to_canvas(hole.center)
            state.manual_mark_length.set("2")
            editor._manual_marking_controls[0].invoke()
            host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(hx), y=round(hy))
            assert "打標位置不合法" in editor._manual_marking_controls[2].cget("text")
            assert not any(api.is_manual_mark(f) for f in state.live_context.feature_list)
            assert not current_workspace_marking_source(app).get(KEY)
            assert not api.resolve_workspace_physical_root_owner(current_workspace_marking_source(app), key)
            assert unmarked.read_bytes() == original_bytes
            editor._manual_marking_controls[1].invoke()

        p = state.manual_marking_draft.context.render_data.material.representative_point()
        x, y = state.canvas_view.transform.world_to_canvas(Vec2(p.x, p.y))
        state.manual_mark_length.set("8")
        state.manual_mark_angle.set("37")
        editor._manual_marking_controls[0].invoke()
        host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        mark, = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        authored = (mark,)
        if full_tools:
            def canvas_click(point):
                cx, cy = state.canvas_view.transform.world_to_canvas(point)
                host.last_hole_editor_canvas.event_generate("<Button-1>", x=round(cx), y=round(cy))
                root.update()

            button, diameter = editor._manual_round_marking_controls
            diameter.set("8")
            if hole is not None:
                button.invoke()
                canvas_click(Vec2(hole.center.x + 4, hole.center.y))
                assert "打標位置不合法" in editor._manual_marking_controls[2].cget("text")
                assert tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f)) == authored
                editor._manual_marking_controls[1].invoke()
            button.invoke()
            canvas_click(Vec2(p.x + 24, p.y))
            radius_mark, = tuple(f for f in state.live_context.feature_list if is_manual_round_mark(f))
            state.manual_mark_pattern.set("dashed")
            state.manual_mark_length.set("28")
            editor._manual_marking_controls[0].invoke()
            canvas_click(Vec2(p.x - 34, p.y))
            state.manual_group_arm_x.set("7")
            state.manual_group_arm_y.set("8")
            state.manual_group_tools["l"].invoke()
            canvas_click(Vec2(p.x + 44, p.y + 15))
            authored = tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
            assert len(authored) == 4 and api.is_manual_group(authored[-1])
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists() and not failures, failures
        save = tmp_path / "same-owner-mark.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(save))
        menu.invoke(2)
        root.update()
        saved = read_project(save)["snapshot"]
        owner = api.resolve_workspace_physical_root_owner(saved, key)
        assert owner and api.read_workspace_marking_owner_record(saved, owner)["features"] == authored

        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(save))
        menu.invoke(0)
        root.update()
        app.activate_part(key)
        root.update()
        for k in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{k}_var").set(k == key)
        out = tmp_path / "operator-export"
        out.mkdir()
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
        export_selected_dxf(host)
        assert not failures, failures
        target, = out.glob("*.dxf")
        doc = ezdxf.readfile(target)
        inks = tuple(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
        assert tuple(map(tuple, inks[0].get_points("xy"))) == tuple((p.x, p.y) for p in mark.points)
        if full_tools:
            circle, = tuple(doc.modelspace().query('CIRCLE[layer=="MARKING"]'))
            assert (circle.dxf.center.x, circle.dxf.center.y) == (radius_mark.offset.x, radius_mark.offset.y)
            assert circle.dxf.radius * 2 == radius_mark.diameter
            assert len(inks) > 3
        else:
            assert len(inks) == 1
        assert doc.header["$INSUNITS"] == 4
        assert doc.layers.get("MARKING").dxf.color == 211

        def physical_rows(drawing):
            rows = []
            for entity in drawing.modelspace():
                if entity.dxf.layer not in {"CUTTING", "BEND"}:
                    continue
                record = {field: value for field, value in entity.dxfattribs().items()
                          if field not in {"handle", "owner"}}
                if entity.dxftype() == "LWPOLYLINE":
                    record["xyseb"] = tuple(map(tuple, entity.get_points("xyseb")))
                rows.append((entity.dxftype(), record))
            return rows

        assert physical_rows(doc) == physical_rows(ezdxf.readfile(unmarked))

        if full_tools:
            import fold_designer_bridge as bridge
            current = current_workspace_marking_source(app)
            original_geometry = app._phase6_resolve_manufacturing_geometry()
            stock = original_geometry.part(key).render_data
            ink = api.read_verified_owner_marking_candidate(current, original_geometry, key).ink
            assert len(ink) == len(inks) + 1
            exported_bytes = target.read_bytes()
            bridge._phase6_show_corner_data(app)
            bridge._phase6_select_corner_data_part(app, key)
            root.update()
            projected = bridge._phase6_corner_data_unfold_projection_for_key(app, key).render_data
            assert tuple(projected.scene.primitives) == (*stock.scene.primitives, *ink)
            assert projected.material is stock.material
            assert projected.fold_guides == stock.fold_guides
            failed_direct = tmp_path / "display-cannot-publish.dxf"
            with pytest.raises(ValueError, match="OWNER_MARKING_DISPLAY_ONLY_NOT_FOR_DXF"):
                api.save_part_render_data_dxf(projected, failed_direct, verify_reopen=True)
            assert not failed_direct.exists()
            assert len(app.corner_data_canvas.find_all()) > len(stock.scene.primitives)
            assert any(app.corner_data_canvas.type(item) == "oval"
                       and app.corner_data_canvas.itemcget(item, "outline") == "#8e8e93"
                       for item in app.corner_data_canvas.find_all())
            assert target.read_bytes() == exported_bytes
            assert original_geometry.part(key).render_data is stock
            assert not any(is_manual_round_mark(p) for p in stock.scene.primitives)

        if key == "head":
            import os
            # Same Project bytes and same physical owner, but a different
            # operator Open must still retire the earlier export transaction.
            other = tmp_path / "another-project.p6fold"
            other.write_bytes(save.read_bytes())
            controller = host.project_controller
            epoch = controller.project_load_epoch
            workspace = app.designer_workspace
            existing_bytes = target.read_bytes()
            real_replace = os.replace
            switched = []

            def open_other_after_publish(source, destination):
                result = real_replace(source, destination)
                if (not switched and str(destination) == str(target)
                        and ".whd-export-stage-" in str(source)):
                    switched.append(True)
                    host.load_phase6_project(other, open_designer=True)
                    root.update()
                    app.activate_part(key)
                    root.update()
                return result

            with monkeypatch.context() as concurrent:
                concurrent.setattr(os, "replace", open_other_after_publish)
                concurrent.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
                export_selected_dxf(host)
            assert switched and controller.project_load_epoch == epoch + 1
            assert controller.project_path == str(other)
            assert host.fold_designer_app is app and app.designer_workspace is workspace
            assert failures and "DXF 出圖專案已切換" in failures[-1][1]
            assert target.read_bytes() == existing_bytes
            assert list(out.iterdir()) == [target]
            failures.clear()

        assert app.remove_part(key)
        app.add_part(key)
        root.update()
        replacement = tmp_path / "replacement-not-old-mark.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(replacement))
        menu.invoke(2)
        root.update()
        replaced = read_project(replacement)["snapshot"]
        new_owner = api.resolve_workspace_physical_root_owner(replaced, key)
        assert new_owner and new_owner != owner
        assert api.read_workspace_marking_owner_record(replaced, owner)["features"] == authored
        assert api.read_workspace_marking_owner_record(replaced, new_owner) is None
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(replacement))
        menu.invoke(0)
        root.update()
        app.activate_part(key)
        root.update()
        blank_editor = host.open_part_hole_editor(key)
        root.update()
        assert blank_editor is not None and hasattr(blank_editor, "_manual_marking_controls"), failures
        cb = blank_editor._manual_marking_place
        blank = dict(zip(cb.__code__.co_freevars, (cell.cell_contents for cell in cb.__closure__)))["s"]
        assert not any(api.is_manual_mark(f) for f in blank.live_context.feature_list)
        blank.cancel_all_btn.invoke()
        root.update()
        if full_tools:
            replacement_projection = bridge._phase6_corner_data_unfold_projection_for_key(app, key).render_data
            assert not any(is_manual_round_mark(p) or getattr(p, "semantic_id", None) == "WHD_MANUAL_MARKING_V1"
                           for p in replacement_projection.scene.primitives)
        plain = tmp_path / "replacement-normal-export"
        plain.mkdir()
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(plain))
        export_selected_dxf(host)
        assert not failures, failures
        plain_dxf, = plain.glob("*.dxf")
        assert not ezdxf.readfile(plain_dxf).modelspace().query('LWPOLYLINE[layer=="MARKING"]')
    finally:
        root.destroy()
