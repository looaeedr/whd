# -*- coding: utf-8 -*-
"""Regression tests for Round 8 deep-audit bug fixes (36 bugs across 31 modules)."""
from __future__ import annotations

import math
from enum import Enum
from types import SimpleNamespace
import pytest


def test_r8_01_pad_bom_demands_rejects_boolean_layer_index():
    """receiving_nfb_pad_delivery: boolean layer_index must not match integer tier 0 or 1."""
    from ae_engine.receiving_nfb_pad_delivery import pad_bom_demands_from_committed_snapshot

    snapshot = {
        "nfb_config_submitted": True,
        "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"},
        "nfb_config": {
            "layer_count": 2,
            "holes": [
                {"layer_index": False, "model_filename": "nfbv5:SHIHLIN:BM100-CN"},
                {"layer_index": True, "model_filename": "nfbv5:SHIHLIN:BM100-CN"},
            ],
        },
    }
    # Neither False nor True is a valid integer tier; no PAD demands should be matched
    assert pad_bom_demands_from_committed_snapshot("v1", snapshot, piece_count=1) == ()


def test_r8_02_inspect_pad_base_seating_rejects_boolean_thickness_and_z():
    """receiving_nfb_pad_fit_witness: boolean plate_thickness_mm, base_front_world_z_mm, or rise_mm must fail closed."""
    from ae_engine.receiving_nfb_pad_fit_witness import inspect_pad_base_seating

    pattern = SimpleNamespace(
        plate_thickness_mm=True,
        rise_mm=10.0,
        tooling_revision="v1",
    )
    pad_draft = SimpleNamespace(
        part_id="pad:1",
        parent_base_id="base_plate",
        owner_hole_id="h1",
        manufacturing_ready=False,
        pattern=pattern,
    )
    skin = SimpleNamespace(
        part_id="pad:1",
        parent_base_id="base_plate",
        owner_hole_id="h1",
        manufacturing_ready=False,
        four_tab_mesh_mating_verified=True,
        base_front_world_z_mm=0.0,
        world_triangles=(((0.0, 0.0, -2.0), (1.0, 0.0, 10.0), (0.0, 1.0, 10.0)),),
    )
    with pytest.raises(ValueError, match="PAD_FIT_ACTUAL_Z_SOURCE_MISSING"):
        inspect_pad_base_seating(skin, pad_draft)


def test_r8_03_build_nfb_pad_draft_part_rejects_nonfinite_and_bad_bend_stations():
    """receiving_nfb_pad_part: non-finite formed_height_mm or wrong-length bend_stations_x_mm must raise ValueError."""
    from ae_engine.receiving_nfb_pad_generator import PadPattern, read_pad_tooling_rule
    from ae_engine.receiving_nfb_pad_part import build_nfb_pad_draft_part

    rule = read_pad_tooling_rule()
    bad_pattern = PadPattern(
        switch_index=0,
        brand="SHIHLIN",
        model="BM100-CN",
        formed_width_mm=50.0,
        formed_height_mm=float("inf"),
        plate_thickness_mm=2.0,
        reference_depth_mm=68.0,
        switch_depth_mm=60.0,
        rise_mm=8.0,
        side_leg_blank_mm=20.0,
        centre_web_blank_mm=50.0,
        blank_width_mm=90.0,
        bend_stations_x_mm=(22.0, 72.0),
        formed_outline_xy_mm=((0.0, 0.0), (50.0, 0.0), (50.0, 100.0), (0.0, 100.0)),
        unfolded_outline_xy_mm=((0.0, 0.0), (94.0, 0.0), (94.0, 100.0), (0.0, 100.0)),
        pad_screw_centres_xy_mm=((25.0, 30.0), (25.0, 70.0)),
        pad_unfolded_screw_centres_xy_mm=((47.0, 30.0), (47.0, 70.0)),
        screw_diameter_mm=5.0,
        base_square_holes_xy_mm=(((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)),) * 4,
        base_screw_centres_xy_mm=((25.0, 30.0), (25.0, 70.0)),
        tooling_revision=rule.revision,
        manufacturing_ready=False,
    )
    with pytest.raises(ValueError, match="PAD 共用折線與含凸耳外框不一致"):
        build_nfb_pad_draft_part(bad_pattern, parent_base_id="base_plate", owner_hole_id="h1")


