# -*- coding: utf-8 -*-
"""#2517 FinalScene uses one headless Engine material and world geometry owner."""
from pathlib import Path
from types import SimpleNamespace

from shapely.geometry import box

from ae_engine import manufacturing_api
from ae_engine.assembly_geometry import (
    folded_mesh_from_polygon, place_box_body_structure_points,
    triangle_bounds, place_assembly_triangles,
)
import phase6_final_scene_projection as view


def test_material_with_true_cutting_hole_is_identical_through_public_api():
    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    xp = ({"len": 100., "core": "W"},)
    yp = ({"len": 60., "core": "H"},)
    expected = folded_mesh_from_polygon(material, xp, yp, fold_guides=())
    actual = manufacturing_api.folded_material_mid_mesh(material, xp, yp, fold_guides=())
    assert actual == expected and actual
    assert view._phase6_folded_mesh_from_polygon(material, xp, yp, fold_guides=()) == list(expected)
    for tri in actual:
        cx = sum(float(p[0]) for p in tri)/3. + 50.
        cy = sum(float(p[1]) for p in tri)/3. + 30.
        assert not (40 < cx < 60 and 20 < cy < 40)


def test_world_mesh_bounds_and_all_semantic_placement_roles_match_engine():
    triangles = (((0., 0., 0.), (2., 0., 0.), (0., 2., 0.)),)
    expected = triangle_bounds(triangles)
    assert manufacturing_api.physical_mesh_world_bounds(triangles) == expected
    assert view._phase6_triangle_bounds(triangles) == expected
    assert manufacturing_api.physical_mesh_world_bounds(()) is None
    for role in ("head", "tail", "door", "back", "divider_horizontal"):
        original = place_assembly_triangles(triangles, role, (400., 600., 250.), (3., 4., 5.))
        assert manufacturing_api.project_assembly_world_triangles(
            triangles, role, (400., 600., 250.), (3., 4., 5.),
        ) == original
        assert view._phase6_place_assembly_triangles(
            triangles, role, (400., 600., 250.), (3., 4., 5.),
        ) == original


def test_box_body_piece_world_datums_are_shared_across_engine_and_gui():
    piece = SimpleNamespace(role="back", formed_w_start=0., formed_w_end=400., formed_y_offset=12.)
    profile = ({"len": 400., "core": "W"},)
    points = ((3., 5., 0.), (-3., 4., 0.))
    original = place_box_body_structure_points(
        points, piece, total_w=400., thickness=2., x_profile=profile,
    )
    public = manufacturing_api.project_box_body_structure_world_points(
        points, piece, total_w=400., thickness=2., x_profile=profile,
    )
    assert public == original
    mapper = view._phase6_box_body_piece_world_mapper(
        piece, total_w=400., thickness=2., x_profile=profile,
    )
    assert tuple(mapper(point) for point in points) == original


def test_final_scene_has_no_direct_private_assembly_geometry_import():
    source = Path(view.__file__).read_text(encoding="utf-8")
    assert "from ae_engine.assembly_geometry import" not in source
    for name in (
        "folded_material_mid_mesh",
        "project_box_body_structure_world_points",
        "physical_mesh_world_bounds",
        "project_assembly_world_triangles",
    ):
        assert hasattr(manufacturing_api, name)
        assert name in source
