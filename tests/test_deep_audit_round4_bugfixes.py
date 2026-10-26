"""Regression tests for Round 4 deep-audit bug fixes (Bugs #51 through #70)."""

from __future__ import annotations

from types import SimpleNamespace
import pytest
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

from ae_engine.assembly_collision_corner import _polygon_parts
from ae_engine.corner_resolver import standard_corner_geometry
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import (
    derive_inner_door_frames,
    inner_door_frame_formed_occupation,
)
from ae_engine.inner_door_panels import InnerDoorPanelPart, derive_inner_door_panel
from ae_engine.receiving_hole_candidates import (
    create_candidate,
    normalize_candidates,
    update_candidate,
)
from ae_engine.receiving_shared_settings import validate_setting
from ae_engine.sheetmetal_drawing import (
    build_endcap_check,
    resolved_features_to_primitives,
)
from ae_engine.sheetmetal_feature_core import (
    CircleFeature,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
    ResolvedProfile,
    _normalize_rotation,
)
from ae_engine.sheetmetal_features import (
    DoorIndicatorContext,
    hit_test_resolved_features,
    indicator_box_outer_size,
    legacy_hole_to_feature,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
)
from ae_engine.sheetmetal_four_side_geometry import (
    FourSideFlangeGeometry,
    _validate_four_side_geometry,
)
from ae_engine.sheetmetal_geometry import (
    EndCapGeometry,
    Vec2,
    calculate_endcap_relief_dimensions,
)
from ae_engine.sheetmetal_geometry_core import CornerTypeSelection, GeometryError
from ae_engine.sheetmetal_part_adapters import (
    build_box_body_result_from_fold_profile,
    calculate_door_finished_size,
    complete_partition,
    derive_door_layout_cells,
    validate_door_layout_dimensions,
)
from ae_engine.sheetmetal_strip_geometry import (
    FoldSegment,
    StripFoldChain,
    build_strip_outline,
)
from gui_modules.application.fold_designer_adapter import (
    Phase6FoldDesignerComposition,
)
from gui_modules.application.fold_designer_manufacturing_projection import (
    _query_fold_designer_render_data,
)
from phase6_box_body_structure import (
    BoxBodyStructureType,
    reconcile_box_body_structure_for_total_w_change,
)
from phase6_custom_parts import custom_part_only_change
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_manufacturing_adapter import build_manufacturing_request


class _DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def _dummy_namespace(extra=None):
    ns = {
        "_setting_number_text": str,
        "_phase6_part_label": lambda k, snapshot=None: str(k),
        "_phase6_render_data_corner_dimension_text": lambda *a, **kw: "",
        "_phase6_render_data_for_blank": lambda *a, **kw: None,
        "_phase6_is_box_body_physical_piece_key": lambda k: str(k).startswith("box_body:"),
        "_phase6_box_body_piece_render_data": lambda *a, **kw: None,
        "_phase6_resolve_manufacturing_geometry": lambda *a, **kw: None,
        "_phase6_scene_query_payload_for_part": lambda *a, **kw: {},
        "_phase6_operator_finished_dimensions": lambda app, part_key=None: (600.0, 800.0, 250.0),
        "_phase6_current_cabinet_family": lambda *a, **kw: "OUTDOOR",
        "_phase6_mesh_profiles_for_part": lambda *a, **kw: (),
        "_phase6_query_final_render_data": lambda *a, **kw: None,
        "_phase6_final_scene_view_request": lambda *a, **kw: None,
        "_phase6_update_assembly_diagnostic_status": lambda *a, **kw: None,
    }
    if extra:
        ns.update(extra)
    return ns