def test_r8_04_committed_nfb_pad_draft_parts_rejects_boolean_t(monkeypatch):
    """receiving_nfb_pad_operator_parts: boolean snapshot['t'] must not coerce to 1.0."""
    import ae_engine.receiving_base_plate_config as bpc_mod
    import ae_engine.receiving_nfb_committed_final_scene as cfs_mod
    import ae_engine.receiving_nfb_model_identity as id_mod
    import ae_engine.receiving_nfb_numeric_catalog as cat_mod
    import ae_engine.receiving_nfb_pad_operator_parts as mod
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT

    fake_hole = SimpleNamespace(
        slot_index=0,
        layer_count=1,
        model_ref="nfbv5:SHIHLIN:BM100-CN",
        brand="SHIHLIN",
        physical_hole_id="h1",
    )
    fake_spec = SimpleNamespace(dimensionally_complete=True, depth_mm=68.0)
    monkeypatch.setattr(bpc_mod, "receiving_base_plate_values", lambda _s: {"receiving_bend_pattern": RECEIVING_BASE_PATTERN_LEFT})
    monkeypatch.setattr(cfs_mod, "_submitted_csv_holes", lambda _s: ("inner_door_0_0", (fake_hole,)))
    monkeypatch.setattr(id_mod, "parse_numeric_model_ref", lambda _r: ("SHIHLIN", "BM100-CN"))
    monkeypatch.setattr(cat_mod, "model_spec", lambda *_a: fake_spec)

    with pytest.raises(ValueError, match="PAD 板厚必須為有限正數"):
        mod.committed_nfb_pad_draft_parts({"model": "受電箱", "nfb_config_submitted": True, "t": True})


def test_r8_05_trial_v5_screws_rejects_boolean_t_in_pad_generation():
    """receiving_nfb_v5_actual_base_screws: boolean snapshot['t'] is rejected."""
    import inspect
    from ae_engine import receiving_nfb_v5_actual_base_screws as mod

    src = inspect.getsource(mod.trial_v5_screws_on_existing_receiving_base)
    assert 'if isinstance(raw_t, bool) or not isinstance(raw_t, (int, float)):' in src


def test_r8_06_pad_pair_manufacturing_validates_pad_square_owner_counts():
    """receiving_nfb_pad_pair_manufacturing: owner tuple count and 4-square count per owner are strictly verified."""
    import inspect
    from ae_engine import receiving_nfb_pad_pair_manufacturing as mod

    src = inspect.getsource(mod.export_verified_pad_base_part_only)
    assert "expected_owners = {(row.owner_hole_id, 4) for row in members}" in src


def test_r8_07_08_live_base_preview_rejects_bool_and_nan_dimensions_and_offsets():
    """receiving_nfb_v5_live_base_preview: boolean/NaN snapshot w/t or base_spec width/thickness are rejected."""
    from ae_engine.contracts import BasePlatePartSpec
    from ae_engine.receiving_nfb_v5_live_base_preview import preview_v5_on_existing_receiving_base
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER

    spec = BasePlatePartSpec(
        width=600.0,
        height=500.0,
        thickness=2.0,
        shrink_top=35.0,
        shrink_bottom=35.0,
        shrink_left=18.0,
        shrink_right=18.0,
        bend=20.0,
        model_name="受電箱",
        receiving_bend_pattern=RECEIVING_BASE_PATTERN_CENTER,
        physical_id="base_plate",
    )
    door = SimpleNamespace(hole_ids=("h1",))
    with pytest.raises(ValueError, match="NFB V5 底板寬／板厚與目前受電箱不符"):
        preview_v5_on_existing_receiving_base(
            {"w": float("nan"), "t": 2.0},
            "inner_door_0_0",
            door=door,
            configured_holes=(),
            base_spec=spec,
        )
    with pytest.raises(ValueError, match="NFB V5 底板寬／板厚與目前受電箱不符"):
        preview_v5_on_existing_receiving_base(
            {"w": 600.0, "t": True},
            "inner_door_0_0",
            door=door,
            configured_holes=(),
            base_spec=spec,
        )


