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
from ae_engine.dxf_acceptance import _circle_rows_close, _rows_close, _one_to_one_tolerance_match
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


@pytest.mark.parametrize("corrupt", [42, True, object()])
def test_bug95_divider_corrupt_panel_payload_fails_with_controlled_validation(corrupt):
    """Corrupt saved input must not crash the 2D/3D divider panel with TypeError."""
    with pytest.raises(ValueError, match="中隔.*資料"):
        collect_divider_input(
            "divider", corrupt, default_depth=250., default_thickness=2.,
        )


@pytest.mark.parametrize("corrupt", [42, True, [("0:0",)]])
def test_bug95_divider_corrupt_handle_edge_source_fails_before_projection(corrupt):
    payload = {
        "door_layout_columns": [(400., (600.,))],
        "door_handle_edges": corrupt,
        "d": None, "t": None,
    }
    with pytest.raises(ValueError, match="把手"):
        collect_divider_input(
            "divider", payload, default_depth=250., default_thickness=2.,
        )
    assert payload["door_handle_edges"] is corrupt


def test_bug95_divider_valid_handle_edges_keep_original_geometry_and_depth_defaults():
    actual = collect_divider_input(
        "divider",
        {"door_layout_columns": [(400., (600.,))],
         "door_handle_edges": {"0:0": "LEFT"}, "d": None, "t": None},
        default_depth=250., default_thickness=2.,
    )
    assert actual["handle_edges"] == {"0:0": "LEFT"}
    assert actual["columns"] == ((400., (600.,)),)
    assert (actual["depth"], actual["thickness"]) == (250., 2.)


@pytest.mark.parametrize("malformed", [42, True, object()])
def test_bug84_invalid_xy_mating_snapshot_cannot_escape_as_unhandled_typeerror(malformed):
    """XY fitting needs authoritative cabinet W/T; nonmapping source fails closed."""
    with pytest.raises(ValueError, match="FIXING_PLATE_GEOMETRY_NONFINITE"):
        resolve_base_fixing_plate_xy_mating(malformed, side="left")


def test_bug84_actual_xy_mating_still_requires_source_side_and_physical_dimensions():
    with pytest.raises(ValueError, match="FIXING_PLATE_SIDE_INVALID"):
        resolve_base_fixing_plate_xy_mating(
            {"w": 800., "t": 2.}, side="center",
        )
    with pytest.raises(ValueError, match="FIXING_PLATE_GEOMETRY_NONFINITE"):
        resolve_base_fixing_plate_xy_mating(
            {"w": 800., "t": float("nan")}, side="left",
        )


@pytest.mark.parametrize("bad_index", [True, False, 0.0, 1.0, "1"])
def test_r5_79_neighbor_query_refuses_noninteger_selected_hole(bad_index):
    """Neighbor lookup is an independent public entry, not only a UI helper."""
    from ae_engine.sheetmetal_feature_reference import (
        ReferenceAnchor, find_reference_neighbor,
    )
    holes = (
        CircleFeature(diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(40., 40.)),
        CircleFeature(diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(150., 40.)),
    )
    with pytest.raises(ValueError, match="reference feature index"):
        find_reference_neighbor(holes, bad_index, ReferenceAnchor.CENTER,
                                "x", "right", 200., 100.)
    actual = find_reference_neighbor(holes, 0, ReferenceAnchor.CENTER,
                                     "x", "right", 200., 100.)
    assert actual is not None
    assert actual.index == 1
    assert find_reference_neighbor(holes, 1, ReferenceAnchor.CENTER,
                                   "x", "right", 200., 100.) is None


