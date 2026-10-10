"""Atomic Receiving mode/session transitions and active-only persistence."""
from copy import deepcopy
import pytest
from ae_engine.cabinet_types import receiving
from ae_engine.receiving_layout import (
    ensure_receiving_layout, resize_receiving_bays, resize_receiving_sets,
    update_receiving_bay, project_primary_bay_legacy_aliases,
)
from ae_engine.receiving_shared_settings import edit_setting, setting_value
from phase6_quantity_model import QuantityModel
import phase6_project_file as project

def old_multibay():
    snapshot=ensure_receiving_layout(receiving.apply_family_defaults({"t":2}))
    layout=resize_receiving_sets(snapshot["receiving_layout"],set_count=2)
    for i in range(2):
        layout=resize_receiving_bays(layout,set_index=i,bay_count=3)
    snapshot["receiving_layout"]=layout
    snapshot["active_mode"]="set_bay"
    return snapshot

def test_first_switch_confirmed_dimensions_new_box_and_session_restore():
    from phase6_receiving_modes import ReceivingModeSession
    original=old_multibay()
    validations=[]
    modes=ReceivingModeSession(original,validator=lambda value:validations.append(deepcopy(value)))
    assert modes.needs_initialization("quantity")
    assert not modes.switch("quantity")
    assert modes.snapshot()==original and validations==[]
    assert modes.switch("quantity",dimensions={"w":900,"h":1700,"d":400})
    quantity=modes.snapshot()
    assert quantity["active_mode"]=="quantity"
    assert (quantity["w"],quantity["h"],quantity["d"])==(900,1700,400)
    layout=quantity["receiving_layout"]
    assert len(layout["sets"])==len(layout["sets"][0]["bays"])==1
    assert layout["sets"][0]["joints"]==[]
    assert quantity["receiving_quantity_box"]["back_panel_mode"]=="FULL"
    assert quantity["receiving_quantity_box"]["inner_door_layers"]==1
    assert quantity["receiving_quantity_box"]["switch_brand"]=="士林"
    model=QuantityModel.from_payload(quantity["quantity"])
    assert model.version_count==model.total_piece_count==1
    assert model.features_for("head")==model.features_for("tail")==[]
    model.set_piece_count(7)
    model.add_version()
    quantity["quantity"]=model.snapshot()
    assert modes.switch("set_bay",current_snapshot=quantity)
    assert modes.snapshot()==original
    assert not modes.needs_initialization("quantity")
    assert modes.switch("quantity",current_snapshot=original)
    assert modes.snapshot()["quantity"]==model.snapshot()
    assert len(validations)==1

@pytest.mark.parametrize("bad",["",0,-1,"oops","nan","inf",True])
@pytest.mark.parametrize("axis",["w","h","d"])
def test_invalid_first_dimensions_leave_mode_and_every_buffer_unchanged(axis,bad):
    from phase6_receiving_modes import ReceivingModeSession
    original=old_multibay()
    modes=ReceivingModeSession(original,validator=lambda value:None)
    dims={"w":900,"h":1700,"d":400};dims[axis]=bad
    with pytest.raises(ValueError):
        modes.switch("quantity",dimensions=dims)
    assert modes.snapshot()==original
    assert modes.needs_initialization("quantity")
    assert not modes.switch("quantity")

def test_geometry_failure_does_not_switch_or_save_partial_buffer():
    from phase6_receiving_modes import ReceivingModeSession
    original=old_multibay()
    def invalid(candidate):
        raise ValueError("canonical geometry failed")
    modes=ReceivingModeSession(original,validator=invalid)
    with pytest.raises(ValueError,match="canonical geometry"):
        modes.switch("quantity",dimensions={"w":900,"h":1700,"d":400})
    assert modes.snapshot()==original and modes.needs_initialization("quantity")