def test_r8_09_require_source_derived_real_plate_rejects_nan_and_bool(monkeypatch):
    """receiving_nfb_v5_part_only_manufacturing: NaN on base_spec or bool on snapshot['w']/['t'] is rejected."""
    import ae_engine.receiving_nfb_v5_part_only_manufacturing as mod
    from ae_engine.contracts import BasePlatePartSpec

    monkeypatch.setattr(
        mod,
        "receiving_base_plate_values",
        lambda _s: {
            "h": 500.0,
            "base_plate_shrink_top": 35.0,
            "base_plate_shrink_bottom": 35.0,
            "base_plate_shrink_left": 18.0,
            "base_plate_shrink_right": 18.0,
            "base_plate_bend": 20.0,
            "receiving_bend_pattern": "CENTER",
            "receiving_nfb_depth_pair_mm": None,
        },
    )
    nan_spec = BasePlatePartSpec(
        width=float("nan"),
        height=500.0,
        thickness=2.0,
        shrink_top=35.0,
        shrink_bottom=35.0,
        shrink_left=18.0,
        shrink_right=18.0,
        bend=20.0,
        model_name="受電箱",
        receiving_bend_pattern="CENTER",
        physical_id="base_plate",
    )
    with pytest.raises(ValueError, match="CSV_BASE_EXPORT_PARTSPEC_VS_LIVE_SOURCE_MISMATCH"):
        mod._require_source_derived_real_plate({"w": 600.0, "t": 2.0}, nan_spec)

    valid_spec = BasePlatePartSpec(
        width=1.0,
        height=500.0,
        thickness=2.0,
        shrink_top=35.0,
        shrink_bottom=35.0,
        shrink_left=18.0,
        shrink_right=18.0,
        bend=20.0,
        model_name="受電箱",
        receiving_bend_pattern="CENTER",
        physical_id="base_plate",
    )
    with pytest.raises(ValueError, match="CSV_BASE_EXPORT_PARTSPEC_VS_LIVE_SOURCE_MISMATCH"):
        mod._require_source_derived_real_plate({"w": True, "t": 2.0}, valid_spec)


def test_r8_10_11_check_q_and_configured_inner_door_finite_guards():
    """receiving_nfb_v5_check_q_preview & receiving_nfb_v5_configured_inner_door: isfinite checks exist."""
    import inspect
    from ae_engine import receiving_nfb_v5_check_q_preview as q_mod
    from ae_engine import receiving_nfb_v5_configured_inner_door as id_mod

    q_src = inspect.getsource(q_mod.check_csv_v5_base_part_only_groups)
    assert "observed.center.x, observed.center.y, observed.radius, x, y" in q_src
    id_src = inspect.getsource(id_mod.trial_configured_nfb_v5_inner_door_render_data)
    assert "if not isfinite(uv_x) or not isfinite(recovered) or abs(x_world - recovered) > 1e-7:" in id_src


def test_r8_12_13_tier_ear_xy_and_z_targets_reject_booleans(monkeypatch):
    """receiving_tier_ear_assembly_xy & receiving_tier_ear_z_targets: reject bool layer_index and bool w/t."""
    import ae_engine.receiving_nfb_base_assembly_xy as bxy_mod
    import ae_engine.receiving_tier_ear_assembly_xy as xy_mod
    from ae_engine.receiving_tier_ear_z_targets import _tier_source_depths

    monkeypatch.setattr(
        bxy_mod,
        "receiving_nfb_layer_centers",
        lambda _s, _d: (SimpleNamespace(layer_part_id="base_plate", layer_index=0, box_world_y_mm=100.0),),
    )
    with pytest.raises(ValueError, match="EAR 焊接腳距來源寬度或板厚無效"):
        xy_mod.resolve_receiving_tier_ear_mating_xy(
            {
                "nfb_config_submitted": True,
                "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"},
                "inner_doors": [{"cell_key": "0:0", "stable_id": "id_0"}],
                "w": 600.0,
                "t": True,
            }
        )

    # Boolean layer_index in _tier_source_depths must be ignored rather than matching tier 0 or 1
    config = {
        "layer_count": 2,
        "holes": [
            {"layer_index": False, "model_filename": "nfbv5:SHIHLIN:BM100-CN"},
            {"layer_index": True, "model_filename": "nfbv5:SHIHLIN:BM100-CN"},
        ],
    }
    assert _tier_source_depths("SHIHLIN", config, 0) == ()
    assert _tier_source_depths("SHIHLIN", config, 1) == ()


