from __future__ import annotations

from enum import Enum
import math
from types import SimpleNamespace
import pytest

from ae_engine.assembly_marking_geometry import (
    _normalize,
    _world_point_to_flat,
    backproject_mapped_skin_world_points,
    resolve_contact_local_frame,
    resolve_side_boundary_pair,
    vector_unit,
)
from ae_engine.baseline_source import (
    BASELINE_SOURCE_UNVERIFIED,
    _BASELINE_DXF_LAST_GOOD,
    baseline_cutting_bounds,
    load_baseline_dxf_source_with_status,
)
from ae_engine.contracts import (
    AssemblyGeometryToleranceContract,
    JointMarkingProductionStatus,
)
from ae_engine.manufacturing_render_data import MaterialSegment
from ae_engine.receiving_nfb_depth_surface_policy import (
    committed_receiving_flat_nfb_depth_mm,
    committed_receiving_nfb_depth_pair_mm,
    receiving_nfb_second_side_fold_mm,
    resolve_receiving_nfb_surface_chain,
)
from ae_engine.receiving_nfb_model_identity import (
    display_model_ref,
    numeric_model_ref,
    validate_stored_model_ref,
)
from ae_engine.receiving_nfb_numeric_catalog import read_numeric_specs
from ae_engine.receiving_nfb_pad_generator import (
    PadToolingRule,
    generate_nfb_pad_patterns,
    read_pad_tooling_rule,
)
from ae_engine.receiving_nfb_persistence import (
    contains_submitted_nfb,
    normalize_nfb_config,
)
from ae_engine.receiving_tier_ear_z_targets import (
    _current_brand_config,
    _tier_source_depths,
)
from ae_engine.receiving_weld_ear_policy import (
    receiving_source_fixing_pitch_x_mm,
    resolve_receiving_large_weld_ear_fit,
)
from ae_engine.sheetmetal_corner_policy import (
    CornerTypeId,
    CornerTypeResidual,
    CornerTypeSelection,
    GeometryError,
    compose_corner_residual,
    corner_selection_residual,
)
from ae_engine.sheetmetal_features import (
    CanvasTransform,
    Vec2,
    expand_grid_pattern,
    expand_linear_pattern,
    indicator_box_opening_size,
)
from ae_engine.sheetmetal_geometry import (
    _factor_or_override,
)
from gui_modules.parts.panels.endcap import setup_tab_endcap_ui
import phase6_box_body_structure as bbs
import phase6_manufacturing_geometry as pmg


