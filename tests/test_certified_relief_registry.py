# -*- coding: utf-8 -*-
"""Certified Relief Registry contract.

Known, certified assembly-relief formulas must win over 3D discovery.  The
3D solver may validate a certified answer, but it must not replace it with a
skin-intersection candidate such as 38.98/39/40 when the certified formula is
38.
"""
from __future__ import annotations

import pytest

from ae_engine import manufacturing_api
from ae_engine.certified_relief_registry import (
    CertifiedReliefStatus,
    lookup_certified_endcap_relief,
    registered_certified_relief_rules,
)
from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
from ae_engine.corner_type_ui import default_selection_for_box_assembly
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    FourCornerTypePolicy,
)
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments


def _insert_fixture(part_key: str):
    snapshot = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": "INSERT",
    }
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    )
    top = default_selection_for_box_assembly(CornerTypeId.INSERT)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)
    body_profile = build_box_body_profile(snapshot)
    # Certified INSERT_V1 applies to the already-confirmed linked EndCap top
    # chain where the editable ytop1 row has been structurally removed and FW is
    # the mating top fold.  Cases still carrying an explicit ytop1 row are left
    # to 3D fallback until separately certified.
    endcap_profiles = {
        "X": [
            {"len": 15, "angle": -90, "phase6_key": "yl1", "ui_len_add": 2.0},
            {"len": 392, "angle": -90, "phase6_key": "endcap_w_core", "core": "W-2T", "ui_len_add": 4.0},
            {"len": 15, "phase6_key": "yr1", "ui_len_add": 2.0},
        ],
        "Y": (
            [
                {"len": 15, "phase6_key": "ybottom1", "angle": -90.0, "ui_len_add": 2.0},
                {"len": 244, "phase6_key": "endcap_d_core", "core": "D-T", "angle": -90.0, "ui_len_add": 4.0},
                {"len": 25, "phase6_key": "fw", "ui_len_add": 2.0},
            ] if part_key == "tail" else [
                {"len": 25, "phase6_key": "fw", "angle": -90.0, "ui_len_add": 2.0},
                {"len": 244, "phase6_key": "endcap_d_core", "core": "D-T", "angle": -90.0, "ui_len_add": 4.0},
                {"len": 15, "phase6_key": "ybottom1", "ui_len_add": 2.0},
            ]
        ),
    }
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        fold_profile=profile_to_fold_segments(body_profile),
        head_corner_policy=policy, tail_corner_policy=policy,
        head_ybottom1=15, tail_ybottom1=15,
    ))
    endcap = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        is_tail=(part_key == "tail"),
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=15, box_fold_right=15,
        fold_profile_x=profile_to_fold_segments(endcap_profiles["X"]),
        fold_profile_y=profile_to_fold_segments(endcap_profiles["Y"]),
        corner_policy=policy,
    ))
    return body, endcap, body_profile, endcap_profiles


def test_registry_contains_certified_insert_formula_not_dead_dimension():
    rules = {rule.rule_id: rule for rule in registered_certified_relief_rules()}
    rule = rules["ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"]
    assert rule.status is CertifiedReliefStatus.CERTIFIED
    assert rule.assembly_intent is CornerTypeId.INSERT
    assert "38" not in rule.formula_x
    assert "27" not in rule.formula_y
    assert "structural contact" in rule.formula_x.lower()


@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_certified_insert_lookup_returns_38_by_27_formula_result(part_key):
    body, endcap, body_profile, endcap_profiles = _insert_fixture(part_key)
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.INSERT,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        sheet_thickness=2,
    )
    assert result is not None
    assert result.trust_level is CertifiedReliefStatus.CERTIFIED
    assert result.rule_id == "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"
    by_name = {relief.corner_name: relief.measurement for relief in result.corner_reliefs}
    expected_names = ({"bottom_left", "bottom_right"} if part_key == "head" else {"top_left", "top_right"})
    assert set(by_name) == expected_names
    for measurement in by_name.values():
        assert measurement.primary_u == pytest.approx(38.0, abs=1e-6)
        assert measurement.primary_v == pytest.approx(27.0, abs=1e-6)
        assert measurement.secondary_u is None
        assert measurement.secondary_depth is None


@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_solver_uses_certified_insert_formula_and_only_shadow_validates(part_key):
    body, endcap, body_profile, endcap_profiles = _insert_fixture(part_key)
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="bottom" if part_key == "tail" else "top",
        sheet_thickness=2,
        clearance=0,
        assembly_intent=CornerTypeId.INSERT,
    )
    assert solution.trust_level == CertifiedReliefStatus.CERTIFIED.value
    assert solution.rule_id == "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"
    assert solution.verified is True
    assert any(projection.has_interference for projection in solution.projections)
    for relief in solution.corner_reliefs:
        assert relief.measurement.primary_u == pytest.approx(38.0, abs=1e-6)
        assert relief.measurement.primary_v == pytest.approx(27.0, abs=1e-6)


