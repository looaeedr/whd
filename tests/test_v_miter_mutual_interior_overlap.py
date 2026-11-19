"""#3317 physical volume interference: coplanar shells are not safe just because surface samples lie on the boundary."""
from __future__ import annotations

import pytest

from ae_engine.assembly_geometry import (
    detect_world_mesh_enclosed_volume_witness,
    detect_world_mesh_surface_interference,
    diagnose_world_mesh_triangle_edge_incidence,
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


def _strict_inside_actual_tetra(point, vertices):
    """Independent barycentric ground truth, not the Engine ray detector."""
    import numpy as np
    rows = np.asarray(vertices, dtype=float)
    delta = np.asarray(point, dtype=float) - rows[0]
    weights = np.linalg.solve((rows[1:] - rows[0]).T, delta)
    barycentric = (1.0 - float(weights.sum()),) + tuple(float(v) for v in weights)
    return all(v > 1e-8 for v in barycentric)


def test_narrow_convex_tetra_overlap_escapes_old_nine_aabb_and_surface_samples():
    # Both four-triangle solids occupy a REAL common 3D volume near the
    # oblique faces. No source mesh vertex/face-centroid is strictly inside
    # the other, and the previous AABB 1+8 probes ALL miss that volume.
    # This is a true closed-surface fixture, not a bounding-box assertion.
    first_vertices = (
        (0.0, 0.0, 0.0), (3.0, 0.0, 0.0),
        (0.0, 3.0, 0.0), (0.0, 0.0, 3.0),
    )
    second_vertices = (
        (-1.29759186, 3.6464283, 2.82933773),
        (4.60418533, 3.95045064, 3.4176386),
        (0.15336671, -1.02663957, -0.90074075),
        (3.37077506, 4.26330466, 4.14362644),
    )
    a = _tetra(first_vertices)
    b = _tetra(second_vertices)
    for surface, other in ((a, second_vertices), (b, first_vertices)):
        for triangle in surface:
            assert not _strict_inside_actual_tetra(
                tuple(sum(p[i] for p in triangle) / 3 for i in range(3)), other,
            )
            for vertex in triangle:
                assert not _strict_inside_actual_tetra(vertex, other)

    import numpy as np
    first_bounds = np.asarray(first_vertices)
    second_bounds = np.asarray(second_vertices)
    lower = np.maximum(first_bounds.min(axis=0), second_bounds.min(axis=0))
    upper = np.minimum(first_bounds.max(axis=0), second_bounds.max(axis=0))
    assert np.all(lower < upper)
    fractions = ((.5, .5, .5),) + tuple(
        (x, y, z) for x in (.25, .75)
        for y in (.25, .75) for z in (.25, .75)
    )
    for row in fractions:
        xyz = lower + (upper - lower) * np.asarray(row)
        assert not (
            _strict_inside_actual_tetra(xyz, first_vertices)
            and _strict_inside_actual_tetra(xyz, second_vertices)
        )

    result = detect_world_mesh_enclosed_volume_witness(a, b)
    assert result.meshes_closed
    assert result.has_enclosed_overlap
    assert len(result.strictly_inside_points) == 1
    actual = result.strictly_inside_points[0]
    assert _strict_inside_actual_tetra(actual, first_vertices)
    assert _strict_inside_actual_tetra(actual, second_vertices)
    # This point came from ACTUAL shared supporting planes, and not
    # the centre/octants of the intersecting bounding boxes.
    assert result.sample_count >= len(fractions) + 1


def test_narrow_convex_overlap_is_winding_independent_and_order_independent():
    a_vertices = ((0, 0, 0), (3, 0, 0), (0, 3, 0), (0, 0, 3))
    b_vertices = (
        (-1.29759186, 3.6464283, 2.82933773),
        (4.60418533, 3.95045064, 3.4176386),
        (0.15336671, -1.02663957, -0.90074075),
        (3.37077506, 4.26330466, 4.14362644),
    )
    a = _tetra(a_vertices)
    b = tuple((tri[0], tri[2], tri[1]) for tri in _tetra(b_vertices))
    for first, second in ((a, b), (b, a)):
        result = detect_world_mesh_enclosed_volume_witness(first, second)
        assert result.meshes_closed
        assert result.has_enclosed_overlap
        point = result.strictly_inside_points[0]
        assert _strict_inside_actual_tetra(point, a_vertices)
        assert _strict_inside_actual_tetra(point, b_vertices)


def test_tetrahedra_with_only_shared_diagonal_face_are_not_volume_overlap():
    # Both true closed solids have the SAME outer AABB. One simplex occupies
    # x+y+z <= 3, the other occupies the other side of the exact shared
    # triangle x+y+z=3. The intersection is a surface, not a solid.
    a = _tetra(((0, 0, 0), (3, 0, 0), (0, 3, 0), (0, 0, 3)))
    b = _tetra(((3, 0, 0), (0, 3, 0), (0, 0, 3), (3, 3, 3)))
    result = detect_world_mesh_enclosed_volume_witness(a, b)
    assert result.meshes_closed
    assert not result.has_enclosed_overlap
    assert result.strictly_inside_points == ()


def test_actual_world_T_shell_edge_diagnostic_distinguishes_closed_open_and_nonmanifold():
    closed = _box((0, 0, 0), (2, 2, 2))
    valid = diagnose_world_mesh_triangle_edge_incidence(closed)
    assert valid.triangle_count == 12
    assert valid.edges_manifold_closed
    assert valid.boundary_edge_count == 0
    assert valid.nonmanifold_edge_count == 0
    assert valid.degenerate_triangle_count == 0
    assert valid.boundary_edge_examples_xyz == ()
    assert valid.manufacturing_status.endswith("UNCERTIFIED")

    open_shell = diagnose_world_mesh_triangle_edge_incidence(closed[:-1])
    assert not open_shell.edges_manifold_closed
    assert open_shell.boundary_edge_count == 3
    assert open_shell.nonmanifold_edge_count == 0
    assert len(open_shell.boundary_edge_examples_xyz) == 3
    assert all(len(edge) == 2 and all(len(p) == 3 for p in edge)
               for edge in open_shell.boundary_edge_examples_xyz)

    duplicated = diagnose_world_mesh_triangle_edge_incidence(closed + (closed[0],))
    assert not duplicated.edges_manifold_closed
    assert duplicated.nonmanifold_edge_count == 3

    degenerate = diagnose_world_mesh_triangle_edge_incidence(
        closed + (((0, 0, 0), (0, 0, 0), (1, 1, 1)),),
    )
    assert not degenerate.edges_manifold_closed
    assert degenerate.degenerate_triangle_count == 1
