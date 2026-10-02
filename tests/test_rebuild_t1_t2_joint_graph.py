# -*- coding: utf-8 -*-
from ae_engine.assembly_joint import (
    AssemblyJoint,
    AssemblyJointRelation,
    AssemblyJointSource,
    ASSEMBLY_JOINT_SCHEMA_VERSION,
    migrate_legacy_snapshot_joints,
    sync_snapshot_intent_joints,
)


def test_registered_intents_have_explicit_four_edge_defaults_and_wrap_is_not_standalone():
    from ae_engine.assembly_intent import registered_assembly_intents
    rows = registered_assembly_intents()
    assert rows
    ids = {row.stable_id for row in rows}
    assert "WRAP" not in ids
    by_id = {row.stable_id: row for row in rows}
    assert by_id["INSERT_OVERLAY"].default_joint_map == {
        "TOP": AssemblyJointRelation.OVERLAY,
        "BOTTOM": AssemblyJointRelation.INSERT,
        "LEFT": AssemblyJointRelation.INSERT,
        "RIGHT": AssemblyJointRelation.INSERT,
    }
    assert by_id["WRAP_OVERLAY"].display_name == "包覆貼外"
    assert by_id["WRAP_OVERLAY"].default_joint_map["BOTTOM"] is AssemblyJointRelation.WRAP
    assert all(set(row.default_joint_map) == {"TOP", "BOTTOM", "LEFT", "RIGHT"} for row in rows)


def test_joint_schema_v2_roundtrip_carries_edge_and_revision_without_breaking_relation_position():
    assert ASSEMBLY_JOINT_SCHEMA_VERSION >= 2
    # relation remains the sixth positional field for backward compatibility.
    j = AssemblyJoint("j1", "head", "box_body", "left_side", "left_mating_zone", AssemblyJointRelation.WRAP,
                      source=AssemblyJointSource.USER_ADDED, edge="LEFT", revision=3)
    raw = j.to_dict()
    restored = AssemblyJoint.from_dict(raw)
    assert restored.relation is AssemblyJointRelation.WRAP
    assert restored.edge == "LEFT"
    assert restored.revision == 3


def test_legacy_intent_migrates_once_to_four_edges_per_endcap():
    snap = {"assembly_type": "INSERT_OVERLAY", "existing_parts": ["box_body", "head", "tail"]}
    migrated = migrate_legacy_snapshot_joints(snap)
    assert migrated["assembly_joint_schema_version"] == ASSEMBLY_JOINT_SCHEMA_VERSION
    rows = migrated["assembly_joints"]
    assert len(rows) == 8
    for part in ("head", "tail"):
        edges = {r["edge"]: r["relation"] for r in rows if r["subject_part"] == part}
        assert edges == {"TOP": "OVERLAY", "BOTTOM": "INSERT", "LEFT": "INSERT", "RIGHT": "INSERT"}
    assert migrate_legacy_snapshot_joints(migrated)["assembly_joints"] == rows


def test_schema1_side_only_graph_is_completed_but_explicit_right_override_wins():
    explicit = AssemblyJoint(
        "head-right-wrap", "head", "box_body", "right_side", "right_mating_zone",
        AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED,
    ).to_dict()
    snap = {
        "assembly_type": "OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_joint_schema_version": 1,
        "assembly_joints": [explicit],
    }
    migrated = migrate_legacy_snapshot_joints(snap)
    head = [r for r in migrated["assembly_joints"] if r["subject_part"] == "head"]
    by_edge = {r["edge"]: r for r in head}
    assert by_edge["RIGHT"]["relation"] == "WRAP"
    assert by_edge["RIGHT"]["source"] == "USER_ADDED"
    assert by_edge["TOP"]["relation"] == "OVERLAY"
    assert by_edge["BOTTOM"]["relation"] == "INSERT"
    assert by_edge["LEFT"]["relation"] == "OVERLAY"


def test_preset_reapply_resets_all_canonical_edges_to_selected_intent_defaults():
    existing = [
        AssemblyJoint("u", "head", "box_body", relation=AssemblyJointRelation.WRAP,
                      source=AssemblyJointSource.USER_ADDED, edge="RIGHT"),
        AssemblyJoint("s", "tail", "box_body", relation=AssemblyJointRelation.WRAP,
                      source=AssemblyJointSource.SOLVER_CONFIRMED, edge="LEFT"),
    ]
    snap = {
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_joint_schema_version": ASSEMBLY_JOINT_SCHEMA_VERSION,
        "assembly_joints": [j.to_dict() for j in existing],
    }
    out = sync_snapshot_intent_joints(snap, "INSERT_OVERLAY")
    rows = [AssemblyJoint.from_dict(r) for r in out["assembly_joints"]]
    by_edge = {(j.subject_part, j.edge): j.relation for j in rows if j.subject_part in {"head", "tail"}}
    expected = {
        "TOP": AssemblyJointRelation.OVERLAY,
        "BOTTOM": AssemblyJointRelation.INSERT,
        "LEFT": AssemblyJointRelation.INSERT,
        "RIGHT": AssemblyJointRelation.INSERT,
    }
    assert by_edge == {(part, edge): relation for part in ("head", "tail") for edge, relation in expected.items()}
    assert not any(j.joint_id in {"u", "s"} for j in rows)


def test_schema_v2_load_prunes_dangling_and_sanitizes_illegal_fixed_edges_to_explicit_defaults():
    kept = AssemblyJoint(
        "head-right-wrap", "head", "box_body", "right_edge", "right_mating_zone",
        AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED, edge="RIGHT",
    ).to_dict()
    dangling = AssemblyJoint(
        "tail-top-overlay", "tail", "box_body", "top_edge", "top_mating_zone",
        AssemblyJointRelation.OVERLAY, source=AssemblyJointSource.INTENT_DERIVED, edge="TOP",
    ).to_dict()
    snap = {
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head"],
        "assembly_joint_schema_version": ASSEMBLY_JOINT_SCHEMA_VERSION,
        "assembly_joints": [kept, dangling],
    }
    loaded = migrate_legacy_snapshot_joints(snap)
    assert loaded["assembly_joint_schema_version"] == ASSEMBLY_JOINT_SCHEMA_VERSION
    assert {row["subject_part"] for row in loaded["assembly_joints"]} == {"head"}
    by_edge = {row["edge"]: row["relation"] for row in loaded["assembly_joints"]}
    assert by_edge == {"TOP": "OVERLAY", "BOTTOM": "INSERT", "LEFT": "INSERT", "RIGHT": "INSERT"}
    assert all(row["joint_id"] != "head-right-wrap" for row in loaded["assembly_joints"])
