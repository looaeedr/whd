"""#2517: GUI assembly selection is one Engine Joint Graph transaction."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import assembly_intent_transactions as owner
from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.sheetmetal_geometry import CornerTypeId
import phase6_settings_transitions as gui


def test_public_engine_owns_assembly_transaction_and_phase6_only_forwards():
    assert api.commit_assembly_intent_state is owner.commit_assembly_intent_state
    assert api.normalize_assembly_type is owner.normalize_assembly_type
    assert gui.AssemblyIntentTransition is owner.AssemblyIntentTransition
    assert "manufacturing_api.commit_assembly_intent_state(" in inspect.getsource(gui.assembly_intent)
    assert "manufacturing_api.normalize_assembly_type(" in inspect.getsource(gui.normalize_assembly_type)
    assert "from phase6_" not in inspect.getsource(owner)
    assert api.normalize_assembly_type("包覆貼外") == "WRAP_OVERLAY"
    assert api.normalize_assembly_type("INSERT") is CornerTypeId.INSERT


@pytest.mark.parametrize("intent,bottom", [
    ("INSERT", AssemblyJointRelation.INSERT),
    ("OVERLAY", AssemblyJointRelation.INSERT),
    ("INSERT_OVERLAY", AssemblyJointRelation.INSERT),
    ("WRAP_OVERLAY", AssemblyJointRelation.WRAP),
])
def test_real_joint_comes_from_engine_registry_and_is_stable_on_reload(intent, bottom):
    input_snapshot = {"model": "金庫型", "assembly_type": "INSERT"}
    bottom_corner = {"type_id": "CROSS", "rotation_quadrants": 0, "cross_mode": "extra_cut", "direction": "both", "amount_t": 2.25}
    corners = {"head": {"bottom_left": deepcopy(bottom_corner)}}
    original_snapshot = deepcopy(input_snapshot)
    original_corners = deepcopy(corners)
    result = api.commit_assembly_intent_state(
        input_snapshot, corners, {}, intent,
        available_parts=("box_body", "head", "tail"),
        project_legacy_corner=True,
    )
    assert input_snapshot == original_snapshot
    assert corners == original_corners
    assert "existing_parts" not in result.input_snapshot
    assert result.input_snapshot["assembly_type"] == intent
    assert result.corner_state["head"]["bottom_left"] == bottom_corner
    for part in ("head", "tail"):
        assert edge_relation_for_part(result.input_snapshot, part, "BOTTOM") is bottom
        expected_top = "OVERLAY" if intent == "WRAP_OVERLAY" else intent
        assert result.corner_state[part]["top_left"]["type_id"] == expected_top
    encoded = json.loads(json.dumps({
        "snapshot": result.input_snapshot,
        "corners": result.corner_state,
        "pairs": result.corner_pair_same,
    }))
    reloaded = api.commit_assembly_intent_state(
        encoded["snapshot"], encoded["corners"], encoded["pairs"], intent,
        available_parts=("box_body", "head", "tail"),
        project_legacy_corner=True,
    )
    assert reloaded.corner_state == encoded["corners"]
    for part in ("head", "tail"):
        assert edge_relation_for_part(reloaded.input_snapshot, part, "BOTTOM") is bottom
    assert reloaded == gui.assembly_intent(
        encoded["snapshot"], encoded["corners"], encoded["pairs"], intent,
        available_parts=("box_body", "head", "tail"), project_legacy_corner=True,
    )


def test_existing_project_topology_not_replaced_by_temporary_parts():
    original = {"model": "金庫型", "assembly_type": "OVERLAY", "existing_parts": ["box_body", "head"]}
    result = api.commit_assembly_intent_state(
        original, {}, {}, "INSERT_OVERLAY",
        available_parts=("box_body", "head", "tail"),
    )
    assert original["existing_parts"] == ["box_body", "head"]
    assert result.input_snapshot["existing_parts"] == ["box_body", "head"]
    assert result.input_snapshot["assembly_type"] == "INSERT_OVERLAY"


def test_invalid_intent_fails_closed_before_any_state_write():
    original = {"assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"]}
    corners = {"head": {"top_left": {"type_id": "CROSS", "rotation_quadrants": 0}}}
    pairs = {"head": {"top": True, "bottom": True}}
    saved = (deepcopy(original), deepcopy(corners), deepcopy(pairs))
    for bad in ("NOT_REAL", "WRAP", "", None):
        with pytest.raises(ValueError, match="unsupported Assembly Intent"):
            api.commit_assembly_intent_state(original, corners, pairs, bad, project_legacy_corner=True)
        assert (original, corners, pairs) == saved
