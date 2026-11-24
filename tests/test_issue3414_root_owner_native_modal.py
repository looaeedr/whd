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
        group_path, copy_snapshot = save_path("owned-saved-group")
        from ae_engine.operator_manual_marking_copy import _saved_source_features
        assert _saved_source_features(copy_snapshot) == grouped

        import fold_designer_bridge as bridge
        import phase6_final_scene_renderer as drawing
        from dataclasses import replace
        original_mesh_collection = drawing.gridless_mesh_collection
        installed = {}

        def track_installed(triangles, *args, **kwargs):
            artist = original_mesh_collection(triangles, *args, **kwargs)
            installed[id(artist)] = tuple(triangles)
            return artist

        def amber():
            return tuple(tuple(zip(*line.get_data_3d())) for line in app.renderer.ax3d.lines
                         if line.get_color() == "#f59e0b")

        monkeypatch.setattr(drawing, "gridless_mesh_collection", track_installed)
        bridge._phase6_show_assembly(app)
        root.update()
        request = bridge._phase6_final_scene_view_request(app)
        view, = dict(request.render_data.owner_marking_views).values()
        part = next(p for p in request.render_data.assembly_parts if p.part_key == key)
        assert part.offset == (0.0, 0.0, -165.5)
        assert view.material is part.render_data.material
        drawn, = (installed[id(artist)] for artist, part_key in app.final_scene_view._hole_pick_artists
                  if part_key == key)
        local = drawing._phase6_folded_mesh_from_polygon(
            part.render_data.material, part.x_profile, part.y_profile,
            fold_guides=part.render_data.fold_guides,
        )
        projected, warning = api.project_checked_owner_marking_assembly_paths(
            part, view, local, drawn, request.finished_dimensions,
        )
        assert warning is None and len(projected) == 4
        first, second, third = drawn[0]
        drift = ((first[0]+0.01, first[1], first[2]), second, third)
        assert api.project_checked_owner_marking_assembly_paths(
            part, view, local, (drift, *drawn[1:]), request.finished_dimensions,
        ) == ((), "OWNER_MARKING_ASSEMBLY_SURFACE_UNPROVED")
        assert any(len(path) == 65 and path[0] == path[-1] for _, path in projected)
        shown = amber()
        installed_mesh = tuple(app.final_scene_view.last_cutting_mesh)
        view_control = app.show_operator_marking_3d_check
        assert view_control.winfo_manager() == "grid"
        assert app.show_operator_marking_3d_var.get() is True
        view_control.invoke()
        root.update()
        assert app.show_operator_marking_3d_var.get() is False
        assert not bridge._phase6_final_scene_view_request(app).show_operator_marking
        assert amber() == shown[:-len(projected)]
        assert tuple(app.final_scene_view.last_cutting_mesh) == installed_mesh
        view_control.invoke()
        root.update()
        assert amber() == shown
        app.final_scene_view.render(replace(request, render_data=replace(request.render_data, owner_marking_views=())))
        assert tuple(app.final_scene_view.last_cutting_mesh) == installed_mesh
        assert shown == amber() + tuple(path for _, path in projected)
        assert marked_dxf.read_bytes() == previous_bytes

        # Exercise the actual Copy chooser from this owner-bound Save As
        # source, not an old role-only .p6fold fixture. It must list the one
        # group under its saved ID, then reject if source bytes drift.
        group_source, = tuple(row for row in grouped if api.is_manual_group(row))
        source_bytes, destination_bytes = group_path.read_bytes(), legacy.read_bytes()
        from hashlib import sha256
        assert api.list_saved_manual_marking_copy_groups(
            source_snapshot=copy_snapshot,
            source_project_path=group_path,
            source_project_sha256=sha256(source_bytes).hexdigest(),
        ) == (api.group_parameters(group_source)["group_id"],)

        # Real Save As changes the project path, not the physical occupant.
        alias_path, same_snapshot = save_path("different-path-same-physical-occupant")
        assert alias_path != group_path
        assert api.resolve_workspace_physical_root_owner(same_snapshot, key) == owner
        alias_bytes = alias_path.read_bytes()
        open_path(alias_path)
        editor, state = edit()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(group_path))
        state.manual_mark_copy_button.invoke()
        root.update()
        assert "MANUAL_COPY_SAME_PHYSICAL_OWNER" in state.manual_mark_status.cget("text")
        assert tuple(state.live_context.feature_list) == grouped
        assert not state.manual_mark_mode[0]
        state.cancel_all_btn.invoke()
        root.update()
        assert alias_path.read_bytes() == alias_bytes and group_path.read_bytes() == source_bytes

        open_path(legacy)
        editor, state = edit()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(group_path))
        state.manual_mark_copy_button.invoke()
        root.update()
        assert "目標轉角" in state.manual_mark_status.cget("text")
        x, y = state.canvas_view.transform.world_to_canvas(Vec2(200, 140))
        canvas = host.last_hole_editor_canvas

        def copy_click(event_time):
            canvas.event_generate("<ButtonPress-1>", x=round(x), y=round(y), time=event_time)
            canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y), time=event_time)
            root.update()

        group_path.write_bytes(source_bytes + b"\n")
        copy_click(9000)
        assert "SOURCE_SAVED_SOURCE_CHANGED" in state.manual_mark_status.cget("text")
        assert not any(api.is_manual_mark(f) for f in state.live_context.feature_list)
        group_path.write_bytes(source_bytes)
        state.manual_mark_copy_button.invoke()
        root.update()
        copy_click(9650)
        cloned, = tuple(row for row in state.live_context.feature_list if api.is_manual_group(row))
        orig_params, copy_params = map(api.group_parameters, (group_source, cloned))
        assert orig_params.pop("group_id") != copy_params.pop("group_id")
        assert orig_params == copy_params and group_source.offset != cloned.offset
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        new_owner = api.resolve_workspace_physical_root_owner(current(), key)
        assert new_owner is not None and new_owner != owner
        assert api.read_workspace_marking_owner_record(current(), new_owner)["features"] == (cloned,)
        assert group_path.read_bytes() == source_bytes and legacy.read_bytes() == destination_bytes

        target_path, target_snapshot = save_path("owned-copy-target")
        target_bytes = target_path.read_bytes()
        assert target_snapshot[KEY]["records"][new_owner]["features"] == (cloned,)
        open_path(target_path)
        editor, state = edit()

        def arm_owned_target():
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(group_path))
            state.manual_mark_copy_button.invoke()
            root.update()
            assert "目標轉角" in state.manual_mark_status.cget("text")

        def owned_click(position, event_time):
            x, y = state.canvas_view.transform.world_to_canvas(position)
            canv = host.last_hole_editor_canvas
            canv.event_generate("<ButtonPress-1>", x=round(x), y=round(y), time=event_time)
            canv.event_generate("<ButtonRelease-1>", x=round(x), y=round(y), time=event_time)
            root.update()

        arm_owned_target()
        assert app.remove_part(key)
        app.add_part(key)
        root.update()
        changed_owner = api.resolve_workspace_physical_root_owner(current(), key)
        assert changed_owner and changed_owner != new_owner
        owned_click(Vec2(290, 140), 10800)
        assert "TARGET_EDITOR_SESSION_STALE" in state.manual_mark_status.cget("text")
        assert tuple(f for f in state.live_context.feature_list if api.is_manual_group(f)) == (cloned,)
        assert api.read_workspace_marking_owner_record(current(), new_owner)["features"] == (cloned,)
        assert api.read_workspace_marking_owner_record(current(), changed_owner) is None
        state.cancel_all_btn.invoke()
        root.update()
        assert target_path.read_bytes() == target_bytes

        open_path(target_path)
        editor, state = edit()
        arm_owned_target()
        owned_click(Vec2(290, 140), 11600)
        retained, appended = tuple(row for row in state.live_context.feature_list if api.is_manual_group(row))
        assert retained == cloned
        assert len({api.group_parameters(row)["group_id"] for row in (group_source, retained, appended)}) == 3
        owned_click(Vec2(320, 140), 12200)  # no implicit second paste
        assert tuple(row for row in state.live_context.feature_list if api.is_manual_group(row)) == (retained, appended)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        assert api.resolve_workspace_physical_root_owner(current(), key) == new_owner
        assert api.read_workspace_marking_owner_record(current(), new_owner)["features"] == (retained, appended)
        assert group_path.read_bytes() == source_bytes and target_path.read_bytes() == target_bytes
        open_path(group_path)
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
        bridge._phase6_show_assembly(app)
        root.update()
        assert not bridge._phase6_final_scene_view_request(app).render_data.owner_marking_views
        assert not amber()

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
            # Keep the actual round ink clear of other authored strokes at
            # native Windows DPI and smaller editor canvas sizes.
            canvas_click(Vec2(p.x + 105, p.y))
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
            initial_stock = stock
            ink = api.read_verified_owner_marking_candidate(current, original_geometry, key).ink
            assert len(ink) == len(inks) + 1
            exported_bytes = target.read_bytes()
            assert app._phase6_3d_display_mode == "single"
            request = bridge._phase6_final_scene_view_request(app)
            assert tuple(request.render_data.scene.primitives) == (*stock.scene.primitives, *ink)
            mesh = api.project_independent_part_view_mesh(
                key, stock, x_profile=request.x_profile, y_profile=request.y_profile,
                thickness=request.thickness,
            )
            assert tuple(app.final_scene_view.last_cutting_mesh) == tuple(mesh.triangles)
            paths, warning = api.project_checked_owner_marking_standalone_paths(
                request.render_data.scene, mesh,
            )
            assert not warning
            visible_ink = tuple(line for line in app.renderer.ax3d.lines if line.get_color() == "#f59e0b")
            expected_ink = tuple(vertices for layer, vertices in paths if layer == "MARKING")
            assert len(visible_ink) == len(expected_ink)
            for artist, points in zip(visible_ink, expected_ink):
                assert tuple(zip(*artist.get_data_3d())) == points
            view_control = app.show_operator_marking_3d_check
            assert view_control.winfo_manager() == "grid"
            assert app.show_operator_marking_3d_var.get()
            project_bytes = save.read_bytes()
            view_control.invoke()
            root.update()
            hidden = bridge._phase6_final_scene_view_request(app)
            assert not hidden.show_operator_marking
            assert hidden.render_data is stock
            hidden_auto = tuple(line for line in app.renderer.ax3d.lines if line.get_color() == "#f59e0b")
            assert tuple(tuple(zip(*line.get_data_3d())) for line in hidden_auto) == expected_ink[:-len(ink)]
            assert tuple(app.final_scene_view.last_cutting_mesh) == tuple(mesh.triangles)
            bridge._phase6_show_corner_data(app)
            bridge._phase6_select_corner_data_part(app, key)
            root.update()
            assert not view_control.winfo_manager()
            assert tuple(bridge._phase6_corner_data_unfold_projection_for_key(
                app, key,
            ).render_data.scene.primitives) == (*stock.scene.primitives, *ink)
            assert target.read_bytes() == exported_bytes and save.read_bytes() == project_bytes
            menu.invoke(0)  # existing filedialog lambda points to exact same file
            root.update()
            app.activate_part(key)
            root.update()
            reopened_stock = app._phase6_resolve_manufacturing_geometry().part(key).render_data
            assert reopened_stock.material.wkb == stock.material.wkb
            assert tuple(reopened_stock.scene.primitives) == tuple(stock.scene.primitives)
            stock = reopened_stock
            assert view_control.winfo_manager() == "grid"
            assert not app.show_operator_marking_3d_var.get()
            view_control.invoke()
            root.update()
            assert app.show_operator_marking_3d_var.get()
            assert tuple(tuple(zip(*line.get_data_3d())) for line in app.renderer.ax3d.lines
                         if line.get_color() == "#f59e0b") == expected_ink
            from dataclasses import replace
            bridge._phase6_show_assembly(app)
            root.update()
            assembly = bridge._phase6_final_scene_view_request(app)
            assert assembly.part_key == "assembly"
            assert key in dict(assembly.render_data.owner_marking_views)
            assert any("OWNER_MARKING_ASSEMBLY_SURFACE_UNPROVED" in row.get_text()
                       for row in app.renderer.ax3d.texts)
            amber = lambda: tuple(tuple(zip(*line.get_data_3d())) for line in app.renderer.ax3d.lines
                                  if line.get_color() == "#f59e0b")
            held_paths = amber()
            held_triangles = tuple(app.final_scene_view.last_cutting_mesh)
            app.final_scene_view.render(replace(
                assembly, render_data=replace(assembly.render_data, owner_marking_views=()),
            ))
            assert amber() == held_paths
            assert tuple(app.final_scene_view.last_cutting_mesh) == held_triangles
            assert target.read_bytes() == exported_bytes
            app.activate_part(key)
            root.update()
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
            canvas = app.corner_data_canvas
            hint, = canvas.find_withtag("phase6_hole_hint")
            assert canvas.itemcget(hint, "text") == "雙擊：開孔／手動打標"
            for event_time in (2750, 2800):
                canvas.event_generate("<ButtonPress-1>", x=80, y=100, time=event_time)
                canvas.event_generate("<ButtonRelease-1>", x=80, y=100, time=event_time)
            root.update()
            from_drawing = host.last_unified_hole_editor
            assert from_drawing.winfo_exists()
            assert from_drawing._manual_marking_controls[0].cget("text") == "打標：中點放置"
            assert from_drawing._manual_round_marking_controls[0].cget("text") == "實線圓打標：選圓心"
            place = from_drawing._manual_marking_place
            reopened_drawing = dict(zip(
                place.__code__.co_freevars, (c.cell_contents for c in place.__closure__),
            ))["s"]
            assert tuple(f for f in reopened_drawing.live_context.feature_list if api.is_manual_mark(f)) == authored

            def live_circle():
                return next(f for f in reopened_drawing.live_context.feature_list if is_manual_round_mark(f))

            def drag_circle(points, event_time):
                edit_canvas = host.last_hole_editor_canvas
                def xy(v):
                    x, y = reopened_drawing.canvas_view.transform.world_to_canvas(v)
                    return {"x": round(x), "y": round(y)}
                initial = live_circle()
                offset = initial.diameter / 2

                def at_ink(center):
                    return xy(Vec2(center.x + offset, center.y))

                press = at_ink(initial.offset)
                idx = reopened_drawing.canvas_view.hit_test(press["x"], press["y"])
                assert idx is not None and reopened_drawing.live_context.feature_list[idx] is initial
                edit_canvas.event_generate("<ButtonPress-1>", **press, time=event_time)
                root.update()
                assert reopened_drawing.hole_session.selected_index == idx
                assert reopened_drawing.dragging[0]
                for n, point in enumerate(points):
                    edit_canvas.event_generate("<B1-Motion>", **at_ink(point), time=event_time+20+n*20)
                    root.update()
                    if n == 0:
                        assert live_circle() != initial  # actual valid preview before drop
                edit_canvas.event_generate("<ButtonRelease-1>", **at_ink(points[-1]), time=event_time+100)
                root.update()

            initial_circle = live_circle()
            mid = Vec2(initial_circle.offset.x + 12, initial_circle.offset.y + 17)
            destination = Vec2(initial_circle.offset.x + 22, initial_circle.offset.y + 25)
            undo_depth = reopened_drawing.hole_session.snapshot().undo_depth
            assert hole is not None
            crossing = Vec2(hole.center.x + initial_circle.diameter / 2, hole.center.y)
            drag_circle((mid, crossing), 3150)
            assert live_circle() == initial_circle  # a valid intermediate sample cannot be dropped
            assert reopened_drawing.hole_session.snapshot().undo_depth == undo_depth
            assert "圓打標移動被拒絕" in reopened_drawing.manual_mark_status.cget("text")
            reopened_drawing.manual_mark_select_button.invoke()
            drag_circle((mid, destination), 4100)
            moved = live_circle()
            assert moved.offset != initial_circle.offset and moved.diameter == initial_circle.diameter
            assert reopened_drawing.hole_session.snapshot().undo_depth == undo_depth + 1
            reopened_drawing.undo_btn.invoke()
            root.update()
            assert live_circle() == initial_circle
            drag_circle((mid,), 5200)
            assert live_circle() != initial_circle
            # Cancel the pending change without touching the committed owner.
            reopened_drawing.cancel_all_btn.invoke()
            root.update()
            assert api.read_workspace_marking_owner_record(
                current_workspace_marking_source(app), owner,
            )["features"] == authored
            held = "box_body:back"
            assert held in app.designer_workspace.available_parts
            bridge._phase6_select_corner_data_part(app, held)
            root.update()
            only_holes, = canvas.find_withtag("phase6_hole_hint")
            assert canvas.itemcget(only_holes, "text") == "雙擊：開孔"
            assert target.read_bytes() == exported_bytes
            assert original_geometry.part(key).render_data is initial_stock
            assert tuple(initial_stock.scene.primitives) == tuple(stock.scene.primitives)
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
