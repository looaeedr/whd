"""Quantity UI acceptance through real Tk and the existing Hole Editor."""
from copy import deepcopy
import pytest
from phase6_quantity_model import QuantityModel, quantity_only_change
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2


def test_receiving_quantity_holes_without_common_box_fails_cleanly():
    from types import SimpleNamespace
    from gui_modules.application.quantity_version_ports import quantity_ports
    model = QuantityModel()
    workspace = SimpleNamespace(quantity_model=model,
        snapshot=lambda: {"active_mode": "quantity", "quantity": model.snapshot()})
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot={"active_mode": "quantity", "model": "受電箱"},
        _settings_values={}, _phase6_box_whd={"w": 900, "h": 1700, "d": 400},
        baseline_model_var=SimpleNamespace(get=lambda: "受電箱"),
    )
    ports = quantity_ports(SimpleNamespace(app=app), None)
    with pytest.raises(ValueError, match="共用箱體"):
        ports["holes"]("head")


def test_hole_button_shows_warning_instead_of_uncaught_tk_keyerror(monkeypatch):
    from gui_modules.application.quantity_version_controls import QuantityVersionControls
    from tkinter import messagebox
    warnings = []
    monkeypatch.setattr(messagebox, "showwarning",
                        lambda *args, **kwargs: warnings.append((args, kwargs)))
    def missing_box(_role):
        raise ValueError("共用箱體尚未初始化")
    ctrl = QuantityVersionControls(
        frame=None, versions=None, count_var=None, totals_var=None,
        ports={"holes": missing_box})
    assert ctrl.edit_holes("head") is False
    assert warnings and "共用箱體" in warnings[0][0][1]


def circle(x=0):
    return CircleFeature(diameter=8, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(x, 0))


@pytest.mark.parametrize("family", ["金庫型", "RO", "未知"])
def test_all_family_unselected_feature_validation(family):
    from ae_engine.receiving_quantity_box import quantity_feature_errors, require_valid_quantity_features
    model = QuantityModel()
    first = model.selected_version_id
    second = model.add_version()
    model.set_features("tail", [circle(430)])
    model.select(first)
    snapshot = dict(model=family, active_mode="quantity", w=900, d=400, t=2, quantity=model.snapshot())
    assert quantity_feature_errors(snapshot) == ()
    snapshot["w"] = 800
    with pytest.raises(ValueError, match=second + "／封尾／特徵 1"):
        require_valid_quantity_features(snapshot)
    assert model.snapshot() == snapshot["quantity"]


@pytest.mark.parametrize("shared_change", ["w", "t", "model", "existing_parts", "door", "part_profiles", "receiving_quantity_box"])
def test_quantity_classifier_rejects_shared_edits(shared_change):
    q = QuantityModel()
    old = dict(active_mode="quantity", quantity=q.snapshot(), w=900, t=2, model="金庫型",
               existing_parts=["box_body", "head"], part_profiles={}, part_features={"door": []})
    new = deepcopy(old)
    q.set_piece_count(30)
    new["quantity"] = q.snapshot()
    assert quantity_only_change(old, new)
    if shared_change == "door":
        new["part_features"]["door"] = [circle()]
    else:
        new[shared_change] = "changed"
    assert not quantity_only_change(old, new)