def test_assembly_marking_geometry_normalization_and_backprojection_guards():
    with pytest.raises(ValueError, match="degenerate vector"):
        _normalize((float("inf"), 0.0, 0.0), 1e-6)
    with pytest.raises(ValueError, match="degenerate vector"):
        _normalize((1.0, 2.0), 1e-6)
    with pytest.raises(ValueError, match="degenerate vector"):
        vector_unit((1.0, 0.0, 0.0), tolerance=float("nan"))
    with pytest.raises(ValueError, match="degenerate vector"):
        vector_unit((float("inf"), 0.0, 0.0), tolerance=1e-6)

    frame_res = resolve_contact_local_frame(
        {"origin_3d": (0.0, 0.0)},
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame_res.status == "SKIPPED_FAIL_CLOSED"

    boundary_res = resolve_side_boundary_pair(
        {"side_boundary_world": [((0.0, 0.0), (1.0, 0.0, 0.0))]},
        None,
    )
    assert boundary_res.status == "SKIPPED_FAIL_CLOSED"

    nan_flat_record = SimpleNamespace(
        world=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        flat=((float("nan"), 0.0), (10.0, 0.0), (0.0, 10.0)),
    )
    assert _world_point_to_flat((2.0, 2.0, 0.0), nan_flat_record) is None

    res_bad_pt = backproject_mapped_skin_world_points([(1.0, 2.0)], [nan_flat_record])
    assert res_bad_pt.status == "SKIPPED_FAIL_CLOSED"
    assert res_bad_pt.diagnostic_code == "BACKPROJECTION_FAILED"

    bad_record = SimpleNamespace(world=((0.0, 0.0),), flat=((0.0, 0.0),))
    res_bad_rec = backproject_mapped_skin_world_points([(1.0, 2.0, 0.0)], [bad_record])
    assert res_bad_rec.status == "SKIPPED_FAIL_CLOSED"
    assert res_bad_rec.diagnostic_code == "BACKPROJECTION_FAILED"


def test_baseline_source_dxf_error_fallback_and_cutting_bounds(tmp_path):
    bad_dxf = tmp_path / "corrupt.dxf"
    bad_dxf.write_text("NOT A VALID DXF\n0\nINVALID\n", encoding="utf-8")
    normalized = str(bad_dxf.resolve())
    sentinel_doc = object()
    _BASELINE_DXF_LAST_GOOD[normalized] = sentinel_doc
    try:
        doc, status = load_baseline_dxf_source_with_status(
            str(bad_dxf),
            allow_unverified_source=True,
        )
        assert doc is sentinel_doc
        assert status == BASELINE_SOURCE_UNVERIFIED
    finally:
        _BASELINE_DXF_LAST_GOOD.pop(normalized, None)

    circle_ent = SimpleNamespace(
        dxftype=lambda: "CIRCLE",
        dxf=SimpleNamespace(
            layer="CUTTING",
            center=SimpleNamespace(x=10.0, y=20.0),
            radius=-5.0,
        ),
    )
    assert baseline_cutting_bounds([circle_ent]) == (5.0, 15.0, 15.0, 25.0)


def test_contracts_and_material_segment_reject_bool_and_nonfinite():
    with pytest.raises(ValueError, match="coplanar_distance_tolerance"):
        AssemblyGeometryToleranceContract(
            coplanar_distance_tolerance=True,
            opposed_normal_residual_tolerance=0.1,
            flat_world_mapping_tolerance=0.1,
            boundary_separation_tolerance=0.1,
            polygon_robustness_epsilon=0.1,
        )
    with pytest.raises(ValueError, match="coplanar_distance_tolerance"):
        AssemblyGeometryToleranceContract(
            coplanar_distance_tolerance=float("nan"),
            opposed_normal_residual_tolerance=0.1,
            flat_world_mapping_tolerance=0.1,
            boundary_separation_tolerance=0.1,
            polygon_robustness_epsilon=0.1,
        )
    with pytest.raises(ValueError, match="production_policy_count"):
        JointMarkingProductionStatus(
            activation_enabled=True,
            gate_state="ACTIVE",
            export_disposition="ALLOW",
            production_policy_count=True,
        )
    with pytest.raises(ValueError, match="MaterialSegment length"):
        MaterialSegment(axis="X", name="flat", length=True, source="test")
    with pytest.raises(ValueError, match="MaterialSegment length"):
        MaterialSegment(axis="X", name="flat", length=float("inf"), source="test")


def test_receiving_nfb_depth_surface_policy_v5_brand_and_bool_guards():
    with pytest.raises(ValueError, match="NFB depth and base plate T must not be boolean"):
        receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=True,
            secondary_nfb_depth_mm=60.0,
            base_plate_thickness_mm=1.5,
        )
    with pytest.raises(ValueError, match="surface chain dimensions must not be boolean"):
        resolve_receiving_nfb_surface_chain(
            inner_door_outer_face_from_front_mm=True,
            inner_door_thickness_mm=1.5,
            base_plate_thickness_mm=1.5,
            fixing_plate_thickness_mm=1.5,
            reference_nfb_depth_mm=60.0,
            secondary_nfb_depth_mm=60.0,
        )

    assert (
        committed_receiving_nfb_depth_pair_mm(
            {
                "receiving_layout": {
                    "sets": [
                        {
                            "bays": [
                                {
                                    "nfb_config_submitted": True,
                                    "nfb_config": {
                                        "layer_count": True,
                                        "holes": [{}, {}],
                                    },
                                }
                            ]
                        }
                    ]
                }
            }
        )
        is None
    )

    v5_snapshot = {
        "t": 1.5,
        "receiving_layout": {
            "sets": [
                {
                    "bays": [
                        {
                            "nfb_config_submitted": True,
                            "nfb_config": {
                                "layer_count": 1,
                                "holes": [
                                    {
                                        "slot_index": 0,
                                        "layer_count": 1,
                                        "model_filename": "nfbv5:士林:BM100-CN",
                                    },
                                    {
                                        "slot_index": 1,
                                        "layer_count": 1,
                                        "model_filename": "nfbv5:東元:TO-100S",
                                    },
                                ],
                            },
                        }
                    ]
                }
            ]
        },
    }
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB"):
        committed_receiving_flat_nfb_depth_mm(v5_snapshot)