def test_bug51_assembly_visibility_reads_app_vars_without_panel_owner():
    app = SimpleNamespace(
        _phase6_assembly_panel_owner=None,
        assembly_part_visible_vars={
            "box_body": _DummyVar(True),
            "base_plate": _DummyVar(False),
            "door": _DummyVar(True),
        },
        assembly_box_body_piece_visible_vars={
            "box_body:left": _DummyVar(False),
            "box_body:right": _DummyVar(True),
        },
    )
    comp = Phase6FoldDesignerComposition(app)
    ports = comp.final_scene_ports(_dummy_namespace())
    parts = [
        SimpleNamespace(
            part_key="box_body",
            render_data=SimpleNamespace(
                pieces=(
                    SimpleNamespace(role="left"),
                    SimpleNamespace(role="right"),
                )
            ),
        ),
        SimpleNamespace(part_key="base_plate"),
        SimpleNamespace(part_key="door"),
    ]
    keys, box_pieces = ports.assembly_visibility(parts)
    assert "base_plate" not in keys
    assert "box_body" in keys
    assert "door" in keys
    assert box_pieces == ("box_body:right",)


def test_bug52_final_scene_ports_and_manufacturing_request_use_operator_dimensions():
    called = []

    def fake_op_dims(part_key=None):
        called.append(part_key)
        return (600.0, 800.0, 250.0)

    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "戶外箱"},
        _settings_values={"t": 1.6},
        _phase6_box_whd={"w": 600.0, "h": 800.0, "d": 250.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        designer_workspace=SimpleNamespace(available_parts=()),
        _phase6_operator_finished_dimensions=fake_op_dims,
    )

    comp = Phase6FoldDesignerComposition(app)
    ports = comp.final_scene_ports(
        _dummy_namespace(
            {"_phase6_operator_finished_dimensions": lambda _a, pk=None: fake_op_dims(pk)}
        )
    )
    op_dims = ports.operator_dimensions("box_body")
    assert op_dims == (600.0, 800.0, 250.0)
    # Current FinalScene reads the LIVE shared dimensions owner, not the
    # historic namespace provider. Verify source parity and no legacy call.
    from phase6_manufacturing_adapter import operator_finished_dimensions_for_app
    assert op_dims == operator_finished_dimensions_for_app(app, "box_body")
    assert called == []

    called.clear()
    req = build_manufacturing_request(app)
    assert req.input_snapshot["w"] == 600.0
    assert req.input_snapshot["h"] == 800.0
    assert req.input_snapshot["d"] == 250.0
    assert req.input_snapshot["t"] == 1.6
    assert req.operator_finished_dimensions == (600.0, 800.0, 250.0)
    assert "box_body" in called


def test_bug53_hit_test_resolved_features_handles_open_and_layered_profiles():
    one_pt = ResolvedProfile(points=(Vec2(10.0, 20.0),))
    assert hit_test_resolved_features(Vec2(10.0, 20.0), [one_pt], tolerance=2.0) == 0
    assert hit_test_resolved_features(Vec2(50.0, 50.0), [one_pt], tolerance=2.0) is None

    two_pt = ResolvedProfile(points=(Vec2(0.0, 0.0), Vec2(100.0, 0.0)))
    assert hit_test_resolved_features(Vec2(50.0, 1.0), [two_pt], tolerance=2.0) == 0
    assert hit_test_resolved_features(Vec2(50.0, 20.0), [two_pt], tolerance=2.0) is None

    layered = ResolvedProfile(
        points=(),
        layered_profiles=(
            (
                "CUT",
                (
                    Vec2(10.0, 10.0),
                    Vec2(30.0, 10.0),
                    Vec2(30.0, 30.0),
                    Vec2(10.0, 30.0),
                ),
                True,
            ),
        ),
    )
    assert hit_test_resolved_features(Vec2(20.0, 20.0), [layered], tolerance=1.0) == 0


def test_bug54_resolved_features_to_primitives_open_two_point_and_endcap_check_actual_flanges():
    two_pt = ResolvedProfile(points=(Vec2(0.0, 0.0), Vec2(40.0, 0.0)), layer="MARK")
    one_pt = ResolvedProfile(points=(Vec2(5.0, 5.0),), layer="MARK")
    prims = resolved_features_to_primitives([two_pt, one_pt])
    assert len(prims) == 1
    assert prims[0].closed is False

    geom = EndCapGeometry(
        total_width=300.0,
        total_depth=150.0,
        left_fold=20.0,
        right_fold=20.0,
        top_first_fold=15.0,
        fw=25.0,
        bottom_fold=18.0,
        thickness=2.0,
    )
    relief = calculate_endcap_relief_dimensions(geom)
    check = build_endcap_check(
        geometry=geom,
        relief=relief,
        finished_width=264.0,
        finished_depth=100.0,
        part_label="Top Cap",
    )
    assert "折彎尺寸: 260*92" in check[0].text


