# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import box

from ae_engine.manufacturing_api import PartRenderData
from ae_engine.assembly_collision import (
    AssemblyRole,
    AssemblyOwnershipPolicy,
    OwnershipAction,
    apply_endcap_relief_candidate,
    default_boxbody_endcap_ownership,
    detect_planar_collision,
    project_collision_to_endcap_relief,
    solve_boxbody_endcap_relief,
)
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def test_default_ownership_retains_box_body_and_cuts_endcap():
    policy = default_boxbody_endcap_ownership()

    assert policy.box_body is OwnershipAction.RETAIN
    assert policy.endcap is OwnershipAction.CUT


def test_detect_planar_collision_returns_overlap_region():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )

    assert collision is not None
    assert collision.source_role is AssemblyRole.BOX_BODY
    assert collision.target_role is AssemblyRole.ENDCAP
    assert collision.region.area == pytest.approx(300.0)


def test_detect_planar_collision_returns_none_for_disjoint_parts():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(120, 10, 140, 40),
    )

    assert collision is None


def test_project_collision_to_endcap_relief_expands_by_clearance():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )

    candidate = project_collision_to_endcap_relief(
        collision,
        default_boxbody_endcap_ownership(),
        clearance=2.0,
    )

    assert candidate is not None
    assert candidate.source_collision_area == pytest.approx(300.0)
    assert candidate.clearance == pytest.approx(2.0)
    minx, miny, maxx, maxy = candidate.cut_polygon_2d.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((88.0, 8.0, 102.0, 42.0))


def test_project_collision_returns_none_when_endcap_is_not_cut_owner():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )
    policy = default_boxbody_endcap_ownership()
    inverted = AssemblyOwnershipPolicy(
        box_body=OwnershipAction.CUT,
        endcap=OwnershipAction.RETAIN,
    )

    candidate = project_collision_to_endcap_relief(collision, inverted)

    assert policy.endcap is OwnershipAction.CUT
    assert candidate is None


def _rect_scene(width, height):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(
            Vec2(0, 0),
            Vec2(width, 0),
            Vec2(width, height),
            Vec2(0, height),
        ),
        layer="CUTTING",
        closed=True,
    ))
    return scene


def test_apply_endcap_relief_candidate_reduces_material_and_preserves_fold_guides():
    scene = _rect_scene(100, 50)
    render = PartRenderData(
        scene=scene,
        material=box(0, 0, 100, 50),
        fold_guides=("fold-guide-sentinel",),
    )
    candidate = project_collision_to_endcap_relief(
        detect_planar_collision(
            box_body_material=box(90, 10, 120, 40),
            endcap_material=render.material,
        ),
        default_boxbody_endcap_ownership(),
        clearance=0.0,
    )

    solved = apply_endcap_relief_candidate(render, candidate)

    assert solved.material.area == pytest.approx(4700.0)
    assert solved.fold_guides == ("fold-guide-sentinel",)
    cutting = [
        primitive for primitive in solved.scene.primitives
        if isinstance(primitive, PolylinePrimitive)
        and primitive.layer == "CUTTING"
        and primitive.closed
    ]
    assert len(cutting) == 1
    assert len(cutting[0].points) > 4


def test_solve_boxbody_endcap_relief_cuts_endcap_and_verifies_clear():
    endcap = PartRenderData(
        scene=_rect_scene(100, 50),
        material=box(0, 0, 100, 50),
        fold_guides=(),
    )
    box_body = PartRenderData(
        scene=_rect_scene(30, 30),
        material=box(90, 10, 120, 40),
        fold_guides=(),
    )

    solution = solve_boxbody_endcap_relief(
        box_body_render_data=box_body,
        endcap_render_data=endcap,
        clearance=0.0,
    )

    assert solution.original_collision is not None
    assert solution.candidate is not None
    assert solution.verified is True
    assert detect_planar_collision(
        box_body_material=box_body.material,
        endcap_material=solution.solved_render_data.material,
    ) is None