def test_receiving_nfb_model_identity_and_catalog_validation(tmp_path):
    with pytest.raises(ValueError, match="DXF"):
        validate_stored_model_ref(" BM100.dxf")
    with pytest.raises(ValueError, match="DXF"):
        validate_stored_model_ref("   .dxf")
    with pytest.raises(ValueError, match="DXF"):
        validate_stored_model_ref("bad:name.dxf")
    with pytest.raises(ValueError, match="V5"):
        numeric_model_ref("士林", " BM100")
    with pytest.raises(ValueError, match="V5"):
        display_model_ref("nfbv5:only_two_parts")

    bad_csv = tmp_path / "bad_v5.csv"
    bad_csv.write_text(
        "型號,NFB寬_mm,NFB高_mm,NFB深_mm,開孔尺寸_mm,螺絲孔中心距_mm,螺絲孔徑_mm,螺絲孔群偏移X_mm,螺絲孔群偏移Y_mm\n"
        "BAD:MODEL,75,100,60,50X80,25X84,4.5,0,0\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(ValueError, match="不合法"):
        read_numeric_specs("士林", path=bad_csv)


def test_receiving_nfb_pad_generator_validation(tmp_path):
    bad_rule = PadToolingRule(
        revision="   ",
        source_dxf_sha256="not_a_sha256",
        tab_projection_mm=True,
        tab_height_mm=10.0,
        tab_end_inset_mm=5.0,
        base_square_side_mm=10.0,
        base_square_center_inset_x_mm=5.0,
    )
    with pytest.raises(ValueError, match="PAD 共用加工規則"):
        bad_rule.validate()

    bad_json = tmp_path / "bad_rule.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="PAD 共用加工規則格式不正確"):
        read_pad_tooling_rule(bad_json)

    with pytest.raises(ValueError, match="PAD 板厚必須為有限正數"):
        generate_nfb_pad_patterns([], plate_thickness_mm=True, tooling=read_pad_tooling_rule())


def test_receiving_nfb_persistence_and_tier_ear_guards():
    with pytest.raises(ValueError, match="physical_hole_id"):
        normalize_nfb_config(
            {
                "layer_count": 1,
                "holes": [
                    {
                        "slot_index": 0,
                        "physical_hole_id": " P1 ",
                        "model_filename": "BM100.dxf",
                    }
                ],
            }
        )

    assert contains_submitted_nfb({"receiving_layout": {"sets": "bad"}}) is False
    assert contains_submitted_nfb({"receiving_layout": {"sets": ["bad"]}}) is False
    assert contains_submitted_nfb({"quantity": {"versions": "bad"}}) is False

    valid_v5_model = next(
        spec.model for spec in read_numeric_specs("士林") if spec.depth_mm is not None
    )
    depths = _tier_source_depths(
        None,
        {
            "layer_count": 1,
            "holes": [
                {
                    "layer_index": 0,
                    "model_filename": numeric_model_ref("士林", valid_v5_model),
                }
            ],
        },
        layer_index=0,
    )
    assert len(depths) == 1 and math.isfinite(depths[0])

    with pytest.raises(ValueError, match="EAR_Z_SOURCE_BAY_AMBIGUOUS"):
        _current_brand_config(
            {
                "receiving_layout": {
                    "sets": [
                        "not_a_dict",
                    ]
                }
            }
        )


def test_receiving_weld_ear_and_sheetmetal_corner_features_geometry_guards():
    with pytest.raises(ValueError, match="boolean"):
        receiving_source_fixing_pitch_x_mm(box_outer_width_mm=True, box_side_thickness_mm=1.5)
    with pytest.raises(ValueError, match="finite"):
        resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=True,
            box_side_thickness_mm=1.5,
            fixing_hole_pitch_x_mm=670.0,
            fixing_hole_pitch_y_mm=210.0,
        )

    with pytest.raises(GeometryError):
        corner_selection_residual(
            CornerTypeSelection(CornerTypeId.OVERLAY),
            thickness=True,
            fw=10.0,
        )
    with pytest.raises(GeometryError, match="第二級截角參數不完整"):
        compose_corner_residual(
            CornerTypeResidual((10.0, 10.0), secondary_u=5.0, secondary_depth=None),
            fold_u=15.0,
            fold_v=15.0,
        )
    with pytest.raises(GeometryError, match="十字截角槽參數不完整"):
        compose_corner_residual(
            CornerTypeResidual(
                (10.0, 10.0),
                slot_width=2.0,
                slot_straight_depth=None,
                slot_radius=None,
            ),
            fold_u=15.0,
            fold_v=15.0,
        )

    with pytest.raises(ValueError, match="boolean"):
        CanvasTransform(scale=True, origin_x=0.0, origin_y=0.0)
    dummy_feature = SimpleNamespace(offset=Vec2(0.0, 0.0))
    with pytest.raises(ValueError, match="boolean"):
        expand_linear_pattern(dummy_feature, count=True, pitch=10.0, axis="x")
    with pytest.raises(ValueError, match="integers"):
        expand_grid_pattern(dummy_feature, rows=2.5, columns=2, pitch_x=10.0, pitch_y=10.0)
    with pytest.raises(ValueError, match="boolean"):
        indicator_box_opening_size([1], thickness=True)

    # A boolean override is rejected as nonphysical before becoming a
    # finite 1-mm factory CUTTING relief. Preserve the current fail-closed
    # GeometryError contract without requiring historic diagnostic wording.
    with pytest.raises(GeometryError, match="bend_factor must be finite"):
        _factor_or_override(True, 1.5, 3.0, "bend_factor")


