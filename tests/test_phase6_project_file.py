# -*- coding: utf-8 -*-
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


def test_p6fold_round_trip_is_utf8_and_preserves_feature_types(tmp_path):
    feature = CircleFeature(
        diameter=12.0, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(3.0, -4.0),
        layer="CUTTING", source_type="test",
    )
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-08-22T19:30:00+08:00",
        "snapshot": {"model": "金庫型", "part_features": {"door": [feature]}},
        "final_geometry": {},
    }
    path = tmp_path / "金庫型.p6fold"

    project.write_project(path, payload)
    loaded = project.read_project(path)

    assert path.read_text(encoding="utf-8").startswith("{")
    restored = loaded["snapshot"]["part_features"]["door"][0]
    assert isinstance(restored, CircleFeature)
    assert restored.anchor is FeatureAnchor.PANEL_CENTER
    assert restored.offset == Vec2(3.0, -4.0)


def _render_data():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_line((20, 0), (20, 60), layer="BEND")
    return manufacturing_api.PartRenderData(
        scene=scene,
        material=manufacturing_api.material_polygon_from_final_scene(scene),
        fold_guides=manufacturing_api.fold_guides_from_final_scene(scene),
    )


def test_project_snapshot_saves_all_available_parts_not_only_active_part():
    from phase6_designer_workspace import Phase6DesignerWorkspace
    data = _render_data()
    state = SimpleNamespace(
        profiles={"X": [{"len": 20}, {"len": 60, "core": "W"}, {"len": 20}], "Y": [{"len": 60, "core": "H"}]},
        profiles_vault={"箱身": [{"len": 100, "core": "W"}]},
    )
    part_profiles = {
        "head": bridge.build_endcap_xy_profiles({"w":400,"d":250,"t":2,"fw":25,"yl1":15,"yr1":15,"ytop1":16,"ybottom1":15}, part_key="head"),
        "tail": bridge.build_endcap_xy_profiles({"w":400,"d":250,"t":2,"fw":25,"yl1":15,"yr1":15,"ytop1":16,"ybottom1":15}, part_key="tail"),
        "door": {"X": [{"len": 19}, {"len":331,"core":"門包外 W"}, {"len":15}], "Y": [{"len":15}, {"len":531,"core":"門包外 H"}, {"len":15}]},
    }
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head", "tail", "door"],
        "active_part": "door",
        "part_profiles": part_profiles,
        "part_features": {key: [] for key in ["box_body", "head", "tail", "door"]},
        "part_face_features": {},
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        state=state,
        _phase6_input_snapshot={
            "model": "金庫型", "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
            "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
            "door_gap_w": 3.5, "door_gap_h": 3.5,
            "door_fold_l": 19.0, "door_fold_r": 15.0, "door_fold_t": 15.0, "door_fold_b": 15.0,
            "part_dimensions": {"door": {"width": 335.0, "height": 535.0}},
        },
        _settings_values={}, _phase6_box_whd={"w": 400.0, "h": 600.0, "d": 250.0},
        _phase6_corner_state={}, _phase6_corner_pair_same={},
        _scene_query_callback=lambda part, payload: data,
        baseline_model_var=SimpleNamespace(get=lambda: "金庫型"),
        _phase6_baseline_initial_model="金庫型",
        _save_current_part=lambda notify=False: None,
    )

    saved = bridge._phase6_build_project_snapshot(holder)

    assert saved["schema"] == project.PROJECT_SCHEMA
    assert saved["snapshot"]["workspace"]["active_part"] == "door"
    assert set(saved["final_geometry"]) == {"box_body", "head", "tail", "door"}
    assert all(row["material"]["geometry_type"] == "Polygon" for row in saved["final_geometry"].values())



def test_project_file_controls_are_global_not_embedded_in_3d_settings_footer():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    settings_center = source[source.index("def _phase6_build_settings_center"):source.index("def _hide_original_structure_mode_controls")]
    assert 'text="讀檔"' not in settings_center
    assert 'text="存檔"' not in settings_center
    gui_source = Path(__import__("gui").__file__).read_text(encoding="utf-8")
    assert 'text="開啟專案"' in gui_source
    assert 'text="儲存專案"' in gui_source
    assert 'text="另存新檔"' in gui_source


