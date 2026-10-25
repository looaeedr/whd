# -*- coding: utf-8 -*-
"""Regression tests for Round 5 deep-audit bugfixes (#71–#95)."""
from __future__ import annotations

import math
from types import MappingProxyType, SimpleNamespace
import pytest
from shapely.geometry import Polygon

from ae_engine.box_body_piece_features import _clip_layered_profile_feature
from ae_engine.contracts import (
    CustomFoldPartSpec,
    FoldProfileSegment,
    ResolvedManufacturingGeometry,
)
from ae_engine.custom_fold_manufacturing import custom_fold_structural_result
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from ae_engine.drawing_annotation_layout import _quantity_text_box
from ae_engine.dxf_acceptance import _circle_rows_close, _rows_close
from ae_engine.hole_catalog import (
    custom_circle_definition,
    custom_rectangle_definition,
    feature_from_definition,
)
from ae_engine.joint_marking_policy import (
    ResolvedPhysicalMatingRegion,
    validate_expected_region_coverage,
)
from ae_engine.receiving_assignment_core import validate_positions
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_base_fixing_plate_mating import resolve_base_fixing_plate_xy_mating
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_frame_baseline import receiving_frame_source
from ae_engine.receiving_inner_door_pairing import paired_bay_parts, paired_set_parts
from ae_engine.receiving_joint_locks import resolve_receiving_joint_lock_pattern
from ae_engine.receiving_joint_marking import resolve_receiving_joint_markings
from ae_engine.sheetmetal_drawing import TextPrimitive
from ae_engine.sheetmetal_feature_reference import (
    _round_pattern_pitch,
    move_feature_by_reference_distance,
)
from ae_engine.sheetmetal_features import (
    CircleFeature,
    FeatureAnchor,
    FeatureSurface,
    ResolvedProfile,
    Vec2,
    resolve_surface_features,
)
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from gui_modules.editors.cadcraft_command_preview_bridge import (
    CadcraftCommandProofError,
    focus_started_cadcraft_window,
    prepare_whd_cadcraft_commands,
)
from gui_modules.editors.cadcraft_control_bridge import (
    CadcraftControlClient,
    CadcraftControlError,
)
from gui_modules.parts.panels.divider import collect_divider_input
from gui_modules.parts.panels.door import (
    _parse_layout_value,
    normalize_door_indicator_state,
)
from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from phase6_project_file import _normalize_authoritative_door_state
from phase6_quantity_model import (
    QUANTITY_MODE,
    normalize_quantity_snapshot,
    quantity_only_change,
)


def test_bug71_clip_layered_profile_preserves_non_from_dxf_primary_points():
    from ae_engine.sheetmetal_features import ProfileFeature
    feat = ProfileFeature(
        points=(Vec2(-10.0, -10.0), Vec2(10.0, -10.0), Vec2(10.0, 10.0), Vec2(-10.0, 10.0)),
        anchor=FeatureAnchor.BOTTOM_LEFT,
        offset=Vec2(50.0, 50.0),
        layer="CUTTING",
        source_type="custom",
        layered_profiles=(
            ("MARKING", (Vec2(-8.0, -8.0), Vec2(8.0, 8.0)), False),
        ),
    )
    context = SimpleNamespace(
        unfolded_min_x=0.0,
        unfolded_max_x=100.0,
        local_to_unfolded=lambda pt: pt,
    )
    piece = SimpleNamespace(
        structural=SimpleNamespace(
            outline=(Vec2(0.0, 0.0), Vec2(100.0, 0.0), Vec2(100.0, 100.0), Vec2(0.0, 100.0)),
            height=100.0,
        )
    )
    out = _clip_layered_profile_feature(context, feat, Vec2(50.0, 50.0), piece)
    assert len(out) == 2
    sub_layers = [item.layer for item in out]
    assert "CUTTING" in sub_layers
    assert "MARKING" in sub_layers


