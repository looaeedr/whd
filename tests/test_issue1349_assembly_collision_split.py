from __future__ import annotations

import inspect

from ae_engine import assembly_collision
from ae_engine import assembly_collision_basic


def test_issue1349_basic_owner_preserves_public_collision_surface():
    assert assembly_collision.AssemblyRole is assembly_collision_basic.AssemblyRole
    assert assembly_collision.JointReliefOwnership is assembly_collision_basic.JointReliefOwnership
    assert assembly_collision.assemble_boxbody_endcap_world_meshes is assembly_collision_basic.assemble_boxbody_endcap_world_meshes
    assert assembly_collision.solve_boxbody_endcap_relief is assembly_collision_basic.solve_boxbody_endcap_relief


def test_issue1349_basic_owner_is_one_way_and_reduces_facade():
    facade = inspect.getsource(assembly_collision)
    owner = inspect.getsource(assembly_collision_basic)
    assert len(facade.splitlines()) < 1700
    assert len(owner.splitlines()) < 450
    assert "class AssemblyRole" not in facade
    assert "class AssemblyRole" in owner
    assert "from .assembly_collision import" not in owner
    assert "import ae_engine.assembly_collision" not in owner


def test_issue1349_backprojection_owner_is_extracted_one_way():
    from ae_engine import assembly_collision_backprojection
    assert assembly_collision.FlatInterferenceProjection is assembly_collision_backprojection.FlatInterferenceProjection
    assert assembly_collision.backproject_world_interference_to_endcap_flat is assembly_collision_backprojection.backproject_world_interference_to_endcap_flat
    assert assembly_collision.backproject_world_interference_to_flat is assembly_collision_backprojection.backproject_world_interference_to_flat
    assert len(inspect.getsource(assembly_collision).splitlines()) < 1500
    owner = inspect.getsource(assembly_collision_backprojection)
    assert "from .assembly_collision import" not in owner
    assert "import ae_engine.assembly_collision" not in owner
