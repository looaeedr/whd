# -*- coding: utf-8 -*-
"""#2517 Head/Tail Joint source migration and edge Policy are public Engine APIs."""
from copy import deepcopy
import ast
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import (
    migrate_legacy_snapshot_joints as owner_migrate,
    edge_relation_for_part,
    project_operator_endcap_joint_edge_policies as owner_project,
)
from ae_engine.assembly_intent import get_assembly_intent

GUI = Path(__file__).resolve().parents[1] / "fold_designer_bridge.py"


def test_root_and_facade_reuse_engine_joint_owner():
    assert api.migrate_operator_assembly_joint_snapshot is owner_migrate
    assert ae_engine.migrate_operator_assembly_joint_snapshot is owner_migrate
    assert api.project_operator_endcap_joint_edge_policies is owner_project
    assert ae_engine.project_operator_endcap_joint_edge_policies is owner_project
    assert {"migrate_operator_assembly_joint_snapshot",
            "project_operator_endcap_joint_edge_policies"} <= set(ae_engine.__all__)


@pytest.mark.parametrize("intent", ("INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP_OVERLAY"))
@pytest.mark.parametrize("part_key", ("head", "tail"))
def test_engine_joint_policy_parity_and_saved_source_untouched(intent, part_key):
    original = {
        "assembly_type": intent,
        "existing_parts": ["box_body", "head", "tail"],
    }
    before = deepcopy(original)
    state = owner_migrate(original)
    assert api.migrate_operator_assembly_joint_snapshot(original) == state

    record = get_assembly_intent(intent)
    expected = tuple({
        "edge": edge,
        "relation": edge_relation_for_part(state, part_key, edge)
                    or record.edge_policy(edge).default_relation,
        "allowed": tuple(record.edge_policy(edge).allowed_relations),
        "editable": bool(record.edge_policy(edge).editable),
    } for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"))

    result = api.project_operator_endcap_joint_edge_policies(
        original, part_key, fallback_intent="INSERT_OVERLAY",
    )
    assert result == owner_project(original, part_key, fallback_intent="INSERT_OVERLAY")
    assert result == expected
    assert len(result) == 4
    assert original == before


def test_legacy_fallback_and_bad_joint_sources_do_not_mutate():
    source = {"existing_parts": ["box_body", "head", "tail"]}
    before = deepcopy(source)
    result = api.project_operator_endcap_joint_edge_policies(
        source, "head", fallback_intent="WRAP_OVERLAY",
    )
    assert [row["edge"] for row in result] == ["TOP", "BOTTOM", "LEFT", "RIGHT"]
    assert source == before
    with pytest.raises(ValueError, match="ENDCAP_JOINT_PHYSICAL_PART_REQUIRED"):
        api.project_operator_endcap_joint_edge_policies(source, "door")
    with pytest.raises(ValueError, match="ENDCAP_JOINT_SOURCE_MAPPING_REQUIRED"):
        api.project_operator_endcap_joint_edge_policies([], "head")
    stale = {"assembly_joint_schema_version": 999, "assembly_type": "INSERT"}
    old = deepcopy(stale)
    with pytest.raises(ValueError, match="unsupported assembly joint schema"):
        api.project_operator_endcap_joint_edge_policies(stale, "head")
    assert stale == old and source == before


def test_fold_designer_bootstrap_and_four_edges_use_public_engine():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not [node.module for node in imports if node.module == "ae_engine.assembly_intent"]
    assert not [name.name for node in imports if node.module == "ae_engine.assembly_joint"
                for name in node.names if name.name in (
                    "migrate_legacy_snapshot_joints", "edge_relation_for_part",
                    "get_assembly_intent",
                )]
    funcs = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    for name, call in (
        ("_phase6_bootstrap_authoritative_state", "migrate_operator_assembly_joint_snapshot"),
        ("_phase6_endcap_joint_policy_rows", "project_operator_endcap_joint_edge_policies"),
    ):
        calls = {
            node.func.attr for node in ast.walk(funcs[name])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "manufacturing_api"
        }
        assert call in calls