def test_bug72_custom_fold_terminal_zero_angle_and_bool_rejection():
    spec = CustomFoldPartSpec(
        physical_id="custom:test_part",
        fold_axis="X",
        thickness=2.0,
        transverse_length=100.0,
        fold_profile=(
            FoldProfileSegment(length=40.0, angle=90.0, formed_length=42.0),
            FoldProfileSegment(length=60.0, angle=0.0, formed_length=62.0),
        ),
    )
    res = custom_fold_structural_result(spec)
    assert res.width == pytest.approx(100.0)
    assert len(res.bends) == 1

    with pytest.raises(ValueError):
        custom_fold_structural_result(
            CustomFoldPartSpec(
                physical_id="custom:bad_len",
                fold_axis="X",
                thickness=2.0,
                transverse_length=100.0,
                fold_profile=(
                    FoldProfileSegment(length=True, angle=90.0),
                    FoldProfileSegment(length=60.0, angle=None),
                ),
            )
        )


def test_bug74_display_dimensions_rejects_bool_nan_and_handles_none_in_settings():
    dims_body = resolve_operator_finished_dimensions(
        "box_body",
        snapshot={"w": 600.0, "h": 800.0, "d": 250.0},
        settings={"w": None, "h": True, "d": float("nan")},
    )
    assert dims_body == (600.0, 800.0, 250.0)

    dims_head = resolve_operator_finished_dimensions(
        "head",
        snapshot={"w": None, "d": float("inf")},
        settings={"w": 500.0, "d": 200.0},
    )
    assert dims_head == (500.0, 200.0)


def test_bug75_quantity_text_box_out_of_range_attachment():
    txt = TextPrimitive(
        text="QTY: 2",
        insert=Vec2(10.0, 20.0),
        char_height=5.0,
        layer="MARKING",
        attachment_point=12,
    )
    b = _quantity_text_box(txt)
    assert b.bounds[0] == pytest.approx(10.0)
    assert b.bounds[1] == pytest.approx(20.0)


def test_bug76_dxf_acceptance_collinear_bends_and_circles_tolerance_order():
    expected_bends = (
        ("vertical", 20.0, 0.0, 40.0),
        ("vertical", 20.0, 60.0, 100.0),
    )
    actual_bends = (
        ("vertical", 20.0 - 1e-9, 60.0, 100.0),
        ("vertical", 20.0 + 1e-9, 0.0, 40.0),
    )
    assert _rows_close(expected_bends, actual_bends, tolerance=1e-4) is True

    expected_circles = (
        (50.0, 20.0, 5.0),
        (50.0, 80.0, 5.0),
    )
    actual_circles = (
        (50.0 - 1e-9, 80.0, 5.0),
        (50.0 + 1e-9, 20.0, 5.0),
    )
    assert _circle_rows_close(expected_circles, actual_circles, tolerance=1e-4) is True


def test_bug77_joint_marking_policy_malformed_plane_returns_fail_closed():
    bad_region = ResolvedPhysicalMatingRegion(
        part_id="p1",
        region_id="r1",
        region_role="locator",
        physical_face_kind="flat",
        supporting_plane=((0.0, 0.0), (0.0, 0.0, 1.0)),
        outward_normal=(0.0, 0.0, 1.0),
        world_polygon=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
    )
    res = validate_expected_region_coverage(
        bad_region,
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
    )
    assert res.status == "SKIPPED_FAIL_CLOSED"
    assert res.diagnostic_code == "OVERLAP_AUTHORITY_MISSING"


