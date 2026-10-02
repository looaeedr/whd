# -*- coding: utf-8 -*-
"""Registry-driven assembly regression matrix.

Adding a new box Assembly Intent to BOX_ASSEMBLY_TYPE_IDS automatically adds it
here.  A registered intent is not deliverable unless both Head and Tail can
show pre-solve collision evidence and converge to a verified zero-penetration
3D relief result from the same manufacturing geometry.
"""
from __future__ import annotations

import pytest

from ae_engine import manufacturing_api
from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
from ae_engine.corner_type_ui import BOX_ASSEMBLY_TYPE_IDS, default_selection_for_box_assembly
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    FourCornerTypePolicy,
)
from phase6_fold_profiles import build_box_body_profile, build_endcap_xy_profiles, profile_to_fold_segments


def _case(intent: CornerTypeId, part_key: str):
    snapshot = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "assembly_type": intent.value,
    }
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH,
        amount_t=0.5,
    )
    top = default_selection_for_box_assembly(intent)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)
    body_profile = build_box_body_profile(snapshot)
    endcap_profiles = build_endcap_xy_profiles(snapshot, part_key=part_key)
    body = manufacturing_api.build_part_render_data(BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        fold_profile=profile_to_fold_segments(body_profile),
        head_corner_policy=policy, tail_corner_policy=policy,
        head_ybottom1=15, tail_ybottom1=15,
    ))
    is_tail = part_key == "tail"
    endcap = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        is_tail=is_tail,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=15, box_fold_right=15,
        fold_profile_x=profile_to_fold_segments(endcap_profiles["X"]),
        fold_profile_y=profile_to_fold_segments(endcap_profiles["Y"]),
        corner_policy=policy,
    ))
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=endcap_profiles["X"],
        endcap_y_profile=endcap_profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="bottom" if is_tail else "top",
        sheet_thickness=2,
        clearance=0,
        assembly_intent=intent,
        cabinet_family="金庫型",
    )
    return endcap, solution


@pytest.mark.parametrize("intent", BOX_ASSEMBLY_TYPE_IDS, ids=lambda item: item.value)
@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_registered_assembly_intent_has_collision_evidence_then_verifies_zero_penetration(intent, part_key):
    _endcap, solution = _case(intent, part_key)
    assert solution.projections, f"{intent.value}/{part_key} must execute pre-solve collision probes"
    assert any(item.has_interference for item in solution.projections), (
        f"{intent.value}/{part_key} must preserve actual pre-solve collision evidence"
    )
    assert solution.verified is True, f"{intent.value}/{part_key} must refold with zero retained-material penetration"
    assert solution.residual_projection is not None

@pytest.mark.parametrize("intent", BOX_ASSEMBLY_TYPE_IDS, ids=lambda item: item.value)
@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_registered_assembly_intent_uses_certified_rule_topology_stage_count(intent, part_key):
    """Certified rule topology is the final manufacturing topology source of truth."""
    from ae_engine.certified_relief_registry import registered_certified_relief_rules

    _endcap, solution = _case(intent, part_key)
    assert solution.trust_level == "CERTIFIED"
    assert solution.rule_id is not None
    assert solution.rule_revision is not None

    rule = next(
        item
        for item in registered_certified_relief_rules()
        if item.rule_id == solution.rule_id and item.revision == solution.rule_revision
    )
    expected_has_secondary = int(rule.topology_levels) == 2
    actual = {
        relief.corner_name: relief.measurement.secondary_u is not None
        for relief in solution.corner_reliefs
    }
    assert actual, f"{intent.value}/{part_key} must resolve at least one manufacturing corner"
    for name, has_secondary in actual.items():
        assert has_secondary is expected_has_secondary, (
            f"{intent.value}/{part_key}/{name}: certified {rule.rule_id}@{rule.revision} "
            f"declares topology_levels={rule.topology_levels}, actual secondary={has_secondary}"
        )

@pytest.mark.parametrize("intent", BOX_ASSEMBLY_TYPE_IDS, ids=lambda item: item.value)
@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_registered_symmetric_case_produces_mirror_equal_corner_measurements(intent, part_key):
    """The registry matrix fixture is X-symmetric; triangulation must not break that symmetry."""
    _endcap, solution = _case(intent, part_key)
    by_name = {item.corner_name: item.measurement for item in solution.corner_reliefs}
    for left_name, right_name in (("bottom_left", "bottom_right"), ("top_left", "top_right")):
        if left_name not in by_name or right_name not in by_name:
            continue
        left = by_name[left_name]
        right = by_name[right_name]
        assert left.primary_u == pytest.approx(right.primary_u, abs=1e-6)
        assert left.primary_v == pytest.approx(right.primary_v, abs=1e-6)
        assert left.secondary_u == pytest.approx(right.secondary_u, abs=1e-6) if left.secondary_u is not None else right.secondary_u is None
        assert left.secondary_depth == pytest.approx(right.secondary_depth, abs=1e-6) if left.secondary_depth is not None else right.secondary_depth is None