def test_quantity_only_reload_requires_reverse_confirmation_and_saves_no_inactive_mode(tmp_path):
    from phase6_receiving_modes import ReceivingModeSession
    modes=ReceivingModeSession(old_multibay(),validator=lambda value:None)
    modes.switch("quantity",dimensions={"w":900,"h":1700,"d":400})
    quantity=modes.snapshot()
    model=QuantityModel.from_payload(quantity["quantity"])
    model.set_piece_count(30)
    quantity["quantity"]=model.snapshot()
    path=project.write_project(tmp_path/"quantity.p6fold",{"schema":project.PROJECT_SCHEMA_V2,"snapshot":quantity})
    import json
    raw=json.loads(path.read_text())["snapshot"]
    assert raw["active_mode"]=="quantity" and raw["receiving_quantity_box"]["w"]==900
    assert "receiving_layout" not in raw and "_mode_buffers" not in raw
    restored=ReceivingModeSession(project.read_project(path)["snapshot"],validator=lambda value:None)
    before=restored.snapshot()
    assert restored.needs_initialization("set_bay")
    assert not restored.switch("set_bay")
    assert restored.snapshot()==before
    assert restored.switch("set_bay",dimensions={"w":800,"h":1600,"d":350})
    fresh=restored.snapshot()
    assert fresh["active_mode"]=="set_bay" and "quantity" not in fresh
    assert len(fresh["receiving_layout"]["sets"])==1
    assert len(fresh["receiving_layout"]["sets"][0]["bays"])==1
    assert fresh["receiving_layout"]["sets"][0]["joints"]==[]
    assert (fresh["w"],fresh["h"],fresh["d"])==(800,1600,350)
    saved=project.write_project(tmp_path/"set-bay.p6fold",{"schema":project.PROJECT_SCHEMA_V2,"snapshot":fresh})
    raw=json.loads(saved.read_text())["snapshot"]
    assert "quantity" not in raw and "receiving_quantity_box" not in raw
    assert restored.switch("quantity",current_snapshot=fresh)
    assert restored.snapshot()["quantity"]==model.snapshot()