def test_real_designer_load_button_replaces_workspace_from_p6fold(tmp_path, monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot.update({"model": "自訂", "active_part": "head", "w": 432.0, "h": 654.0, "d": 210.0})
        snapshot["settings"] = dict(snapshot.get("settings") or {})
        snapshot["settings"].update({"w": 432.0, "h": 654.0, "d": 210.0})
        snapshot["workspace"] = {
            "box_body_profile": snapshot.get("box_body_profile") or [],
            "existing_parts": ["box_body", "head"],
            "active_part": "head",
            "part_profiles": snapshot.get("part_profiles", {}),
            "endcap_fw": snapshot.get("endcap_fw", {}),
        }
        snapshot["existing_parts"] = ["box_body", "head"]
        payload = {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-08-23T08:45:00+08:00",
            "snapshot": snapshot,
            "final_geometry": {},
        }
        path = project.write_project(tmp_path / "讀檔測試.p6fold", payload)

        old_designer = app.open_original_fold_designer()
        old_window = app.fold_designer_window
        root.update_idletasks(); root.update()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(path))

        old_designer.load_project_file()
        for _ in range(6):
            root.update_idletasks(); root.update()

        assert float(app.w_var.get()) == pytest.approx(432.0)
        assert float(app.h_var.get()) == pytest.approx(654.0)
        assert float(app.d_var.get()) == pytest.approx(210.0)
        assert set(app._phase6_existing_parts) == {"box_body", "head"}
        assert app.export_head_var.get() is True
        assert app.export_tail_var.get() is False
        assert app.export_door_var.get() is False
        assert app.fold_designer_app is not old_designer
        assert app.fold_designer_window is not old_window
        assert app.fold_designer_app.active_part_key == "head"
        assert set(app.fold_designer_app.available_parts) == {"box_body", "head"}
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_project_argv_and_windows_open_command_support_double_click(tmp_path):
    p = tmp_path / "job.p6fold"
    p.write_text('{"schema":"phase6-fold-project-v1","snapshot":{},"final_geometry":{}}', encoding="utf-8")

    assert project.project_path_from_argv([str(p)]) == p
    assert project.project_path_from_argv(["other.txt"]) is None
    assert project.windows_open_command(r"C:\\CAD\\mycad.exe", frozen=True) == '"C:\\\\CAD\\\\mycad.exe" "%1"'
    cmd = project.windows_open_command(r"C:\\Python\\python.exe", script_path=r"C:\\CAD\\gui.py", frozen=False)
    assert 'gui.py' in cmd and '"%1"' in cmd


def test_real_main_gui_load_restores_workspace_and_opens_saved_part(tmp_path):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot.update({"model": "金庫型", "active_part": "door"})
        snapshot["workspace"] = {
            "box_body_profile": snapshot.get("box_body_profile") or [],
            "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
            "active_part": "door",
            "part_profiles": snapshot.get("part_profiles", {}),
        }
        snapshot["existing_parts"] = list(snapshot["workspace"]["existing_parts"])
        snapshot["w"] = 432.0
        snapshot["settings"] = dict(snapshot.get("settings") or {})
        snapshot["settings"]["w"] = 432.0
        payload = {"schema": project.PROJECT_SCHEMA, "saved_at": "now", "snapshot": snapshot, "final_geometry": {}}
        path = project.write_project(tmp_path / "restore.p6fold", payload)

        designer = app.load_phase6_project(path, open_designer=True)
        root.update_idletasks(); root.update()

        assert float(app.w_var.get()) == pytest.approx(432.0)
        assert designer.active_part_key == "door"
        assert set(designer.available_parts) >= {"box_body", "head", "tail", "door", "base_plate"}
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_main_gui_has_global_project_controls_and_3d_footer_has_no_project_file_buttons():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update_idletasks(); root.update()
        assert app.project_open_button.cget("text") == "開啟專案"
        assert app.project_save_button.cget("text") == "儲存專案"
        assert app.project_save_as_button.cget("text") == "另存新檔"

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        footer_texts = []
        for child in designer.settings_center.winfo_children():
            for sub in child.winfo_children():
                try:
                    footer_texts.append(str(sub.cget("text")))
                except Exception:
                    pass
        assert "讀檔" not in footer_texts
        assert "存檔" not in footer_texts
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_global_save_save_as_and_open_round_trip_project_without_forcing_3d(tmp_path, monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("432")
        app.h_var.set("654")
        app.d_var.set("210")
        app._apply_existing_parts_from_fold_workspace(["box_body", "head"])
        root.update_idletasks(); root.update()

        first = tmp_path / "global-save.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kwargs: str(first))
        saved = app.save_phase6_project_as()
        assert Path(saved) == first
        assert app._phase6_loaded_project_path == str(first)
        payload = project.read_project(first)
        assert payload["snapshot"]["w"] == pytest.approx(432.0)
        assert set(payload["snapshot"]["existing_parts"]) == {"box_body", "head"}
        assert "_runtime_project_path" not in payload["snapshot"]

        # Normal Save reuses the current project path and must not ask for a new one.
        monkeypatch.setattr(
            filedialog, "asksaveasfilename",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("Save must reuse current path")),
        )
        app.w_var.set("444")
        saved_again = app.save_phase6_project()
        assert Path(saved_again) == first
        assert project.read_project(first)["snapshot"]["w"] == pytest.approx(444.0)

        # Global Open restores the committed main project only; it does not force-open 3D.
        app.w_var.set("999")
        app._apply_existing_parts_from_fold_workspace(["box_body", "head", "tail", "door"])
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(first))
        loaded = app.open_phase6_project()
        root.update_idletasks(); root.update()
        assert Path(loaded) == first
        assert float(app.w_var.get()) == pytest.approx(444.0)
        assert set(app._phase6_existing_parts) == {"box_body", "head"}
        assert app.fold_designer_window is None
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_loaded_project_session_baseline_survives_main_committed_recapture(tmp_path):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot["w"] = 400.0
        snapshot["settings"] = dict(snapshot.get("settings") or {})
        snapshot["settings"]["w"] = 400.0
        payload = {"schema": project.PROJECT_SCHEMA, "saved_at": "now", "snapshot": snapshot, "final_geometry": {}}
        path = project.write_project(tmp_path / "baseline.p6fold", payload)

        app.load_phase6_project(path, open_designer=False)
        root.update_idletasks(); root.update()

        assert app.project_controller.loaded_baseline_snapshot()["w"] == pytest.approx(400.0)
        assert app.project_controller.committed_snapshot()["w"] == pytest.approx(400.0)

        app.w_var.set("450")
        app._capture_phase6_committed_snapshot()

        assert app.project_controller.committed_snapshot()["w"] == pytest.approx(450.0)
        assert app.project_controller.loaded_baseline_snapshot()["w"] == pytest.approx(400.0)
    finally:
        root.destroy()