def test_solve_boxbody_endcap_relief_returns_original_when_no_collision():
    endcap = PartRenderData(
        scene=_rect_scene(100, 50),
        material=box(0, 0, 100, 50),
        fold_guides=(),
    )
    box_body = PartRenderData(
        scene=_rect_scene(20, 20),
        material=box(120, 10, 140, 30),
        fold_guides=(),
    )

    solution = solve_boxbody_endcap_relief(
        box_body_render_data=box_body,
        endcap_render_data=endcap,
    )

    assert solution.original_collision is None
    assert solution.candidate is None
    assert solution.verified is True
    assert solution.solved_render_data is endcap


def test_boxbody_endcap_world_meshes_share_one_assembly_coordinate_system():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_world_meshes

    box_body_local = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    endcap_local = (
        ((-50.0, -20.0, 0.0), (50.0, -20.0, 0.0), (50.0, 20.0, 0.0)),
        ((-50.0, -20.0, 0.0), (50.0, 20.0, 0.0), (-50.0, 20.0, 0.0)),
    )

    assembly = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=box_body_local,
        endcap_triangles=endcap_local,
        finished_dimensions=(100.0, 80.0, 40.0),
        endcap_placement="top",
    )

    body_points = [point for tri in assembly.box_body_triangles for point in tri]
    endcap_points = [point for tri in assembly.endcap_triangles for point in tri]

    assert min(point[1] for point in body_points) == pytest.approx(-40.0)
    assert max(point[1] for point in body_points) == pytest.approx(40.0)
    assert min(point[1] for point in endcap_points) == pytest.approx(40.0)
    assert max(point[1] for point in endcap_points) == pytest.approx(40.0)
    assert min(point[0] for point in endcap_points) == pytest.approx(-50.0)
    assert max(point[0] for point in endcap_points) == pytest.approx(50.0)


def test_boxbody_endcap_render_data_can_be_folded_into_same_world_assembly():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_render_meshes

    box_body = PartRenderData(
        scene=_rect_scene(100, 80),
        material=box(0, 0, 100, 80),
        fold_guides=(),
    )
    endcap = PartRenderData(
        scene=_rect_scene(100, 40),
        material=box(0, 0, 100, 40),
        fold_guides=(),
    )

    assembly = assemble_boxbody_endcap_render_meshes(
        box_body_render_data=box_body,
        endcap_render_data=endcap,
        box_body_x_profile=({"len": 100.0, "core": True},),
        endcap_x_profile=({"len": 100.0, "core": True},),
        endcap_y_profile=({"len": 40.0, "core": True},),
        finished_dimensions=(100.0, 80.0, 40.0),
        endcap_placement="top",
    )

    body_points = [point for tri in assembly.box_body_triangles for point in tri]
    endcap_points = [point for tri in assembly.endcap_triangles for point in tri]

    assert body_points
    assert endcap_points
    assert min(point[1] for point in body_points) == pytest.approx(-40.0)
    assert max(point[1] for point in body_points) == pytest.approx(40.0)
    assert min(point[1] for point in endcap_points) == pytest.approx(40.0)
    assert max(point[1] for point in endcap_points) == pytest.approx(40.0)
    assert min(point[2] for point in endcap_points) == pytest.approx(-20.0)
    assert max(point[2] for point in endcap_points) == pytest.approx(20.0)


def test_head_world_mesh_rotates_180_about_x_and_core_face_touches_box_top():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_world_meshes

    box_body_local = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    # z=0 is the semantic EndCap core face.  z>0 is a folded flange.
    head_local = (
        ((-30.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 20.0, 12.0)),
    )

    assembly = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=box_body_local,
        endcap_triangles=head_local,
        finished_dimensions=(100.0, 80.0, 40.0),
        endcap_placement="top",
    )

    body_top = max(point[1] for tri in assembly.box_body_triangles for point in tri)
    p0, p1, p2 = assembly.endcap_triangles[0]

    # Head core face is anchored directly on the Box Body top plane.
    assert p0[1] == pytest.approx(body_top)
    assert p1[1] == pytest.approx(body_top)
    # Head is rotated 180 degrees about world X: local +z points downward,
    # and local y is reversed in world z.
    assert p2[1] == pytest.approx(body_top - 12.0)
    assert (p0[2], p2[2]) == pytest.approx((15.0, -15.0))
    assert (p0[0], p1[0]) == pytest.approx((-20.0, 20.0))


