"""Cross-owner v1.5 acceptance using selectable families and real GUI Output."""
from copy import deepcopy
import json
import re
import time

import ezdxf
import pytest


def test_settings_projection_preserves_integer_ids_and_counts_without_fingerprint_drift():
    from phase6_settings_contracts import freeze_settings_value, settings_fingerprint
    from phase6_settings_profile_projection import (SettingsProfileProjectionRequest,
        materialize_settings_profile_value, build_settings_profile_projection)
    from ae_engine.cabinet_types import receiving
    source = receiving.apply_family_defaults({"t": 2})
    source["custom_parts"] = {"schema": "phase6-custom-parts-v1", "next_id": 2**53+1, "items": {}}
    request = SettingsProfileProjectionRequest({}, source, available_parts=("box_body",))
    data = materialize_settings_profile_value(request.input_snapshot)
    assert type(data["custom_parts"]["next_id"]) is int
    assert data["custom_parts"]["next_id"] == 2**53+1
    plan = build_settings_profile_projection(request)
    assert materialize_settings_profile_value(plan.snapshot)["custom_parts"] == source["custom_parts"]
    assert type(freeze_settings_value(True)) is bool
    assert type(freeze_settings_value(2.5)) is float
    assert settings_fingerprint({"w": 900, "count": 2}) == settings_fingerprint({"w": 900.0, "count": 2.0})


def resolved_batch(app):
    from phase6_manufacturing_adapter import (build_manufacturing_request,
        build_scene_payload_for_app, operator_finished_dimensions_for_app)
    from phase6_quantity_manufacturing import resolve_quantity_manufacturing
    request = build_manufacturing_request(app,
        scene_payload_builder=lambda key: build_scene_payload_for_app(app, key),
        render_data_provider=app._scene_query_callback,
        part_spec_provider=app._part_spec_query_callback,
        finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(app, key))
    return resolve_quantity_manufacturing(request, app.designer_workspace.snapshot())


@pytest.mark.parametrize("family,first_count,second_count", [
    ("金庫型", 30, 20), ("受電箱", 30, 20), ("自訂", 30, 20),
    ("金庫型", 6, 4), ("金庫型", 3, 2)])