def test_r8_14_tier_fixing_contact_receipt_same_and_flat_depth_pair():
    """receiving_tier_fixing_contact_receipt: _same rejects None/bool, and flat base plate keeps depth_pair None."""
    import inspect
    from ae_engine import receiving_tier_fixing_contact_receipt as mod

    assert mod._same(None, 0.0) is False
    assert mod._same(False, 0.0) is False
    assert mod._same(True, 1.0) is False
    assert mod._same(10.0, 10.0) is True
    src = inspect.getsource(mod.validate_receiving_tier_fixing_contact_receipts)
    assert "if center_fold and len(depth.source_depths_mm) == 2" in src


def test_r8_15_cadcraft_command_preview_bridge_wraps_errors(tmp_path):
    """cadcraft_command_preview_bridge: missing DXF or invalid dimensions raise CadcraftCommandProofError."""
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        CadcraftCommandProofError,
        open_cadcraft_hole_editor,
        prepare_whd_cadcraft_commands,
    )

    with pytest.raises(CadcraftCommandProofError, match="CADCRAFT_EDIT_EXCHANGE_INVALID"):
        open_cadcraft_hole_editor(tmp_path / "nonexistent.dxf")

    with pytest.raises(CadcraftCommandProofError, match="INVALID_WHD_FINISHED_FACE_DIMENSIONS"):
        prepare_whd_cadcraft_commands(surface=None, features=(), width=None, height=100.0)


def test_r8_16_cadcraft_control_bridge_rejects_total_mismatch(monkeypatch):
    """cadcraft_control_bridge: total != len(rows) raises CADCRAFT_INSPECTION_COUNT_INCONSISTENT."""
    from gui_modules.editors.cadcraft_control_bridge import CadcraftControlClient, CadcraftControlError

    client = CadcraftControlClient(12345)
    monkeypatch.setattr(
        client,
        "request",
        lambda _m, _p=None: {
            "entities": [{"handle": "1A", "type": "CIRCLE", "layer": "CUTTING", "geometry": {}}],
            "counts": {"CIRCLE": 1},
            "entityCount": 5,  # Server reported 5 total entities while returning only 1
            "skipped": {"count": 0},
            "space": "Model",
            "dirty": False,
        },
    )
    with pytest.raises(CadcraftControlError, match="CADCRAFT_INSPECTION_COUNT_INCONSISTENT"):
        client.inspect()


def test_r8_17_cadcraft_live_return_bridge_wraps_missing_file_and_inspect_error(tmp_path):
    """cadcraft_live_return_bridge: missing ticket.output raises CadcraftCommandProofError instead of FileNotFoundError."""
    from gui_modules.editors.cadcraft_command_preview_bridge import CadcraftCommandProofError
    from gui_modules.editors.cadcraft_live_return_bridge import capture_unsaved_cadcraft_return
    from gui_modules.editors.cadcraft_manual_hole_return_bridge import ManualReturnTicket
    from phase6_hole_editor_session import Phase6HoleEditorSession

    session = Phase6HoleEditorSession("ctx", [])
    ticket = ManualReturnTicket(
        session=session,
        context_key="ctx",
        surface=None,
        width=100.0,
        height=100.0,
        original=(),
        output=tmp_path / "deleted.dxf",
        original_sha256="00" * 32,
    )
    with pytest.raises(CadcraftCommandProofError, match="CADCRAFT_ISSUED_SOURCE_NOT_READABLE"):
        capture_unsaved_cadcraft_return(ticket, port=12345)


def test_r8_18_cadcraft_manual_hole_return_bridge_rejects_bool_and_missing_output(tmp_path):
    """cadcraft_manual_hole_return_bridge: bool dimensions or missing output raise CadcraftCommandProofError."""
    from gui_modules.editors.cadcraft_command_preview_bridge import CadcraftCommandProofError
    from gui_modules.editors.cadcraft_manual_hole_return_bridge import create_manual_return_ticket
    from phase6_hole_editor_session import Phase6HoleEditorSession

    session = Phase6HoleEditorSession("ctx", [])
    with pytest.raises(CadcraftCommandProofError, match="INVALID_WHD_FINISHED_FACE_DIMENSIONS"):
        create_manual_return_ticket(
            session=session,
            surface=None,
            features=(),
            width=True,
            height=100.0,
            output=tmp_path / "missing.dxf",
        )
    with pytest.raises(CadcraftCommandProofError, match="RETURN_DXF_NOT_FOUND_OR_EMPTY"):
        create_manual_return_ticket(
            session=session,
            surface=None,
            features=(),
            width=100.0,
            height=100.0,
            output=tmp_path / "missing.dxf",
        )