def test_tail_world_mesh_preserves_native_up_down_and_folds_inward_from_box_bottom():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_world_meshes

    box_body_local = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    # z=0 is retained/core material that must sit on the box-body mating plane.
    # z>0 is a real folded flange and therefore must extend INTO the cabinet.
    tail_local = (
        ((-30.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 20.0, 12.0)),
    )

    assembly = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=box_body_local,
        endcap_triangles=tail_local,
        finished_dimensions=(100.0, 80.0, 40.0),
        endcap_placement="bottom",
    )

    body_bottom = min(point[1] for tri in assembly.box_body_triangles for point in tri)
    p0, p1, p2 = assembly.endcap_triangles[0]

    # Retained/core material stays on the actual box-body bottom mating plane.
    assert p0[1] == pytest.approx(body_bottom)
    assert p1[1] == pytest.approx(body_bottom)
    # Tail Fold Profile is already stored in its authoritative native orientation.
    # Assembly must preserve local Y in world Z (no second up/down mirror), while
    # local +Z folds upward into the box body.
    assert p2[1] == pytest.approx(body_bottom + 12.0)
    assert (p0[0], p1[0]) == pytest.approx((-20.0, 20.0))
    assert (p0[2], p2[2]) == pytest.approx((-15.0, 15.0))


def test_head_and_tail_retained_material_mates_box_while_positive_z_folds_go_inside():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_world_meshes

    body = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    # Two z=0 points model retained material; the z>0 point models any of the
    # semantic yl1/yr1/ybottom1 folded regions after Fold Profile resolution.
    endcap = (((-25.0, -15.0, 0.0), (25.0, -15.0, 0.0), (25.0, 15.0, 8.0)),)

    head = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=body, endcap_triangles=endcap,
        finished_dimensions=(100.0, 80.0, 40.0), endcap_placement="top",
    )
    tail = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=body, endcap_triangles=endcap,
        finished_dimensions=(100.0, 80.0, 40.0), endcap_placement="bottom",
    )

    top = 40.0
    bottom = -40.0
    hp0, hp1, hp2 = head.endcap_triangles[0]
    tp0, tp1, tp2 = tail.endcap_triangles[0]
    assert (hp0[1], hp1[1]) == pytest.approx((top, top))
    assert hp2[1] < top
    assert (tp0[1], tp1[1]) == pytest.approx((bottom, bottom))
    assert tp2[1] > bottom

@pytest.mark.parametrize(
    ("assembly_type", "expected_x_keys"),
    [
        ("INSERT", ["yl1", "endcap_w_core", "yr1"]),
        ("OVERLAY", ["endcap_w_flat"]),
        ("INSERT_OVERLAY", ["yl1", "endcap_w_core", "yr1"]),
    ],
)
def test_real_endcap_assembly_type_profiles_mate_retained_plane_and_fold_inside_box(
    assembly_type, expected_x_keys
):
    from ae_engine.assembly_geometry import (
        folded_mesh_from_polygon,
        place_assembly_triangles,
        place_endcap_against_box_body,
        triangle_bounds,
    )
    from phase6_fold_profiles import build_endcap_xy_profiles

    body_local = (
        ((-250.0, -300.0, 0.0), (250.0, -300.0, 0.0), (250.0, 300.0, 0.0)),
        ((-250.0, -300.0, 0.0), (250.0, 300.0, 0.0), (-250.0, 300.0, 0.0)),
    )
    body_world = place_assembly_triangles(body_local, "box_body", (500.0, 600.0, 200.0))
    body_bounds = triangle_bounds(body_world)
    snapshot = {
        "w": 500,
        "h": 600,
        "d": 200,
        "t": 2,
        "fw": 24,
        "yl1": 15,
        "yr1": 15,
        "ytop1": 16,
        "ybottom1": 15,
        "assembly_type": assembly_type,
    }

    for part_key, placement in (("head", "top"), ("tail", "bottom")):
        profiles = build_endcap_xy_profiles(snapshot, part_key=part_key)
        assert [row.get("phase6_key") for row in profiles["X"]] == expected_x_keys
        total_x = sum(float(row["len"]) for row in profiles["X"])
        total_y = sum(float(row["len"]) for row in profiles["Y"])
        local = folded_mesh_from_polygon(
            box(0.0, 0.0, total_x, total_y), profiles["X"], profiles["Y"]
        )
        local_bounds = triangle_bounds(local)
        assert local_bounds[2][0] == pytest.approx(0.0)
        assert local_bounds[2][1] > 0.0

        world = place_endcap_against_box_body(local, placement, body_world)
        world_bounds = triangle_bounds(world)
        if part_key == "head":
            # Retained/core plane is the top mating plane; every positive-Z fold
            # is at or below it, therefore inside the Box Body volume.
            assert world_bounds[1][1] == pytest.approx(body_bounds[1][1])
            assert world_bounds[1][0] < body_bounds[1][1]
            assert world_bounds[1][0] >= body_bounds[1][0]
        else:
            # Tail uses the same semantic in the opposite direction: retained/core
            # plane is the bottom mating plane and positive-Z folds extend upward.
            assert world_bounds[1][0] == pytest.approx(body_bounds[1][0])
            assert world_bounds[1][1] > body_bounds[1][0]
            assert world_bounds[1][1] <= body_bounds[1][1]