def test_real_gui_cancel_switch_common_edit_and_active_only_save(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import gui
    import fold_designer_bridge as bridge
    from gui_modules.application import receiving_mode_controls as controls
    from gui_modules.application import fold_designer_composition_receiving as implementation
    errors = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    root = tk.Tk(); root.withdraw()
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        root.update()
        composition = bridge._phase6_composition(app)
        namespace = vars(bridge)
        composition.settings_transactions().commit_endcap_fw_override("head", 44)
        app.submit_update_intent("geometry", commit=True)
        before = implementation._current_mode_snapshot(composition, namespace)
        # Fresh sessions use Family dimensions without an initialization dialog.
        assert before["active_mode"] == "set_bay"
        composition.final_scene_set_preview_enabled(False)
        import phase6_manufacturing_service as mode_manufacturing
        before_failed = deepcopy(app.designer_workspace.snapshot())
        before_settings = deepcopy(app._settings_values)
        original_resolve = mode_manufacturing.resolve
        failed_calls = []
        def fail_fresh_geometry(request):
            if request.input_snapshot.get("active_mode") == "quantity":
                failed_calls.append(1)
                raise ValueError("injected canonical manufacturing failure")
            return original_resolve(request)
        with monkeypatch.context() as failure_patch:
            failure_patch.setattr(mode_manufacturing, "resolve", fail_fresh_geometry)
            assert not implementation._switch_mode(composition, namespace, "quantity")
        assert failed_calls
        assert app.designer_workspace.snapshot() == before_failed
        assert app._settings_values == before_settings
        assert main.workspace_controller.receiving_mode_session(implementation._current_mode_snapshot(composition, namespace)).needs_initialization("quantity")
        assert len(errors) == 1 and "模式未切換" in errors[0]
        errors.clear()
        assert implementation._switch_mode(composition, namespace, "quantity")
        root.update()
        assert not app.preview_3d_enabled
        composition.final_scene_set_preview_enabled(True)
        assert app.designer_workspace.quantity_model is not None
        assert app._phase6_endcap_fw_state["head"]["follow_box"] is True
        assert app._phase6_endcap_fw_state["head"]["value"] == 29
        assert not app.receiving_set_bay_control.winfo_manager()
        assert not app.receiving_mode_controls.common_button.winfo_manager()
        assert app._phase6_box_whd["w"] == 800
        assert app._phase6_box_whd["d"] == 350
        app.designer_workspace.quantity_model.set_piece_count(7)
        app.designer_workspace.quantity_model.add_version()
        assert implementation._switch_mode(composition, namespace, "set_bay")
        root.update()
        assert app.designer_workspace.quantity_model is None
        assert app._phase6_endcap_fw_state["head"]["follow_box"] is False
        assert app._phase6_endcap_fw_state["head"]["value"] == 44
        assert not app.receiving_set_bay_control.winfo_manager()
        assert implementation._switch_mode(composition, namespace, "quantity")
        root.update()
        assert app.designer_workspace.quantity_model.total_piece_count == 8
        assert implementation._open_common_box(composition, namespace)
        root.update()
        win = next(c for c in app.root.winfo_children() if hasattr(c, "_phase6_receiving_preview_2d"))
        assert win.title() == "共用箱體設定"
        assert win._phase6_receiving_preview_mesh_count == 0
        ports = win._phase6_receiving_settings_ports
        import time
        import ezdxf
        import phase6_manufacturing_service as manufacturing_service
        calls = {"manufacturing_resolve":0, "dxf_read":0, "render":0, "live_publish":0}
        resolve = manufacturing_service.resolve
        readfile = ezdxf.readfile
        render = app.renderer.render
        live = app._live_sync_callback
        def counted_resolve(*args, **kw):
            calls["manufacturing_resolve"] += 1
            return resolve(*args, **kw)
        def counted_read(*args, **kw):
            calls["dxf_read"] += 1
            return readfile(*args, **kw)
        def counted_render(*args, **kw):
            calls["render"] += 1
            return render(*args, **kw)
        def counted_live(*args, **kw):
            calls["live_publish"] += 1
            return live(*args, **kw)
        monkeypatch.setattr(app.renderer, "render", counted_render)
        monkeypatch.setattr(app, "_live_sync_callback", counted_live)
        monkeypatch.setattr(manufacturing_service, "resolve", counted_resolve)
        monkeypatch.setattr(ezdxf, "readfile", counted_read)
        from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
        model = app.designer_workspace.quantity_model
        model.select(model.snapshot()["versions"][0]["version_id"])
        model.set_features("head", [CircleFeature(diameter=8,anchor=FeatureAnchor.TOP_RIGHT,offset=Vec2(-20,-20))])
        receipts = []
        composition.final_scene_set_preview_enabled(False)
        for action in (lambda:ports["change"]("back_panel_mode", "HALF"),
                       lambda:ports["change"]("inner_door_layers", 2),
                       lambda:ports["brand"]("東元"),
                       lambda:ports["dimensions"](800.75,1700.5,420.25,door_columns=((800.75,(1100,600.5)),))):
            if receipts and not app.preview_3d_enabled:
                composition.final_scene_set_preview_enabled(True)
                root.update()
            before_calls = dict(calls)
            before_calculations = app._phase6_update_scheduler._metrics["calculation_flushes"]
            started = time.perf_counter()
            action()
            root.update()
            receipt = {key:calls[key]-before_calls[key] for key in calls}
            receipt["calculation"] = app._phase6_update_scheduler._metrics["calculation_flushes"]-before_calculations
            receipt["wall_seconds"] = time.perf_counter()-started
            assert receipt["calculation"] <= 1 and receipt["manufacturing_resolve"] <= 1 and receipt["dxf_read"] == 0, receipt
            assert receipt["render"] <= 1 and receipt["live_publish"] <= 1, receipt
            receipts.append(receipt)
        view = win._phase6_receiving_preview_2d
        assert app._phase6_box_whd == {"w":800.75,"h":1700.5,"d":420.25}
        before_invalid = deepcopy(app.designer_workspace.snapshot())
        with pytest.raises(ValueError):
            ports["dimensions"](0,1700,400)
        assert app.designer_workspace.snapshot() == before_invalid
        from gui_modules.application.receiving_settings_preview_2d import physical_drawings
        from ae_engine import manufacturing_api
        drawings = physical_drawings(view.requests[0])
        head = next(data for _, key, data in drawings if key == "head")
        assert any(getattr(primitive, "radius", None) == 4 for primitive in head.scene.primitives)
        for index, (_, key, data) in enumerate(drawings):
            output = tmp_path / f"common-piece-{index}.dxf"
            manufacturing_api.save_part_render_data_dxf(data,output,overwrite=True)
            assert manufacturing_api.verify_saved_part_render_data_dxf(data,output).ok, key
        before_calls = dict(calls)
        before_draws = view.geometry_draw_count
        started = time.perf_counter()
        for _ in range(12):
            view.zoom(.95)
            view.reset_view()
            root.update()
        display = {key:calls[key]-before_calls[key] for key in calls}
        display["geometry_draw"] = view.geometry_draw_count-before_draws
        display["wall_seconds"] = time.perf_counter()-started
        assert all(display[key] == 0 for key in ("manufacturing_resolve", "dxf_read", "render", "live_publish", "geometry_draw"))
        import json
        receipt_path = tmp_path / "common-box-stress.json"
        receipt_path.write_text(json.dumps({"edits":receipts,"display":display},indent=2))
        print("RECEIVING_COMMON_BOX_PROFILE=" + receipt_path.read_text())
        root.update()
        box = app.designer_workspace.snapshot()["receiving_quantity_box"]
        assert (box["back_panel_mode"],box["inner_door_layers"],box["switch_brand"]) == ("HALF",2,"東元")
        assert app.designer_workspace.quantity_model.total_piece_count == 8
        win.destroy()
        # A bad unselected version blocks manufacturing, but must not lock the
        # common settings editor needed to repair its dimensions after reopening.
        model = app.designer_workspace.quantity_model
        first, second = [row["version_id"] for row in model.snapshot()["versions"]]
        model.select(second)
        model.set_features("tail", [CircleFeature(diameter=8,anchor=FeatureAnchor.PANEL_CENTER,offset=Vec2(430,0))])
        model.select(first)
        assert implementation._open_common_box(composition, namespace)
        root.update()
        win = next(c for c in app.root.winfo_children() if hasattr(c, "_phase6_receiving_preview_2d"))
        view = win._phase6_receiving_preview_2d
        assert not view.requests and second in view.status.get() and "封尾" in view.status.get()
        win._phase6_receiving_settings_ports["dimensions"](1000,1700.5,420.25)
        root.update()
        assert view.requests and view.status.get() == ""
        assert app.designer_workspace.quantity_model.total_piece_count == 8
        box = app.designer_workspace.snapshot()["receiving_quantity_box"]
        assert box["w"] == 1000
        win.destroy()
        path = tmp_path / "quantity-real.p6fold"
        monkeypatch.setattr(filedialog,"asksaveasfilename",lambda **kw:str(path))
        assert app.save_project_file_as()
        loaded = project.read_project(path)["snapshot"]
        assert loaded["receiving_quantity_box"] == box
        assert loaded["quantity"]["versions"][0]["piece_count"] == 7
        import json
        raw = json.loads(path.read_text())["snapshot"]
        assert "receiving_layout" not in raw
        assert "receiving_layout" not in raw.get("workspace", {})
        assert main.workspace_controller.workspace_snapshot()["receiving_quantity_box"] == box
        assert not errors, errors
    finally:
        root.destroy()


def test_common_edits_share_all_versions_and_validate_unselected_anchor(tmp_path):
    from phase6_receiving_modes import fresh_receiving_mode
    from ae_engine.receiving_quantity_box import update_common_box, quantity_feature_errors, require_valid_quantity_features
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
    source = fresh_receiving_mode("quantity", {"w":900, "h":1700, "d":400})
    model = QuantityModel.from_payload(source["quantity"])
    first = model.selected_version_id
    model.set_features("head", [CircleFeature(anchor=FeatureAnchor.TOP_RIGHT, offset=Vec2(-20,-20), diameter=8)])
    second = model.add_version()
    model.set_features("head", [])
    model.set_features("tail", [CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(430,0), diameter=8)])
    model.select(first)
    source["quantity"] = model.snapshot()
    assert quantity_feature_errors(source) == ()
    changed = update_common_box(source, {"w":800, "d":350, "back_panel_mode":"HALF", "inner_door_layers":2, "switch_brand":"東元"})
    assert changed["quantity"] == source["quantity"]
    assert changed["w"] == changed["receiving_quantity_box"]["w"] == 800
    errors = quantity_feature_errors(changed)
    assert len(errors) == 1 and second in errors[0] and "封尾" in errors[0] and "特徵 1" in errors[0]
    with pytest.raises(ValueError, match=second):
        require_valid_quantity_features(changed)
    old = deepcopy(source)
    with pytest.raises(ValueError):
        update_common_box(source, {"d":0})
    assert source == old
    saved = project.write_project(tmp_path/"common.p6fold", {"schema":project.PROJECT_SCHEMA_V2,"snapshot":source})
    loaded = project.read_project(saved)["snapshot"]
    assert loaded["quantity"] == source["quantity"]
    assert loaded["receiving_quantity_box"] == source["receiving_quantity_box"]


