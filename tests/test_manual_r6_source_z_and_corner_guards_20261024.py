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

@pytest.mark.parametrize("total_rows,unit_rows", [(True, 1), (1, True)])
def test_r6_flat_base_layer_count_is_exact_integer_not_bool(total_rows, unit_rows):
    from ae_engine.receiving_nfb_depth_surface_policy import committed_receiving_flat_nfb_depth_mm
    source = {"receiving_layout": {"sets": [{"bays": [{
        "nfb_config_submitted": True,
        "nfb_config": {"layer_count": total_rows, "holes": [{
            "model_filename": "nfbv5:士林:MODEL_TEST",
            "layer_count": unit_rows, "slot_index": 0,
        }]},
    }]}]}}
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_MULTIPLE_ROWS_NEED_DISTINCT_BASE"):
        committed_receiving_flat_nfb_depth_mm(source)


def test_r6_v5_model_owns_brand_even_if_legacy_set_brand_is_stale(monkeypatch):
    from ae_engine import receiving_nfb_model_identity as identity
    from ae_engine.receiving_nfb_depth_surface_policy import _source_depth_for_submitted_hole
    ref = "nfbv5:士林:MODEL_TEST"
    monkeypatch.setattr(
        identity, "selected_numeric_spec",
        lambda brand, model: SimpleNamespace(depth_mm=107.)
        if (brand, model) == ("士林", ref) else None,
    )
    assert _source_depth_for_submitted_hole(
        {"model_filename": ref}, legacy_set_brand="東元",
    ) == 107.
    with pytest.raises(ValueError, match="RECEIVING_NFB_DEPTH_V5_BRAND_IDENTITY_MISMATCH"):
        _source_depth_for_submitted_hole(
            {"model_filename": ref, "source_brand": "東元"}, legacy_set_brand="東元",
        )

@pytest.mark.parametrize("invalid_thickness", [None, True, False])
def test_r6_flat_nfb_pad_source_rejects_nonphysical_thickness_before_generation(
    monkeypatch, invalid_thickness,
):
    """Never coerce bool->1 mm or None into the physical PAD tooling owner."""
    from ae_engine import receiving_nfb_depth_surface_policy as policy
    from ae_engine import receiving_nfb_model_identity as identity
    from ae_engine import receiving_nfb_numeric_catalog as catalog

    spec = SimpleNamespace(dimensionally_complete=True)
    monkeypatch.setattr(identity, "selected_numeric_spec", lambda *_: spec)
    monkeypatch.setattr(catalog, "model_spec", lambda *_: spec)
    monkeypatch.setattr(
        policy, "_source_depth_for_submitted_hole",
        lambda hole, **_kw: 107. if hole["model_filename"].endswith("MODEL_A") else 72.,
    )
    rows = [
        {"model_filename": "nfbv5:士林:MODEL_A", "source_brand": "士林", "slot_index": 0},
        {"model_filename": "nfbv5:士林:MODEL_B", "source_brand": "士林", "slot_index": 1},
    ]
    source = {"t": invalid_thickness, "receiving_layout": {"sets": [{"bays": [{
        "nfb_config_submitted": True,
        "nfb_config": {"layer_count": 1, "holes": rows},
    }]}]}}
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_PLATE_THICKNESS_INVALID"):
        policy.committed_receiving_flat_nfb_depth_mm(source)

@pytest.mark.parametrize("bad_tier", [True, False, 1., 0., "1", None, -1, 2, []])
def test_r6_ear_z_tier_depth_source_never_coerces_boolean_or_fractional_tier(bad_tier):
    """One NFB may not borrow a different physical tier's Z via Python equality."""
    source = next(spec for spec in read_numeric_specs("士林") if spec.depth_mm is not None)
    model = numeric_model_ref("士林", source.model)
    config = {"layer_count": 2, "holes": [
        {"layer_index": bad_tier, "model_filename": model},
    ]}
    assert _tier_source_depths(None, config, 1) == ()
    # Correct immutable source still resolves only its own typed integer tier.
    config["holes"][0]["layer_index"] = 1
    assert _tier_source_depths(None, config, 1) == pytest.approx((source.depth_mm,))
    assert _tier_source_depths(None, config, 0) == ()


@pytest.mark.parametrize("bad_count", [True, False, 0, 1., "1", None])
def test_r6_ear_z_tier_depth_requires_actual_positive_integer_layer_count(bad_count):
    source = next(spec for spec in read_numeric_specs("士林") if spec.depth_mm is not None)
    model = numeric_model_ref("士林", source.model)
    config = {"layer_count": bad_count, "holes": [{"model_filename": model}]}
    assert _tier_source_depths(None, config, 0) == ()
    config["layer_count"] = 1
    assert _tier_source_depths(None, config, 0) == pytest.approx((source.depth_mm,))


