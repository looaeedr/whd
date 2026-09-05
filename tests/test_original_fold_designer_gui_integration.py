import tkinter as tk

import gui


def make_app():
    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    return root, app


def test_main_gui_has_original_fold_designer_entry_and_snapshot_bridge():
    root, app = make_app()
    try:
        assert hasattr(app, "fold_designer_button")
        assert app.fold_designer_button.winfo_exists()
        snap = app._make_original_fold_designer_snapshot()
        assert snap["w"] == float(app.w_var.get())
        assert snap["d"] == float(app.d_var.get())
        assert snap["zl1"] == float(app.zl1_var.get())
        assert snap["fw"] == float(app.fw_z_var.get())
        assert snap["ytop1"] == float(app.ytop1_var.get())
        assert snap["ybottom1"] == float(app.ybottom1_var.get())
        # Corner state remains a legacy/UI projection, while the explicit
        # schema-v2 Joint Graph is the assembly source of truth.
        assert "corner_state" in snap
        assert snap["assembly_joint_schema_version"] == 2
        assert len(snap["assembly_joints"]) >= 4
    finally:
        root.destroy()


def test_designer_result_only_writes_existing_phase6_numeric_data_and_profile_state():
    root, app = make_app()
    try:
        before_t = app.t_var.get()
        before_corner = app.manual_corner_state
        result = app._make_original_fold_designer_snapshot()
        result.update({
            "w": 600, "h": 700, "d": 250,
            "zl1": 18, "zl2": 22, "fw": 30, "zr2": 23, "zr1": 19,
            "ytop1": 17, "ybottom1": 16,
            "box_body_profile": [
                {"len": 18, "phase6_key": "zl1"},
                {"len": 22, "phase6_key": "zl2"},
                {"len": 30, "phase6_key": "fw_left"},
                {"len": 250, "core": "D", "phase6_key": "d_left"},
                {"len": 600, "core": "W", "phase6_key": "w"},
                {"len": 250, "core": "D", "phase6_key": "d_right"},
                {"len": 30, "phase6_key": "fw_right"},
                {"len": 23, "phase6_key": "zr2"},
                {"len": 19, "phase6_key": "zr1"},
            ],
        })
        result["settings"].update({
            "w": 600, "h": 700, "d": 250,
            "zl1": 18, "zl2": 22, "fw": 30, "zr2": 23, "zr1": 19,
            "ytop1": 17, "ybottom1": 16,
        })
        app._apply_original_fold_designer_snapshot(result)
        assert app.w_var.get() == "600"
        assert app.h_var.get() == "700"
        assert app.d_var.get() == "250"
        assert app.zl1_var.get() == "18"
        assert app.zl2_var.get() == "22"
        assert app.fw_z_var.get() == "30"
        assert app.fw_head_var.get() == "30"
        assert app.fw_tail_var.get() == "30"
        assert app.zr2_var.get() == "23"
        assert app.zr1_var.get() == "19"
        assert app.ytop1_var.get() == "17"
        assert app.ybottom1_var.get() == "16"
        assert app.t_var.get() == before_t
        assert app.manual_corner_state is before_corner
        assert app.fold_designer_box_body_profile == result["box_body_profile"]
    finally:
        root.destroy()


def test_open_designer_uses_original_bridge_not_fix9_custom_renderer():
    root, app = make_app()
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks()
        import fold_designer_original as original
        assert type(designer.renderer) is original.Renderer
        assert designer.state.struct_mode == "vault"
        assert app.fold_designer_window.winfo_exists()
        app.fold_designer_window.destroy()
    finally:
        root.destroy()