def test_registry_rejects_insert_result_that_invents_second_stage(monkeypatch):
    """A one-stage INSERT rule may never return two-stage corner geometry."""
    from dataclasses import replace
    from shapely.geometry import box
    import ae_engine.certified_relief_registry as registry
    from ae_engine.assembly_collision import BackprojectedCornerRelief, CornerReliefMeasurement

    base = registry.CertifiedReliefRule(
        rule_id="BAD_INSERT_TWO_STAGE",
        revision=1,
        status=registry.CertifiedReliefStatus.CERTIFIED,
        cabinet_family="ANY",
        part_role="HEAD_OR_TAIL",
        joint_face="TOP",
        assembly_intent=CornerTypeId.INSERT,
        topology_levels=1,
        formula_x="bad",
        formula_y="bad",
        source_evidence="regression fixture",
        evaluator=None,
    )

    def evaluator(*, rule, **_kwargs):
        cut = box(0, 0, 10, 10)
        measurement = CornerReliefMeasurement(
            "bottom_left", 10.0, 10.0, secondary_u=5.0, secondary_depth=2.0
        )
        return registry.CertifiedReliefResult(
            rule=rule,
            cut_polygons=(cut,),
            corner_reliefs=(BackprojectedCornerRelief("bottom_left", cut, measurement),),
        )

    bad = replace(base, evaluator=evaluator)
    monkeypatch.setattr(registry, "_RULES", (bad,))
    _body, endcap, body_profile, endcap_profiles = _insert_fixture("head")

    with pytest.raises(registry.CertifiedReliefRegistryError, match="topology"):
        registry.lookup_certified_endcap_relief(
            assembly_intent=CornerTypeId.INSERT,
            endcap_render_data=endcap,
            box_body_x_profile=body_profile,
            endcap_x_profile=endcap_profiles["X"],
            endcap_y_profile=endcap_profiles["Y"],
            sheet_thickness=2,
        )


def test_joint_signature_with_wrap_does_not_hit_plain_insert_rule():
    _body, endcap, body_profile, endcap_profiles = _insert_fixture("head")
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.INSERT,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        sheet_thickness=2,
        joint_signature_relations=("INSERT", "WRAP"),
    )
    assert result is None


def test_wrap_registry_miss_never_cuts_wrapper_as_unsafe_fallback():
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    body, endcap, body_profile, endcap_profiles = _insert_fixture("head")
    wrap = AssemblyJoint(
        joint_id="head-wrap-box",
        subject_part="head", target_part="box_body",
        subject_region="top_left", target_region="rear_mating",
        relation=AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED,
    )
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        clearance=0,
        assembly_intent=CornerTypeId.INSERT,
        assembly_joint=wrap,
    )
    assert solution.verified is False
    assert solution.trust_level == "FAILED"
    assert solution.shadow_validation["reason"] == "WRAP_RELIEF_OWNER_IS_TARGET"
    assert solution.shadow_validation["preserve_part"] == "head"
    assert solution.shadow_validation["relief_part"] == "box_body"


def test_editable_candidate_can_be_evaluated_ephemerally_and_shadow_validated_without_registry_mutation():
    from ae_engine.certified_relief_registry import evaluate_editable_endcap_rule_record
    body, endcap, body_profile, endcap_profiles = _insert_fixture("head")
    record = {
        "rule_id": "FORM_PREVIEW_INSERT",
        "cabinet_family": "ANY",
        "part_role": "HEAD_OR_TAIL",
        "joint_face": "TOP",
        "assembly_intent": "INSERT",
        "joint_signature": [{
            "relation": "INSERT", "subject_role": "HEAD_OR_TAIL", "target_role": "BOX_SIDE",
            "subject_region": "TOP", "target_region": "MATING_ZONE",
        }],
        "topology_levels": 1,
        "preconditions": ["ytop1_absent", "x_folded"],
        "formula": {"primary_u": "side_fold + FW - T", "primary_v": "FW + T"},
        "source": "candidate-specific preview test",
    }
    ephemeral = evaluate_editable_endcap_rule_record(
        record,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        sheet_thickness=2,
    )
    assert ephemeral is not None
    assert ephemeral.rule_id == "FORM_PREVIEW_INSERT"
    assert ephemeral.rule_revision == 0
    assert all(r.measurement.primary_u == pytest.approx(38.0) for r in ephemeral.corner_reliefs)

    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        clearance=0,
        assembly_intent=CornerTypeId.INSERT,
        allow_3d_fallback=False,
        certified_result_override=ephemeral,
    )
    assert solution.rule_id == "FORM_PREVIEW_INSERT"
    assert solution.rule_revision == 0
    assert solution.verified is True
