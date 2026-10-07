# -*- coding: utf-8 -*-
from copy import deepcopy
import pytest
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays, update_receiving_bay, normalize_receiving_layout, project_receiving_bay_legacy_aliases
from ae_engine.receiving_shared_settings import edit_setting, share_setting, unlink_setting, setting_value
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


@pytest.mark.parametrize("depth_alignment", ["FRONT", "REAR"])
@pytest.mark.parametrize("height_alignment", ["BOTTOM", "TOP"])
def test_joint_alignment_places_approved_outer_faces_together(depth_alignment, height_alignment):
    from ae_engine.receiving_layout import receiving_bay_assembly_offsets, update_receiving_joint_alignment
    layout = resize_receiving_bays(new_receiving_layout(width=800, height=1600, depth=350), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=900, height=1500, depth=420)
    layout = update_receiving_joint_alignment(layout, set_index=0, joint_index=0, depth_alignment=depth_alignment, height_alignment=height_alignment)
    left, right = receiving_bay_assembly_offsets(layout)
    assert left[0] + 800 / 2 == right[0] - 900 / 2
    sign = 1 if height_alignment == "TOP" else -1
    assert left[1] + sign * 1600 / 2 == right[1] + sign * 1500 / 2
    sign = 1 if depth_alignment == "FRONT" else -1
    assert left[2] + sign * 350 / 2 == right[2] + sign * 420 / 2