@pytest.mark.parametrize("saved", [None, "", "diagonal", True, 42, " top_left "])
def test_r5_79_invalid_explicit_reference_anchor_never_silently_moves_origin(saved):
    """A corrupt stored anchor must not silently use CENTER for hole edits."""
    from dataclasses import replace
    from ae_engine.sheetmetal_feature_reference import (
        ReferenceAnchor, feature_reference_anchor,
    )
    circle = CircleFeature(
        diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(40., 40.),
    )
    # Absence is the pre-existing CENTER default, not an error.
    assert feature_reference_anchor(circle) is ReferenceAnchor.CENTER
    valid = replace(circle, source_params=(("reference_anchor", "top_left"),))
    assert feature_reference_anchor(valid) is ReferenceAnchor.TOP_LEFT
    corrupt = replace(circle, source_params=(("reference_anchor", saved),))
    with pytest.raises(ValueError, match="reference_anchor"):
        feature_reference_anchor(corrupt)


def test_r5_73_readonly_mapping_hole_projects_identically_to_mutable_source():
    """A real manufactured sheet must retain a hole saved as MappingProxyType."""
    from ae_engine.manufacturing_render_data import PartRenderData
    from ae_engine.physical_sheet_features import with_physical_sheet_features
    from ae_engine.sheetmetal_drawing import DrawingScene, CirclePrimitive
    from shapely.geometry import Polygon

    outline = ((0., 0.), (200., 0.), (200., 100.), (0., 100.))
    scene = DrawingScene()
    scene.add_polyline(outline, layer="CUTTING", closed=True)
    original = PartRenderData(scene=scene, material=Polygon(outline))
    saved_hole = {
        "type": "圓形", "x": 60., "y": 40.,
        "params": {"diameter": 10.},
    }
    readonly = MappingProxyType(saved_hole)
    mapped = with_physical_sheet_features("base_plate", original, (readonly,))
    mutable = with_physical_sheet_features("base_plate", original, (saved_hole,))
    assert mapped.scene.primitives == mutable.scene.primitives
    assert mapped.material.area == pytest.approx(mutable.material.area)
    assert mapped.material.area < original.material.area
    assert any(isinstance(x, CirclePrimitive) for x in mapped.scene.primitives)
    assert saved_hole["params"]["diameter"] == 10.
    assert len(original.scene.primitives) == 1


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "invalid"])
def test_bug88_hole_editor_canvas_rect_rejects_nonphysical_screen_coordinates(bad):
    """Corrupt contours cannot pass Boolean/nonfinite coordinates to Tk overlays."""
    view = Phase6HoleEditorCanvasView(
        canvas=SimpleNamespace(),
        draw_grid=lambda: None,
        render_secondary_scene=lambda *args: None,
        render_resolved_features=lambda *args: None,
    )
    view.transform = SimpleNamespace(world_to_canvas=lambda pt: (pt.x, pt.y))
    bad_profile = ResolvedProfile(
        points=(), layer="FROM_DXF", source_type="saved",
        layered_profiles=(
            ("CUTTING", (Vec2(bad, 2.0), Vec2(20.0, 30.0)), False),
        ),
    )
    assert view._resolved_canvas_rect(bad_profile) is None
    valid_profile = ResolvedProfile(
        points=(), layer="FROM_DXF", source_type="saved",
        layered_profiles=(("CUTTING", (Vec2(1., 2.), Vec2(20., 30.)), False),),
    )
    assert view._resolved_canvas_rect(valid_profile) == (1., 2., 20., 30.)