def test_3d_live_edit_updates_committed_state_without_project_draft():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("400")
        app._capture_phase6_committed_snapshot()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        assert app.project_controller.has_draft is False
        designer.left_global_vars["w"].set("500")
        designer.flush_pending_settings()
        for _ in range(4):
            root.update_idletasks(); root.update()

        assert app.project_controller.has_draft is False
        assert app.project_controller.committed_snapshot()["w"] == pytest.approx(500.0)
        assert float(app.w_var.get()) == pytest.approx(500.0)
        assert not hasattr(designer, "confirm_transaction_button")
        assert not hasattr(designer, "cancel_transaction_button")
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_3d_window_close_keeps_already_live_committed_width():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("400")
        app._capture_phase6_committed_snapshot()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.left_global_vars["w"].set("500")
        designer.flush_pending_settings()
        for _ in range(3):
            root.update_idletasks(); root.update()
        assert float(app.w_var.get()) == pytest.approx(500.0)

        app.fold_designer_window.event_generate("<Destroy>") if False else None
        protocol = app.fold_designer_window.protocol("WM_DELETE_WINDOW")
        # Invoke the Tcl command registered by open_original_fold_designer.
        app.fold_designer_window.tk.call(protocol)
        root.update_idletasks(); root.update()

        assert app.project_controller.has_draft is False
        assert app.project_controller.committed_snapshot()["w"] == pytest.approx(500.0)
        assert float(app.w_var.get()) == pytest.approx(500.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_main_connected_designer_project_save_as_persists_current_live_canonical_state(tmp_path, monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("400")
        app._capture_phase6_committed_snapshot()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.left_global_vars["w"].set("500")
        designer.flush_pending_settings()
        for _ in range(3):
            root.update_idletasks(); root.update()

        path = tmp_path / "live-canonical.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kwargs: str(path))
        saved = designer.save_project_file_as()

        assert Path(saved) == path
        assert project.read_project(path)["snapshot"]["w"] == pytest.approx(500.0)
        assert app.project_controller.has_draft is False
        assert app.project_controller.committed_snapshot()["w"] == pytest.approx(500.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()

def test_main_gui_exposes_project_controller_as_the_project_transaction_boundary():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        assert not hasattr(app, "project_session")
        assert app.project_controller.has_draft is False
        assert app.project_controller.project_path is None
    finally:
        if app is not None and getattr(app, "fold_designer_window", None) is not None:
            try:
                app.fold_designer_window.destroy()
            except Exception:
                pass
        root.destroy()


def test_p6fold_round_trip_preserves_endcap_fw_control_mode_and_values(tmp_path):
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-08-23T21:00:00+08:00",
        "snapshot": {
            "fw": 25.0,
            "endcap_fw": {
                "mode": "INDEPENDENT",
                "head": {"follow_box": False, "value": 31.0},
                "tail": {"follow_box": False, "value": 29.0},
            },
        },
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "fw-state.p6fold", payload)
    loaded = project.read_project(path)

    assert loaded["snapshot"]["endcap_fw"]["mode"] == "INDEPENDENT"
    assert loaded["snapshot"]["endcap_fw"]["head"]["value"] == pytest.approx(31.0)
    assert loaded["snapshot"]["endcap_fw"]["tail"]["value"] == pytest.approx(29.0)


def test_legacy_p6fold_read_migrates_assembly_type_to_versioned_joint_graph_without_wrap(tmp_path):
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-08-29T18:00:00+08:00",
        "snapshot": {
            "model": "金庫型",
            "assembly_type": "OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        },
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "legacy-joint.p6fold", payload)
    loaded = project.read_project(path)
    snap = loaded["snapshot"]
    assert snap["assembly_joint_schema_version"] == 2
    assert len(snap["assembly_joints"]) == 8
    for part in ("head", "tail"):
        by_edge = {row["edge"]: row["relation"] for row in snap["assembly_joints"] if row["subject_part"] == part}
        assert by_edge == {"TOP": "OVERLAY", "BOTTOM": "INSERT", "LEFT": "OVERLAY", "RIGHT": "OVERLAY"}
    assert all(row["source"] == "LEGACY_MIGRATED" for row in snap["assembly_joints"])
    assert not any(row["relation"] == "WRAP" for row in snap["assembly_joints"])


def test_write_project_persists_versioned_joint_graph_and_user_wrap(tmp_path):
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-08-29T18:30:00+08:00",
        "snapshot": {
            "model": "受電箱",
            "assembly_type": "INSERT_OVERLAY",
            "existing_parts": ["box_body", "head"],
            "assembly_joint_schema_version": 1,
            "assembly_joints": [
                {
                    "joint_id": "head-wrap-rear",
                    "subject_part": "head",
                    "target_part": "box_body",
                    "subject_region": "rear_edge",
                    "target_region": "rear_mating",
                    "relation": "WRAP",
                    "contact_mode": "AUTO",
                    "preserve_side": "AUTO",
                    "relief_intent": "AUTO",
                    "clearance_policy": "ZERO",
                    "solver_constraints": {},
                    "source": "USER_ADDED",
                }
            ],
        },
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "wrap-save.p6fold", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["snapshot"]["assembly_joint_schema_version"] == 2
    rows = raw["snapshot"]["assembly_joints"]
    assert any(row["relation"] == "WRAP" and row["source"] == "USER_ADDED" for row in rows)
    assert {row["edge"] for row in rows if row["source"] == "LEGACY_MIGRATED"} == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    loaded = project.read_project(path)
    assert any(row["relation"] == "WRAP" and row["source"] == "USER_ADDED" for row in loaded["snapshot"]["assembly_joints"])


def test_write_project_migrates_legacy_snapshot_before_bytes_hit_disk(tmp_path):
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "saved_at": "2026-08-29T18:31:00+08:00",
        "snapshot": {"assembly_type": "INSERT", "existing_parts": ["box_body", "head"]},
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "legacy-save.p6fold", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["snapshot"]["assembly_joint_schema_version"] == 2
    assert len(raw["snapshot"]["assembly_joints"]) == 4
    assert {j["edge"] for j in raw["snapshot"]["assembly_joints"]} == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
    assert {j["relation"] for j in raw["snapshot"]["assembly_joints"]} == {"INSERT"}


def test_project_round_trip_preserves_verified_joint_relief_state(tmp_path):
    state = {
        "schema_version": 1,
        "items": {
            "head-wrap-body": {
                "joint_id": "head-wrap-body", "subject_part": "head", "target_part": "box_body",
                "relation": "WRAP", "source": "USER_ADDED", "relief_part": "box_body",
                "topology_levels": 1, "verified": True, "trust_level": "PROVISIONAL_3D",
                "source_material_bounds": [0.0,0.0,100.0,80.0], "source_material_area": 8000.0,
                "cut_polygons": [[[0.0,0.0],[10.0,0.0],[10.0,12.0],[0.0,12.0]]],
                "evidence": {"pre_pair_count": 4, "post_pair_count": 0},
            }
        },
    }
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {"assembly_type":"INSERT_OVERLAY","existing_parts":["box_body","head"],"joint_relief_state":state},
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "joint-relief-state.p6fold", payload)
    loaded = project.read_project(path)
    assert loaded["snapshot"]["joint_relief_state"] == state


def test_p6fold_round_trip_preserves_receiving_bottom_wrap_linkage_and_reserves(tmp_path):
    import phase6_project_file as project

    state = {
        "mode": "INDEPENDENT",
        "head": {"enabled": True, "reserve_u": 3.5, "reserve_v": 2.25},
        "tail": {"enabled": False, "reserve_u": 4.0, "reserve_v": 1.5},
    }
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "assembly_type": "OVERLAY",
            "endcap_bottom_wrap": state,
        },
    }
    path = project.write_project(tmp_path / "receiving-wrap.p6fold", payload)
    loaded = project.read_project(path)

    assert loaded["snapshot"]["endcap_bottom_wrap"] == state
