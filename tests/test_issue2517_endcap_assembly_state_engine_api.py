"""#2517: registered Assembly Intent to legacy CornerType is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
import pytest

from ae_engine import legacy_endcap_corner_projection_for_intent, manufacturing_api
from ae_engine import endcap_factory_fold as owner
from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.sheetmetal_geometry import CornerTypeId
from phase6_settings_transitions import assembly_intent
import phase6_endcap_semantics as gui


@pytest.mark.parametrize("intent,corner", [
    ("INSERT", CornerTypeId.INSERT),
    ("INSERT_OVERLAY", CornerTypeId.INSERT_OVERLAY),
    ("OVERLAY", CornerTypeId.OVERLAY),
    ("WRAP_OVERLAY", CornerTypeId.OVERLAY),
])
def test_legacy_projection_is_the_same_public_engine_callable(intent, corner):
    assert legacy_endcap_corner_projection_for_intent is owner.legacy_corner_projection_for_intent
    assert legacy_endcap_corner_projection_for_intent is manufacturing_api.legacy_endcap_corner_projection_for_intent
    assert legacy_endcap_corner_projection_for_intent(intent) is corner
    assert gui.legacy_corner_projection_for_intent(intent) is corner


def test_real_operator_intent_transaction_keeps_joint_authority_after_save_reload():
    original_snapshot = {
        "assembly_type": "INSERT",
        "existing_parts": ["box_body", "head", "tail"],
    }
    bottom = {"type_id": "CROSS", "rotation_quadrants": 0,
              "cross_mode": "extra_cut", "direction": "both", "amount_t": 2.25}
    original_corners = {"head": {"bottom_left": deepcopy(bottom)},
                        "tail": {"bottom_right": deepcopy(bottom)}}
    result = assembly_intent(
        original_snapshot, original_corners, {}, "WRAP_OVERLAY",
        available_parts=("box_body", "head", "tail"),
        project_legacy_corner=True, reset_bottom_defaults=False,
    )
    assert original_snapshot["assembly_type"] == "INSERT"
    assert original_corners["head"]["bottom_left"] == bottom
    assert result.input_snapshot["assembly_type"] == "WRAP_OVERLAY"
    for part in ("head", "tail"):
        assert edge_relation_for_part(result.input_snapshot, part, "BOTTOM") is AssemblyJointRelation.WRAP
        assert result.corner_state[part]["top_left"]["type_id"] == "OVERLAY"
        assert result.corner_state[part]["top_right"]["type_id"] == "OVERLAY"
    assert result.corner_state["head"]["bottom_left"] == bottom
    assert result.corner_state["tail"]["bottom_right"] == bottom
    stored = json.loads(json.dumps({
        "snapshot": result.input_snapshot, "corners": result.corner_state,
        "pairs": result.corner_pair_same,
    }))
    loaded = assembly_intent(
        stored["snapshot"], stored["corners"], stored["pairs"], "WRAP_OVERLAY",
        project_legacy_corner=True, reset_bottom_defaults=False,
    )
    assert loaded.corner_state == stored["corners"]
    for part in ("head", "tail"):
        assert edge_relation_for_part(loaded.input_snapshot, part, "BOTTOM") is AssemblyJointRelation.WRAP


def test_invalid_intent_rejected_and_gui_has_no_mirror_formula():
    with pytest.raises(ValueError, match="unsupported Assembly Intent"):
        legacy_endcap_corner_projection_for_intent("FORGED")
    assert "manufacturing_api.legacy_endcap_corner_projection_for_intent(" in inspect.getsource(
        gui.legacy_corner_projection_for_intent
    )
    assert "from phase6_" not in inspect.getsource(owner)