def test_thicken_triangle_surface_builds_real_two_sided_sheet_without_internal_diagonal_wall():
    from ae_engine.assembly_geometry import thicken_triangle_surface, triangle_bounds

    surface = (
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
        ((0.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)),
    )

    solid = thicken_triangle_surface(surface, 2.0)

    # 2 upper + 2 lower skins + 4 outer edges * 2 side triangles.
    assert len(solid) == 12
    bounds = triangle_bounds(solid)
    assert bounds[2] == pytest.approx((-1.0, 1.0))


def test_endcap_physical_sheet_mates_inner_face_to_box_and_keeps_outer_formed_face_outside():
    from ae_engine.assembly_geometry import (
        place_assembly_triangles,
        place_endcap_against_box_body,
        thicken_triangle_surface,
        triangle_bounds,
    )

    body = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    body_world = place_assembly_triangles(body, "box_body", (100.0, 80.0, 40.0))
    # Flat retained/core face.  Thickness is added only after semantic placement.
    endcap_surface = (
        ((-20.0, -10.0, 0.0), (20.0, -10.0, 0.0), (20.0, 10.0, 0.0)),
        ((-20.0, -10.0, 0.0), (20.0, 10.0, 0.0), (-20.0, 10.0, 0.0)),
    )

    head_surface = place_endcap_against_box_body(
        endcap_surface, "top", body_world, sheet_thickness=2.0
    )
    tail_surface = place_endcap_against_box_body(
        endcap_surface, "bottom", body_world, sheet_thickness=2.0
    )
    head_solid = thicken_triangle_surface(head_surface, 2.0)
    tail_solid = thicken_triangle_surface(tail_surface, 2.0)

    head_bounds = triangle_bounds(head_solid)
    tail_bounds = triangle_bounds(tail_solid)
    # Inner skin touches the box.  The second skin is the visible formed face
    # one full sheet thickness outside the cabinet.
    assert head_bounds[1] == pytest.approx((40.0, 42.0))
    assert tail_bounds[1] == pytest.approx((-42.0, -40.0))


def test_shared_world_mesh_builder_can_return_physical_endcap_sheet_for_collision():
    from ae_engine.assembly_collision import assemble_boxbody_endcap_world_meshes
    from ae_engine.assembly_geometry import triangle_bounds

    body = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    endcap = (
        ((-20.0, -10.0, 0.0), (20.0, -10.0, 0.0), (20.0, 10.0, 0.0)),
        ((-20.0, -10.0, 0.0), (20.0, 10.0, 0.0), (-20.0, 10.0, 0.0)),
    )

    result = assemble_boxbody_endcap_world_meshes(
        box_body_triangles=body,
        endcap_triangles=endcap,
        finished_dimensions=(100.0, 80.0, 40.0),
        endcap_placement="top",
        sheet_thickness=2.0,
    )

    bounds = triangle_bounds(result.endcap_triangles)
    assert bounds[1] == pytest.approx((40.0, 42.0))
    assert len(result.endcap_triangles) > len(endcap)


def test_restore_unrelieved_endcap_material_fills_exterior_notch_but_preserves_hole():
    from shapely.geometry import Point, box
    from ae_engine.assembly_collision import restore_unrelieved_endcap_material

    outer = box(0, 0, 100, 80)
    notched = outer.difference(box(0, 0, 12, 10))
    holed = notched.difference(Point(50, 40).buffer(5.0, resolution=16))

    restored = restore_unrelieved_endcap_material(holed)

    assert restored.covers(Point(5, 5))
    assert not restored.covers(Point(50, 40))
    assert restored.bounds == outer.bounds