def test_bug55_normalize_rotation_rejects_bool_and_fractional_degrees():
    with pytest.raises(ValueError, match="rotation"):
        _normalize_rotation(True)
    with pytest.raises(ValueError, match="rotation"):
        _normalize_rotation(45.0)
    with pytest.raises(ValueError, match="rotation"):
        legacy_hole_to_feature(
            {
                "type": "方形",
                "x": 10.0,
                "y": 10.0,
                "params": {"width": 20.0, "height": 10.0, "rotation_deg": True},
            }
        )
    with pytest.raises(ValueError, match="rotation"):
        legacy_hole_to_feature(
            {
                "type": "方形",
                "x": 10.0,
                "y": 10.0,
                "params": {"width": 20.0, "height": 10.0, "rotation_deg": 30},
            }
        )


def test_bug56_standard_corner_geometry_validates_corner_name_and_mapping_rows_with_negative_lengths():
    with pytest.raises(ValueError, match="Unsupported corner_name"):
        standard_corner_geometry("invalid_corner", [], [])

    x_profile = [
        {"phase6_key": "yl1", "len": -25.0},
        {"phase6_key": "xr1", "len": -15.0},
    ]
    y_profile = [
        {"phase6_key": "ytop1", "len": -30.0},
        {"phase6_key": "ybot1", "len": -12.0},
    ]
    res = standard_corner_geometry("top_left", x_profile, y_profile)
    assert res.primary_u == pytest.approx(25.0)
    assert res.primary_v == pytest.approx(30.0)


def test_bug57_indicator_groups_reject_bool_and_non_positive():
    ctx = DoorIndicatorContext(500.0, 700.0, 19.0, 19.0)
    for bad in (True, False, 0, -2, "abc"):
        with pytest.raises(ValueError, match="group"):
            indicator_box_outer_size([bad])
        with pytest.raises(ValueError, match="group"):
            resolve_door_indicator_features(ctx, [bad])
        with pytest.raises(ValueError, match="group"):
            resolve_door_indicator_layout(ctx, [bad])


def test_bug58_receiving_candidates_and_shared_settings_validate_feature_types():
    with pytest.raises(ValueError, match="Feature"):
        normalize_candidates(
            {
                "schema": "receiving-hole-candidates-v1",
                "head": {
                    "next_number": 2,
                    "versions": [{"id": "head-v1", "features": [{"not": "a_feature"}]}],
                },
                "tail": {"next_number": 1, "versions": []},
            }
        )
    with pytest.raises(ValueError, match="Feature"):
        create_candidate(None, "head", ["bad_feature"])
    valid_store, vid = create_candidate(
        None,
        "head",
        [
            CircleFeature(
                diameter=10.0,
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(0.0, 0.0),
            )
        ],
    )
    with pytest.raises(ValueError, match="Feature"):
        update_candidate(valid_store, "head", vid, [123])
    with pytest.raises(ValueError, match="feature"):
        validate_setting("head_features", [{"bad": "dict"}])


def test_bug59_part_adapters_reject_bool_nan_and_negative_inputs():
    with pytest.raises(ValueError):
        complete_partition([100.0], True)
    with pytest.raises(ValueError):
        complete_partition([100.0], 500.0, tolerance=-0.5)
    with pytest.raises(ValueError):
        derive_door_layout_cells([(True, [800.0])])
    with pytest.raises(ValueError):
        validate_door_layout_dimensions(
            [(600.0, [800.0])], total_width=float("nan"), total_height=800.0
        )
    with pytest.raises(ValueError):
        calculate_door_finished_size(
            w=600.0, h=800.0, t=True, fw=25.0, gap_w=2.0, gap_h=2.0
        )
    with pytest.raises(ValueError):
        calculate_door_finished_size(
            w=600.0, h=800.0, t=1.5, fw=-1.0, gap_w=2.0, gap_h=2.0
        )


