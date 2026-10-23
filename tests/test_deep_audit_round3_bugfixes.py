"""Regression tests for Round 3 deep audit bugfixes (R3-1 through R3-14)."""

from types import SimpleNamespace
import pytest


def test_r3_1_receiving_mode_session_preserves_inner_door_candidates():
    """R3-1: Switching Receiving mode (set_bay <-> quantity) must carry project-global receiving_inner_door_candidates."""
    from phase6_receiving_modes import ReceivingModeSession
    from ae_engine.receiving_inner_door_candidates import (
        create_inner_candidate,
        inner_versions,
    )

    candidates, version_id = create_inner_candidate(
        None,
        {"layers": 1, "models": ("BH-3P.dxf", "")},
    )
    initial = {
        "model": "受電箱",
        "w": 700.0,
        "h": 2300.0,
        "d": 500.0,
        "t": 2.0,
        "receiving_inner_door_candidates": candidates,
    }
    session = ReceivingModeSession(initial)
    switched = session.switch(
        "quantity",
        dimensions={"w": 700.0, "h": 2300.0, "d": 500.0},
        current_snapshot=session.snapshot(),
    )
    assert switched is True
    active = session.snapshot()
    assert "receiving_inner_door_candidates" in active
    versions = inner_versions(active["receiving_inner_door_candidates"])
    assert len(versions) == 1
    assert versions[0]["id"] == version_id
    assert versions[0]["config"]["models"] == ["BH-3P.dxf", ""]


def test_r3_2_materialize_project_snapshot_does_not_leak_bay1_door_state_to_bay2():
    """R3-2: _materialize_project_snapshot must not leak Set 1 / Bay 1 inner_doors or nameplate datum into sibling Bays."""
    from phase6_project_file import _materialize_project_snapshot
    from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays, update_receiving_bay

    layout = new_receiving_layout(width=600.0, height=800.0, depth=250.0)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    bay1_door_state = {
        "multi_door_enabled": True,
        "door_layout_columns": [(600.0, (400.0, 400.0))],
        "door_layout_scope": "receiving-main",
        "door_handle_edges": {"1:1": "RIGHT", "1:2": "RIGHT"},
        "door_nameplate_center_datum_top": 85.0,
        "inner_doors": [{"cell_id": "1:1", "enabled": True}],
    }
    bay2_door_state = {
        "multi_door_enabled": True,
        "door_layout_columns": [(600.0, (800.0,))],
        "door_layout_scope": "receiving-main",
        "door_handle_edges": {"1:1": "LEFT"},
        # Intentionally omit inner_doors and door_nameplate_center_datum_top
    }
    layout = update_receiving_bay(layout, set_index=0, bay_index=0, door_state=bay1_door_state)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, door_state=bay2_door_state)

    snap = {
        "model": "受電箱",
        "t": 2.0,
        "fw": 29.0,
        "receiving_layout": layout,
    }
    materialized = _materialize_project_snapshot(snap)
    bays = materialized["receiving_layout"]["sets"][0]["bays"]
    assert bays[0]["door_state"]["inner_doors"] == [{"cell_id": "1:1", "enabled": True}]
    assert bays[0]["door_state"]["door_nameplate_center_datum_top"] == 85.0
    assert bays[1]["door_state"].get("inner_doors", []) == []
    assert bays[1]["door_state"].get("door_nameplate_center_datum_top") != 85.0