def test_detect_world_mesh_surface_interference_returns_target_zone_for_crossing_meshes():
    from ae_engine.assembly_collision import detect_world_mesh_surface_interference

    source = (
        ((0.0, -1.0, -1.0), (0.0, 1.0, -1.0), (0.0, 0.0, 1.0)),
    )
    target = (
        ((-1.0, 0.0, -0.5), (1.0, 0.0, -0.5), (0.0, 0.0, 0.8)),
    )

    diagnostic = detect_world_mesh_surface_interference(source, target)

    assert diagnostic.has_interference is True
    assert diagnostic.target_triangles == target
    assert diagnostic.intersection_points
    assert diagnostic.intersection_segments


def test_detect_world_mesh_surface_interference_ignores_disjoint_and_coplanar_contact():
    from ae_engine.assembly_collision import detect_world_mesh_surface_interference

    source = (
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
    )
    disjoint = (
        ((0.0, 0.0, 3.0), (2.0, 0.0, 3.0), (0.0, 2.0, 3.0)),
    )
    coplanar = (
        ((0.2, 0.2, 0.0), (1.2, 0.2, 0.0), (0.2, 1.2, 0.0)),
    )

    assert detect_world_mesh_surface_interference(source, disjoint).has_interference is False
    assert detect_world_mesh_surface_interference(source, coplanar).has_interference is False


def test_restored_endcap_relief_delta_contains_only_material_added_back_by_diagnostic_restore():
    from shapely.geometry import Point, box
    from ae_engine.assembly_geometry import restored_endcap_relief_delta

    outer = box(0, 0, 100, 80)
    original = outer.difference(box(0, 0, 12, 10))
    original = original.difference(Point(50, 40).buffer(5.0, resolution=16))

    delta = restored_endcap_relief_delta(original)

    assert not delta.is_empty
    assert delta.covers(Point(5, 5))
    assert not delta.covers(Point(50, 40))
    assert delta.intersection(original).area == pytest.approx(0.0, abs=1e-8)
    assert delta.area == pytest.approx(120.0)


def test_folded_mesh_with_flat_uv_preserves_original_flat_coordinates():
    from ae_engine.assembly_geometry import folded_mesh_with_flat_uv_from_polygon

    material = box(0.0, 0.0, 20.0, 10.0)
    mapped = folded_mesh_with_flat_uv_from_polygon(
        material,
        (
            {"len": 10.0, "angle": 90.0},
            {"len": 10.0, "core": True},
        ),
        ({"len": 10.0, "core": True},),
    )

    assert mapped
    flat_points = {
        (round(float(point[0]), 6), round(float(point[1]), 6))
        for tri in mapped
        for point in tri.flat
    }
    assert flat_points == {(0.0, 0.0), (0.0, 10.0), (10.0, 0.0), (10.0, 10.0), (20.0, 0.0), (20.0, 10.0)}
    assert any(abs(float(point[2])) > 1e-6 for tri in mapped for point in tri.local)


def test_endcap_world_skin_with_flat_uv_keeps_uv_on_both_physical_skins():
    from ae_engine.assembly_geometry import (
        endcap_world_skin_with_flat_uv,
        folded_mesh_with_flat_uv_from_polygon,
        place_assembly_triangles,
    )

    body = place_assembly_triangles(
        (
            ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
            ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
        ),
        "box_body",
        (100.0, 80.0, 40.0),
    )
    mapped = folded_mesh_with_flat_uv_from_polygon(
        box(0.0, 0.0, 20.0, 10.0),
        ({"len": 20.0, "core": True},),
        ({"len": 10.0, "core": True},),
    )

    skins = endcap_world_skin_with_flat_uv(
        mapped, "top", body, sheet_thickness=2.0
    )

    assert len(skins) == len(mapped) * 2
    assert {skin.side for skin in skins} == {-1, 1}
    assert {skin.flat for skin in skins[::2]} == {tri.flat for tri in mapped}
    ys = [point[1] for skin in skins for point in skin.world]
    assert min(ys) == pytest.approx(40.0)
    assert max(ys) == pytest.approx(42.0)


