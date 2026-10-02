# -*- coding: utf-8 -*-
import pytest
from shapely.geometry import box

from ae_engine.assembly_collision import (
    FlatInterferenceProjection,
    fit_joint_projection_to_corner_topology,
)


def test_topology_fitter_rejects_secondary_stage_when_contract_is_single_stage():
    component = box(0, 0, 20, 20)
    # Two horizontal depth bands implied by a stepped component.
    component = box(0,0,20,10).union(box(0,10,10,20))
    projection = FlatInterferenceProjection(
        segments_2d=(((15, 5), (15, 9)), ((8, 12), (8, 18))), points_2d=(), pair_count=2
    )
    with pytest.raises(ValueError, match="topology"):
        fit_joint_projection_to_corner_topology(
            projection=projection, relief_component=component, blank_bounds=(0,0,100,100),
            corner_name="bottom_left", topology_levels=1,
        )


def test_topology_fitter_returns_two_stage_measurement_for_two_stage_contract():
    component = box(0,0,20,10).union(box(0,10,10,20))
    projection = FlatInterferenceProjection(
        segments_2d=(((15, 5), (15, 9)), ((8, 12), (8, 18))), points_2d=(), pair_count=2
    )
    fitted = fit_joint_projection_to_corner_topology(
        projection=projection, relief_component=component, blank_bounds=(0,0,100,100),
        corner_name="bottom_left", topology_levels=2,
    )
    assert fitted is not None
    assert fitted.measurement.secondary_u is not None
    assert fitted.measurement.secondary_depth is not None


def test_wrap_backprojects_interference_onto_wrapped_target_flat_not_wrapper():
    from ae_engine.assembly_geometry import MappedSkinTriangle
    from ae_engine.assembly_collision import project_joint_interference_to_relief_owner
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation

    joint = AssemblyJoint(
        joint_id="head-wrap-body",
        subject_part="head",
        target_part="box_body",
        subject_region="rear_edge",
        target_region="top_left",
        relation=AssemblyJointRelation.WRAP,
    )
    target_skin = MappedSkinTriangle(
        flat=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
        world=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        side=1,
    )
    wrapper_world = (
        ((5.0, -5.0, -1.0), (5.0, 15.0, -1.0), (5.0, 5.0, 1.0)),
    )

    result = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part={"head": wrapper_world, "box_body": (target_skin.world,)},
        mapped_skin_triangles_by_part={"box_body": (target_skin,)},
        flat_material_by_part={"box_body": box(0.0, 0.0, 10.0, 10.0)},
    )

    assert result.joint_id == "head-wrap-body"
    assert result.preserve_part == "head"
    assert result.relief_part == "box_body"
    assert result.projection.pair_count == 1
    assert result.projection.segments_world
    assert len(result.projection.segments_world[0][0]) == 3
    assert result.illegal_penetration is True
    assert result.projection.segments_2d[0][0][0] == pytest.approx(5.0)


def test_insert_backprojects_interference_onto_inserting_subject_flat():
    from ae_engine.assembly_geometry import MappedSkinTriangle
    from ae_engine.assembly_collision import project_joint_interference_to_relief_owner
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation

    joint = AssemblyJoint(
        joint_id="head-insert-body", subject_part="head", target_part="box_body",
        subject_region="top_left", target_region="left_mating_zone",
        relation=AssemblyJointRelation.INSERT,
    )
    subject_skin = MappedSkinTriangle(
        flat=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
        world=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)), side=1,
    )
    target_world = (
        ((5.0, -5.0, -1.0), (5.0, 15.0, -1.0), (5.0, 5.0, 1.0)),
    )
    result = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part={"head": (subject_skin.world,), "box_body": target_world},
        mapped_skin_triangles_by_part={"head": (subject_skin,)},
        flat_material_by_part={"head": box(0.0, 0.0, 10.0, 10.0)},
    )
    assert result.relief_part == "head"
    assert result.preserve_part == "box_body"
    assert result.projection.pair_count == 1


def test_joint_discovery_fails_safe_when_relief_region_is_not_a_physical_corner():
    from ae_engine.assembly_geometry import MappedSkinTriangle
    from ae_engine.assembly_collision import discover_joint_relief_candidate
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation

    joint = AssemblyJoint(
        joint_id="head-wrap-body", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="rear_mating",
        relation=AssemblyJointRelation.WRAP,
    )
    target_skin = MappedSkinTriangle(
        flat=((0.0, 0.0), (20.0, 0.0), (0.0, 20.0)),
        world=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 20.0, 0.0)), side=1,
    )
    source = (((8.0,-5.0,-1.0),(8.0,20.0,-1.0),(8.0,8.0,1.0)),)
    result = discover_joint_relief_candidate(
        joint,
        world_triangles_by_part={"head":source,"box_body":(target_skin.world,)},
        mapped_skin_triangles_by_part={"box_body":(target_skin,)},
        flat_material_by_part={"box_body":box(0,0,20,20)},
        topology_levels=1,
    )
    assert result.status == "UNFITTED_REGION"
    assert result.cut_polygon_2d is None
    assert result.projection.illegal_penetration is True