@pytest.mark.parametrize("bad", ["0", "-1", "NaN", "inf", "-inf"])
def test_r5_78_csv_cutting_circle_rejects_nonphysical_catalog_dimension(tmp_path, bad):
    from ae_engine.hole_catalog import load_hole_catalog
    (tmp_path / "開孔.csv").write_text(
        f"名稱,孔徑,次尺寸\n非法圓孔,{bad},\n", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite positive dimension"):
        load_hole_catalog(tmp_path)


@pytest.mark.parametrize("bad", ["0", "-5", "NaN", "inf", "-inf"])
@pytest.mark.parametrize("field", ["width", "height"])
def test_r5_78_csv_cutting_rectangle_rejects_nonphysical_catalog_dimensions(tmp_path, bad, field):
    from ae_engine.hole_catalog import load_hole_catalog
    w, h = (bad, "50") if field == "width" else ("90", bad)
    (tmp_path / "開孔.csv").write_text(
        f"名稱,孔寬,孔高\n非法方孔,{w},{h}\n", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite positive dimension"):
        load_hole_catalog(tmp_path)


@pytest.mark.parametrize("bad", ["0", "-1", "NaN", "inf"])
def test_r5_78_csv_blind_pipe_rejects_nonphysical_catalog_diameter(tmp_path, bad):
    from ae_engine.hole_catalog import load_pipe_catalog
    (tmp_path / "管孔尺寸清單.csv").write_text(
        f"代號,孔徑\n*D1,Ø{bad}\n", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite positive dimension"):
        load_pipe_catalog(tmp_path)


def test_r5_78_csv_existing_positive_holes_and_profile_reference_preserved(tmp_path):
    from ae_engine.hole_catalog import load_hole_catalog, load_pipe_catalog
    (tmp_path / "開孔.csv").write_text(
        "名稱,孔徑,次尺寸\n圓孔22,22,\n插座盒,90,50\nASVS,ASVS.dxf,\n",
        encoding="utf-8",
    )
    (tmp_path / "管孔尺寸清單.csv").write_text(
        "代號,孔徑\n*D1,Ø116\n", encoding="utf-8",
    )
    defs = load_hole_catalog(tmp_path)
    assert [(x.shape, x.diameter, x.width, x.height) for x in defs] == [
        ("circle", 22.0, None, None),
        ("rectangle", None, 90.0, 50.0),
        ("profile", None, None, None),
    ]
    assert defs[2].profile_path == tmp_path / "ASVS.dxf"
    assert load_pipe_catalog(tmp_path)[0].diameter == 116.0


@pytest.mark.parametrize("bad_radius", [0.0, -5.0, float("nan"), float("inf")])
def test_r5_78_dxf_circle_with_nonphysical_radius_never_enters_cutting_profile(tmp_path, bad_radius):
    import ezdxf
    from ae_engine.hole_catalog import load_profile_entities
    path = tmp_path / "bad_profile_radius.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_circle((5., 5.), bad_radius, dxfattribs={"layer": "CUTTING"})
    doc.saveas(path)
    with pytest.raises(ValueError, match="孔型 DXF"):
        load_profile_entities(path)


@pytest.mark.parametrize("bad_coordinate", [float("nan"), float("inf"), float("-inf")])
def test_r5_78_dxf_nonfinite_polyline_vertex_cannot_produce_cutting_profile(tmp_path, bad_coordinate):
    import ezdxf
    from ae_engine.hole_catalog import load_profile_entities
    path = tmp_path / "bad_profile_vertex.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline(
        [(0., 0.), (10., 0.), (bad_coordinate, 15.), (0., 15.)],
        close=True, dxfattribs={"layer": "CUTTING"},
    )
    doc.saveas(path)
    with pytest.raises(ValueError, match="孔型 DXF"):
        load_profile_entities(path)


def test_r5_78_valid_cutting_dxf_circle_still_preserves_layer_and_local_center(tmp_path):
    import ezdxf
    from ae_engine.hole_catalog import load_profile_entities
    path = tmp_path / "valid_profile_circle.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_circle((80., 40.), 12., dxfattribs={"layer": "CUTTING"})
    doc.saveas(path)
    entities = load_profile_entities(path)
    assert len(entities) == 1
    layer, points, closed = entities[0]
    assert layer == "CUTTING" and closed is True
    assert len(points) == 64
    assert min(p.x for p in points) == pytest.approx(-12.)
    assert max(p.x for p in points) == pytest.approx(12.)
    assert min(p.y for p in points) == pytest.approx(-12.)
    assert max(p.y for p in points) == pytest.approx(12.)


@pytest.mark.parametrize("malformed", [True, False, 42, "indicator", ["indicator"]])
def test_r5_94_invalid_indicator_state_root_must_fail_closed(malformed):
    """Corrupt saved Door indicator authority must not silently add/drop holes."""
    with pytest.raises(ValueError, match="Door indicator state must be a mapping"):
        normalize_door_indicator_state(malformed)


def test_r5_94_absent_and_readonly_indicator_mapping_keep_existing_defaults():
    from types import MappingProxyType
    assert normalize_door_indicator_state(None)["mode"] == "none"
    saved = MappingProxyType({"mode": "indicator", "layers": 2, "groups": (3, 3)})
    normalized = normalize_door_indicator_state(saved)
    assert normalized["mode"] == "indicator"
    assert normalized["enabled"] is True
    assert normalized["layers"] == 2
    assert normalized["groups"][:2] == [3, 3]


@pytest.mark.parametrize("bad_face", [
    (),
    ((0., 0., 0.),),
    ((0., 0., 0.), (2., 0., 0.)),
])
def test_r5_74_partial_real_3d_face_cannot_disappear_before_finished_dimensions(bad_face):
    """A malformed supplied FinalScene face is not a missing whole mesh."""
    from ae_engine.display_dimensions import folded_outside_envelope
    valid = ((0., 0., 0.), (4., 0., 0.), (0., 2., 0.))
    for mesh in ((bad_face,), (valid, bad_face)):
        with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
            folded_outside_envelope(mesh, 2.)
        with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
            resolve_operator_finished_dimensions(
                "box_body", snapshot={"w": 800., "h": 1600., "d": 350.},
                triangles=mesh, thickness=2.,
            )


@pytest.mark.parametrize("bad_thickness", [
    True, False, -1., float("nan"), float("inf"), 10 ** 400,
])
def test_r5_74_mesh_envelope_cannot_disguise_nonphysical_explicit_thickness(bad_thickness):
    from ae_engine.display_dimensions import folded_outside_envelope
    mesh = (((0., 0., 0.), (4., 0., 0.), (0., 2., 0.)),)
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        folded_outside_envelope(mesh, bad_thickness)
    # Real T2 face normal still adds exactly 2 mm to each Z side.
    measured, _bounds = folded_outside_envelope(mesh, 2.)
    assert measured == pytest.approx((4., 2., 4.))
    # No mesh is an intentionally valid preview-only fallback.
    assert folded_outside_envelope((), None) is None


def test_bug76_dxf_acceptance_large_overlapping_one_to_one_match_is_not_recursive():
    """1100 near-coincident CUTTING/BEND rows need reassignment, never recursion."""
    n = 1100
    rows = tuple(range(n))

    def compatible(expected_index, actual_index):
        if expected_index == n - 1:
            return actual_index == 0
        return actual_index in (expected_index, expected_index + 1)

    # There IS a complete assignment: last row takes 0, every other row
    # shifts one station right. The older recursive augment raises
    # RecursionError at approximately a thousand increasingly shared holes.
    assert _one_to_one_tolerance_match(rows, rows, compatible) is True
    # Even after a failed greedy first-fit, missing/duplicate entities must
    # still fail the strict one-to-one manufacturing DXF readback.
    assert _one_to_one_tolerance_match(
        (0, 1), (0, 1), lambda _row, col: col == 0
    ) is False


def test_bug77_joint_covering_xy_cannot_certify_contact_displaced_in_world_z():
    """An XY overlap separated in Z is not a physical contact or valid MARKING."""
    from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
    face = ((0., 0., 0.), (20., 0., 0.), (20., 10., 0.), (0., 10., 0.))
    region = ResolvedPhysicalMatingRegion(
        part_id="side",
        region_id="real-formed-skin",
        region_role="EXPECTED_MATING_REGION",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=((0., 0., 0.), (0., 0., 1.)),
        outward_normal=(0., 0., 1.),
        world_polygon=face,
    )
    plane_tol = PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.coplanar_distance_tolerance
    assert validate_expected_region_coverage(region, face).status == "COVERED"
    # Preserve source engineering robustness tolerance for numerical drift.
    almost_on_plane = tuple((x, y, plane_tol / 2) for x, y, _ in face)
    assert validate_expected_region_coverage(region, almost_on_plane).status == "COVERED"
    # Both profiles are IDENTICAL after XY projection; the Z datum is not.
    for delta_z in (plane_tol * 2, 10., -10.):
        off_plane = tuple((x, y, delta_z) for x, y, _ in face)
        result = validate_expected_region_coverage(region, off_plane)
        assert result.status == "SKIPPED_FAIL_CLOSED"
        assert result.diagnostic_code == "OVERLAP_AUTHORITY_MISSING"

    from dataclasses import replace
    invalid_plane = replace(
        region, supporting_plane=((0., 0., 0.), (0., 0., 0.))
    )
    result = validate_expected_region_coverage(invalid_plane, face)
    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "OVERLAP_AUTHORITY_MISSING"

@pytest.mark.parametrize("typed", ("", "abc", "nan", "inf", "-30", "0"))
def test_audit116_bug94_invalid_door_width_entry_restores_last_committed_value(
    monkeypatch, typed,
):
    """Real app FocusOut/Return callback must reject invalid text atomically.

    A new Door column always owns width_committed. Its editable Tk Entry
    must never be parsed *before* the handler that reverts invalid input.
    """
    from gui_modules.application import door_layout_host_adapter as adapter
    from gui_modules.parts.panels import door as door_panel

    class Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    warnings, redraws, commits = [], [], []
    monkeypatch.setattr(
        door_panel.messagebox, "showwarning",
        lambda *args: warnings.append(args),
    )
    width_var = Var(typed)
    column = {
        "width_var": width_var, "width_auto": False,
        "width_committed": 400.,
        "height_vars": [Var("600")], "height_auto": [False],
        "height_committed": [600.],
    }
    host = SimpleNamespace(
        door_layout_columns=[column],
        w_var=Var("800"), h_var=Var("600"),
        _parse_layout_value=adapter._parse_layout_value,
        _door_layout_number_text=adapter._door_layout_number_text,
        refresh_door_layout_status=lambda: redraws.append("status"),
        draw_preview=lambda: redraws.append("preview"),
        _recompute_door_layout_remainders=lambda **kw: commits.append(("recompute", kw)),
        _on_door_layout_value_changed=lambda **kw: commits.append(("change", kw)),
    )
    host._door_layout_controller_columns = lambda: adapter._door_layout_controller_columns(host)
    host._reject_door_layout_dimension = (
        lambda var, previous, message:
        adapter._reject_door_layout_dimension(host, var, previous, message)
    )

    # The same callback is bound to both <FocusOut> and <Return> in the
    # original door panel. Failed edits cannot mutate the committed width.
    assert adapter.commit_door_layout_width(host, 0) is False
    assert width_var.get() == "400"
    assert column["width_committed"] == 400.
    assert len(warnings) == 1
    assert redraws == ["status", "preview"]
    assert commits == []

    # Prove valid edits still reach the real layout controller validation.
    width_var.set("450")
    assert adapter.commit_door_layout_width(host, 0) is True
    assert column["width_committed"] == 450.
    assert width_var.get() == "450"
    assert len(commits) == 2
    assert len(warnings) == 1


@pytest.mark.parametrize("bad_t", [True, False, -1., float("nan"), float("inf"), float("-inf"), 10 ** 400])
def test_r5_74_operator_finished_mesh_explicit_invalid_t_fails_closed(bad_t):
    """Do not replace an explicitly corrupted FinalScene T with saved T2."""
    mesh = (((0., 0., 0.), (4., 0., 0.), (0., 2., 0.)),)
    saved = {"w": 800., "h": 1600., "d": 350., "t": 2.}
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        resolve_operator_finished_dimensions(
            "box_body", snapshot=saved, triangles=mesh, thickness=bad_t,
        )


def test_r5_74_operator_finished_mesh_missing_t_uses_existing_valid_saved_t():
    mesh = (((0., 0., 0.), (4., 0., 0.), (0., 2., 0.)),)
    saved = {"w": 800., "h": 1600., "d": 350., "t": 2.}
    for explicit in (None, 2.):
        assert resolve_operator_finished_dimensions(
            "box_body", snapshot=saved, triangles=mesh, thickness=explicit,
        ) == pytest.approx((4., 2., 4.))
