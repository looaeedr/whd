"""DM8-C1: joint and pairing share neutral vector/normal owner without policy drift."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ae_engine import assembly_marking_geometry as neutral
from ae_engine import receiving_joint_marking as joint
from ae_engine import receiving_pairing_marking as pairing
from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES as tolerances


def test_exact_shared_vector_operations_and_triangle_normal():
    a = (1, 2, 3)
    b = (4, 6, 8)
    assert neutral.vector_sub(b, a) == (3.0, 4.0, 5.0)
    assert neutral.vector_add(a, b) == (5.0, 8.0, 11.0)
    assert neutral.vector_scale(a, 2) == (2.0, 4.0, 6.0)
    assert neutral.vector_dot(a, b) == 40.0
    assert neutral.vector_cross((1, 0, 0), (0, 1, 0)) == (0.0, 0.0, 1.0)
    assert neutral.vector_norm((3, 4, 0)) == 5.0
    tri = ((0., 0., 0.), (0., 1., 0.), (0., 0., 1.))
    assert joint._triangle_normal(tri) == pairing._triangle_normal(tri) == (1., 0., 0.)
    assert joint._triangle_normal(tuple(reversed(tri))) == pairing._triangle_normal(tuple(reversed(tri))) == (-1., 0., 0.)


def test_policy_specific_canonical_orientation_threshold_parity():
    # Policy thresholds must NOT be collapsed into one global epsilon.
    near_boundary = (-5.0e-8, 1.0, 0.0)
    j = joint._canonical_plane_normal(near_boundary)
    p = pairing._canonical_normal(near_boundary)
    assert j[1] < 0.0 and p[1] > 0.0
    assert j[0] > 0.0 and p[0] < 0.0
    assert tolerances.polygon_robustness_epsilon < 5e-8 < tolerances.boundary_separation_tolerance


def test_degenerate_normal_keeps_each_policy_error_contract():
    for func, expected in (
        (joint._triangle_normal, "degenerate geometry direction"),
        (pairing._triangle_normal, "degenerate mapped-skin triangle"),
    ):
        with pytest.raises(ValueError, match=expected):
            func(((0., 0., 0.), (0., 0., 0.), (0., 0., 0.)))


def test_local_duplicate_vector_owners_did_not_regrow():
    root = Path(neutral.__file__).parent
    forbidden = {"_sub", "_dot", "_cross", "_norm", "_triangle_normal"}
    for file in ("receiving_joint_marking.py", "receiving_pairing_marking.py"):
        tree = ast.parse((root / file).read_text(encoding="utf-8"))
        local = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert not (local & forbidden), f"duplicated vector owner in {file}"
    source = (root / "assembly_marking_geometry.py").read_text(encoding="utf-8")
    assert source.count("def backproject_mapped_skin_world_points(") == 1
    for file in ("receiving_joint_marking.py", "receiving_pairing_marking.py"):
        source = (root / file).read_text(encoding="utf-8")
        assert "from .assembly_marking_geometry import" in source
