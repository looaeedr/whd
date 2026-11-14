"""#2517 FinalScene user-added Joint eligibility belongs to Engine, not GUI."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource,
    migrate_legacy_snapshot_joints, project_operator_user_assembly_joint_parts,
)

ROOT = Path(__file__).resolve().parents[1]
GUI_FILE = ROOT / "gui_modules/application/fold_designer_adapter.py"


def _source(version=2):
    user = AssemblyJoint(
        joint_id="user-head-door",
        subject_part="head",
        target_part="door",
        relation=AssemblyJointRelation.OVERLAY,
        source=AssemblyJointSource.USER_ADDED,
    )
    managed = AssemblyJoint(
        joint_id="derived-box-tail",
        subject_part="box_body",
        target_part="tail",
        relation=AssemblyJointRelation.INSERT,
        source=AssemblyJointSource.INTENT_DERIVED,
    )
    return {
        "assembly_joint_schema_version": version,
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail", "door"],
        "assembly_joints": [user.to_dict(), managed.to_dict()],
    }


def _legacy_gui_projection(snapshot):
    migrated = migrate_legacy_snapshot_joints(snapshot)
    return {
        str(raw.get(field) or "")
        for raw in tuple(migrated.get("assembly_joints", ()) or ())
        if str(raw.get("source") or "") == AssemblyJointSource.USER_ADDED.value
        for field in ("subject_part", "target_part")
    }


@pytest.mark.parametrize("version", (1, 2))
def test_public_projection_matches_original_engine_migrated_user_joint_eligibility(version):
    snapshot = _source(version)
    before = deepcopy(snapshot)
    expected = _legacy_gui_projection(snapshot)
    projected = api.project_operator_user_assembly_joint_parts(snapshot)
    assert projected == expected
    assert type(projected) is frozenset
    assert {"head", "door"} <= projected
    assert "box_body" not in projected
    assert snapshot == before
    assert api.project_operator_user_assembly_joint_parts is project_operator_user_assembly_joint_parts
    assert ae_engine.project_operator_user_assembly_joint_parts is project_operator_user_assembly_joint_parts
    assert "project_operator_user_assembly_joint_parts" in ae_engine.__all__


def test_no_saved_user_joints_cannot_invent_user_eligibility():
    source = {"assembly_joint_schema_version": 2, "existing_parts": ["box_body", "head", "tail"], "assembly_type": "INSERT_OVERLAY"}
    before = deepcopy(source)
    assert api.project_operator_user_assembly_joint_parts(source) == frozenset()
    assert source == before


def test_future_joint_schema_is_rejected_without_mutation_or_gui_fallback():
    source = _source(999)
    before = deepcopy(source)
    with pytest.raises(ValueError, match="unsupported assembly joint schema version"):
        api.project_operator_user_assembly_joint_parts(source)
    assert source == before


def test_fold_designer_finalscene_calls_public_projection_and_never_scans_joint_source():
    tree = ast.parse(GUI_FILE.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "ae_engine.assembly_joint"
        and any(alias.name == "AssemblyJointSource" for alias in node.names)
        for node in ast.walk(tree)
    )
    calls = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    ]
    assert calls.count("project_operator_user_assembly_joint_parts") == 1
    assert calls.count("migrate_operator_assembly_joint_snapshot") == 0