def test_r8_19_20_21_hole_editor_controls_composition_and_render():
    """hole_editor_controls, hole_editor_composition, hole_editor_render fixes."""
    import inspect
    from gui_modules.editors import hole_editor_composition as comp_mod
    from gui_modules.editors import hole_editor_render as render_mod
    from gui_modules.editors.hole_editor_controls import HoleEditorIndicatorStateCollector

    assert "if not isinstance(pid, bool) and isinstance(pid, int) and pid > 0:" in inspect.getsource(comp_mod)
    assert 'and context["door_gap_w"] is not None' in inspect.getsource(render_mod.HoleEditorCanvasRenderer.draw_extra)

    collector = HoleEditorIndicatorStateCollector(
        mode_var_provider=lambda: SimpleNamespace(get=lambda: "indicator"),
        layers_var_provider=lambda: SimpleNamespace(get=lambda: None),
        group_vars_provider=lambda: [SimpleNamespace(get=lambda: "99"), SimpleNamespace(get=lambda: None)],
        offset_x_var_provider=lambda: SimpleNamespace(get=lambda: "nan"),
        offset_y_var_provider=lambda: SimpleNamespace(get=lambda: None),
        box_dist_var_provider=lambda: SimpleNamespace(get=lambda: False),
        normalize_state=lambda d: d,
    )
    res = collector.collect()
    assert res["layers"] == 1
    assert res["groups"][0] == 8  # clamped to max 8
    assert res["groups"][1] == 2  # None fallback
    assert res["offset_x"] == 0.0
    assert res["offset_y"] == 0.0


def test_r8_22_box_body_baseline_faces_returns_copy():
    """box_body_view: mutating returned dict/lists must not corrupt host._box_body_baseline_face_cache."""
    from gui_modules.rendering.box_body_view import box_body_baseline_faces

    host = SimpleNamespace(
        _box_body_baseline_face_cache={},
        _baseline_source_model=lambda: "標準箱",
        _box_body_corner_policies=lambda _fw: (None, None),
    )
    ae_mod = SimpleNamespace(
        has_baseline_part=lambda *_a: True,
        baseline_expected_path=lambda *_a: "dummy.dxf",
        baseline_source_fingerprint=lambda _p: "fp1",
        get_box_body_baseline_face_features=lambda *_a, **_kw: {"left": ["f1"], "back": [], "right": []},
    )
    val = {
        "w": 600, "h": 800, "d": 250, "t": 2.0, "fw": 25,
        "zl1": 20, "zl2": 15, "zr1": 20, "zr2": 15, "z_comp": True,
    }
    first = box_body_baseline_faces(host, val, ae_module=ae_mod)
    first["left"].append("corrupted")
    first["extra"] = ["bad"]
    second = box_body_baseline_faces(host, val, ae_module=ae_mod)
    assert second == {"left": ["f1"], "back": [], "right": []}


def test_r8_23_24_25_door_view_interaction_and_panels():
    """door_view, interaction, door.py, and multipart.py fixes."""
    from gui_modules.parts.panels.door import collect_door_input, rebuild_door_layers_config_ui
    from gui_modules.parts.panels.multipart import collect_multipart_input
    from gui_modules.rendering.interaction import _safe_event_time_ms, door_layout_cell_at_canvas_point

    # Tuple keys and inverted bounds in door_layout_cell_at_canvas_point
    assert door_layout_cell_at_canvas_point({(1, 2): (100, 200, 0, 0)}, 50, 100) == (1, 2)
    assert door_layout_cell_at_canvas_point({"2:3": (0, 0, 100, 100)}, 50, 50) == (2, 3)

    # Synthetic Tkinter event with time="??"
    assert _safe_event_time_ms(SimpleNamespace(time="??")) > 0

    # Deepcopy in collect_door_input and collect_multipart_input
    cols = [{"width": 300}]
    d_in = collect_door_input({"door_layout_columns": cols})
    cols[0]["width"] = 999
    assert d_in["door_layout_columns"][0]["width"] == 300

    mp_src = {"items": [1, 2, 3]}
    mp_in = collect_multipart_input(mp_src)
    mp_src["items"].append(4)
    assert mp_in["items"] == [1, 2, 3]

    # rebuild_door_layers_config_ui clamps layers > 6 or None without IndexError
    fake_host = SimpleNamespace(
        door_layers_config_frame=SimpleNamespace(winfo_children=lambda: ()),
        door_indicator_l_var=SimpleNamespace(get=lambda: "99"),
        door_indicator_layer_g_vars=(),
    )
    rebuild_door_layers_config_ui(fake_host)


