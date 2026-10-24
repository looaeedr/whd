# -*- coding: utf-8 -*-
"""Regression tests for Round 9 deep audit bugfixes across ae_engine, gui_modules, and phase6."""
from __future__ import annotations

import math
from types import SimpleNamespace
import pytest


def test_round9_ae_engine_receiving_base_and_ear_guards():
    from ae_engine.receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
    from ae_engine.receiving_fixed_plate_side_contact import (
        derive_receiving_ear_side_contact_from_formed_skin,
    )
    from ae_engine.receiving_fixed_plate_side_uv_marking import _fold_guide_flat_segment
    from ae_engine.receiving_fixed_plate_weld_skin_mating import _normal_of_skin
    from ae_engine.receiving_nfb_pad_preview_cache import pad_preview_source_fingerprint
    from ae_engine.receiving_nfb_w800_three_cutting import _three_hole_rows
    from ae_engine.receiving_nfb_x_projection import _physical_w800_basis
    from ae_engine.receiving_nfb_y_projection import _inner_door_y_basis

    with pytest.raises(ValueError, match="positive finite"):
        receiving_base_plate_3d_profiles(
            {"model": "受電箱", "w": True, "t": 2.0},
            {"h": 500.0, "base_plate_bend": 20.0},
        )

    bad_formed = SimpleNamespace(
        physical_z_verified=True,
        manufacturing_ready=False,
        source_sheet_t_mm=True,
        source_bend_y_mm=23.0,
        side_wall_inside_world_x_mm=10.0,
        actual_mid_surface_hinge_y_mm=50.0,
        parent_base_back_skin_world_z_mm=20.0,
        layer_index=0,
    )
    with pytest.raises(ValueError):
        derive_receiving_ear_side_contact_from_formed_skin(bad_formed)

    with pytest.raises(ValueError, match="EAR_SIDE_UV_INVALID_SIDE_BEND_GUIDE"):
        _fold_guide_flat_segment(
            SimpleNamespace(axis="x", position=True, span_start=0.0, span_end=100.0)
        )

    assert _normal_of_skin(
        SimpleNamespace(
            world=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            side=True,
        )
    ) is None

    rd = SimpleNamespace(
        material=SimpleNamespace(is_empty=False, wkb=b"\x01\x03\x00\x00\x00"),
        scene=SimpleNamespace(primitives=()),
        metadata={},
    )
    p1 = SimpleNamespace(part_key="base_plate", placement="A", rotation=(0, 0, 0), offset=(0, 0, 0), render_data=rd)
    p2 = SimpleNamespace(part_key="base_plate", placement="B", rotation=(0, 0, 90), offset=(0, 0, 0), render_data=rd)
    fp1 = pad_preview_source_fingerprint({"model": "受電箱"}, (p1,))
    fp2 = pad_preview_source_fingerprint({"model": "受電箱"}, (p2,))
    assert fp1 != fp2

    from ae_engine.receiving_nfb_w800_three_cutting import NfbW800ThreeRow

    with pytest.raises(ValueError, match="three actual slots"):
        _three_hole_rows(
            {"model": "受電箱"},
            "inner_door:upper:panel",
            (NfbW800ThreeRow(layer_index=0, physical_hole_ids="abc", rotations_deg=(0, 0, 0)),),
        )
    with pytest.raises(ValueError):
        _three_hole_rows(
            {"model": "受電箱"},
            "inner_door:upper:panel",
            (NfbW800ThreeRow(layer_index=0, physical_hole_ids=(" a ", "b", "c"), rotations_deg=(0, 0, 0)),),
        )

    with pytest.raises(ValueError):
        _physical_w800_basis(
            {"model": "受電箱", "w": True, "t": 2.0, "door_layout_columns": [(800.0, [1100.0])]},
            "inner_door:upper:panel",
        )
    with pytest.raises(ValueError):
        _inner_door_y_basis(
            {"model": "受電箱", "h": True, "w": 800.0, "t": 2.0, "door_layout_columns": [(800.0, [1100.0])]},
            "inner_door:upper:panel",
        )