def test_real_settings_preview_exports_every_piece_and_reload_keeps_each_bay(tmp_path, monkeypatch):
    import os
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import hashlib
    from pathlib import Path
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from ae_engine import manufacturing_api as api
    from ae_engine.cabinet_types import receiving
    from ae_engine.receiving_layout import ensure_receiving_layout
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    config = Path("config.ini")
    before = hashlib.sha256(config.read_bytes()).hexdigest()
    counts = []
    figures = []
    original_render = Phase6FinalSceneRenderer.render

    def observe_render(renderer, request):
        result = original_render(renderer, request)
        if not hasattr(renderer.renderer.ax3d, "__getattr__"):
            return result
        counts.append(len(renderer.renderer.ax3d.__getattr__("collections")))
        figures.append(renderer.renderer.ax3d.figure)
        return result

    root = tk.Tk()
    root.withdraw()
    try:
        host = gui.BoxCalculatorGUI(root)
        host.baseline_var.set("受電箱")
        root.update_idletasks()
        root.update()
        app = host.open_original_fold_designer()
        app._ui_text_size_change_callback = lambda value: host._apply_ui_text_size_preference(value, persist=False, notify_designer=False)
        snapshot = ensure_receiving_layout(receiving.apply_family_defaults({"t": 2}))
        layout = resize_receiving_bays(snapshot["receiving_layout"], set_index=0, bay_count=2)
        door = deepcopy(layout["sets"][0]["bays"][1]["door_state"])
        door["door_layout_columns"] = [[900, [1100, 500]]]
        layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=900, depth=420, door_state=door)
        layout = share_setting(layout, set_index=0, bay_indices=[0, 1], source_bay_index=0, kind="head_features")
        layout = edit_setting(layout, set_index=0, bay_index=1, kind="head_features", value=[CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=8)])
        app._phase6_input_snapshot["receiving_layout"] = layout
        composition = bridge._phase6_composition(app)
        namespace = vars(bridge)
        requests = [composition.receiving_bay_preview_request(namespace, 0, i) for i in range(2)]
        assert requests[0].finished_dimensions == (800, 1600, 350)
        assert requests[1].finished_dimensions == (900, 1600, 420)
        from ae_engine.sheetmetal_drawing import CirclePrimitive
        for request in requests:
            head = next(part for part in request.render_data.assembly_parts if part.part_key == "head")
            assert sum(isinstance(primitive, CirclePrimitive) and primitive.radius == 4 for primitive in head.render_data.scene.primitives) == 1
        doors = [next(part for part in request.render_data.assembly_parts if part.part_key == "door_c1_r1") for request in requests]
        assert doors[1].render_data.material.bounds[2] - doors[1].render_data.material.bounds[0] > doors[0].render_data.material.bounds[2] - doors[0].render_data.material.bounds[0]
        assert composition.receiving_bay_preview_request(namespace, 0, 0) is requests[0]
        inventory = []
        for index, request in enumerate(requests):
            for part in request.render_data.assembly_parts:
                physical = tuple(getattr(part.render_data, "pieces", ()) or ())
                rows = [(piece.key, piece.render_data) for piece in physical] if physical else [(part.part_key, part.render_data)]
                for ordinal, (key, data) in enumerate(rows):
                    path = tmp_path / f"bay{index}-part{len(inventory)}.dxf"
                    api.save_part_render_data_dxf(data, path, overwrite=True)
                    assert api.verify_saved_part_render_data_dxf(data, path).ok, key
                    inventory.append(path)
        assert len(inventory) >= 24
        payload = {"schema": project.PROJECT_SCHEMA_V2, "snapshot": {**snapshot, "receiving_layout": layout}, "final_geometry": {}}
        saved = project.write_project(tmp_path / "各連.p6fold", payload)
        loaded = project.read_project(saved)["snapshot"]
        app._phase6_input_snapshot["receiving_layout"] = loaded["receiving_layout"]
        composition.receiving_adapter(namespace, reset=True)
        for index, previous in enumerate(requests):
            current = composition.receiving_bay_preview_request(namespace, 0, index)
            assert current.finished_dimensions == previous.finished_dimensions
            assert [(part.part_key, part.render_data.material.wkb) for part in current.render_data.assembly_parts] == [(part.part_key, part.render_data.material.wkb) for part in previous.render_data.assembly_parts]
        monkeypatch.setattr(Phase6FinalSceneRenderer, "render", observe_render)
        assert composition.open_receiving_layer_preview(namespace, 0)
        root.update_idletasks()
        root.update()
        assert len(counts) >= 2 and counts[1] > counts[0]
        assert not figures[-1].axes[0].texts
        windows = [child for child in app.root.winfo_children() if hasattr(child, "_phase6_receiving_preview_canvas")]
        assert len(windows) == 1
        win = windows[0]
        canvas_widget = win._phase6_receiving_preview_canvas.get_tk_widget()
        initial_scaling = float(root.tk.call("tk", "scaling"))
        for factor in (1.0, 1.2, 1.4):
            root.tk.call("tk", "scaling", initial_scaling * factor)
            root.update_idletasks()
            root.update()
            assert canvas_widget.winfo_height() >= int(win.winfo_height() * 0.55), factor
            assert canvas_widget.winfo_width() >= int(win.winfo_width() * 0.75), factor
        root.tk.call("tk", "scaling", initial_scaling)
        ports = composition.receiving_settings_ports(namespace, 0)
        ports["select"](0)
        editor_args = {}
        monkeypatch.setattr(host, "_open_unified_hole_editor", lambda *args, **kwargs: editor_args.update(kwargs))
        ports["holes"]("tail", (0, 1))
        editor_args["feature_list_override"].append(CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=12))
        editor_args["sync_callback"]()
        shared = ports["row"]()["settings"]["tail_features"]
        assert len(set(shared["refs"].values())) == 1
        for index in (0, 1):
            after_edit = composition.receiving_bay_preview_request(namespace, 0, index)
            tail = next(part.render_data for part in after_edit.render_data.assembly_parts if part.part_key == "tail")
            assert any(isinstance(primitive, CirclePrimitive) and primitive.radius == 6 for primitive in tail.scene.primitives)
            output = tmp_path / f"連{index + 1}_封尾共享編輯.dxf"
            api.save_part_render_data_dxf(tail, output, overwrite=True)
            assert api.verify_saved_part_render_data_dxf(tail, output).ok
        figures[-1].savefig(tmp_path / "每連設定3D.png")
    finally:
        root.destroy()
    assert hashlib.sha256(config.read_bytes()).hexdigest() == before


def five_bays():
    return resize_receiving_bays(new_receiving_layout(width=800, height=1600, depth=350), set_index=0, bay_count=5)


def test_noncontinuous_sharing_is_independent_per_setting_and_unlink_copies_value():
    original = five_bays()
    layout = share_setting(original, set_index=0, bay_indices=[0, 1, 3, 4], source_bay_index=0, kind="back_panel_mode")
    layout = share_setting(layout, set_index=0, bay_indices=[0, 1], source_bay_index=0, kind="inner_door_layers")
    layout = edit_setting(layout, set_index=0, bay_index=4, kind="back_panel_mode", value="HALF")
    layout = edit_setting(layout, set_index=0, bay_index=1, kind="inner_door_layers", value=2)
    selected = layout["sets"][0]
    assert [setting_value(selected, i, "back_panel_mode") for i in range(5)] == ["HALF", "HALF", "FULL", "HALF", "HALF"]
    assert [setting_value(selected, i, "inner_door_layers") for i in range(5)] == [2, 2, 1, 1, 1]
    layout = unlink_setting(layout, set_index=0, bay_index=1, kind="back_panel_mode")
    assert setting_value(layout["sets"][0], 1, "back_panel_mode") == "HALF"
    layout = edit_setting(layout, set_index=0, bay_index=0, kind="back_panel_mode", value="BACK_OPENING")
    assert setting_value(layout["sets"][0], 1, "back_panel_mode") == "HALF"
    assert original == five_bays()


