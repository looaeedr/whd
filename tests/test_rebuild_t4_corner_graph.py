# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource, ResolvedAssemblyGraph


def _j(edge, relation, jid):
    return AssemblyJoint(jid, "head", "box_body", f"{edge.lower()}_edge", f"{edge.lower()}_mating_zone", relation, source=AssemblyJointSource.USER_ADDED, edge=edge)


def test_nearby_corner_reads_both_face_and_side_edges_and_keeps_asymmetry():
    graph = ResolvedAssemblyGraph(("box_body","head"), (
        _j("TOP", AssemblyJointRelation.OVERLAY, "top"),
        _j("LEFT", AssemblyJointRelation.INSERT, "left"),
        _j("RIGHT", AssemblyJointRelation.WRAP, "right"),
        _j("BOTTOM", AssemblyJointRelation.INSERT, "bottom"),
    ))
    left = graph.nearby_joints("head", "top_left")
    right = graph.nearby_joints("head", "top_right")
    assert {(j.edge, j.relation.value) for j in left} == {("TOP","OVERLAY"),("LEFT","INSERT")}
    assert {(j.edge, j.relation.value) for j in right} == {("TOP","OVERLAY"),("RIGHT","WRAP")}


def test_standard_corner_comes_from_fold_topology_not_final_polygon_bbox():
    from ae_engine.corner_resolver import standard_corner_geometry
    from ae_engine.contracts import FoldProfileSegment
    x = (
        FoldProfileSegment(15, angle=-90, phase6_key="yl1"),
        FoldProfileSegment(392, angle=-90, phase6_key="endcap_w_core"),
        FoldProfileSegment(15, phase6_key="yr1"),
    )
    y = (
        FoldProfileSegment(16, angle=-90, phase6_key="ytop1"),
        FoldProfileSegment(25, angle=-90, phase6_key="fw"),
        FoldProfileSegment(244, angle=-90, phase6_key="endcap_d_core"),
        FoldProfileSegment(15, phase6_key="ybottom1"),
    )
    assert standard_corner_geometry("top_left", x, y).primary_u == 15
    assert standard_corner_geometry("top_left", x, y).primary_v == 41
    assert standard_corner_geometry("bottom_left", x, y).primary_v == 15


def test_graph_corner_pattern_derives_registry_intent_without_high_level_preset():
    from ae_engine.corner_resolver import registry_intent_for_corner
    graph = ResolvedAssemblyGraph(("box_body","head"), (
        _j("TOP", AssemblyJointRelation.OVERLAY, "top"),
        _j("LEFT", AssemblyJointRelation.INSERT, "left"),
        _j("RIGHT", AssemblyJointRelation.OVERLAY, "right"),
        _j("BOTTOM", AssemblyJointRelation.INSERT, "bottom"),
    ))
    assert registry_intent_for_corner(graph, "head", "top_left").value == "INSERT_OVERLAY"
    assert registry_intent_for_corner(graph, "head", "top_right").value == "OVERLAY"