def test_joint_discovery_fits_known_corner_without_bbox_guessing():
    from ae_engine.assembly_geometry import MappedSkinTriangle
    from ae_engine.assembly_collision import discover_joint_relief_candidate
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation

    joint = AssemblyJoint(
        joint_id="head-wrap-body", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="bottom_left",
        relation=AssemblyJointRelation.WRAP,
    )
    target_skin = MappedSkinTriangle(
        flat=((0.0, 0.0), (20.0, 0.0), (0.0, 20.0)),
        world=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 20.0, 0.0)), side=1,
    )
    source = (
        ((10.0,-5.0,-1.0),(10.0,20.0,-1.0),(10.0,15.0,1.0)),
        ((-5.0,15.0,-1.0),(20.0,15.0,-1.0),(10.0,15.0,1.0)),
    )
    result = discover_joint_relief_candidate(
        joint,
        world_triangles_by_part={"head":source,"box_body":(target_skin.world,)},
        mapped_skin_triangles_by_part={"box_body":(target_skin,)},
        flat_material_by_part={"box_body":box(0,0,20,20)},
        relief_component=box(0,0,20,20),
        topology_levels=1,
    )
    assert result.status == "CANDIDATE"
    assert result.cut_polygon_2d is not None
    assert result.corner_relief.measurement.secondary_u is None


def test_joint_candidate_replay_verifies_zero_penetration_on_relief_owner():
    from ae_engine.assembly_geometry import MappedSkinTriangle, folded_mesh_with_flat_uv_from_polygon
    from ae_engine.assembly_collision import discover_joint_relief_candidate, verify_joint_candidate_replay
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation

    joint = AssemblyJoint(
        joint_id="wrap", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="bottom_left", relation=AssemblyJointRelation.WRAP,
    )
    initial = box(0,0,20,20)

    def map_flat(material):
        mapped = folded_mesh_with_flat_uv_from_polygon(
            material, ({"len":20.0,"core":True},), ({"len":20.0,"core":True},)
        )
        return tuple(MappedSkinTriangle(flat=m.flat, world=m.local, side=0) for m in mapped)

    source = (
        ((10.0,-5.0,-1.0),(10.0,20.0,-1.0),(10.0,15.0,1.0)),
        ((-5.0,15.0,-1.0),(20.0,15.0,-1.0),(10.0,15.0,1.0)),
    )
    initial_skin = MappedSkinTriangle(
        flat=((0.0, 0.0), (20.0, 0.0), (0.0, 20.0)),
        world=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 20.0, 0.0)), side=0,
    )
    candidate = discover_joint_relief_candidate(
        joint,
        world_triangles_by_part={"head":source,"box_body":(initial_skin.world,)},
        mapped_skin_triangles_by_part={"box_body":(initial_skin,)},
        flat_material_by_part={"box_body":initial}, relief_component=initial, topology_levels=1,
    )
    assert candidate.status == "CANDIDATE"
    verified = verify_joint_candidate_replay(
        joint, candidate,
        world_triangles_by_part={"head":source},
        flat_material_by_part={"box_body":initial},
        rebuild_mapped_skins=lambda part, material: map_flat(material),
    )
    assert verified.verified is True
    assert verified.residual.illegal_penetration is False
    assert verified.solved_material.area < initial.area


def test_generic_world_skin_with_flat_uv_preserves_flat_mapping_for_box_body():
    from ae_engine.assembly_geometry import FoldedTriangleMap, world_skin_with_flat_uv
    mapped = (
        FoldedTriangleMap(
            flat=((0.0,0.0),(10.0,0.0),(0.0,10.0)),
            local=((0.0,0.0,0.0),(10.0,0.0,0.0),(0.0,10.0,0.0)),
        ),
    )
    skins = world_skin_with_flat_uv(mapped, "box_body", (100.0,80.0,40.0), sheet_thickness=2.0)
    assert len(skins) == 2
    assert skins[0].flat == mapped[0].flat
    assert skins[1].flat == mapped[0].flat
    assert skins[0].side == -1 and skins[1].side == 1