def test_bug60_build_box_body_result_from_fold_profile_supports_mapping_rows():
    rows = [
        {"length": None, "len": 25.0, "angle": 90.0},
        {"core": "D", "length": None, "len": 200.0, "angle": 90.0},
        {"core": "W", "len": 400.0, "angle": 90.0},
        {"core": "D", "len": 200.0, "angle": 90.0},
        {"len": 25.0, "angle": None},
    ]
    res = build_box_body_result_from_fold_profile(rows, h=500.0, t=1.5)
    assert res.width > 0
    assert res.height > 0


def test_bug61_geometry_dataclasses_reject_bool_and_non_finite():
    with pytest.raises(GeometryError):
        CornerTypeSelection(type_id="C01", amount_t=True)
    with pytest.raises(GeometryError):
        calculate_endcap_relief_dimensions(
            EndCapGeometry(
                total_width=True,
                total_depth=100.0,
                left_fold=15.0,
                right_fold=15.0,
                top_first_fold=15.0,
                fw=25.0,
                bottom_fold=15.0,
                thickness=1.5,
            )
        )
    with pytest.raises(GeometryError):
        _validate_four_side_geometry(
            FourSideFlangeGeometry(
                total_width=300.0,
                total_height=400.0,
                thickness=float("nan"),
                left_fold=15.0,
                right_fold=15.0,
                top_fold=15.0,
                bottom_fold=15.0,
            )
        )
    with pytest.raises(GeometryError):
        build_strip_outline(
            StripFoldChain(
                segments=(FoldSegment("A", 50.0), FoldSegment("B", 50.0)),
                height=True,
            )
        )


def test_bug62_door_dividers_inner_panels_and_frames_reject_bool_and_nan():
    with pytest.raises(ValueError):
        derive_box_body_dividers(
            [(300.0, [800.0]), (300.0, [800.0])],
            depth=True,
            thickness=1.5,
            layout_scope="box_body",
        )
    with pytest.raises(ValueError):
        InnerDoorPanelPart(
            stable_id="inner_door:1:panel",
            inner_door_id="1",
            cell_key="0:0",
            width=True,
            height=300.0,
            thickness=1.5,
            fold_left=19.0,
            fold_right=19.0,
            fold_top=19.0,
            fold_bottom=19.0,
        )
    with pytest.raises(ValueError):
        derive_inner_door_panel(
            "1", cell_key="0:0", width=200.0, height=300.0, thickness=True
        )
    with pytest.raises(ValueError):
        inner_door_frame_formed_occupation(True)
    with pytest.raises(ValueError):
        derive_inner_door_frames(
            "1",
            spans={"left": 300.0, "right": 300.0, "top": 200.0, "bottom": 200.0},
            thickness=float("nan"),
        )


def test_bug63_manufacturing_projection_checks_fold_designer_app_snapshot():
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot={
                "model": "戶外箱",
                "w": 600.0,
                "h": 800.0,
                "d": 250.0,
                "t": 1.5,
            }
        )
    )
    with pytest.raises(ValueError, match="BASE_FIXING_PLATE"):
        _query_fold_designer_render_data(host, "base_plate:fixing_plate:unknown", {})


def test_bug64_reconcile_box_body_structure_default_driver_and_inactive_mode_tolerance():
    two_key = BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    three_key = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    two_piece = {
        "active_type": two_key,
        "configs": {
            two_key: {
                "driver": "default",
                "left_w": 300.0,
                "right_w": 300.0,
            }
        },
    }
    updated = reconcile_box_body_structure_for_total_w_change(two_piece, 800.0)
    assert updated["configs"][two_key]["left_w"] == pytest.approx(400.0)
    assert updated["configs"][two_key]["right_w"] == pytest.approx(400.0)

    inactive_conflict = {
        "active_type": three_key,
        "configs": {
            two_key: {
                "driver": "left",
                "left_w": 700.0,
                "right_w": 100.0,
            }
        },
    }
    res = reconcile_box_body_structure_for_total_w_change(inactive_conflict, 500.0)
    assert res["active_type"] == three_key
    assert res["configs"][two_key]["left_w"] is None
    assert res["configs"][two_key]["right_w"] is None
    assert res["configs"][two_key]["driver"] == "default"