def test_round9_gui_application_editors_and_rendering_guards():
    from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_features import CanvasTransform, CircleFeature, FeatureAnchor
    from gui_modules.application.receiving_base_plate_settings_transaction import (
        commit_receiving_base_plate_settings,
    )
    from gui_modules.application.receiving_ear_side_2d import (
        present_receiving_ear_side_designer_piece_3d,
    )
    from gui_modules.application.receiving_inner_door_hole_editor import (
        inner_door_work_area_guide,
    )
    from gui_modules.application.receiving_nfb_partial_batch_dispatcher import (
        require_highlighted_nfb_inner_doors,
    )
    from gui_modules.application.receiving_nfb_v5_scene_preview import (
        _paint_real_finalscene,
    )
    from gui_modules.editors.cadcraft_command_session_bridge import (
        CadcraftCommandProofError,
        _polygon,
    )
    from gui_modules.editors.cadcraft_new_hole_import import new_hole_from_cadcraft_entity
    from gui_modules.editors.cadcraft_preview_bridge import (
        CadcraftPreviewError,
        build_hole_editor_cadcraft_scene,
    )
    from gui_modules.rendering.canvas_2d import render_secondary_scene
    from gui_modules.rendering.overlays import (
        draw_phase6_corner_dimension_overlay,
        layout_reference_overlay_rects,
    )
    from gui_modules.rendering.transforms import (
        YMirroredPreviewTransform,
        phase6_2d_material_viewport,
    )

    with pytest.raises(ValueError, match="外箱尺寸來源"):
        commit_receiving_base_plate_settings(
            input_snapshot={"model": "受電箱", "w": 600.0, "h": 800.0, "t": 2.0},
            settings_values=None,
            submit_geometry_update=lambda s: None,
            config={},
        )

    ear_host = SimpleNamespace()
    orig_data = SimpleNamespace(metadata={}, scene=SimpleNamespace(primitives=()), material=None)
    res_3d = present_receiving_ear_side_designer_piece_3d(
        ear_host,
        {"model": "受電箱", "nfb_config_submitted": True, "w": True, "h": 800.0, "d": 250.0, "t": 2.0},
        SimpleNamespace(part=lambda k: SimpleNamespace(render_data=SimpleNamespace(pieces=()))),
        SimpleNamespace(role="left_side", render_data=orig_data),
        "box_body:left_side",
    )
    assert res_3d is orig_data
    assert getattr(ear_host, "last_receiving_ear_single_piece_blocker", None) == "EAR_2D_PREVIEW_INVALID_DIMENSIONS"

    with pytest.raises(ValueError, match="door_gap_h"):
        inner_door_work_area_guide(
            {"door_layout_columns": [(800.0, [1100.0])], "door_gap_h": True},
            SimpleNamespace(thickness=2.0, cell_key="0:0", inner_door_id="inner_door:upper:panel"),
            SimpleNamespace(width=800.0, height=1100.0),
        )

    with pytest.raises(TypeError, match="ports required"):
        require_highlighted_nfb_inner_doors(
            None,
            0,
            {0: False},
            allow_held=True,
        )

    with pytest.raises(ValueError, match="展開尺寸不存在"):
        _paint_real_finalscene(SimpleNamespace(), None, "label")

    with pytest.raises(CadcraftCommandProofError, match="INVALID_WHD_FEATURE_FOOTPRINT"):
        _polygon(
            CircleFeature(diameter=True, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0.0, 0.0)),
            100.0,
            100.0,
        )

    with pytest.raises(CadcraftCommandProofError, match="INVALID_CADCRAFT_DXF_ENTITY"):
        new_hole_from_cadcraft_entity(SimpleNamespace())

    with pytest.raises(CadcraftPreviewError, match="有效數值"):
        build_hole_editor_cadcraft_scene(
            surface=None,
            features=(),
            width=True,
            height=100.0,
        )

    scene = DrawingScene()
    scene.primitives.append(
        PolylinePrimitive(
            points=(Vec2(0.0, 0.0), Vec2(10.0, 0.0), Vec2(10.0, 10.0)),
            layer="CUTTING",
            closed=False,
        )
    )
    transform = CanvasTransform(scale=1.0, origin_x=0.0, origin_y=0.0)
    poly_calls = []
    mock_canvas = SimpleNamespace(
        delete=lambda *a: None,
        create_polygon=lambda *a, **kw: poly_calls.append(a),
    )
    render_secondary_scene(
        mock_canvas,
        scene,
        transform,
        scene_renderer=lambda c, s, t: None,
    )
    assert poly_calls == []

    rects = layout_reference_overlay_rects(
        120.0,
        80.0,
        crosshair=(60.0, 40.0),
        feature_rect=(80.0, 60.0, 40.0, 20.0),
        sizes={
            "x_edge": (200.0, 100.0),
            "x_neighbor": (200.0, 100.0),
            "y_edge": (200.0, 100.0),
            "y_neighbor": (200.0, 100.0),
            "panel": (200.0, 100.0),
        },
        x_side="left",
        y_side="top",
    )
    assert "panel" in rects
    assert all(math.isfinite(v) for v in rects["panel"])

    text_calls = []
    overlay_canvas = SimpleNamespace(
        delete=lambda *a: None,
        create_text=lambda x, y, **kw: text_calls.append((x, y, kw)),
    )
    draw_phase6_corner_dimension_overlay(
        overlay_canvas,
        SimpleNamespace(),
        canvas_width=float("nan"),
        text_builder=lambda d: "corner text",
    )
    assert len(text_calls) == 1
    assert text_calls[0][0] == 175.0

    with pytest.raises(ValueError, match="cannot be bool"):
        YMirroredPreviewTransform(transform, True)
    vp = phase6_2d_material_viewport(
        (100.0, 200.0, 10.0, 20.0),
        canvas_width=400.0,
        canvas_height=300.0,
    )
    assert vp[0].scale > 0