def test_r8_26_phase6_final_scene_projection_nan_and_bool_guards():
    """phase6_final_scene_projection: _phase6_profile_map handles NaN; _default_number_text handles bool/NaN/Inf."""
    from phase6_final_scene_projection import _default_number_text, _phase6_profile_map

    u, z = _phase6_profile_map(float("nan"), [0.0, 100.0], [(0.0, 0.0), (100.0, 0.0)])
    assert math.isfinite(u) and math.isfinite(z)
    assert (u, z) == (0.0, 0.0)

    assert _default_number_text(True) == "True"
    assert _default_number_text(False) == "False"
    assert _default_number_text(float("nan")) == "nan"
    assert _default_number_text(float("inf")) == "inf"
    assert _default_number_text(12.0) == "12"


def test_r8_27_phase6_zoom_scale_and_3d_limits_reject_nan_and_nonpositive():
    """phase6_final_scene_renderer & phase6_final_scene_view: NaN/<=0 zoom_scale and ratio are safely guarded."""
    from phase6_final_scene_renderer import Phase6FinalSceneView, _scale_current_3d_limits
    from phase6_final_scene_view import _phase6_adjust_zoom_scale

    limits = [(-10.0, 10.0)]
    renderer = SimpleNamespace(
        ax3d=SimpleNamespace(
            get_xlim3d=lambda: limits[0],
            set_xlim3d=lambda a, b: limits.__setitem__(0, (a, b)),
            get_ylim3d=lambda: (-10.0, 10.0),
            set_ylim3d=lambda a, b: None,
            get_zlim3d=lambda: (-10.0, 10.0),
            set_zlim3d=lambda a, b: None,
        )
    )
    _scale_current_3d_limits(renderer, float("nan"))
    _scale_current_3d_limits(renderer, -2.0)
    assert limits[0] == (-10.0, 10.0)

    view = Phase6FinalSceneView(renderer)
    view.zoom_scale = float("nan")
    new_scale = view.adjust_zoom_scale("up")
    assert math.isfinite(new_scale) and new_scale > 0

    owner = SimpleNamespace(final_scene_view=None, _phase6_zoom_scale=float("-inf"))
    owner_scale = _phase6_adjust_zoom_scale(owner, "down")
    assert math.isfinite(owner_scale) and owner_scale > 0


def test_r8_28_29_hole_editor_canvas_view_and_session_finish():
    """phase6_hole_editor_canvas_view & phase6_hole_editor_session fixes."""
    from shapely.geometry import Polygon
    from ae_engine.sheetmetal_features import Vec2
    from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView
    from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession

    # Empty polygon bounds fallback in _build_transform
    view = Phase6HoleEditorCanvasView.__new__(Phase6HoleEditorCanvasView)
    view._pad = 20.0
    frame = SimpleNamespace(
        surface=SimpleNamespace(polygon=Polygon(), outline=()),
        reference_guide=SimpleNamespace(min_point=Vec2(0.0, 0.0), max_point=Vec2(100.0, 200.0)),
        extra_bounds=None,
    )
    tr = view._build_transform(frame, 400, 400)
    cx, cy = tr.world_to_canvas(Vec2(0.0, 0.0))
    assert math.isfinite(tr.scale) and math.isfinite(cx) and math.isfinite(cy)

    # Phase6HoleEditorSession.finish(commit=True) updates state.original
    session = Phase6HoleEditorSession("ctx", ["f1"])
    session.execute(HoleEditorAction.insert("f2"))
    session.finish(commit=True)
    # Subsequent cancel must revert to committed ["f1", "f2"], not pre-commit ["f1"]
    snap = session.finish(commit=False)
    assert snap.features == ("f1", "f2")


