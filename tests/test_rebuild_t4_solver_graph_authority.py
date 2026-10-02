# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    ResolvedAssemblyGraph,
)
from ae_engine.certified_relief_registry import CertifiedReliefStatus
from ae_engine.sheetmetal_geometry import CornerTypeId


def _insert_graph(part: str) -> ResolvedAssemblyGraph:
    joints = []
    for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
        joints.append(AssemblyJoint(
            f"{part}:{edge}",
            part,
            "box_body",
            f"{edge.lower()}_edge",
            f"{edge.lower()}_mating_zone",
            AssemblyJointRelation.INSERT,
            source=AssemblyJointSource.USER_ADDED,
            edge=edge,
        ))
    return ResolvedAssemblyGraph(("box_body", part), tuple(joints))


def test_solver_joint_graph_overrides_wrong_legacy_assembly_mirror_and_preserves_blank_topology():
    from tests.test_certified_relief_registry import _insert_fixture
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief

    body, endcap, body_profile, profiles = _insert_fixture("head")
    graph = _insert_graph("head")
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        # Deliberately wrong legacy mirror. The graph is the authority.
        assembly_intent=CornerTypeId.OVERLAY,
        assembly_graph=graph,
        endcap_part="head",
        allow_3d_fallback=False,
    )
    assert solution.verified is True
    assert solution.trust_level == CertifiedReliefStatus.CERTIFIED.value
    assert solution.rule_id == "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"
    assert solution.solved_render_data.unfolded_topology == endcap.unfolded_topology

def test_solver_graph_miss_does_not_fall_back_to_legacy_intent_formula():
    from tests.test_certified_relief_registry import _insert_fixture
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief

    body, endcap, body_profile, profiles = _insert_fixture("head")
    # LEFT/RIGHT WRAP is intentionally not certified by the current TOP registry.
    joints = (
        AssemblyJoint("top", "head", "box_body", "top_edge", "top_mating_zone", AssemblyJointRelation.INSERT,
                      source=AssemblyJointSource.USER_ADDED, edge="TOP"),
        AssemblyJoint("left", "head", "box_body", "left_edge", "left_mating_zone", AssemblyJointRelation.WRAP,
                      source=AssemblyJointSource.USER_ADDED, edge="LEFT"),
        AssemblyJoint("right", "head", "box_body", "right_edge", "right_mating_zone", AssemblyJointRelation.WRAP,
                      source=AssemblyJointSource.USER_ADDED, edge="RIGHT"),
        AssemblyJoint("bottom", "head", "box_body", "bottom_edge", "bottom_mating_zone", AssemblyJointRelation.INSERT,
                      source=AssemblyJointSource.USER_ADDED, edge="BOTTOM"),
    )
    graph = ResolvedAssemblyGraph(("box_body", "head"), joints)
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        assembly_intent=CornerTypeId.INSERT,  # would certify if incorrectly used
        assembly_graph=graph,
        endcap_part="head",
        allow_3d_fallback=False,
    )
    assert solution.verified is False
    assert solution.trust_level == "FAILED"
    assert solution.rule_id is None