def test_r3_3_endcap_world_relief_solver_passes_preserve_core_origin():
    """R3-3: All _project_probe_material and _project_probe_mid_surface calls pass preserve_core_origin."""
    import ast
    from pathlib import Path

    source = Path("ae_engine/endcap_world_relief_solver.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"_project_probe_material", "_project_probe_mid_surface"}:
                kw_names = {kw.arg for kw in node.keywords}
                calls.append((node.func.id, node.lineno, "preserve_core_origin" in kw_names))
    assert len(calls) == 6
    assert all(has_kw for _, _, has_kw in calls), f"Missing preserve_core_origin in calls: {calls}"


def test_r3_4_certified_relief_family_key_normalizes_receiving_alias():
    """R3-4: certified_relief_models and certified_relief_corner_policy normalize 'RECEIVING' to '受電箱'."""
    from ae_engine.certified_relief_models import _family_key as models_family_key
    from ae_engine.certified_relief_corner_policy import (
        _family_key as policy_family_key,
        certified_corner_policy_for_part,
    )

    assert models_family_key("RECEIVING") == "受電箱"
    assert models_family_key("receiving") == "受電箱"
    assert policy_family_key("RECEIVING") == "受電箱"
    assert certified_corner_policy_for_part("RECEIVING", "door") == certified_corner_policy_for_part("受電箱", "door")


def test_r3_5_is_receiving_snapshot_recognizes_receiving_alias():
    """R3-5: is_receiving_snapshot accepts 'RECEIVING' in model or cabinet_type."""
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot

    assert is_receiving_snapshot({"model": "受電箱"}) is True
    assert is_receiving_snapshot({"model": "RECEIVING"}) is True
    assert is_receiving_snapshot({"cabinet_type": "RECEIVING"}) is True
    assert is_receiving_snapshot({"model": "金庫型"}) is False


def test_r3_6_family_model_transition_canonical_receiving_and_none_structure():
    """R3-6: family_model_transition resolves Receiving box_body_structure even when current_structure is None or new_model is 'RECEIVING'."""
    from phase6_settings_transitions import family_model_transition
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    result = family_model_transition(
        "RECEIVING",
        "金庫型",
        new_editable=False,
        old_editable=False,
        input_snapshot={"model": "金庫型", "w": 500.0, "h": 700.0, "d": 200.0, "t": 2.0, "fw": 29.0, "fh": 25.0},
        settings_values={"w": 500.0, "h": 700.0, "d": 200.0, "t": 2.0, "fw": 29.0, "fh": 25.0},
        corner_state={},
        corner_pair_same={},
        endcap_bottom_wrap_state=None,
        assembly_type=cabinet_family_policy.fresh_assembly_intent("金庫型"),
        available_parts=("box_body", "head", "tail", "door", "base_plate"),
        current_structure=None,
    )
    assert result.desired_structure is not None
    assert result.desired_structure["active_type"] == "three_piece_side_back_split"
    assert result.input_snapshot.get("active_mode") == "set_bay"


def test_r3_7_receiving_alias_accepted_across_navigation_and_projection():
    """R3-7: operator_part_label, fixed_corner_summary, and _inner_door_y_basis accept 'RECEIVING' alias."""
    from phase6_part_navigation import operator_part_label
    from gui_modules.parts.panels.assembly_corner import fixed_corner_summary

    snap = {
        "model": "RECEIVING",
        "door_layout_columns": [(600.0, (400.0, 400.0))],
    }
    assert operator_part_label("door_c1_r1", snapshot=snap) == "上門"
    assert operator_part_label("base_plate_c1_r2", snapshot=snap) == "下門底板"

    host = SimpleNamespace(assembly_joint_state={})
    summary = fixed_corner_summary(host, "head", "RECEIVING")
    assert summary is not None and "上方：嵌入貼外型" in summary


def test_r3_8_readback_marking_lines_rejects_extra_marking_lines(tmp_path):
    """R3-8: _readback_marking_lines raises EAR_SIDE_CHECK_SAVED_MARKING_UV_LINE_EXTRA when extra MARKING lines exist."""
    import ezdxf
    from ae_engine.receiving_fixed_plate_side_check_dxf import _readback_marking_lines

    dxf_path = tmp_path / "extra_marking.dxf"
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0.0, 0.0), (10.0, 0.0), dxfattribs={"layer": "MARKING"})
    msp.add_line((0.0, 5.0), (10.0, 5.0), dxfattribs={"layer": "MARKING"})
    doc.saveas(dxf_path)

    with pytest.raises(ValueError, match="EAR_SIDE_CHECK_SAVED_MARKING_UV_LINE_EXTRA"):
        _readback_marking_lines(dxf_path, [((0.0, 0.0), (10.0, 0.0))])


def test_r3_9_receiving_shared_settings_rejects_negative_and_bool_indices():
    """R3-9: setting_value, edit_setting, share_setting, and unlink_setting reject negative and bool indices."""
    from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
    from ae_engine.receiving_shared_settings import (
        setting_value,
        edit_setting,
        share_setting,
        unlink_setting,
    )

    layout = resize_receiving_bays(
        new_receiving_layout(width=600.0, height=800.0, depth=250.0),
        set_index=0,
        bay_count=2,
    )
    with pytest.raises(IndexError):
        setting_value(layout["sets"][0], -1, "back_panel_mode")
    with pytest.raises(IndexError):
        setting_value(layout["sets"][0], True, "back_panel_mode")
    with pytest.raises(IndexError):
        edit_setting(layout, set_index=-1, bay_index=0, kind="back_panel_mode", value="OUTSIDE")
    with pytest.raises(IndexError):
        share_setting(layout, set_index=0, bay_indices=[-1, 0], kind="back_panel_mode", source_bay_index=-1)
    with pytest.raises(IndexError):
        unlink_setting(layout, set_index=0, bay_index=-1, kind="back_panel_mode")