def test_backproject_world_interference_maps_crossing_segment_to_flat_uv():
    from ae_engine.assembly_geometry import MappedSkinTriangle
    from ae_engine.assembly_collision import backproject_world_interference_to_endcap_flat

    target = MappedSkinTriangle(
        flat=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
        world=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        side=1,
    )
    source = (
        ((5.0, -5.0, -1.0), (5.0, 15.0, -1.0), (5.0, 5.0, 1.0)),
    )

    projection = backproject_world_interference_to_endcap_flat(source, (target,))

    assert projection.pair_count == 1
    assert len(projection.segments_2d) == 1
    segment = sorted(projection.segments_2d[0])
    assert segment[0] == pytest.approx((5.0, 0.0))
    assert segment[1] == pytest.approx((5.0, 5.0))


def test_derive_corner_relief_selects_blank_corner_side_and_measures_primary_cut():
    from ae_engine.assembly_collision import derive_corner_relief_from_flat_interference

    result = derive_corner_relief_from_flat_interference(
        relief_component=box(0.0, 0.0, 20.0, 20.0),
        segments_2d=(
            ((10.0, 0.0), (10.0, 15.0)),
            ((10.0, 15.0), (0.0, 15.0)),
        ),
        blank_bounds=(0.0, 0.0, 100.0, 100.0),
        corner_name="bottom_left",
        clearance=0.0,
    )

    assert result is not None
    assert result.cut_polygon_2d.equals(box(0.0, 0.0, 10.0, 15.0))
    assert result.measurement.primary_u == pytest.approx(10.0)
    assert result.measurement.primary_v == pytest.approx(15.0)
    assert result.measurement.secondary_u is None
    assert result.measurement.secondary_depth is None


def test_derive_corner_relief_clearance_a_expands_cut_inward_from_blank_edges():
    from ae_engine.assembly_collision import derive_corner_relief_from_flat_interference

    result = derive_corner_relief_from_flat_interference(
        relief_component=box(0.0, 0.0, 20.0, 20.0),
        segments_2d=(
            ((10.0, 0.0), (10.0, 15.0)),
            ((10.0, 15.0), (0.0, 15.0)),
        ),
        blank_bounds=(0.0, 0.0, 100.0, 100.0),
        corner_name="bottom_left",
        clearance=2.0,
    )

    assert result is not None
    assert result.measurement.clearance_a == pytest.approx(2.0)
    assert result.measurement.primary_u == pytest.approx(12.0)
    assert result.measurement.primary_v == pytest.approx(17.0)
    assert result.cut_polygon_2d.bounds == pytest.approx((0.0, 0.0, 12.0, 17.0))


def test_derive_corner_relief_uses_deepest_physical_skin_boundary_not_nearest_one():
    from ae_engine.assembly_collision import derive_corner_relief_from_flat_interference

    result = derive_corner_relief_from_flat_interference(
        relief_component=box(0.0, 0.0, 20.0, 20.0),
        segments_2d=(
            ((10.0, 0.0), (10.0, 15.0)), ((10.0, 15.0), (0.0, 15.0)),
            ((12.0, 0.0), (12.0, 17.0)), ((12.0, 17.0), (0.0, 17.0)),
        ),
        blank_bounds=(0.0, 0.0, 100.0, 100.0),
        corner_name="bottom_left",
        clearance=0.0,
    )

    assert result is not None
    assert result.measurement.primary_u == pytest.approx(12.0)
    assert result.measurement.primary_v == pytest.approx(17.0)


def test_endcap_subset_placement_can_use_full_endcap_reference_without_recentering_subset():
    from ae_engine.assembly_geometry import place_endcap_against_box_body

    body = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    full = (
        ((-50.0, -20.0, 0.0), (50.0, -20.0, 0.0), (50.0, 20.0, 0.0)),
        ((-50.0, -20.0, 0.0), (50.0, 20.0, 0.0), (-50.0, 20.0, 0.0)),
    )
    left_subset = (((-50.0, -20.0, 0.0), (-40.0, -20.0, 0.0), (-40.0, -10.0, 0.0)),)

    placed = place_endcap_against_box_body(
        left_subset, "top", body, reference_triangles=full
    )

    xs = [p[0] for tri in placed for p in tri]
    assert min(xs) == pytest.approx(-50.0)
    assert max(xs) == pytest.approx(-40.0)