def test_editor_targets_identity_after_selection_changes_and_deletion():
    model = QuantityModel()
    first = model.selected_version_id
    second = model.add_version()
    model.set_version_features(first, "head", [circle(12)])
    assert model.selected_version_id == second
    assert model.features_for("head") == []
    model.select(first)
    model.delete_selected(confirmed=True)
    with pytest.raises(ValueError, match=first):
        model.set_version_features(first, "head", [circle()])
    assert model.features_for("head") == []


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_real_gui_quantity_controls_holes_and_manual_save(family, tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    import phase6_manufacturing_service as manufacturing
    import ae_engine.manufacturing_api as api
    from gui_modules.application import receiving_mode_controls
    from gui_modules.application import fold_designer_composition_receiving as implementation
    root = tk.Tk(); root.withdraw()
    errors = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set(family); root.update()
        app = main.open_original_fold_designer(); root.update()
        composition = bridge._phase6_composition(app)
        namespace = vars(bridge)
        if family == "受電箱":
            monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions", lambda *a: dict(w=900, h=1700, d=400))
            assert implementation._switch_mode(composition, namespace, "quantity")
            root.update()
        if family == "金庫型":
            app.activate_part("head"); root.update()
        controls = app.receiving_mode_controls.quantity_editor
        model = app.designer_workspace.quantity_model
        # Receiving operator controls now live in the Assembly multi-settings
        # window; non-Receiving quantity UI retains its existing inline form.
        assert bool(controls.frame.winfo_manager()) is (family != "受電箱")
        assert bool(app.receiving_mode_controls.common_button.winfo_manager()) is (family != "受電箱")
        assert not app.receiving_set_bay_control.winfo_manager()
        import time, json, ezdxf
        from phase6_final_scene_view import Phase6FinalSceneViewAdapter
        calls = dict(resolve=0, build=0, render=0, dxf_read=0, final_scene=0)
        calculations_before = app._phase6_update_scheduler._metrics["calculation_flushes"]
        started = time.perf_counter()
        def counted(name, original):
            def call(*a, **kw):
                calls[name] += 1
                return original(*a, **kw)
            return call
        monkeypatch.setattr(manufacturing, "resolve", counted("resolve", manufacturing.resolve))
        monkeypatch.setattr(api, "build_part_render_data", counted("build", api.build_part_render_data))
        monkeypatch.setattr(app.renderer, "render", counted("render", app.renderer.render))
        monkeypatch.setattr(ezdxf, "readfile", counted("dxf_read", ezdxf.readfile))
        monkeypatch.setattr(Phase6FinalSceneViewAdapter, "build_request", counted("final_scene", Phase6FinalSceneViewAdapter.build_request))
        first = model.selected_version_id
        controls.count_var.set("30"); assert controls.commit_count()
        controls.add()
        second = model.selected_version_id
        controls.count_var.set("20"); assert controls.commit_count()
        assert controls.totals_var.get() == "版本數：2    總件數：50"
        controls.ports["select"](first); controls.refresh()
        controls.add()
        middle = model.selected_version_id
        assert [r["version_id"] for r in model.snapshot()["versions"]] == [first, middle, second]
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: False)
        before = model.snapshot()
        assert not controls.delete() and model.snapshot() == before
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)
        assert controls.delete()
        assert model.selected_version_id == second
        for value in ("0", "-1", "1.5"):
            before = model.snapshot()
            controls.count_var.set(value)
            assert not controls.commit_count()
            assert model.snapshot() == before
        assert len(errors) == 3
        errors.clear()
        root.update()
        assert not any(calls.values()), calls

        # Open the actual unified 2D editor, capturing its detached apply port.
        captured = []
        original_editor = main._open_unified_hole_editor
        def open_editor(*a, **kw):
            captured.append((a, kw))
            return original_editor(*a, **kw)
        monkeypatch.setattr(main, "_open_unified_hole_editor", open_editor)
        controls.ports["holes"]("head"); root.update()
        assert captured and "finished_boundary" == captured[-1][1]["reference_guide"].role
        editor_args, editor_kw = captured[-1]
        assert editor_args[0] == "head"
        controls.ports["select"](first)
        editor_kw["feature_list_override"][:] = [circle(10)]
        editor_kw["sync_callback"]()
        assert model.features_for_version(second, "head") == [circle(10)]
        assert model.features_for("head") == []
        assert not any(calls.values()), calls
        controls.ports["select"](second); controls.refresh()
        controls.add()
        third = model.selected_version_id
        assert model.features_for("head") == [circle(10)]
        controls.ports["holes"]("head"); root.update()
        before_calculations = app._phase6_update_scheduler._metrics["calculation_flushes"]
        captured[-1][1]["feature_list_override"][:] = [circle(20)]
        captured[-1][1]["sync_callback"]()
        assert app._phase6_update_scheduler._metrics["calculation_flushes"] - before_calculations == 1
        controls.ports["holes"]("tail"); root.update()
        before_calculations = app._phase6_update_scheduler._metrics["calculation_flushes"]
        captured[-1][1]["feature_list_override"][:] = [circle(30)]
        captured[-1][1]["sync_callback"]()
        assert app._phase6_update_scheduler._metrics["calculation_flushes"] - before_calculations == 1
        assert model.features_for_version(second, "head") == [circle(10)]
        assert model.features_for_version(third, "head") == [circle(20)]
        assert model.features_for_version(second, "tail") == []
        after_apply = dict(calls)
        controls.ports["select"](first); controls.refresh()
        assert calls == after_apply
        assert calls["dxf_read"] == 0
        calculations = app._phase6_update_scheduler._metrics["calculation_flushes"] - calculations_before
        assert calculations == 2
        receipt = dict(calls, calculation_flushes=calculations, wall_seconds=time.perf_counter()-started)
        (tmp_path / "quantity-ui-stress.json").write_text(json.dumps(receipt, indent=2))
        print("QUANTITY_UI_STRESS=" + json.dumps(receipt))
        # Close modeless windows before Save and use the real save path.
        for window in list(root.winfo_children()):
            if isinstance(window, tk.Toplevel) and window is not app.root:
                window.destroy()
        path = tmp_path / "versions.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
        assert app.save_project_file_as()
        saved = path.read_bytes()
        controls.count_var.set("7"); assert controls.commit_count()
        assert path.read_bytes() == saved
        loaded = project.read_project(path)["snapshot"]
        restored = QuantityModel.from_payload(loaded["quantity"])
        assert restored.total_piece_count == 51
        assert restored.features_for_version(second, "head") == [circle(10)]
        assert restored.features_for_version(first, "head") == []
        assert restored.features_for_version(third, "head") == [circle(20)]
        assert restored.features_for_version(third, "tail") == [circle(30)]
        assert main.workspace_controller.quantity_model.total_piece_count == 28
        before = model.snapshot()
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: False)
        assert not controls.delete() and model.snapshot() == before
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)
        controls.delete(); controls.delete()
        assert model.version_count == 1
        monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
        before = model.snapshot()
        assert not controls.delete() and model.snapshot() == before
        controls.add()
        assert model.selected_version_id not in (first, second, third)
        assert path.read_bytes() == saved
        stale_callback = app._live_sync_callback
        stale_payload = deepcopy(app._phase6_last_live_payload)
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
        opened = app.load_project_file()
        assert opened == str(path), errors
        root.update()
        reopened = main.fold_designer_app
        reloaded = reopened.designer_workspace.quantity_model
        assert reloaded.snapshot() == restored.snapshot()
        assert reloaded.features_for_version(third, "tail") == [circle(30)]
        next_controls = reopened.receiving_mode_controls.quantity_editor
        next_controls.count_var.set("8")
        assert next_controls.commit_count()
        assert main.workspace_controller.quantity_model.total_piece_count == 29
        stale_payload["revision"] = 10000
        assert stale_callback(stale_payload) is False
        assert main.workspace_controller.quantity_model.total_piece_count == 29
        assert path.read_bytes() == saved
        assert not errors, errors
    finally:
        root.destroy()


