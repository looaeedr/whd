# -*- coding: utf-8 -*-
"""T01 — four-edge Assembly Intent policy registry contract."""
from __future__ import annotations

from ae_engine.assembly_intent import (
    assembly_intent_primitive_records,
    get_assembly_intent,
    registered_assembly_intents,
)
from ae_engine.assembly_joint import AssemblyJointRelation


EXPECTED = {
    "INSERT": {
        "TOP": ("INSERT",),
        "BOTTOM": ("INSERT",),
        "LEFT": ("INSERT",),
        "RIGHT": ("INSERT",),
    },
    "INSERT_OVERLAY": {
        "TOP": ("OVERLAY",),
        "BOTTOM": ("INSERT",),
        "LEFT": ("INSERT",),
        "RIGHT": ("INSERT",),
    },
    "OVERLAY": {
        "TOP": ("OVERLAY",),
        "BOTTOM": ("INSERT", "OVERLAY"),
        "LEFT": ("OVERLAY",),
        "RIGHT": ("OVERLAY",),
    },
    "WRAP_OVERLAY": {
        "TOP": ("OVERLAY",),
        "BOTTOM": ("WRAP",),
        "LEFT": ("INSERT", "OVERLAY", "WRAP"),
        "RIGHT": ("INSERT", "OVERLAY", "WRAP"),
    },
}


def test_registry_exposes_canonical_default_allowed_and_editable_policy_for_every_edge():
    rows = {row.stable_id: row for row in registered_assembly_intents()}
    assert set(rows) == set(EXPECTED)

    for intent_id, expected_edges in EXPECTED.items():
        row = rows[intent_id]
        assert set(row.edge_policy_map) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        for edge, allowed_names in expected_edges.items():
            policy = row.edge_policy_map[edge]
            assert tuple(item.value for item in policy.allowed_relations) == allowed_names
            assert policy.default_relation is row.default_joint_map[edge]
            assert policy.default_relation in policy.allowed_relations
            assert policy.editable is (len(allowed_names) > 1)


def test_registry_policy_matches_required_four_preset_defaults():
    assert get_assembly_intent("INSERT").default_joint_map == {
        "TOP": AssemblyJointRelation.INSERT,
        "BOTTOM": AssemblyJointRelation.INSERT,
        "LEFT": AssemblyJointRelation.INSERT,
        "RIGHT": AssemblyJointRelation.INSERT,
    }
    assert get_assembly_intent("INSERT_OVERLAY").default_joint_map == {
        "TOP": AssemblyJointRelation.OVERLAY,
        "BOTTOM": AssemblyJointRelation.INSERT,
        "LEFT": AssemblyJointRelation.INSERT,
        "RIGHT": AssemblyJointRelation.INSERT,
    }
    assert get_assembly_intent("OVERLAY").default_joint_map["BOTTOM"] is AssemblyJointRelation.INSERT
    assert get_assembly_intent("WRAP_OVERLAY").default_joint_map["BOTTOM"] is AssemblyJointRelation.WRAP


def test_primitive_records_publish_policy_without_consumers_rebuilding_a_whitelist():
    records = {row["stable_id"]: row for row in assembly_intent_primitive_records()}
    assert set(records) == set(EXPECTED)
    for intent_id, expected_edges in EXPECTED.items():
        primitive = records[intent_id]
        policy_map = primitive["edge_policy_map"]
        assert set(policy_map) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        for edge, allowed_names in expected_edges.items():
            policy = policy_map[edge]
            assert tuple(policy["allowed_relations"]) == allowed_names
            assert policy["default_relation"] == get_assembly_intent(intent_id).default_joint_map[edge].value
            assert policy["editable"] is (len(allowed_names) > 1)