def test_snapshot_carries_current_part_set_active_context_and_feature_data():
    root, app = make_app()
    try:
        from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
        from ae_engine.sheetmetal_geometry import Vec2

        marker = CircleFeature(20.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(30.0, 40.0))
        app.surface_features["indicator_box"][:] = [marker]
        app.is_indicator_box_var.set(True)
        app.workspace_controller.set_part_presence("indicator_box", True)
        app.workspace_controller.set_active_part("indicator_box")
        snap = app._make_original_fold_designer_snapshot()

        assert "box_body" in snap["existing_parts"]
        assert "door" in snap["existing_parts"]
        assert "indicator_box" in snap["existing_parts"]
        assert snap["active_part"] == "indicator_box"
        assert snap["part_features"]["indicator_box"] == [marker]
        assert snap["part_features"]["indicator_box"][0] is marker
    finally:
        root.destroy()


def test_snapshot_carries_box_body_face_holes_separately_for_renderer_projection():
    root, app = make_app()
    try:
        from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
        from ae_engine.sheetmetal_geometry import Vec2

        left = CircleFeature(10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(20.0, 30.0))
        back = CircleFeature(12.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40.0, 50.0))
        app.box_body_face_features["left"][:] = [left]
        app.box_body_face_features["back"][:] = [back]
        snap = app._make_original_fold_designer_snapshot()

        assert snap["part_face_features"]["box_body"]["left"] == [left]
        assert snap["part_face_features"]["box_body"]["back"] == [back]
    finally:
        root.destroy()


def test_snapshot_can_be_empty_and_bridge_is_responsible_for_default_box_body():
    root, app = make_app()
    try:
        for var in (
            app.export_z_var, app.export_head_var, app.export_tail_var,
            app.export_door_var, app.export_base_plate_var,
        ):
            var.set(False)
        app.is_indicator_box_var.set(False)
        app.surface_features["indicator_box"].clear()
        app.surface_features["indicator_door"].clear()
        snap = app._make_original_fold_designer_snapshot()
        # Export selection is not physical presence. Turning every export flag
        # off must not delete the cabinet parts from the 3D workspace.
        assert snap["existing_parts"] == ["box_body", "head", "tail", "door", "base_plate"]
        assert "indicator_box" not in snap["existing_parts"]
        assert "indicator_door" not in snap["existing_parts"]
    finally:
        root.destroy()


def test_noop_designer_apply_preserves_phase6_feature_objects_and_stores_part_bundle():
    root, app = make_app()
    try:
        from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
        from ae_engine.sheetmetal_geometry import Vec2

        marker = CircleFeature(20.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(30.0, 40.0))
        app.surface_features["door"][:] = [marker]
        snap = app._make_original_fold_designer_snapshot()
        snap["part_profiles"] = {"door": {"X": [{"len": 20}], "Y": [{"len": 20}]}}
        snap["active_part"] = "door"
        app._apply_original_fold_designer_snapshot(snap)

        assert app.surface_features["door"] == [marker]
        assert app.surface_features["door"][0] is marker
        assert app.fold_designer_part_bundle["active_part"] == "door"
        assert "door" in app.fold_designer_part_bundle["part_profiles"]
    finally:
        root.destroy()


def test_designer_endcap_result_updates_all_authoritative_endcap_vars_and_part_spec():
    root, app = make_app()
    try:
        result = app._make_original_fold_designer_snapshot()
        result.update({
            "w": 600, "d": 200, "fw": 30,
            "yl1": 18, "yr1": 19,
            "ytop1": 17, "ybottom1": 16,
        })
        result["settings"].update({
            "w": 600, "d": 200, "fw": 30,
            "yl1": 18, "yr1": 19,
            "ytop1": 17, "ybottom1": 16,
        })
        app._apply_original_fold_designer_snapshot(result)

        assert app.yl1_var.get() == "18"
        assert app.yr1_var.get() == "19"
        assert app.ytop1_var.get() == "17"
        assert app.ybottom1_var.get() == "16"
        assert app.fw_head_var.get() == "30"
        assert app.fw_tail_var.get() == "30"

        val = app.get_float_values()
        spec = app._end_cap_part_spec(val, is_tail=False)
        assert spec.width == 600
        assert spec.depth == 200
        assert spec.frame_width == 30
        assert spec.fold_left == 18
        assert spec.fold_right == 19
        assert spec.fold_top == 17
        assert spec.fold_bottom == 16
    finally:
        root.destroy()