@pytest.mark.parametrize("bad_holes", [True, False, 42, "not-a-hole-list", {"hole": 1}])
def test_r6_ear_z_source_rejects_nonsequence_hole_containers_without_raw_typeerror(bad_holes):
    """The EAR/Z physical source must reject a corrupt hole array safely."""
    config = {"layer_count": 1, "holes": bad_holes}
    with pytest.raises(ValueError, match="EAR_Z_SOURCE_HOLE_INVALID"):
        _tier_source_depths(None, config, 0)
    assert config["holes"] is bad_holes


def test_r6_ear_z_missing_hole_list_is_unresolved_not_certified():
    assert _tier_source_depths(None, {"layer_count": 1}, 0) == ()
    assert _tier_source_depths(None, {"layer_count": 1, "holes": []}, 0) == ()


def test_r6_joint_marking_policy_activation_and_revision_never_coerce_corrupt_types():
    """A saved "false" must never activate a manufactured Joint MARKING policy."""
    from dataclasses import replace
    from ae_engine.contracts import JointMarkingPolicy
    from ae_engine.joint_marking_policy import JointMarkingPolicyRegistry

    valid = JointMarkingPolicy(
        policy_id="RECEIVING_TEST_POLICY",
        revision=1,
        enabled=False,
        locator_selector="RECEIVING_DIVIDER",
        attached_selector="RECEIVING_INNER_FRAME",
        locator_contact_region="CORE_PHYSICAL_SEGMENT",
        attached_contact_region="LOWER_TERMINAL_FACE",
        footprint_mode="SIDE_BOUNDARY_PAIR",
        boundary_frame_contract={"frame_version": "CONTACT_LOCAL_FRAME_V1"},
        contact_span_contract="EXPECTED_REGION_COVERAGE",
        allowed_overlap_contract="NONE",
    )
    disabled = JointMarkingPolicyRegistry((valid,)).resolve(
        locator_selector=valid.locator_selector,
        attached_selector=valid.attached_selector,
    )
    assert disabled.status == "NO_POLICY_REQUIRED"
    assert disabled.policy is None
    active = replace(valid, enabled=True)
    assert JointMarkingPolicyRegistry((active,)).resolve(
        locator_selector=valid.locator_selector,
        attached_selector=valid.attached_selector,
    ).policy == active

    for corrupt_activation in ("false", "0", 0, 1, None):
        with pytest.raises(ValueError, match="enabled must be boolean"):
            replace(valid, enabled=corrupt_activation)
    for corrupt_revision in (True, 1.5, "1", float("nan"), float("inf"), 0, -1):
        with pytest.raises(ValueError, match="revision must be a positive integer"):
            replace(valid, revision=corrupt_revision)
    # Positive Python integers remain valid revision identities: this source
    # defines no arbitrary upper cap, and rejects only fractional/mistyped IDs.
    assert replace(valid, revision=2).revision == 2
    assert replace(valid, revision=10 ** 400).revision == 10 ** 400


@pytest.mark.parametrize("field", [
    "reference_nfb_depth_mm", "secondary_nfb_depth_mm", "base_plate_thickness_mm",
])
def test_r6_nfb_second_side_depth_conversion_overflow_fails_as_physical_value_error(field):
    """Malformed depth sources never escape into a manufactured second return."""
    from ae_engine.receiving_nfb_depth_surface_policy import receiving_nfb_second_side_fold_mm
    dimensions = {
        "reference_nfb_depth_mm": 107.,
        "secondary_nfb_depth_mm": 72.,
        "base_plate_thickness_mm": 2.,
    }
    assert receiving_nfb_second_side_fold_mm(**dimensions) == 33.
    dimensions[field] = 10 ** 400
    with pytest.raises(ValueError, match="NFB depth and base plate T"):
        receiving_nfb_second_side_fold_mm(**dimensions)


@pytest.mark.parametrize("field", [
    "inner_door_outer_face_from_front_mm", "inner_door_thickness_mm",
    "base_plate_thickness_mm", "fixing_plate_thickness_mm",
    "reference_nfb_depth_mm", "secondary_nfb_depth_mm",
])
def test_r6_nfb_formed_skin_z_chain_conversion_overflow_fails_closed(field):
    """Malformed D/T cannot leak raw overflow or create an infinite contact Z."""
    from ae_engine.receiving_nfb_depth_surface_policy import resolve_receiving_nfb_surface_chain
    dimensions = {
        "inner_door_outer_face_from_front_mm": 80.,
        "inner_door_thickness_mm": 2.,
        "base_plate_thickness_mm": 2.,
        "fixing_plate_thickness_mm": 2.,
        "reference_nfb_depth_mm": 107.,
        "secondary_nfb_depth_mm": 72.,
    }
    good = resolve_receiving_nfb_surface_chain(**dimensions)
    assert good.second_side_fold_mm == 33.
    assert good.fixing_plate_contact_face_mm == 191.
    dimensions[field] = 10 ** 400
    with pytest.raises(ValueError, match="surface chain"):
        resolve_receiving_nfb_surface_chain(**dimensions)