@pytest.mark.parametrize("family", ["金庫型", "RO", "未知"])
def test_all_family_invalid_unselected_feature_blocks_before_cache(family):
    from types import SimpleNamespace
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_manufacturing_adapter import resolve_manufacturing_for_app
    source = dict(model=family, w=400, h=600, d=250, t=2, existing_parts=["box_body", "head", "tail"])
    workspace = Phase6DesignerWorkspace.from_snapshot(source)
    first = workspace.quantity_model.selected_version_id
    second = workspace.quantity_model.add_version()
    workspace.quantity_model.set_features("head", [circle(500)])
    workspace.quantity_model.select(first)
    source["active_mode"] = "quantity"
    app = SimpleNamespace(_phase6_input_snapshot=source, designer_workspace=workspace)
    with pytest.raises(ValueError, match=second):
        resolve_manufacturing_for_app(app)


def test_quantity_edit_survives_semantically_equal_stale_relief_fingerprint():
    from phase6_sync_envelope import plan_live_sync_envelope, stable_fingerprint, materialize_sync_value
    previous = {"quantity": {"piece_count": 30}, "assembly_relief": {"revision": 1}}
    current = {"quantity": {"piece_count": 8}, "assembly_relief": {"revision": 1}}
    plan = plan_live_sync_envelope(
        current_state=current, previous_state=previous,
        previous_fingerprint=stable_fingerprint(previous), current_revision=0,
        active_transaction_id="", host_relief_present=True,
        host_relief={"revision": 1.0}, force=True)
    assert plan.should_publish
    assert materialize_sync_value(plan.payload)["quantity"]["piece_count"] == 8
    assert materialize_sync_value(plan.delta)["quantity"] == {"piece_count": 8}