def test_designer_apply_reloads_current_baseline_without_restoring_baseline_defaults():
    root, app = make_app()
    try:
        baseline_before = app.baseline_var.get()
        # Pretend baseline-derived scenes were already cached before entering designer.
        app._door_layout_baseline_cache[("old",)] = object()
        app._box_body_baseline_face_cache[("old",)] = {"left": []}

        result = app._make_original_fold_designer_snapshot()
        result.update({
            "w": 600, "d": 200, "fw": 30,
            "yl1": 18, "yr1": 19,
            "ytop1": 17, "ybottom1": 16,
        })
        result["settings"].update({
            "w": 600, "d": 200, "fw": 30,
            "yl1": 18, "yr1": 19,
            "ytop1": 17, "ybottom1": 16,
        })
        app._apply_original_fold_designer_snapshot(result)

        # Reload means baseline-derived caches are invalidated so the selected
        # baseline DXF is re-read/re-stretched on the next redraw. It must NOT
        # mean calling on_baseline_changed(), which would restore old defaults.
        assert app.baseline_var.get() == baseline_before
        assert app._door_layout_baseline_cache == {}
        assert app._box_body_baseline_face_cache == {}
        assert app.w_var.get() == "600"
        assert app.d_var.get() == "200"
        assert app.fw_head_var.get() == "30"
        assert app.yl1_var.get() == "18"
        assert app.yr1_var.get() == "19"
        assert app.ytop1_var.get() == "17"
        assert app.ybottom1_var.get() == "16"
    finally:
        root.destroy()


def test_committed_verified_assembly_relief_flows_into_endcap_partspec_and_invalidates_on_dimension_change():
    root, app = make_app()
    try:
        val = app.get_float_values()
        snapshot = app._make_original_fold_designer_snapshot()
        head_profiles = app.workspace_controller.profile_for("head") or {}
        import hashlib, json
        from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
        from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION
        structure_payload = json.dumps(
            app.workspace_controller.box_body_structure_state() or {},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        )
        app.assembly_relief_state = {
            "enabled": True,
            "clearance": 0.0,
            "source": {
                **{key: snapshot[key] for key in (
                    "w", "h", "d", "t", "fw", "zl1", "zr1", "yl1", "yr1", "ytop1", "ybottom1", "assembly_type"
                )},
                "relief_contract_version": RELIEF_CONTRACT_VERSION,
                "joint_graph_fingerprint": resolved_joint_graph_fingerprint(app.assembly_joint_state),
                "family_structure_fingerprint": hashlib.sha256(structure_payload.encode("utf-8")).hexdigest(),
                "cabinet_family": app._baseline_source_model(),
                "part_profiles": {"head": head_profiles},
            },
            "parts": {
                "head": {
                    "verified": True,
                    "cuts": [[[0.0, 0.0], [7.0, 0.0], [7.0, 9.0], [0.0, 9.0]]],
                    "measurements": [],
                }
            },
        }

        spec = app._end_cap_part_spec(val, is_tail=False)
        assert spec.resolved_assembly_relief_cuts == (((0.0, 0.0), (7.0, 0.0), (7.0, 9.0), (0.0, 9.0)),)

        changed = dict(val)
        changed["w"] = float(val["w"]) + 1.0
        stale = app._end_cap_part_spec(changed, is_tail=False)
        assert stale.resolved_assembly_relief_cuts == ()
    finally:
        root.destroy()


def test_open_designer_first_assembly_render_has_no_scene_contract_error():
    root, app = make_app()
    try:
        designer = app.open_original_fold_designer()
        for _ in range(6):
            root.update_idletasks()
            root.update()

        assert designer.part_var.get() == "組合體"
        assert designer._phase6_3d_display_mode == "assembly"
        assert designer.final_scene_view.cutting_mesh_error is None
        assert len(designer.final_scene_view.last_cutting_mesh or []) > 0
        app.fold_designer_window.destroy()
    finally:
        root.destroy()