def test_phase6_box_body_structure_string_bool_and_three_piece_guards():
    state = bbs.normalize_box_body_structure_state(
        {
            "locked": "false",
            "configs": {
                bbs.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value: {
                    "piece_profiles": "invalid_not_a_dict",
                }
            },
        }
    )
    assert state["locked"] is False
    assert (
        state["configs"][bbs.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value][
            "piece_profiles"
        ]
        == {}
    )

    locked_state = bbs.set_structure_locked({}, "0")
    assert locked_state["locked"] is False

    with pytest.raises(ValueError, match="不一致"):
        bbs.resolve_three_piece_widths(
            {
                "configs": {
                    bbs.BoxBodyStructureType.THREE_PIECE_W_SPLIT.value: {
                        "left_w": 150.0,
                        "middle_w": 200.0,
                        "right_w": None,
                    }
                }
            },
            600.0,
        )

    reconciled = bbs.reconcile_box_body_structure_for_total_w_change(
        {
            "configs": {
                bbs.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value: {
                    "driver": "right",
                    "left_w": None,
                    "right_w": 180.0,
                }
            }
        },
        700.0,
    )
    two_cfg = reconciled["configs"][bbs.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert two_cfg["driver"] == "right"
    assert two_cfg["left_w"] == pytest.approx(520.0)
    assert two_cfg["right_w"] == pytest.approx(180.0)


def test_phase6_manufacturing_geometry_and_endcap_guards():
    columns = ((300.0, (500.0,)),)
    cell_key = pmg.door_layout_part_key(pmg.derive_door_layout_cells(columns)[0])
    plane, center = pmg._phase6_door_part_assembly_placement(
        {"w": None, "h": None, "door_layout_columns": columns},
        cell_key,
    )
    assert plane == "front"
    assert center == (0.0, 0.0, 0.0)

    dummy_self = SimpleNamespace(
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "not_a_float"),
    )
    assert pmg._phase6_assembly_relief_clearance(dummy_self) == 0.0

    class _Color(str, Enum):
        RED = "red_val"

    assert pmg._phase6_signature_canonical_value(_Color.RED) == "red_val"
    assert pmg._phase6_signature_canonical_value(frozenset([2, 1])) == (1, 2)
    # Invalid numeric dimensions must never produce a cache key that can
    # collide with a literal marker such as "__NaN__".
    with pytest.raises(ValueError, match="nonfinite manufacturing signature value"):
        pmg._phase6_signature_canonical_value(float("nan"))
    assert pmg._phase6_signature_canonical_value("__NaN__") == "__NaN__"

    fake_piece = SimpleNamespace(
        role="left_side",
        fold_profile=(
            SimpleNamespace(phase6_key="fw_left", length=20.0, formed_length=21.5, core=""),
            SimpleNamespace(phase6_key="d_left", length=100.0, formed_length=None, core="D"),
        ),
    )
    assert pmg._phase6_expand_box_body_fw_world_mid(
        fake_piece,
        [SimpleNamespace(flat=((5.0, 0.0), (10.0, 0.0), (15.0, 1.0)))] * 5,
        [[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        sheet_thickness=1.5,
    ) == (((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)

    part_input = SimpleNamespace(
        part_key="box_body:left_side",
        x_profile=[{"len": 10.0}],
        y_profile=[{"len": 20.0}],
    )
    bad_bounds_material = SimpleNamespace(bounds=(0.0, 0.0))
    assert pmg._phase6_request_profiles_for_material(part_input, bad_bounds_material) == (
        [{"len": 10.0}],
        [{"len": 20.0}],
    )
    good_bounds_material = SimpleNamespace(bounds=(0.0, 10.0, 100.0, 210.0))
    # A physical SIDE has its own authoritative Y fold profile. A mesh
    # envelope for an unrelated view must never overwrite its 20-mm input.
    assert pmg._phase6_request_profiles_for_material(part_input, good_bounds_material) == (
        [{"len": 10.0}],
        [{"len": 20.0}],
    )
    # Only the WHOLE box body uses material height unconditionally; a
    # single-axis divider/frame may borrow the missing axis, not overwrite
    # a completed physical profile.
    whole_body = SimpleNamespace(
        part_key="box_body",
        x_profile=[{"len": 10.0}], y_profile=[{"len": 20.0}],
    )
    assert pmg._phase6_request_profiles_for_material(whole_body, good_bounds_material) == (
        [{"len": 10.0}],
        [{"len": 200.0}],
    )
    frame = SimpleNamespace(
        part_key="box_body:divider:middle",
        x_profile=[{"len": 10.0}], y_profile=[],
    )
    assert pmg._phase6_request_profiles_for_material(frame, good_bounds_material) == (
        [{"len": 10.0}],
        [{"len": 200.0}],
    )

    with pytest.raises(ValueError, match="Unsupported endcap tab key"):
        setup_tab_endcap_ui(object(), object(), "invalid_key")


@pytest.mark.parametrize("field", [
    "coplanar_distance_tolerance",
    "opposed_normal_residual_tolerance",
    "flat_world_mapping_tolerance",
    "boundary_separation_tolerance",
    "polygon_robustness_epsilon",
])
@pytest.mark.parametrize("bad", [10 ** 400, -(10 ** 400), "not-a-distance"])
def test_r6_invalid_tolerance_source_cannot_escape_as_overflow_or_type_error(field, bad):
    """Physical contact tolerances fail with the existing ValueError contract."""
    baseline = {
        "coplanar_distance_tolerance": 1e-6,
        "opposed_normal_residual_tolerance": 1e-7,
        "flat_world_mapping_tolerance": 1e-7,
        "boundary_separation_tolerance": 1e-7,
        "polygon_robustness_epsilon": 1e-9,
    }
    with pytest.raises(ValueError, match=field):
        AssemblyGeometryToleranceContract(**{**baseline, field: bad})
    # The canonical numerical tolerance source remains unchanged.
    assert AssemblyGeometryToleranceContract(**baseline).coplanar_distance_tolerance == 1e-6


@pytest.mark.parametrize("invalid_length", [-1.0, -120.0, -1e-9])
def test_r6_material_segment_rejects_negative_source_instead_of_clamping(invalid_length):
    """Physical unfolded material cannot silently convert a bad minus into 0 mm."""
    with pytest.raises(ValueError, match="MaterialSegment length"):
        MaterialSegment(axis="X", name="source_fold", length=invalid_length, source="profile")
    assert MaterialSegment("X", "zero_relief", 0.0, "profile").length == 0.0
    assert MaterialSegment("X", "real_flat", 29.0, "profile").length == 29.0


@pytest.mark.parametrize("axis", ["X", "Y"])
def test_r6_multiple_finite_segments_cannot_overflow_manufacturing_blank(axis):
    """Two finite raw lengths may sum to Inf, which is not a physical DXF blank."""
    from ae_engine.manufacturing_render_data import UnfoldedBlankTopology
    overlarge = (
        MaterialSegment(axis, "first", 1e308, "profile"),
        MaterialSegment(axis, "second", 1e308, "profile"),
    )
    ordinary = (MaterialSegment("X", "real", 35.0, "profile"),)
    topology = UnfoldedBlankTopology(
        piece_id="head", x_segments=overlarge if axis == "X" else ordinary,
        y_segments=overlarge if axis == "Y" else ordinary,
        source="profile",
    )
    with pytest.raises(ValueError, match=f"UnfoldedBlankTopology {axis.lower()}.*finite"):
        _ = topology.width if axis == "X" else topology.height
    assert (topology.height if axis == "X" else topology.width) == 35.0