def test_two_level_corner_relief_uses_collision_maximum_inside_each_physical_band():
    from shapely.ops import unary_union
    from ae_engine.assembly_collision import derive_corner_relief_from_flat_interference

    component = unary_union([
        box(0.0, 0.0, 39.0, 38.0),
        box(0.0, 38.0, 16.0, 42.0),
    ])
    result = derive_corner_relief_from_flat_interference(
        relief_component=component,
        segments_2d=(
            ((39.0, 10.0), (39.0, 38.0)),
            ((14.0, 38.0), (14.0, 42.0)),
        ),
        blank_bounds=(0.0, 0.0, 100.0, 100.0),
        corner_name="bottom_left",
        clearance=0.0,
    )

    assert result is not None
    m = result.measurement
    assert m.primary_u == pytest.approx(39.0)
    assert m.primary_v == pytest.approx(38.0)
    assert m.secondary_u == pytest.approx(14.0)
    assert m.secondary_depth == pytest.approx(4.0)
    assert result.cut_polygon_2d.area == pytest.approx(39.0 * 38.0 + 14.0 * 4.0)


def test_projection_boundary_line_contact_is_not_material_penetration():
    from ae_engine.assembly_collision import FlatInterferenceProjection, projection_has_material_penetration

    material = box(0.0, 0.0, 10.0, 10.0)
    boundary_touch = FlatInterferenceProjection(
        segments_2d=(((0.0, 2.0), (0.0, 8.0)),),
        points_2d=((0.0, 2.0), (0.0, 8.0)),
        pair_count=1,
    )
    interior_cross = FlatInterferenceProjection(
        segments_2d=(((5.0, 2.0), (5.0, 8.0)),),
        points_2d=((5.0, 2.0), (5.0, 8.0)),
        pair_count=1,
    )

    assert projection_has_material_penetration(boundary_touch, material) is False
    assert projection_has_material_penetration(interior_cross, material) is True


def test_projection_sub_tolerance_material_sliver_is_not_penetration():
    from ae_engine.assembly_collision import FlatInterferenceProjection, projection_has_material_penetration

    # After a verified corner cut, floating-point reconstruction may leave a
    # sliver thinner than the manufacturing/numerical tolerance.  Once the
    # inward tolerance buffer removes it completely, it is not retained
    # material penetration and must not be resurrected for verification.
    material = box(0.0, 0.0, 0.000005, 10.0)
    residual = FlatInterferenceProjection(
        segments_2d=(((0.000004, 2.0), (0.000004, 8.0)),),
        points_2d=((0.000004, 2.0), (0.000004, 8.0)),
        pair_count=1,
    )

    assert projection_has_material_penetration(residual, material, tolerance=0.00001) is False


def test_endcap_placement_uses_fold_profile_core_origin_not_asymmetric_folded_envelope_center():
    """Folded profiles already center their base/core segment on local x=y=0."""
    from ae_engine.assembly_geometry import place_endcap_against_box_body

    body = (
        ((-50.0, -40.0, 0.0), (50.0, -40.0, 0.0), (50.0, 40.0, 0.0)),
        ((-50.0, -40.0, 0.0), (50.0, 40.0, 0.0), (-50.0, 40.0, 0.0)),
    )
    # The core uses local y=-50..50; an asymmetric folded flange extends to +70.
    # Its existence must not translate the core by +10 in assembly depth.
    core = (((-20.0, -50.0, 0.0), (20.0, -50.0, 0.0), (20.0, 50.0, 0.0)),)
    full_reference = core + (((-20.0, 50.0, 0.0), (20.0, 50.0, 0.0), (20.0, 70.0, 0.0)),)

    placed = place_endcap_against_box_body(
        core,
        "top",
        body,
        reference_triangles=full_reference,
        preserve_core_origin=True,
    )

    # Top placement maps local depth y to world z=-y.  The core endpoints stay
    # exactly at +/-50; the extra flange must not move them to -40/+60.
    zs = [p[2] for tri in placed for p in tri]
    assert min(zs) == pytest.approx(-50.0)
    assert max(zs) == pytest.approx(50.0)