def test_existing_bay_editor_updates_shared_value_and_resize_copies_without_link():
    layout = share_setting(five_bays(), set_index=0, bay_indices=[0, 4], source_bay_index=0, kind="back_panel_mode")
    layout = update_receiving_bay(layout, set_index=0, bay_index=4, back_panel_mode="HALF", width=900)
    assert layout["sets"][0]["bays"][0]["back_panel_mode"] == "HALF"
    assert layout["sets"][0]["bays"][0]["width"] == 800
    layout = resize_receiving_bays(layout, set_index=0, bay_count=6)
    layout = edit_setting(layout, set_index=0, bay_index=4, kind="back_panel_mode", value="FULL")
    assert setting_value(layout["sets"][0], 5, "back_panel_mode") == "HALF"
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    assert len(layout["sets"][0]["settings"]["back_panel_mode"]["refs"]) == 3


def test_head_tail_features_have_separate_links_and_project_per_bay():
    layout = five_bays()
    layout = share_setting(layout, set_index=0, bay_indices=[0, 1], source_bay_index=0, kind="head_features")
    layout = share_setting(layout, set_index=0, bay_indices=[3, 4], source_bay_index=3, kind="tail_features")
    feature = CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=6.4)
    layout = edit_setting(layout, set_index=0, bay_index=1, kind="head_features", value=[feature])
    snap = {"model": "受電箱", "t": 2, "receiving_layout": layout, "surface_features": {"door": [feature]}}
    projected = project_receiving_bay_legacy_aliases(snap, bay_index=0, validate_common=False)
    assert projected["surface_features"]["head"] == [feature]
    assert projected["surface_features"]["tail"] == []
    assert projected["surface_features"]["door"] == [feature]
    assert setting_value(layout["sets"][0], 2, "head_features") == []
    assert snap["surface_features"] == {"door": [feature]}


def test_save_reload_preserves_feature_types_links_brand_and_layers(tmp_path):
    layout = share_setting(five_bays(), set_index=0, bay_indices=[0, 4], source_bay_index=0, kind="head_features")
    layout = edit_setting(layout, set_index=0, bay_index=4, kind="head_features", value=[CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=8)])
    layout = edit_setting(layout, set_index=0, bay_index=2, kind="inner_door_layers", value=2)
    layout["sets"][0]["switch_brand"] = "東元"
    payload = {"schema": project.PROJECT_SCHEMA_V2, "snapshot": {"model": "受電箱", "t": 2, "receiving_layout": layout}, "final_geometry": {}}
    path = project.write_project(tmp_path / "shared.p6fold", payload)
    loaded = project.read_project(path)["snapshot"]["receiving_layout"]
    assert loaded == normalize_receiving_layout(layout)
    value = setting_value(loaded["sets"][0], 0, "head_features")[0]
    assert isinstance(value, CircleFeature) and value.diameter == 8


def test_dangling_refs_and_invalid_layers_fail_closed():
    layout = edit_setting(five_bays(), set_index=0, bay_index=0, kind="inner_door_layers", value=2)
    broken = deepcopy(layout)
    broken["sets"][0]["settings"]["inner_door_layers"]["values"].clear()
    with pytest.raises(ValueError, match="引用不存在"):
        normalize_receiving_layout(broken)
    with pytest.raises(ValueError, match="1 或 2"):
        edit_setting(layout, set_index=0, bay_index=0, kind="inner_door_layers", value=3)


