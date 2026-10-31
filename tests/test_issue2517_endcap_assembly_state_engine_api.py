"""#2517: EndCap Assembly Intent legacy corner mutation is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api
from ae_engine import endcap_assembly_state as owner
from ae_engine.assembly_joint import (
    AssemblyJointRelation, edge_relation_for_part, sync_snapshot_intent_joints,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
)
from phase6_endcap_semantics import (
    apply_box_assembly_type_to_raw_state as gui_apply,
    legacy_corner_projection_for_intent as gui_projection,
    selection_from_raw as gui_from_raw,
    selection_to_raw as gui_to_raw,
)


def _original_state():
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH, amount_t=2.25,
    )
    custom = manufacturing_api.endcap_corner_selection_to_raw(bottom)
    return {
        "head": {"bottom_left": deepcopy(custom), "bottom_right": deepcopy(custom)},
        "tail": {"bottom_left": deepcopy(custom), "bottom_right": deepcopy(custom)},
    }, {
        "head": {"top": False, "bottom": False},
        "tail": {"top": False, "bottom": True},
    }


@pytest.mark.parametrize("intent", ("INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP_OVERLAY"))
def test_public_engine_intent_projection_keeps_legacy_and_canonical_joint_separate(intent):
    projected = manufacturing_api.legacy_corner_projection_for_intent(intent)
    assert projected is gui_projection(intent)
    assert projected is (CornerTypeId.OVERLAY if intent == "WRAP_OVERLAY" else CornerTypeId(intent))
    source = {"assembly_type": intent, "existing_parts": ["box_body", "head", "tail"]}
    canonical = sync_snapshot_intent_joints(source, intent)
    if intent == "WRAP_OVERLAY":
        for part in ("head", "tail"):
            assert edge_relation_for_part(canonical, part, "BOTTOM") is AssemblyJointRelation.WRAP
    before = deepcopy(source)
    corners, pair = _original_state()
    original_bottom = deepcopy(corners)
    original_pair = deepcopy(pair)
    returned = manufacturing_api.apply_box_assembly_type_to_raw_state(corners, pair, projected)
    assert returned is projected
    assert before == source
    assert original_pair == pair
    for part in ("head", "tail"):
        assert corners[part]["bottom_left"] == original_bottom[part]["bottom_left"]
        assert corners[part]["bottom_right"] == original_bottom[part]["bottom_right"]
        assert corners[part]["top_left"]["type_id"] == projected.value
        assert corners[part]["top_right"]["type_id"] == projected.value
    # Real Save→Reload of the returned serialization must retain physical state.
    serialized = json.loads(json.dumps({"corner_state": corners, "corner_pair_same": pair}))
    loaded = serialized["corner_state"]
    manufacturing_api.apply_box_assembly_type_to_raw_state(
        loaded, serialized["corner_pair_same"], projected,
    )
    assert loaded == corners


def test_explicit_overlay_preset_reset_updates_only_canonical_bottom_default():
    corners, pairs = _original_state()
    original_pairs = deepcopy(pairs)
    result = gui_apply(corners, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True)
    assert result is CornerTypeId.OVERLAY
    assert pairs == original_pairs
    for part in ("head", "tail"):
        for key in ("bottom_left", "bottom_right"):
            selection = gui_from_raw(corners[part][key])
            assert selection.type_id is CornerTypeId.CROSS
            assert selection.cross_mode is CrossCornerMode.EXTRA_CUT
            assert selection.direction is CornerDirection.WIDTH
            assert selection.amount_t == pytest.approx(1.5)


def test_public_serialization_round_trip_preserves_original_corner_source_fields():
    original = CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY, amount_t=1.0,
        secondary_retain_t=0.5, secondary_depth_t=2.0,
    )
    raw = manufacturing_api.endcap_corner_selection_to_raw(original)
    assert raw == gui_to_raw(original)
    assert raw["type_id"] == "INSERT_OVERLAY"
    assert gui_from_raw(json.loads(json.dumps(raw))) == original
    assert raw["rotation_quadrants"] == 0


def test_bad_assembly_intent_or_corner_type_rejects_without_mutation():
    with pytest.raises(ValueError, match="unsupported Assembly Intent"):
        manufacturing_api.legacy_corner_projection_for_intent("FAKE")
    corners, pairs = _original_state()
    before = deepcopy((corners, pairs))
    with pytest.raises(ValueError):
        manufacturing_api.apply_box_assembly_type_to_raw_state(
            corners, pairs, CornerTypeId.C02,
        )
    assert (corners, pairs) == before


def test_phase6_compatibility_has_no_corner_mutation_formula():
    assert "manufacturing_api.legacy_corner_projection_for_intent(" in inspect.getsource(gui_projection)
    assert "manufacturing_api.endcap_corner_selection_to_raw(" in inspect.getsource(gui_to_raw)
    assert "manufacturing_api.apply_box_assembly_type_to_raw_state(" in inspect.getsource(gui_apply)
    assert "from phase6_" not in inspect.getsource(owner)
