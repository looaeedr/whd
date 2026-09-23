# -*- coding: utf-8 -*-
from types import SimpleNamespace
import pytest

import fold_designer_bridge as bridge
from ae_engine.assembly_joint import (
    AssemblyJointRelation, migrate_legacy_snapshot_joints,
    sync_snapshot_intent_joints,
)


def _app():
    return SimpleNamespace(
        _phase6_input_snapshot={
            "existing_parts": ["box_body", "head", "tail"],
            "assembly_type": "INSERT_OVERLAY",
        }
    )


def test_add_user_wrap_joint_persists_subject_to_target_direction():
    app = _app()
    row = bridge._phase6_add_user_joint(
        app,
        subject_part="head",
        target_part="box_body",
        relation=AssemblyJointRelation.WRAP,
        subject_region="rear_edge",
        target_region="rear_mating",
        clearance_policy="ZERO",
    )
    assert row["relation"] == "WRAP"
    assert row["source"] == "USER_ADDED"
    assert row["subject_part"] == "head" and row["target_part"] == "box_body"
    assert any(j["joint_id"] == row["joint_id"] for j in app._phase6_input_snapshot["assembly_joints"])


def test_delete_joint_allows_only_user_added():
    app = _app()
    user = bridge._phase6_add_user_joint(
        app, subject_part="head", target_part="box_body", relation="WRAP",
        subject_region="rear_edge", target_region="rear_mating",
    )
    assert bridge._phase6_delete_user_joint(app, user["joint_id"]) is True
    snapshot = migrate_legacy_snapshot_joints(app._phase6_input_snapshot)
    snapshot = sync_snapshot_intent_joints(snapshot, "INSERT")
    app._phase6_input_snapshot.update({
        "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
        "assembly_joints": snapshot["assembly_joints"],
        "assembly_type": snapshot["assembly_type"],
    })
    derived = next(
        j for j in app._phase6_input_snapshot["assembly_joints"]
        if j["source"] == "INTENT_DERIVED"
    )
    with pytest.raises(ValueError, match="USER_ADDED"):
        bridge._phase6_delete_user_joint(app, derived["joint_id"])


def test_user_added_joint_can_store_explicit_solver_topology_contract():
    app = _app()
    row = bridge._phase6_add_user_joint(
        app, subject_part="head", target_part="box_body", relation="WRAP",
        subject_region="rear_edge", target_region="bottom_left",
        solver_constraints={"topology_levels": 1},
    )
    assert row["solver_constraints"]["topology_levels"] == 1
