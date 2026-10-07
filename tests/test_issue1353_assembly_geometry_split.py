from __future__ import annotations

import inspect

from ae_engine import assembly_geometry
from ae_engine import assembly_geometry_primitives


def test_issue1353_primitives_are_reexported_from_assembly_geometry():
    assert assembly_geometry.triangle_bounds is assembly_geometry_primitives.triangle_bounds
    assert assembly_geometry.thicken_triangle_surface is assembly_geometry_primitives.thicken_triangle_surface
    assert assembly_geometry.place_assembly_points is assembly_geometry_primitives.place_assembly_points
    assert assembly_geometry.place_assembly_triangles is assembly_geometry_primitives.place_assembly_triangles
    assert assembly_geometry.place_endcap_against_box_body is assembly_geometry_primitives.place_endcap_against_box_body


def test_issue1353_primitives_owner_is_one_way_and_facade_shrinks():
    facade = inspect.getsource(assembly_geometry)
    owner = inspect.getsource(assembly_geometry_primitives)
    assert len(facade.splitlines()) < 1200
    assert len(owner.splitlines()) < 350
    assert "from .assembly_geometry import" not in owner
    assert "import ae_engine.assembly_geometry" not in owner


def test_issue1353_folded_mesh_owner_is_extracted_one_way():
    from ae_engine import assembly_geometry_folded_mesh
    assert assembly_geometry.folded_mesh_from_polygon is assembly_geometry_folded_mesh.folded_mesh_from_polygon
    assert assembly_geometry.folded_world_mesh_from_render_data is assembly_geometry_folded_mesh.folded_world_mesh_from_render_data
    assert assembly_geometry.place_box_body_structure_points is assembly_geometry_folded_mesh.place_box_body_structure_points
    assert len(inspect.getsource(assembly_geometry).splitlines()) < 850
    owner = inspect.getsource(assembly_geometry_folded_mesh)
    assert "from .assembly_geometry import" not in owner
    assert "import ae_engine.assembly_geometry" not in owner