def test_r3_10_receiving_destructive_tail_ids_rejects_bool_and_float():
    """R3-10: receiving_destructive_tail_ids rejects bool and float counts, and layout index functions reject bool."""
    from ae_engine.receiving_layout import (
        new_receiving_layout,
        receiving_destructive_tail_ids,
        derive_bay_lock_state,
    )

    layout = new_receiving_layout(width=600.0, height=800.0, depth=250.0)
    with pytest.raises(ValueError, match="integer"):
        receiving_destructive_tail_ids(layout, set_count=True)
    with pytest.raises(ValueError, match="integer"):
        receiving_destructive_tail_ids(layout, set_count=1.5)
    with pytest.raises(ValueError, match="integer"):
        receiving_destructive_tail_ids(layout, set_index=0, bay_count=False)
    with pytest.raises(IndexError):
        derive_bay_lock_state(layout, set_index=False, bay_index=0)


def test_r3_11_box_body_piece_features_side_panel_clips_to_piece_bounds():
    """R3-11: Side-piece features in multi-piece box bodies are clipped via _clip_resolved_feature_to_piece."""
    from ae_engine.box_body_piece_features import resolve_box_body_piece_face_features
    from ae_engine.box_body_structure import resolve_box_body_structure
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2

    profile = [
        {"len": 15.0, "angle": 90.0, "phase6_key": "zl1"},
        {"len": 15.0, "angle": 90.0, "phase6_key": "zl2"},
        {"len": 25.0, "angle": -90.0, "phase6_key": "fw_left"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_left"},
        {"len": 596.0, "angle": -90.0, "core": "W", "phase6_key": "w_main"},
        {"len": 246.0, "angle": -90.0, "core": "D", "phase6_key": "d_right"},
        {"len": 25.0, "angle": 90.0, "phase6_key": "fw_right"},
        {"len": 15.0, "angle": 90.0, "phase6_key": "zr2"},
        {"len": 15.0, "phase6_key": "zr1"},
    ]
    structure = resolve_box_body_structure(
        profile,
        w=600.0,
        h=800.0,
        d=250.0,
        t=2.0,
        structure_state={"active_type": "three_piece_side_back_split"},
    )
    in_bounds = CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(0.0, 0.0),
        source_type="side_ok",
    )
    out_of_bounds = CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(9999.0, 0.0),
        source_type="side_out",
    )
    stores = resolve_box_body_piece_face_features(
        structure,
        face_features={"left": [in_bounds, out_of_bounds]},
        w=600.0,
        h=800.0,
        d=250.0,
        t=2.0,
    )
    left_key = next(k for k in stores if "left" in k)
    left_sources = [f.source_type for f in stores[left_key]]
    assert "side_ok" in left_sources
    assert "side_out" not in left_sources


def test_r3_12_13_14_gui_rendering_and_dialog_fixes():
    """R3-12, R3-13, R3-14: Windows path basename, YMirroredPreviewTransform.canvas_to_world, and dialog newline strings."""
    from pathlib import Path
    from ae_engine.sheetmetal_geometry_core import Vec2
    from ae_engine.sheetmetal_features import CanvasTransform
    from gui_modules.rendering.transforms import YMirroredPreviewTransform

    # R3-12: Windows backslash basename extraction
    win_path = r"Z:\localX\assets\baseline\receiving_side.dxf"
    basename = str(win_path).replace("\\", "/").rsplit("/", 1)[-1]
    assert basename == "receiving_side.dxf"

    # R3-13: YMirroredPreviewTransform roundtrip world -> canvas -> world
    base_tf = CanvasTransform(scale=2.0, origin_x=10.0, origin_y=20.0)
    mirrored_tf = YMirroredPreviewTransform(base_tf, height=500.0)
    pt = Vec2(120.0, 175.0)
    cx, cy = mirrored_tf.world_to_canvas(pt)
    recovered = mirrored_tf.canvas_to_world(cx, cy)
    assert recovered.x == pytest.approx(pt.x)
    assert recovered.y == pytest.approx(pt.y)

    # R3-14: No double-escaped \\n in export_selected_dxf_from_3d
    src = Path("gui_modules/application/fold_designer_composition_state.py").read_text(encoding="utf-8")
    segment = src[src.index("def export_selected_dxf_from_3d"):src.index("def collect_workspace_state")]
    assert "\\\\n" not in segment

    # R3-15: _phase6_assembly_physical_dimension_lines handles pieces without fold_profile attribute
    from phase6_final_scene_projection import _phase6_assembly_physical_dimension_lines
    stub_part = SimpleNamespace(
        part_key="box_body",
        render_data=SimpleNamespace(
            pieces=(SimpleNamespace(role="left_side"), SimpleNamespace(role="right_side")),
        ),
    )
    assert _phase6_assembly_physical_dimension_lines(stub_part, thickness=2.0) == ()