def test_selectable_family_save_reload_real_output_custom_bom(family, first_count, second_count, tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import gui
    import fold_designer_bridge as bridge
    from gui_modules.application import receiving_mode_controls, fold_designer_composition_receiving as modes
    from gui_modules.project.export_actions import _export_selected_parts
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
    from ae_engine.drawing_annotation_layout import annotate_quantity_render_data
    from ae_engine import manufacturing_api as api
    from phase6_quantity_manufacturing import quantity_manufacturing_groups
    root = tk.Tk()
    root.withdraw()
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: errors.append(a))
    try:
        main = gui.BoxCalculatorGUI(root)
        assert set(main._baseline_model_choices()) == {"金庫型", "受電箱", "自訂"}
        main.baseline_var.set(family)
        root.update()
        app = main.open_original_fold_designer()
        root.update()
        if family == "受電箱":
            monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions",
                lambda *a: dict(w=900, h=1700, d=400))
            assert modes._switch_mode(bridge._phase6_composition(app), vars(bridge), "quantity")
            root.update()
        ws = app.designer_workspace
        custom = ws.add_custom_part(display_name="共同加強板", fold_axis="Y",
            transverse_length=234, per_box_count=2)
        controls = app.receiving_mode_controls.quantity_editor
        controls.count_var.set(str(first_count))
        assert controls.commit_count()
        controls.add()
        controls.count_var.set(str(second_count))
        assert controls.commit_count()
        second = ws.quantity_model.selected_version_id
        captured = []
        original_editor = main._open_unified_hole_editor
        def open_editor(*args, **kwargs):
            captured.append(kwargs)
            return original_editor(*args, **kwargs)
        monkeypatch.setattr(main, "_open_unified_hole_editor", open_editor)
        controls.ports["holes"]("head")
        root.update()
        captured[-1]["feature_list_override"][:] = [
            CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(10, 0))]
        captured[-1]["sync_callback"]()
        assert ws.quantity_model.features_for_version(second, "head") == captured[-1]["feature_list_override"]
        for window in list(root.winfo_children()):
            if isinstance(window, tk.Toplevel) and window is not app.root:
                window.destroy()
        root.update()
        if family == "受電箱":
            composition = bridge._phase6_composition(app)
            assert modes._open_common_box(composition, vars(bridge))
            root.update()
            win = next(c for c in app.root.winfo_children()
                if hasattr(c, "_phase6_receiving_settings_ports"))
            ports = win._phase6_receiving_settings_ports
            box = ws.snapshot()["receiving_quantity_box"]
            assert (box["back_panel_mode"], box["inner_door_layers"], box["switch_brand"]) == ("FULL", 1, "士林")
            actual_doors = deepcopy(box["door_state"]["inner_doors"])
            ports["change"]("back_panel_mode", "HALF")
            ports["change"]("inner_door_layers", 2)
            ports["brand"]("東元")
            root.update()
            # #1331 defines switch-configuration layers, not sheet multiplicity.
            # Its future switch DXF is not an authority for inventing another door.
            assert ws.snapshot()["receiving_quantity_box"]["door_state"]["inner_doors"] == actual_doors
            assert win._phase6_receiving_preview_mesh_count == 0
            win.destroy()
        path = tmp_path / "quantity.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
        assert app.save_project_file_as()
        saved = path.read_bytes()
        quantity = deepcopy(ws.quantity_model.snapshot())
        controls.count_var.set("7")
        assert controls.commit_count()
        assert path.read_bytes() == saved
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
        assert app.load_project_file() == str(path)
        root.update()
        app = main.fold_designer_app
        ws = app.designer_workspace
        assert ws.quantity_model.snapshot() == quantity
        assert ws.snapshot()["custom_parts"]["items"][custom]["per_box_count"] == 2
        if family == "受電箱":
            box = ws.snapshot()["receiving_quantity_box"]
            assert (box["w"], box["h"], box["d"]) == (900, 1700, 400)
            assert (box["back_panel_mode"], box["inner_door_layers"], box["switch_brand"]) == ("HALF", 2, "東元")
            raw = json.loads(path.read_text())["snapshot"]
            assert "receiving_layout" not in raw and "_mode_buffers" not in raw
        before = deepcopy(ws.snapshot())
        flags = dict.fromkeys(("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door"), True)
        exported, problems = _export_selected_parts(main, str(tmp_path), {}, flags, False)
        assert exported and not problems, problems
        batch = resolved_batch(app)
        groups = quantity_manufacturing_groups(batch)
        assert set(exported) == {g.filename for g in groups}
        custom_groups = [g for g in groups if any(r.source_part_id == custom for r in g.members)]
        assert len(custom_groups) == 1 and custom_groups[0].quantity == 2*(first_count+second_count)
        head_groups = [g for g in groups if any(r.source_part_id == "head" for r in g.members)]
        assert len(head_groups) == 2 and sorted(g.quantity for g in head_groups) == sorted((first_count, second_count))
        for group in groups:
            output = tmp_path / group.filename
            assert api.verify_saved_part_render_data_dxf(
                annotate_quantity_render_data(group.render_data, group.quantity), output).ok
            doc = ezdxf.readfile(output)
            q, = [e for e in doc.modelspace().query("MTEXT")
                if re.fullmatch(r"[Qq][0-9]+", e.plain_text())]
            assert q.plain_text() == f"Q{group.quantity}"
            assert q.dxf.layer == "CHECK" and q.dxf.color == 2
            assert doc.layers.get("CHECK").dxf.linetype == "CONTINUOUS"
        assert ws.snapshot() == before and path.read_bytes() == saved
        assert not errors, errors
    finally:
        root.destroy()