def test_r8_30_31_32_manufacturing_adapter_contracts_and_geometry():
    """phase6_manufacturing_adapter, phase6_manufacturing_contracts, phase6_manufacturing_geometry fixes."""
    from phase6_manufacturing_adapter import _profile_value
    from phase6_manufacturing_contracts import ManufacturingResolveRequest, freeze_manufacturing_value
    from phase6_manufacturing_geometry import _phase6_signature_canonical_value

    # _profile_value with len=0.0 vs len=None
    assert _profile_value([{"phase6_key": "k", "len": 0.0}], "k", default=20.0) == 0.0
    assert _profile_value([{"phase6_key": "k", "len": None}], "k", default=20.0) == 20.0

    # freeze_manufacturing_value rejects NaN/Inf
    with pytest.raises(ValueError, match="non-finite float"):
        freeze_manufacturing_value(float("nan"))
    with pytest.raises(ValueError, match="non-finite float"):
        freeze_manufacturing_value(float("inf"))

    # ManufacturingResolveRequest rejects bool or non-finite relief_clearance
    with pytest.raises(TypeError, match="relief_clearance"):
        ManufacturingResolveRequest(relief_clearance=True)
    with pytest.raises(ValueError, match="relief_clearance"):
        ManufacturingResolveRequest(relief_clearance=float("nan"))

    # _phase6_signature_canonical_value does not strip non-Enum objects that happen to have .value
    obj_a = SimpleNamespace(value=1, extra="A")
    obj_b = SimpleNamespace(value=1, extra="B")
    assert _phase6_signature_canonical_value(obj_a) != _phase6_signature_canonical_value(obj_b)


def test_r8_33_34_35_36_settings_and_sync_envelope():
    """phase6_settings_panel_primitives, profile_projection, settings_transitions, sync_envelope fixes."""
    from phase6_box_body_structure import BoxBodyStructureType
    from phase6_settings_panel_primitives import setting_number_text
    from phase6_settings_profile_projection import merge_keyed_profiles
    from phase6_settings_transitions import (
        apply_box_structure_numeric,
        normalize_updates,
        plan_external_sync,
    )
    from phase6_sync_envelope import _UNCHANGED, actual_delta, stable_fingerprint

    # setting_number_text handles bool, NaN, Inf
    assert setting_number_text(True) == "True"
    assert setting_number_text(float("nan")) == "nan"
    assert setting_number_text(float("inf")) == "inf"
    assert setting_number_text(15.0) == "15"

    # merge_keyed_profiles replaces stale existing when defaults has no phase6_key segments
    existing = {"X": [{"len": 100.0, "phase6_key": "old"}], "Y": []}
    defaults = {"X": [{"len": 250.0, "ang": 0}], "Y": [{"len": 300.0, "ang": 0}]}
    merged = merge_keyed_profiles(existing, defaults)
    assert merged["X"][0]["len"] == 250.0

    # normalize_updates rejects bool and NaN for numeric settings
    settings = {"w": 600.0, "flag": False}
    assert normalize_updates(settings, {"w": True}) == {}
    assert normalize_updates(settings, {"w": float("nan")}) == {}
    assert normalize_updates(settings, {"w": 700}) == {"w": 700.0}

    # apply_box_structure_numeric rejects bool and NaN
    with pytest.raises(ValueError, match="有限數值"):
        apply_box_structure_numeric({}, BoxBodyStructureType.TWO_PIECE_W_SPLIT, "seam_bend", True, total_w=600.0)
    with pytest.raises(ValueError, match="有限數值"):
        apply_box_structure_numeric({}, BoxBodyStructureType.TWO_PIECE_W_SPLIT, "seam_bend", float("nan"), total_w=600.0)

    # plan_external_sync rejects bool revision, preserves current_revision on STALE_REVISION, handles non-mapping delta
    assert plan_external_sync({"origin": "main_gui", "revision": True}, last_external_revision=5).reason == "INVALID_REVISION"
    stale = plan_external_sync({"origin": "main_gui", "revision": 2}, last_external_revision=5)
    assert stale.reason == "STALE_REVISION"
    assert stale.revision == 5
    ok_non_map = plan_external_sync({"origin": "main_gui", "revision": 6, "delta": "bad"}, last_external_revision=5)
    assert ok_non_map.accepted is True and ok_non_map.settings == {}

    # actual_delta distinguishes bool from int (1 vs True, 0 vs False) and frozenset is deterministic in stable_fingerprint
    assert actual_delta({"a": 1}, {"a": True}) == {"a": True}
    assert actual_delta({"a": [0]}, {"a": [False]}) == {"a": [False]}
    assert actual_delta({"a": 1}, {"a": 1}) is _UNCHANGED
    assert stable_fingerprint(frozenset({"b", "a"})) == stable_fingerprint(frozenset({"a", "b"}))