def test_bug65_custom_part_only_change_detects_custom_profile_edits_and_blocks_standard_edits():
    custom_spec = {
        "next_id": 2,
        "items": {
            "custom:1": {
                "display_name": "外掛板1",
                "fold_axis": "X",
                "transverse_length": 300,
                "per_box_count": 1,
            }
        },
    }
    base = {
        "available_parts": ["box_body", "custom:1"],
        "custom_parts": custom_spec,
        "part_profiles": {
            "box_body": [{"id": "F1", "len": 20.0}],
            "custom:1": [{"id": "F1", "len": 15.0}],
        },
        "part_features": {},
        "part_face_features": {},
    }
    edited_custom = {
        "available_parts": ["box_body", "custom:1"],
        "custom_parts": custom_spec,
        "part_profiles": {
            "box_body": [{"id": "F1", "len": 20.0}],
            "custom:1": [{"id": "F1", "len": 30.0}],
        },
        "part_features": None,
        "part_face_features": None,
    }
    assert custom_part_only_change(base, edited_custom) is True

    edited_standard = {
        "available_parts": ["box_body", "custom:1"],
        "custom_parts": custom_spec,
        "part_profiles": {
            "box_body": [{"id": "F1", "len": 25.0}],
            "custom:1": [{"id": "F1", "len": 15.0}],
        },
    }
    assert custom_part_only_change(base, edited_standard) is False


def test_bug66_receiving_bay_preview_request_preserves_custom_parts():
    ws = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": ["box_body", "custom:1"],
            "active_part": "custom:1",
            "custom_parts": {
                "next_id": 2,
                "items": {
                    "custom:1": {
                        "display_name": "外掛板1",
                        "fold_axis": "X",
                        "transverse_length": 300,
                        "per_box_count": 1,
                    }
                },
            },
        }
    )
    snap = ws.snapshot()
    proxy_ws = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": ws.available_parts,
            "custom_parts": snap["custom_parts"],
            "part_profiles": ws.part_profiles_snapshot(),
        }
    )
    assert "custom:1" in proxy_ws.available_parts
    assert proxy_ws.custom_part("custom:1") is not None


def test_bug67_workspace_remove_part_prunes_stale_assembly_placements():
    ws = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": ["box_body", "door", "base_plate"],
            "active_part": "box_body",
            "assembly_placements": {
                "door": {"offset_x": 0.0},
                "inner_door:1:panel": {"offset_x": 10.0, "parent_assembly_node": "door"},
                "base_plate": {"offset_x": 5.0},
            },
        }
    )
    assert ws.remove_part("door") is True
    snap = ws.snapshot()
    assert "door" not in snap["assembly_placements"]
    assert "inner_door:1:panel" not in snap["assembly_placements"]
    assert "base_plate" in snap["assembly_placements"]


def test_bug68_polygon_parts_recursively_flattens_nested_geometry_collections():
    p1 = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    p2 = Polygon([(20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0)])
    nested = GeometryCollection([MultiPolygon([p1, p2])])
    parts = _polygon_parts(nested)
    assert len(parts) == 2

@pytest.mark.parametrize("bad", [True, False, 1.0, 2.0, "1", "2"])
def test_r4_58_inner_door_layer_count_cannot_keep_a_noninteger_source(bad):
    from ae_engine.receiving_shared_settings import validate_setting
    with pytest.raises(ValueError, match="內門層數必須為 1 或 2"):
        validate_setting("inner_door_layers", bad)
    assert validate_setting("inner_door_layers", 1) == 1
    assert validate_setting("inner_door_layers", 2) == 2