def test_independent_door_partition_rejects_wrong_total_and_roundtrips(tmp_path):
    from ae_engine.receiving_layout import ensure_receiving_layout, ReceivingBayProjectionError
    from ae_engine.cabinet_types import receiving
    snapshot = receiving.apply_family_defaults({"t": 2})
    snapshot = ensure_receiving_layout(snapshot)
    layout = resize_receiving_bays(snapshot["receiving_layout"], set_index=0, bay_count=2)
    invalid = update_receiving_bay(layout, set_index=0, bay_index=1, width=900)
    with pytest.raises(ReceivingBayProjectionError):
        project_receiving_bay_legacy_aliases({**snapshot, "receiving_layout": invalid}, bay_index=1)
    door = deepcopy(layout["sets"][0]["bays"][1]["door_state"])
    door["door_layout_columns"][0][0] = 900
    valid = update_receiving_bay(layout, set_index=0, bay_index=1, width=900, door_state=door)
    one = project_receiving_bay_legacy_aliases({**snapshot, "receiving_layout": valid}, bay_index=0)
    two = project_receiving_bay_legacy_aliases({**snapshot, "receiving_layout": valid}, bay_index=1)
    assert one["door_layout_columns"][0][0] == 800
    assert two["door_layout_columns"][0][0] == 900
    payload = {"schema": project.PROJECT_SCHEMA_V2, "snapshot": two, "final_geometry": {}}
    saved = project.write_project(tmp_path / "doors.p6fold", payload)
    loaded = project.read_project(saved)["snapshot"]
    assert loaded["receiving_layout"] == valid


def test_legacy_switch_topology_migrates_once_into_receiving_sets():
    from ae_engine.receiving_layout import ensure_receiving_layout
    snapshot = {"model": "受電箱", "w": 800, "h": 1600, "d": 350,
                "receiving_switch_layout": {"schema": "receiving-switch-layout-v1", "switch_brand": "東元", "layers": [{"stable_id": "old1", "connection_count": 3}, {"stable_id": "old2", "connection_count": 2}]}}
    migrated = ensure_receiving_layout(snapshot)
    assert "receiving_switch_layout" not in migrated
    assert [len(row["bays"]) for row in migrated["receiving_layout"]["sets"]] == [3, 2]
    assert [row["switch_brand"] for row in migrated["receiving_layout"]["sets"]] == ["東元", "東元"]
    assert ensure_receiving_layout(migrated) == migrated


def test_existing_head_features_migrate_without_losing_other_settings(tmp_path):
    from ae_engine.receiving_layout import ensure_receiving_layout
    feature = CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=12)
    snapshot = ensure_receiving_layout({"model": "受電箱", "w": 800, "h": 1600, "d": 350, "part_features": {"head": [feature]}, "receiving_layout": five_bays()})
    row = snapshot["receiving_layout"]["sets"][0]
    assert all(setting_value(row, i, "head_features") == [feature] for i in range(5))
    saved = project.write_project(tmp_path / "migrated.p6fold", {"schema": project.PROJECT_SCHEMA_V2, "snapshot": snapshot, "final_geometry": {}})
    import json
    raw = json.loads(saved.read_text(encoding="utf-8"))["snapshot"]
    assert "head" not in raw["part_features"]
    assert all("back_panel_mode" not in bay for bay in raw["receiving_layout"]["sets"][0]["bays"])
    loaded = project.read_project(saved)["snapshot"]
    assert setting_value(loaded["receiving_layout"]["sets"][0], 4, "head_features") == [feature]


def test_legacy_head_holes_and_surface_features_migrate_by_role_once(tmp_path):
    from ae_engine.receiving_layout import ensure_receiving_layout
    circle = CircleFeature(anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0), diameter=8)
    snapshot = {"model": "受電箱", "w": 800, "h": 1600, "d": 350,
                "part_features": {"door": [circle]}, "surface_features": {"tail": [circle]},
                "head_holes": [{"type": "圓孔", "x": 20, "y": 30, "params": {"diameter": 12}}],
                "receiving_layout": five_bays()}
    migrated = ensure_receiving_layout(snapshot)
    row = migrated["receiving_layout"]["sets"][0]
    assert setting_value(row, 4, "head_features")[0].diameter == 12
    assert setting_value(row, 4, "tail_features") == [circle]
    assert migrated["part_features"]["door"] == [circle]
    saved = project.write_project(tmp_path / "legacy.p6fold", {"schema": project.PROJECT_SCHEMA_V2, "snapshot": migrated, "final_geometry": {}})
    loaded = project.read_project(saved)["snapshot"]
    assert "head_holes" not in loaded
    assert setting_value(loaded["receiving_layout"]["sets"][0], 4, "head_features")[0].diameter == 12