def test_round9_phase6_and_ui_text_scale_guards():
    from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
    from phase6_corner_dimension_display import measurement_text
    from phase6_custom_fold_profiles import _validated_custom_part_thickness
    from phase6_derived_part_projection import (
        DerivedPartProjectionRequest,
        DerivedPartRequestAssemblyInput,
        _freeze,
        _thaw,
        build_derived_part_projection_request,
    )
    from phase6_diagnostics import json_safe, material_diagnostic
    from phase6_final_scene_mesh_display import gridless_mesh_collection
    from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin
    from phase6_navigation_view_adapter import (
        pack_right_panel_above_canvas,
        refresh_part_selector,
        refresh_sticky_structure_tree,
    )
    from phase6_part_navigation import operator_part_label
    from phase6_registry_diagnostics_controller import (
        Phase6RegistryDiagnosticsController,
    )
    from phase6_registry_diagnostics_panel import _registry_operator_text
    from phase6_settings_contracts import (
        ExternalModelTransitionRequest,
        ExternalSettingsSyncRequest,
        SettingsStateSnapshot,
        freeze_settings_value,
    )
    from phase6_workspace_navigation_controller import (
        Phase6WorkspaceNavigationController,
    )
    from ui_text_scale import _scaled_size

    assert Phase6CornerDataViewAdapter.zoom_from_event(1.0, delta=True, button=False) is None
    assert Phase6CornerDataViewAdapter.zoom_from_event(float("nan"), delta=120) == pytest.approx(1.12)

    with pytest.raises(ValueError):
        measurement_text(SimpleNamespace(topology_levels=1, primary_u=True, primary_v=5.0))
    with pytest.raises(ValueError):
        measurement_text(SimpleNamespace(topology_levels=1, primary_u=float("nan"), primary_v=5.0))
    assert measurement_text(
        SimpleNamespace(topology_levels=1, primary_u=-0.00001, primary_v=5.0)
    ) == "0×5"

    with pytest.raises(ValueError):
        _validated_custom_part_thickness({"t": True})
    with pytest.raises(ValueError):
        _validated_custom_part_thickness({"t": float("nan")})

    mutable_obj = SimpleNamespace(val=[1, 2])
    frozen_obj = _freeze(mutable_obj)
    mutable_obj.val.append(3)
    assert frozen_obj.val == [1, 2]
    thawed_obj = _thaw(frozen_obj)
    thawed_obj.val.append(4)
    assert frozen_obj.val == [1, 2]

    req = build_derived_part_projection_request(
        DerivedPartRequestAssemblyInput(
            door_part_keys=(),
            door_profiles={},
            base_plate_profiles={},
            divider_profiles={},
            inner_profiles={},
            box_piece_profiles={},
            current_piece_keys=(),
            source_parts=("box_body", "door", "base_plate"),
            available_parts=("box_body", "door", "base_plate"),
            source_part_features={},
            known_feature_keys=(),
            single_door_profiles={},
            single_base_plate_profiles={},
            active_part="door_c1_r1",
            selected_part="base_plate_c1_r1",
            preserve_single_base_plate=False,
        )
    )
    assert isinstance(req, DerivedPartProjectionRequest)
    assert req.active_part_repair == "door"
    assert req.selected_part_repair == "base_plate"

    assert json_safe(float("nan")) is None
    assert json_safe(frozenset([1])) == [1]
    assert material_diagnostic(None)["geometry_type"] == "NoneType"

    with pytest.raises(ValueError, match="cannot be bool"):
        gridless_mesh_collection([], facecolor="#ffffff", opacity=True)

    helper = Phase6FinalSceneRenderHelpersMixin()
    helper.renderer = SimpleNamespace(ax3d=SimpleNamespace(add_collection3d=lambda c: None))
    helper._add_mesh_boundary_lines(
        [[(0.0, 0.0, 0.0), (float("nan"), 1.0, 0.0), (0.0, 1.0, 0.0)]],
        color="#333333",
    )

    spacer_forgot = []
    sticky_host = SimpleNamespace(
        structure_tree_host=SimpleNamespace(winfo_manager=lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
        structure_tree_spacer=SimpleNamespace(winfo_manager=lambda: "pack", pack_forget=lambda: spacer_forgot.append(True)),
    )
    refresh_sticky_structure_tree(sticky_host)
    assert spacer_forgot == [True]

    no_part_var_host = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱"},
        _phase6_3d_display_mode="assembly",
        _phase6_assembly_panel_owner=SimpleNamespace(set_multi_settings_visible=lambda v: setattr(no_part_var_host, "multi_vis", v)),
    )
    refresh_part_selector(
        no_part_var_host,
        tk_end="end",
        operator_selector_keys=lambda p: (),
        label_for_key=lambda k, **kw: k,
        is_box_piece=lambda k: False,
        show_assembly=lambda: None,
        show_corner_data=lambda: None,
        activate_part=lambda k: None,
        refresh_button_states=lambda: None,
        refresh_piece_selector=lambda: None,
        refresh_back_panel=lambda: None,
        refresh_assembly_panel=None,
        refresh_structure_tree=lambda: None,
        refresh_content_switch=lambda: None,
        refresh_status_bar=lambda: None,
    )
    assert getattr(no_part_var_host, "multi_vis", False) is True

    packed_opts = []
    pack_widget = SimpleNamespace(pack=lambda **kw: packed_opts.append(kw), master=None)
    assert pack_right_panel_above_canvas(SimpleNamespace(renderer=None), pack_widget, tk_top="top", tk_x="x") is True
    assert len(packed_opts) == 1

    assert operator_part_label("door_c1_r1", snapshot={"custom_parts": "bad", "workspace": "bad"}) == "第1欄第1門"

    reg_ctrl = Phase6RegistryDiagnosticsController()
    reg_ctrl.save_candidate({"rule_id": "R1"}, saver=lambda r: {"candidate_id": "C1"})
    with pytest.raises(ValueError):
        reg_ctrl.run_formula_matrix(
            {"rule_id": "R1"},
            {"T": True, "FW": 20.0},
            validator=lambda r: r,
            evaluator=lambda r, v: None,
        )
    status_size, status_verify = reg_ctrl.diagnostic_status(
        fallback_enabled=False,
        solutions={"head": None},
        errors={},
        measurement_text=str,
    )
    assert "等待資料庫查詢" in status_size

    replaced = _registry_operator_text(
        "door_c1_r1 + door",
        part_labels={"door": "門板", "door_c1_r1": "上門"},
    )
    assert replaced == "上門 + 門板"

    with pytest.raises(ValueError):
        freeze_settings_value(float("nan"))
    with pytest.raises(TypeError):
        SettingsStateSnapshot(last_external_revision=True)
    with pytest.raises(TypeError):
        ExternalSettingsSyncRequest(revision=True)
    with pytest.raises(TypeError):
        ExternalModelTransitionRequest(model="受電箱", revision=True)

    ws_ctrl = Phase6WorkspaceNavigationController(
        SimpleNamespace(
            available_parts=["box_body", "box_body:left"],
            active_part="box_body:left",
            selected_part="box_body:left",
            remove_part=lambda k: False,
        )
    )
    ws_ctrl.remembered_box_body_child = "box_body:left"
    res = ws_ctrl.remove_part("box_body:left")
    assert res.changed is False
    assert ws_ctrl.remembered_box_body_child == "box_body:left"

    with pytest.raises(ValueError):
        _scaled_size(True, 1.0)
    with pytest.raises(ValueError):
        _scaled_size(10, float("nan"))
    with pytest.raises(ValueError):
        _scaled_size(10, 0.0)