def test_family_geometry_failure_and_workspace_callback_are_atomic():
    from phase6_receiving_modes import ReceivingModeSession
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController
    session = ReceivingModeSession(old_multibay())
    before = session.snapshot()
    with pytest.raises(ValueError):
        session.switch("quantity", dimensions={"w":10,"h":1700,"d":400})
    assert session.snapshot() == before and session.needs_initialization("quantity")
    session.switch("quantity", dimensions={"w":900,"h":1700,"d":400})
    workspace = Phase6DesignerWorkspace.from_snapshot(before)
    navigation = Phase6WorkspaceNavigationController(workspace)
    navigation.replace_receiving_mode(session.snapshot())
    assert navigation.workspace is workspace
    workspace.mark_clean()
    workspace.quantity_model.set_piece_count(4)
    assert workspace.dirty
    assert workspace.snapshot()["receiving_quantity_box"]["w"] == 900


def test_common_fractional_dimensions_roundtrip_existing_fold_adapters():
    from phase6_receiving_modes import fresh_receiving_mode
    from phase6_fold_profiles import build_box_body_profile, read_box_body_profile, build_endcap_xy_profiles, read_endcap_xy_profiles, build_linked_endcap_xy_profiles
    source = fresh_receiving_mode("quantity", {"w":900.5,"h":1700.75,"d":400.25})
    body = build_box_body_profile(source)
    values = read_box_body_profile(body, source)
    assert (values["w"],values["d"]) == (900.5,400.25)
    for role in ("head", "tail"):
        values = read_endcap_xy_profiles(build_endcap_xy_profiles(source,part_key=role), source)
        assert (values["w"],values["d"]) == (900.5,400.25)


