"""#2517: Engine owns Joint migration, physical membership and graph validity."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api, resolve_manufacturing_joint_graph
from ae_engine.assembly_joint import (
    ASSEMBLY_JOINT_SCHEMA_VERSION, migrate_legacy_snapshot_joints,
    ResolvedAssemblyGraph,
)
import phase6_manufacturing_service as service


def _source(parts=("box_body", "head", "tail"), joints=()):
    return {
        "assembly_joint_schema_version": ASSEMBLY_JOINT_SCHEMA_VERSION,
        "existing_parts": list(parts),
        "assembly_type": "INSERT",
        "assembly_joints": list(joints),
    }


def _joint(jid, subject, target):
    return {
        "joint_id": jid, "subject_part": subject, "target_part": target,
        "subject_region": "TOP", "target_region": "TOP",
        "relation": "INSERT", "source": "USER_ADDED",
    }


def test_headless_engine_preserves_registry_provenance_and_snapshot():
    source = _source(joints=(_joint("explicit-head", "head", "box_body"),))
    before = deepcopy(source)
    graph = resolve_manufacturing_joint_graph(source, {"box_body", "head", "tail"})
    assert manufacturing_api.resolve_manufacturing_joint_graph is resolve_manufacturing_joint_graph
    assert isinstance(graph, ResolvedAssemblyGraph)
    assert graph.parts == ("box_body", "head", "tail")
    expected = migrate_legacy_snapshot_joints(source)
    assert tuple(j.to_dict() for j in graph.joints) == tuple(expected["assembly_joints"])
    assert any(j.joint_id == "explicit-head" for j in graph.joints)
    assert source == before


def test_stale_joint_disappears_when_a_physical_part_is_unavailable():
    source = _source(joints=(_joint("stale", "head", "tail"),))
    graph = resolve_manufacturing_joint_graph(source, ("box_body", "head"))
    assert graph.parts == ("box_body", "head")
    assert all(j.target_part in graph.parts and j.subject_part in graph.parts for j in graph.joints)
    assert not any(j.joint_id == "stale" for j in graph.joints)


def test_custom_joint_without_confirmed_placement_fails_closed():
    source = _source(parts=("box_body", "head", "custom:example"),
                     joints=(_joint("custom-link", "custom:example", "box_body"),))
    with pytest.raises(ValueError, match="自訂板件尚無已確認 assembly placement"):
        resolve_manufacturing_joint_graph(source, ("box_body", "head", "custom:example"))


def test_duplicate_eligible_joint_ids_fail_graph_validation():
    source = _source(joints=(_joint("duplicate", "head", "box_body"),
                             _joint("duplicate", "tail", "box_body")))
    with pytest.raises(ValueError, match="duplicate joint_id"):
        resolve_manufacturing_joint_graph(source, ("box_body", "head", "tail"))


def test_phase6_uses_public_graph_api_not_private_identity_logic():
    src = inspect.getsource(service.resolve)
    assert "resolve_manufacturing_joint_graph(" in src
    assert "migrate_legacy_snapshot_joints(" not in src
    assert "AssemblyJoint.from_dict(" not in src
    assert "ResolvedAssemblyGraph(" not in src
    assert "自訂板件尚無已確認 assembly placement" not in src
    assert "joints = resolved_joint_graph.joints" in src