def test_bug78_hole_catalog_rejects_bool_and_nonpositive_dimensions():
    for bad in (True, False, 0, -5.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            custom_circle_definition(bad)
        with pytest.raises(ValueError):
            custom_rectangle_definition(bad, 10.0)
        with pytest.raises(ValueError):
            custom_rectangle_definition(10.0, bad)

    defn = custom_circle_definition(22.0)
    with pytest.raises(ValueError):
        feature_from_definition(defn, Vec2(50.0, 50.0), 100.0, 100.0, rotation_deg=True)


def test_bug79_sheetmetal_feature_reference_rejects_bool_and_nan():
    circle = CircleFeature(diameter=10.0, anchor=FeatureAnchor.BOTTOM_LEFT, offset=Vec2(20.0, 20.0))
    for bad in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            _round_pattern_pitch(circle, "center", bad)
        with pytest.raises(ValueError):
            _round_pattern_pitch(circle, "gap", bad)


def test_bug80_receiving_inner_door_pairing_rejects_negative_and_bool_indices():
    layout = {
        "sets": [
            {
                "stable_id": "set-1",
                "bays": [{"stable_id": "bay-1", "w": 800, "h": 1800, "d": 400}],
            }
        ]
    }
    for bad_idx in (-1, True, False):
        with pytest.raises((IndexError, ValueError)):
            paired_bay_parts(layout, set_index=bad_idx, bay_index=0)
        with pytest.raises((IndexError, ValueError)):
            paired_bay_parts(layout, set_index=0, bay_index=bad_idx)
        with pytest.raises((IndexError, ValueError)):
            paired_set_parts(layout, set_index=bad_idx)


def test_bug81_receiving_assignment_core_rejects_bool_keys_and_malformed_sets():
    with pytest.raises(ValueError, match="受電箱套／連資料不合法"):
        validate_positions({"sets": ["not-a-dict"]}, ["v1"], {"v1": 1}, {(0, 0): "v1"})

    valid_layout = {"sets": [{"bays": [{}]}]}
    with pytest.raises(ValueError, match="配置連位與目前套／連不一致"):
        validate_positions(valid_layout, ["v1"], {"v1": 1}, {(False, False): "v1"})

    with pytest.raises(ValueError, match="總連數已變動"):
        validate_positions(valid_layout, ["v1"], {"v1": 1}, {(0, 0): "v1"}, expected_counts=[True])


def test_bug82_83_84_receiving_base_and_fixing_plate_validation():
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_CONFIG_INVALID"):
        receiving_base_plate_values(
            {
                "model": "受電箱",
                "receiving_base_plate": {
                    "pattern": RECEIVING_BASE_PATTERN_LEFT,
                    "height": True,
                    "shrink_top": 20.0,
                    "shrink_bottom": 20.0,
                    "shrink_left": 20.0,
                    "shrink_right": 20.0,
                    "bend": 20.0,
                },
            }
        )

    assert (
        receiving_base_fixing_plate_previews(
            {"model": "受電箱", "w": True, "t": 2.0, "receiving_base_plate": {"pattern": RECEIVING_BASE_PATTERN_LEFT}},
            available_parts=("base_plate",),
        )
        == ()
    )

    with pytest.raises(ValueError, match="FIXING_PLATE_GEOMETRY_NONFINITE"):
        resolve_base_fixing_plate_xy_mating(
            {"model": "受電箱", "w": float("nan"), "t": 2.0, "receiving_base_plate": {"pattern": RECEIVING_BASE_PATTERN_LEFT}},
            side="left",
        )


def test_bug85_receiving_frame_baseline_rejects_bool_and_nan():
    # Reject nonphysical dimensions BEFORE reading any external DXF. A NaN
    # cannot be treated as a real width mismatch or short physical span.
    for width, span in (
        (True, 1000.0),
        (float("nan"), 1000.0),
        (90.0, float("nan")),
    ):
        with pytest.raises(ValueError, match="DIMENSIONS_INVALID"):
            receiving_frame_source("left", material_width=width, span=span)
    # Preserve the distinct, source-verified errors for actual finite geometry:
    # the A-frame baseline owns width=90 mm, with a minimum longitudinal span.
    with pytest.raises(ValueError, match="WIDTH_MISMATCH"):
        receiving_frame_source("left", material_width=91.0, span=1000.0)
    with pytest.raises(ValueError, match="SPAN_TOO_SHORT"):
        receiving_frame_source("left", material_width=90.0, span=100.0)


def test_bug86_receiving_joint_locks_rejects_bool_indices():
    layout = {
        "sets": [
            {
                "stable_id": "set-1",
                "bays": [
                    {"stable_id": "bay-1", "w": 800, "h": 1800, "d": 400},
                    {"stable_id": "bay-2", "w": 800, "h": 1800, "d": 400},
                ],
            }
        ]
    }
    with pytest.raises(TypeError):
        resolve_receiving_joint_lock_pattern(layout, set_index=False, joint_index=0)
    with pytest.raises(TypeError):
        resolve_receiving_joint_lock_pattern(layout, set_index=0, joint_index=False)


def test_bug87_receiving_joint_marking_malformed_divider_topology_fails_closed():
    res = resolve_receiving_joint_markings(
        {
            "model": "受電箱",
            "multi_door_enabled": True,
            "door_layout_columns": [[800.0, [float("nan")]]],
            "d": 300.0,
            "t": 2.0,
        },
        ResolvedManufacturingGeometry(parts=()),
        dimensions=(800.0, 1800.0, 300.0),
        sheet_thickness=2.0,
        world_geometry={},
    )
    assert res.results == ()


def test_bug88_hole_editor_canvas_view_layered_profile_empty_primary_points():
    view = Phase6HoleEditorCanvasView(
        canvas=SimpleNamespace(),
        draw_grid=lambda: None,
        render_secondary_scene=lambda *a: None,
        render_resolved_features=lambda *a: None,
    )
    view.transform = SimpleNamespace(world_to_canvas=lambda pt: (float(pt.x), float(pt.y)))
    prof = ResolvedProfile(
        points=(),
        layer="FROM_DXF",
        source_type="test",
        layered_profiles=(("CUTTING", (Vec2(10.0, 20.0), Vec2(30.0, 50.0)), False),),
    )
    assert view._resolved_canvas_rect(prof) == (10.0, 20.0, 30.0, 50.0)

    empty_prof = ResolvedProfile(points=(), layer="FROM_DXF", source_type="test", layered_profiles=())
    assert view._resolved_canvas_rect(empty_prof) is None


def test_bug89_hole_editor_session_rejects_bool_indices():
    with pytest.raises(TypeError):
        HoleEditorAction.select(False)
    with pytest.raises(TypeError):
        HoleEditorAction.preview_all([], selected_index=False)

    session = Phase6HoleEditorSession("door", ["hole0"])
    with pytest.raises(ValueError):
        session.execute(HoleEditorAction("select", index=False))


def test_bug90_quantity_model_preserves_workspace_quantity_on_save_and_validates_both():
    valid_q = {
        "schema": "phase6-quantity-v1",
        "versions": [
            {
                "version_id": "quantity-v1",
                "piece_count": 2,
                "head_features": [],
                "tail_features": [],
            }
        ],
        "selected_version_id": "quantity-v1",
        "next_version_number": 2,
    }
    snap = {
        "active_mode": QUANTITY_MODE,
        "workspace": {
            "active_mode": QUANTITY_MODE,
            "quantity": valid_q,
        },
    }
    saved = normalize_quantity_snapshot(snap, for_save=True)
    assert saved["quantity"]["versions"][0]["piece_count"] == 2

    prev = {"active_mode": QUANTITY_MODE, "quantity": valid_q, "workspace": {"quantity": valid_q}}
    curr_bad_ws = {"active_mode": QUANTITY_MODE, "quantity": valid_q, "workspace": {"quantity": "invalid"}}
    assert quantity_only_change(prev, curr_bad_ws) is False


def test_bug91_project_file_door_state_rejects_bool_and_nan():
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state({"door_nameplate_center_datum_top": True})
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state({"door_nameplate_center_datum_top": float("nan")})
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state({"door_layout_columns": [[True, [500.0]]]})
    with pytest.raises(ValueError):
        _normalize_authoritative_door_state({"door_layout_columns": [[400.0, "500"]]})


def test_bug92_cadcraft_bridges_reject_bool_timeout_pid_and_dimensions():
    with pytest.raises(CadcraftControlError, match="CADCRAFT_INVALID_CONTROL_TIMEOUT"):
        CadcraftControlClient(12345, timeout=True)

    assert focus_started_cadcraft_window(True) is False
    assert focus_started_cadcraft_window(False) is False

    with pytest.raises(CadcraftCommandProofError, match="INVALID_WHD_FINISHED_FACE_DIMENSIONS"):
        prepare_whd_cadcraft_commands(surface=None, features=(), width=True, height=100.0)


def test_bug94_95_door_and_divider_panels_reject_bool_nan_and_handle_none_defaults():
    for bad in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            _parse_layout_value(SimpleNamespace(get=lambda b=bad: b), "欄寬")

    ind = normalize_door_indicator_state(
        {
            "layers": True,
            "groups": "123456",
            "offset_x": float("nan"),
            "offset_y": True,
        }
    )
    assert ind["layers"] == 1
    assert ind["groups"] == [2, 2, 2, 2, 2, 2]
    assert ind["offset_x"] == 0.0
    assert ind["offset_y"] == 0.0

    div = collect_divider_input(
        "divider",
        {"door_layout_columns": [(400.0, (600.0,))], "d": None, "t": None},
        default_depth=250.0,
        default_thickness=2.0,
    )
    assert div["depth"] == 250.0
    assert div["thickness"] == 2.0

    with pytest.raises(ValueError):
        collect_divider_input(
            "divider",
            {"door_layout_columns": [(True, (600.0,))]},
            default_depth=250.0,
            default_thickness=2.0,
        )


@pytest.mark.parametrize("saved,mode,box_distance", [
    ({"enabled": "false", "box_enabled": "false", "is_box_dist": "false"}, "none", False),
    ({"enabled": "true", "box_enabled": "false", "is_box_dist": "0"}, "indicator", False),
    ({"enabled": "false", "box_enabled": "true", "is_box_dist": "1"}, "indicator_box", True),
    ({"enabled": "0", "box_enabled": "0", "is_box_dist": "off"}, "none", False),
    ({"enabled": "garbled", "box_enabled": "unknown", "is_box_dist": "garbled"}, "none", False),
    ({"enabled": True, "box_enabled": False, "is_box_dist": True}, "indicator", True),
])
def test_r5_94_saved_indicator_boolean_text_never_mints_unrequested_holes(
    saved, mode, box_distance,
):
    """Legacy Tk string 'false' must not become a manufactured indicator box."""
    result = normalize_door_indicator_state(saved)
    assert result["mode"] == mode
    assert result["enabled"] is (mode == "indicator")
    assert result["box_enabled"] is (mode == "indicator_box")
    assert result["is_box_dist"] is box_distance


def test_r5_94_explicit_valid_mode_remains_primary_saved_indicator_authority():
    result = normalize_door_indicator_state({
        "mode": "indicator_box", "box_enabled": "false", "enabled": "false",
    })
    assert result["mode"] == "indicator_box"
    assert result["box_enabled"] is True


@pytest.mark.parametrize("bad_index", [-2, -1, 2, 100, True, False])
def test_r5_79_invalid_reference_selection_never_moves_a_different_hole(bad_index):
    """No selected hole (index -1) must not silently select Python's last."""
    from ae_engine.sheetmetal_features import feature_surface_from_rect, feature_finished_point
    from ae_engine.sheetmetal_feature_reference import ReferenceAnchor
    surface = feature_surface_from_rect("reference", Vec2(0., 0.), Vec2(200., 100.))
    holes = (
        CircleFeature(diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(40., 40.)),
        CircleFeature(diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(150., 40.)),
    )
    with pytest.raises(ValueError, match="reference feature index"):
        move_feature_by_reference_distance(
            surface, holes, bad_index, ReferenceAnchor.CENTER,
            200., 100., axis="x", mode="edge", value=30.,
        )
    # The distance display must not silently show another hole either.
    from ae_engine.sheetmetal_feature_reference import reference_distances
    with pytest.raises(ValueError, match="reference feature index"):
        reference_distances(
            surface, holes, bad_index, ReferenceAnchor.CENTER, 200., 100.,
        )
    # A valid index must still move exactly the intended physical hole.
    valid = move_feature_by_reference_distance(
        surface, holes, 0, ReferenceAnchor.CENTER,
        200., 100., axis="x", mode="edge", value=30.,
    )
    assert feature_finished_point(valid, 200., 100.) == Vec2(30., 40.)
    assert holes[0].offset == Vec2(40., 40.)
    assert holes[1].offset == Vec2(150., 40.)