def test_custom_physical_allocator_spans_independent_mode_buffers():
    from phase6_receiving_modes import ReceivingModeSession
    from phase6_designer_workspace import Phase6DesignerWorkspace
    source = old_multibay()
    workspace = Phase6DesignerWorkspace.from_snapshot(source)
    first = workspace.add_custom_part(display_name="舊模式板",fold_axis="X",transverse_length=100)
    source.update(workspace.snapshot())
    session = ReceivingModeSession(source)
    session.switch("quantity", dimensions={"w":900,"h":1700,"d":400})
    quantity = session.snapshot()
    workspace = Phase6DesignerWorkspace.from_snapshot(quantity)
    second = workspace.add_custom_part(display_name="數量模式板",fold_axis="Y",transverse_length=100)
    assert second != first
    assert first not in workspace.available_parts
    quantity.update(workspace.snapshot())
    session.switch("set_bay",current_snapshot=quantity)
    restored = session.snapshot()
    workspace = Phase6DesignerWorkspace.from_snapshot(restored)
    assert first in workspace.available_parts and second not in workspace.available_parts
    third = workspace.add_custom_part(display_name="新板",fold_axis="X",transverse_length=100)
    assert third not in (first,second)


def test_invalid_unselected_feature_blocks_before_manufacturing_cache_lookup():
    from types import SimpleNamespace
    from phase6_receiving_modes import fresh_receiving_mode
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_manufacturing_adapter import resolve_manufacturing_for_app
    from ae_engine.sheetmetal_features import CircleFeature,FeatureAnchor,Vec2
    source = fresh_receiving_mode("quantity", {"w":900,"h":1700,"d":400})
    workspace = Phase6DesignerWorkspace.from_snapshot(source)
    first = workspace.quantity_model.selected_version_id
    second = workspace.quantity_model.add_version()
    workspace.quantity_model.set_features("tail",[CircleFeature(diameter=8,anchor=FeatureAnchor.PANEL_CENTER,offset=Vec2(900,0))])
    workspace.quantity_model.select(first)
    app = SimpleNamespace(_phase6_input_snapshot=source,designer_workspace=workspace)
    with pytest.raises(ValueError,match=second):
        resolve_manufacturing_for_app(app)
