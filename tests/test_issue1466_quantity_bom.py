"""Physical multiplicity and real GUI quantity manufacturing acceptance."""
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace
import pytest

from ae_engine.manufacturing_api import resolved_quantity_physical_demands
from ae_engine.manufacturing_quantity import ResolvedQuantityVersion
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart


def inventory():
    one, two, custom = object(), object(), object()
    body = SimpleNamespace(pieces=(
        SimpleNamespace(key="left", render_data=one),
        SimpleNamespace(key="right", render_data=two),
    ))
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", body),
        ResolvedManufacturingPart("custom:1", custom),
        ResolvedManufacturingPart("door_c1", object()),
        ResolvedManufacturingPart("door_c2", object()),
        ResolvedManufacturingPart("box_body:divider:1", object()),
    ))
    return geometry, one, two, custom


def test_physical_sheets_multiply_without_name_or_topology_grouping():
    geometry, one, two, custom = inventory()
    rows = resolved_quantity_physical_demands((
        ResolvedQuantityVersion("quantity-v1", 30, geometry),
        ResolvedQuantityVersion("quantity-v2", 20, geometry),
    ), per_box_counts={"custom:1": 2, "custom:999": 999})
    totals = {}
    for row in rows:
        totals[row.physical_id] = totals.get(row.physical_id, 0) + row.quantity
    assert totals == {
        "box_body:left": 50, "box_body:right": 50, "custom:1": 100,
        "door_c1": 50, "door_c2": 50, "box_body:divider:1": 50,
    }
    assert rows[0].render_data is one and rows[1].render_data is two
    assert rows[2].render_data is custom
    assert rows[0].source_part_id == "box_body"


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_invalid_multiplicity_fails_before_any_demand(count):
    geometry, *_ = inventory()
    with pytest.raises(ValueError, match="positive integer"):
        resolved_quantity_physical_demands(
            (ResolvedQuantityVersion("quantity-v1", 1, geometry),),
            per_box_counts={"custom:1": count})


def test_duplicate_physical_or_version_identity_fails_closed():
    geometry, *_ = inventory()
    version = ResolvedQuantityVersion("quantity-v1", 1, geometry)
    with pytest.raises(ValueError, match="unique"):
        resolved_quantity_physical_demands((version, version))
    same = SimpleNamespace(parts=(geometry.parts[0], geometry.parts[0]))
    with pytest.raises(ValueError, match="duplicate physical"):
        resolved_quantity_physical_demands((replace(version, geometry=same),))


