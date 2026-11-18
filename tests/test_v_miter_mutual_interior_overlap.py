"""#3317 physical volume interference: coplanar shells are not safe just because surface samples lie on the boundary."""
from __future__ import annotations

import pytest

from ae_engine.assembly_geometry import (
    detect_world_mesh_enclosed_volume_witness,
    detect_world_mesh_surface_interference,
)


def _box(lo, hi):
    """Twelve genuine triangles forming a closed three-dimensional cuboid."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    p = (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2),
        (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5),
    )
    return tuple(tuple(p[i] for i in face) for face in faces)


def _tetra(vertices):
    # Four physically closed non-degenerate triangular faces, no fake
    # bounding-box convex-hull solid substitute.
    return tuple(
        tuple(vertices[i] for i in face)
        for face in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2))
    )


def test_exactly_coincident_closed_true_T_solids_have_strict_shared_interior():
    a = _box((0, 0, 0), (2, 2, 2))
    # BEFORE the new witness, all box vertices and triangle centroids of
    # one mesh were *on* the coincident other's surface, so the original
    # nesting-only sampling could not find any strictly interior point.
    result = detect_world_mesh_enclosed_volume_witness(a, a)
    assert result.meshes_closed
    assert result.sample_count > 0
    assert result.has_enclosed_overlap
    assert len(result.strictly_inside_points) == 1
    p = result.strictly_inside_points[0]
    assert p == pytest.approx((1, 1, 1), abs=1e-5)


def test_reverse_triangle_winding_does_not_hide_coplanar_volume_overlap():
    a = _box((0, 0, 0), (2, 2, 2))
    reversed_winding = tuple((t[0], t[2], t[1]) for t in a)
    result = detect_world_mesh_enclosed_volume_witness(a, reversed_winding)
    assert result.meshes_closed
    assert result.has_enclosed_overlap
    assert result.strictly_inside_points[0] == pytest.approx((1, 1, 1), abs=1e-5)


def test_shared_face_contact_is_not_shared_volume_interference():
    first = _box((0, 0, 0), (1, 2, 2))
    second = _box((1, 0, 0), (2, 2, 2))
    witness = detect_world_mesh_enclosed_volume_witness(first, second)
    assert witness.meshes_closed
    assert not witness.has_enclosed_overlap
    assert witness.strictly_inside_points == ()


def test_disjoint_closed_tetrahedra_with_identical_bounding_boxes_not_false_positive():
    # Both bbox ranges are (0..1.5) on ALL three axes. But one tetrahedron
    # occupies x+y+z <= 1.5, the other x+y+z >= 3.0; volume disjoint.
    a = _tetra(((0, 0, 0), (1.5, 0, 0), (0, 1.5, 0), (0, 0, 1.5)))
    b = _tetra(((1.5, 1.5, 1.5), (0, 1.5, 1.5),
                (1.5, 0, 1.5), (1.5, 1.5, 0)))
    witness = detect_world_mesh_enclosed_volume_witness(a, b)
    assert witness.meshes_closed
    assert not witness.has_enclosed_overlap


def test_real_nested_closed_volume_still_blocks_and_open_mesh_remains_unknown():
    outer = _box((0, 0, 0), (10, 10, 10))
    inner = _box((2, 2, 2), (3, 3, 3))
    positive = detect_world_mesh_enclosed_volume_witness(outer, inner)
    assert positive.meshes_closed
    assert positive.has_enclosed_overlap
    assert all(0 < v < 10 for v in positive.strictly_inside_points[0])

    unknown = detect_world_mesh_enclosed_volume_witness(outer[:-1], inner)
    assert not unknown.meshes_closed
    assert not unknown.has_enclosed_overlap
    assert unknown.sample_count == 0


def test_two_noncontacting_true_solids_never_need_invented_overlap_witness():
    a = _box((-10, 0, 0), (-9, 1, 1))
    b = _box((9, 0, 0), (10, 1, 1))
    assert not detect_world_mesh_surface_interference(a, b).has_interference
    result = detect_world_mesh_enclosed_volume_witness(a, b)
    assert result.meshes_closed
    assert not result.has_enclosed_overlap