def test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, filedialog
    from types import SimpleNamespace
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    import phase6_manufacturing_service as service
    from ae_engine import manufacturing_api as api
    from gui_modules.application import receiving_mode_controls, fold_designer_composition_receiving as modes
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    from tests.test_issue1463_receiving_modes import old_multibay
    from ae_engine.receiving_layout import update_receiving_bay, update_receiving_joint_alignment
    from ae_engine.receiving_shared_settings import edit_setting
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
    source = old_multibay()
    edited = source["receiving_layout"]
    door = deepcopy(edited["sets"][0]["bays"][1]["door_state"])
    door["door_layout_columns"] = [[900, [1100, 600]]]
    edited = update_receiving_bay(edited, set_index=0, bay_index=1,
        width=900, height=1700, depth=420, door_state=door)
    edited = update_receiving_joint_alignment(edited, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP")
    edited = edit_setting(edited, set_index=0, bay_index=1, kind="back_panel_mode", value="HALF")
    edited = edit_setting(edited, set_index=0, bay_index=1, kind="head_features",
        value=[CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(0, 0))])
    edited = edit_setting(edited, set_index=1, bay_index=2, kind="tail_features",
        value=[CircleFeature(10, FeatureAnchor.PANEL_CENTER, Vec2(0, 0))])
    edited = edit_setting(edited, set_index=1, bay_index=2, kind="inner_door_layers", value=2)
    edited["sets"][1]["switch_brand"] = "東元"
    source["receiving_layout"] = edited
    # This is an actual legacy project: no quantity or mode field on disk.
    source.pop("active_mode")
    legacy = project.write_project(tmp_path / "legacy.p6fold",
        {"schema": project.PROJECT_SCHEMA_V2, "snapshot": source})
    root = tk.Tk()
    root.withdraw()
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: errors.append(a))
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(legacy))
        assert app.load_project_file() == str(legacy)
        root.update()
        app = main.fold_designer_app
        composition, namespace = bridge._phase6_composition(app), vars(bridge)
        original = modes._current_mode_snapshot(composition, namespace)
        layout = deepcopy(original["receiving_layout"])
        assert original["active_mode"] == "set_bay"
        assert len(layout["sets"]) == 2
        assert [len(row["bays"]) for row in layout["sets"]] == [3, 3]
        assert modes.open_receiving_layer_preview(composition, namespace, 0)
        root.update()
        win = next(c for c in app.root.winfo_children() if hasattr(c, "_phase6_receiving_preview_2d"))
        view, panel = win._phase6_receiving_preview_2d, win._phase6_receiving_settings_panel
        assert view.ax.name == "rectilinear" and win._phase6_receiving_preview_mesh_count == 0
        calls = dict(resolve=0, build=0, read=0, final_scene=0, render=0)
        def counted(name, original_call):
            def call(*args, **kwargs):
                calls[name] += 1
                return original_call(*args, **kwargs)
            return call
        with monkeypatch.context() as profile:
            profile.setattr(service, "resolve", counted("resolve", service.resolve))
            profile.setattr(api, "build_part_render_data", counted("build", api.build_part_render_data))
            profile.setattr(ezdxf, "readfile", counted("read", ezdxf.readfile))
            profile.setattr(Phase6FinalSceneViewAdapter, "build_request", counted("final_scene", Phase6FinalSceneViewAdapter.build_request))
            profile.setattr(app.renderer, "render", counted("render", app.renderer.render))
            before_calculation = app._phase6_update_scheduler._metrics["calculation_flushes"]
            before_draw = view.geometry_draw_count
            started = time.perf_counter()
            panel._receiving_select_bay(2)
            assert not panel._receiving_pending
            panel._receiving_kind_var.set("封頭孔")
            panel._receiving_refresh()
            rect = view.tiles[0][3]
            event = SimpleNamespace(inaxes=view.ax, xdata=rect.get_x()+30, ydata=rect.get_y()+30)
            for _ in range(20):
                panel._receiving_select_bay(2)
                view._motion(event)
                view.zoom(.95)
                view.reset_view()
                root.update()
            receipt = dict(calls, calculation=app._phase6_update_scheduler._metrics["calculation_flushes"]-before_calculation,
                geometry_draw=view.geometry_draw_count-before_draw,
                wall_seconds=time.perf_counter()-started)
            print("V15_ACTUAL_MULTIBAY_2D_PROFILE=" + json.dumps(receipt))
            (tmp_path / "multibay-2d-profile.json").write_text(json.dumps(receipt, indent=2))
            assert all(value == 0 for key, value in receipt.items() if key != "wall_seconds"), receipt
            assert modes._current_mode_snapshot(composition, namespace)["receiving_layout"] == layout
        win.destroy()
        monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: None)
        assert not modes._switch_mode(composition, namespace, "quantity")
        assert modes._current_mode_snapshot(composition, namespace) == original
        monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: dict(w=0, h=1700, d=400))
        assert not modes._switch_mode(composition, namespace, "quantity")
        assert modes._current_mode_snapshot(composition, namespace) == original
        assert errors
        errors.clear()
        monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: dict(w=900, h=1700, d=400))
        assert modes._switch_mode(composition, namespace, "quantity")
        root.update()
        box = app.designer_workspace.snapshot()["receiving_quantity_box"]
        assert (box["back_panel_mode"], box["inner_door_layers"], box["switch_brand"]) == ("FULL", 1, "士林")
        assert app.designer_workspace.quantity_model.features_for("head") == []
        assert app.designer_workspace.quantity_model.features_for("tail") == []
        controls = app.receiving_mode_controls.quantity_editor
        controls.count_var.set("7")
        assert controls.commit_count()
        batch = resolved_batch(app)
        assert len(batch.versions) == 1 and batch.versions[0].piece_count == 7
        assert all(demand.quantity == 7 for demand in batch.demands)
        for _, _, request in batch.requests:
            one = request.input_snapshot["receiving_layout"]
            assert len(one["sets"]) == len(one["sets"][0]["bays"]) == 1
            assert not one["sets"][0]["joints"]
        saved = tmp_path / "quantity-only.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        assert app.save_project_file_as()
        raw = json.loads(saved.read_text())["snapshot"]
        assert "receiving_layout" not in raw and "_mode_buffers" not in raw
        quantity = deepcopy(app.designer_workspace.quantity_model.snapshot())
        assert modes._switch_mode(composition, namespace, "set_bay")
        root.update()
        assert modes._current_mode_snapshot(composition, namespace)["receiving_layout"] == layout
        assert modes._switch_mode(composition, namespace, "quantity")
        assert app.designer_workspace.quantity_model.snapshot() == quantity
        # Actual project reopen clears the old Session; reverse needs confirmation.
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        assert app.load_project_file() == str(saved)
        root.update()
        app = main.fold_designer_app
        composition = bridge._phase6_composition(app)
        before = modes._current_mode_snapshot(composition, namespace)
        monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: None)
        assert not modes._switch_mode(composition, namespace, "set_bay")
        assert modes._current_mode_snapshot(composition, namespace) == before
        monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: dict(w=800, h=1600, d=350))
        assert modes._switch_mode(composition, namespace, "set_bay")
        root.update()
        fresh = modes._current_mode_snapshot(composition, namespace)
        one = fresh["receiving_layout"]
        assert len(one["sets"]) == len(one["sets"][0]["bays"]) == 1
        assert one["sets"][0]["joints"] == []
        assert (fresh["w"], fresh["h"], fresh["d"]) == (800, 1600, 350)
        assert "quantity" not in fresh
        assert not errors, errors
    finally:
        root.destroy()