@pytest.mark.parametrize("family,back_mode,layers", [("金庫型", "FULL", 1)] + [("受電箱", mode, layers) for mode in ("FULL", "HALF", "BACK_OPENING") for layers in (1, 2)])
def test_real_quantity_bom_30_plus_20_custom_100_and_read_only(family, back_mode, layers, tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    from gui_modules.application import receiving_mode_controls
    from gui_modules.application import fold_designer_composition_receiving as modes
    from phase6_quantity_manufacturing import resolve_quantity_manufacturing_for_app
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2

    root = tk.Tk()
    root.withdraw()
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set(family)
        root.update()
        app = main.open_original_fold_designer()
        root.update()
        if family == "受電箱":
            monkeypatch.setattr(receiving_mode_controls, "ask_initial_dimensions",
                                lambda *a: dict(w=900, h=1700, d=400))
            assert modes._switch_mode(bridge._phase6_composition(app), vars(bridge), "quantity")
            root.update()
            from ae_engine.receiving_quantity_box import update_common_box
            composition = bridge._phase6_composition(app)
            common = update_common_box(modes._current_mode_snapshot(composition, vars(bridge)),
                                       dict(back_panel_mode=back_mode, inner_door_layers=layers))
            if layers == 2:
                # Configure the second *actual* panel via the existing Door
                # topology. The layers label alone must never invent a sheet.
                common["inner_doors"].append(dict(stable_id="lower", cell_key="0:1",
                    included_frame_sides=["top", "left", "right"]))
                common["receiving_quantity_box"]["door_state"]["inner_doors"] = deepcopy(common["inner_doors"])
                common["receiving_layout"]["sets"][0]["bays"][0]["door_state"]["inner_doors"] = deepcopy(common["inner_doors"])
            modes._apply_mode_snapshot(composition, vars(bridge), common)
            root.update()
        workspace = app.designer_workspace
        custom = workspace.add_custom_part(
            display_name="加強板", fold_axis="X", transverse_length=234, per_box_count=2)
        removed = workspace.add_custom_part(
            display_name="加強板", fold_axis="Y", transverse_length=321, per_box_count=7)
        workspace.remove_part(removed)
        controls = app.receiving_mode_controls.quantity_editor
        controls.count_var.set("30")
        assert controls.commit_count()
        first = workspace.quantity_model.selected_version_id
        controls.add()
        second = workspace.quantity_model.selected_version_id
        controls.count_var.set("20")
        assert controls.commit_count()
        workspace.quantity_model.set_version_features(
            second, "head", [CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(10, 0))])
        controls.ports["select"](first)
        controls.refresh()
        root.update()
        path = tmp_path / "bom.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
        assert app.save_project_file_as()
        disk = path.read_bytes()
        restored = project.read_project(path)["snapshot"]
        assert restored["custom_parts"]["items"][custom]["per_box_count"] == 2
        before = deepcopy(workspace.snapshot())
        calculations = app._phase6_update_scheduler._metrics["calculation_flushes"]
        renders = []
        monkeypatch.setattr(app.renderer, "render", lambda *a, **kw: renders.append(True))
        import time, json, ezdxf
        import phase6_manufacturing_service as service
        from ae_engine import manufacturing_api as api
        from phase6_final_scene_view import Phase6FinalSceneViewAdapter
        calls = dict(manufacturing=0, build=0, dxf_read=0, final_scene=0)
        def counted(name, original):
            def run(*a, **kw):
                calls[name] += 1
                return original(*a, **kw)
            return run
        monkeypatch.setattr(service, "resolve", counted("manufacturing", service.resolve))
        monkeypatch.setattr(api, "build_part_render_data", counted("build", api.build_part_render_data))
        monkeypatch.setattr(ezdxf, "readfile", counted("dxf_read", ezdxf.readfile))
        monkeypatch.setattr(Phase6FinalSceneViewAdapter, "build_request", counted("final_scene", Phase6FinalSceneViewAdapter.build_request))
        started = time.perf_counter()
        batch = resolve_quantity_manufacturing_for_app(app)
        receipt = dict(calls, render=len(renders),
            calculation=app._phase6_update_scheduler._metrics["calculation_flushes"]-calculations,
            wall_seconds=time.perf_counter()-started)
        (tmp_path / "quantity-bom-performance.json").write_text(json.dumps(receipt, indent=2))
        print("QUANTITY_BOM_PERFORMANCE=" + json.dumps(receipt))
        assert calls["manufacturing"] == 2
        assert calls["final_scene"] == 0
        assert [version.piece_count for version in batch.versions] == [30, 20]
        assert [version.version_id for version in batch.versions] == [first, second]
        totals = {}
        for row in batch.demands:
            totals[row.physical_id] = totals.get(row.physical_id, 0) + row.quantity
        assert totals[custom] == 100 and removed not in totals
        assert len(totals) > 3
        assert all(total == (100 if key == custom else 50) for key, total in totals.items())
        assert batch.versions[0].geometry.part("head").render_data.scene.primitives != batch.versions[1].geometry.part("head").render_data.scene.primitives
        assert workspace.snapshot() == before
        assert path.read_bytes() == disk
        assert not renders
        assert app._phase6_update_scheduler._metrics["calculation_flushes"] == calculations
        assert not errors, errors
        if family == "受電箱":
            panels = [key for key in totals if key.startswith("inner_door:") and key.endswith(":panel")]
            assert len(panels) == layers
            assert "box_body:box_body_back" in totals
            for _, _, request in batch.requests:
                source = dict(request.input_snapshot)
                assert len(source["receiving_layout"]["sets"]) == 1
                assert len(source["receiving_layout"]["sets"][0]["bays"]) == 1
                assert not source["receiving_layout"]["sets"][0].get("joints", [])
    finally:
        root.destroy()


@pytest.mark.parametrize("family", ["RO", "未知"])
def test_formal_family_parts_feed_same_physical_demand_boundary(family):
    from ae_engine.contracts import BoxBodyPartSpec, DoorPartSpec
    from ae_engine.manufacturing_api import build_part_render_data
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
    profile = profile_to_fold_segments(build_box_body_profile(dict(model=family, w=400, h=600, d=250, t=2, fw=15, zl1=15, zl2=15, zr1=15, zr2=15, z_comp=0)))
    body = build_part_render_data(BoxBodyPartSpec(400, 600, 250, 2, 15, model_name=family, fold_profile=profile))
    door = build_part_render_data(DoorPartSpec(400, 600, 2, 15, model_name=family))
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", body), ResolvedManufacturingPart("door", door)))
    rows = resolved_quantity_physical_demands((ResolvedQuantityVersion("quantity-v1", 30, geometry),
                                              ResolvedQuantityVersion("quantity-v2", 20, geometry)))
    assert len(rows) == 4
    assert sum(row.quantity for row in rows if row.physical_id == "door") == 50
    assert rows[0].render_data is body
