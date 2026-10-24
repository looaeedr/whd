# -*- coding: utf-8 -*-
"""Manually traced R6 source guards for NFB V5 identity and physical weld Z.

Tests reference the actual model catalogue, fixed-plate source equations,
assembled corner residuals and production DTOs. They are not manufacturing
release receipts for the rest of the six-round 116-item audit.
"""
import math

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import read_numeric_specs
from ae_engine.receiving_tier_ear_z_targets import (
    _current_brand_config, _tier_source_depths,
)
from ae_engine.receiving_weld_ear_policy import (
    receiving_source_fixing_pitch_x_mm, resolve_receiving_large_weld_ear_fit,
)
from ae_engine.contracts import (
    AssemblyGeometryToleranceContract, JointMarkingProductionStatus,
)
from ae_engine.manufacturing_render_data import MaterialSegment
from ae_engine.sheetmetal_features import (
    CanvasTransform, Vec2, expand_linear_pattern, expand_grid_pattern,
    indicator_box_opening_size,
)
from types import SimpleNamespace
from ae_engine.sheetmetal_corner_policy import (
    CornerTypeResidual, GeometryError, compose_corner_residual,
    CornerTypeSelection, CornerTypeId, corner_selection_residual,
    box_body_height_from_corner_policies, FourCornerTypePolicy,
)


def test_r6_tier_ear_bad_set_bay_fails_closed_without_attribute_error():
    for layout in (
        {"sets": ["bad"]},
        {"sets": [{"bays": ["bad"]}]},
        {"sets": [{"bays": "bad"}]},
    ):
        with pytest.raises(ValueError, match="EAR_Z_"):
            _current_brand_config({"receiving_layout": layout})


def test_r6_v5_tier_depth_brand_is_model_owned_not_legacy_set_owned():
    source = next(
        spec for spec in read_numeric_specs("士林")
        if spec.depth_mm is not None
    )
    model = numeric_model_ref("士林", source.model)
    config = {"layer_count": 1, "holes": [
        {"layer_index": 0, "model_filename": model}
    ]}
    assert _tier_source_depths(None, config, 0) == pytest.approx((source.depth_mm,))
    config["holes"][0]["source_brand"] = "東元"
    assert _tier_source_depths(None, config, 0) == ()


def test_r6_fixed_plate_source_remains_parametric_and_rejects_boolean():
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=800, box_side_thickness_mm=2
    ) == pytest.approx(670.)
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800., box_side_thickness_mm=2.,
        fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=210.,
    )
    assert fit.fixing_center_from_inside_skin_mm == pytest.approx(63.)
    assert fit.nominal_fold_from_weld_edge_mm == pytest.approx(23.)
    for bad in (True, float("nan")):
        with pytest.raises(ValueError):
            receiving_source_fixing_pitch_x_mm(
                box_outer_width_mm=bad, box_side_thickness_mm=2.)
        with pytest.raises(ValueError):
            resolve_receiving_large_weld_ear_fit(
                box_outer_width_mm=bad, box_side_thickness_mm=2.,
                fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=210.)


def test_r6_assembly_tolerance_and_production_gate_refuse_invalid_types():
    data = dict(
        coplanar_distance_tolerance=1e-6,
        opposed_normal_residual_tolerance=1e-7,
        flat_world_mapping_tolerance=1e-7,
        boundary_separation_tolerance=1e-7,
        polygon_robustness_epsilon=1e-9,
    )
    for invalid in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="coplanar_distance_tolerance"):
            AssemblyGeometryToleranceContract(
                **{**data, "coplanar_distance_tolerance": invalid}
            )
    with pytest.raises(ValueError, match="production_policy_count"):
        JointMarkingProductionStatus(
            gate_state="ACTIVE", activation_enabled=True,
            export_disposition="BLOCK_EXPORT", production_policy_count=True,
        )


def test_r6_material_segment_is_never_nan_inf_or_boolean():
    for invalid in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="MaterialSegment length"):
            MaterialSegment(axis="X", name="source", length=invalid, source="CSV")
    assert MaterialSegment(axis="X", name="flat", length=20., source="flat").length == 20.


def test_r6_corner_second_cut_needs_complete_physical_geometry():
    for bad in (
        CornerTypeResidual((10., 10.), secondary_u=5., secondary_depth=None),
        CornerTypeResidual((10., 10.), slot_width=2., slot_straight_depth=None,
                           slot_radius=None),
    ):
        with pytest.raises(GeometryError, match="不完整"):
            compose_corner_residual(bad, fold_u=15., fold_v=15.)
    with pytest.raises(GeometryError):
        corner_selection_residual(
            CornerTypeSelection(CornerTypeId.OVERLAY),
            thickness=True, fw=20.,
        )
    for height in (True, float("nan")):
        with pytest.raises(GeometryError):
            box_body_height_from_corner_policies(height, 2.)


def test_r6_canvas_hole_pattern_and_fw_guard_real_numeric_inputs():
    for value in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            CanvasTransform(scale=value, origin_x=0., origin_y=0.)
    feature = SimpleNamespace(offset=Vec2(0., 0.))
    with pytest.raises(ValueError, match="boolean"):
        expand_linear_pattern(feature, count=True, pitch=10., axis="x")
    with pytest.raises(ValueError, match="integers"):
        expand_grid_pattern(feature, rows=2.5, columns=2, pitch_x=10., pitch_y=10.)
    with pytest.raises(ValueError, match="boolean"):
        indicator_box_opening_size([1], thickness=True)
    with pytest.raises(ValueError, match="thickness"):
        indicator_box_opening_size([1], thickness=float("nan"))


def test_r6_four_corner_fw_cannot_hide_boolean_or_nonfinite_override():
    corner = CornerTypeSelection(CornerTypeId.CROSS)
    for invalid in (True, float("nan"), float("inf"), -2.):
        cfg = FourCornerTypePolicy(
            corner, corner, corner, corner,
            fw=20., bottom_fw=invalid,
        )
        with pytest.raises(GeometryError):
            cfg.fw_for("bottom_left")
    valid = FourCornerTypePolicy(corner, corner, corner, corner, fw=20.)
    assert valid.fw_for("top_right") == 20.

@pytest.mark.parametrize("invalid_bay", [None, False, 0, "bad", [], ()])
def test_r6_unselected_flat_nfb_depth_rejects_corrupt_one_bay_without_crash(invalid_bay):
    """A malformed saved Bay cannot become the physical flat-base depth owner."""
    from ae_engine.receiving_nfb_depth_surface_policy import committed_receiving_flat_nfb_depth_mm

    snapshot = {"receiving_layout": {"sets": [
        {"stable_id": "set-1", "bays": [invalid_bay]},
    ]}}
    assert committed_receiving_flat_nfb_depth_mm(snapshot) is None
    unsubmitted = {"receiving_layout": {"sets": [
        {"stable_id": "set-1", "bays": [{"stable_id": "bay-1", "nfb_config_submitted": False}]},
    ]}}
    assert committed_receiving_flat_nfb_depth_mm(unsubmitted) is None
