"""#2517: saved typed Corner restore is one public Engine draft, not GUI edits."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import corner_type_ui as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from gui_modules.application import lifecycle


def _seed():
    parts = ("head", "tail", "door")
    return (owner.new_manual_corner_state(parts),
            owner.new_manual_corner_pair_same_state(parts))


def _gui(state, pairs, *, model):
    calls = []
    host = SimpleNamespace(
        manual_corner_state=state,
        manual_corner_pair_same=pairs,
        baseline_var=SimpleNamespace(get=lambda: model),
        _current_cabinet_type_name=lambda: model if model != "自訂" else "金庫型",
        refresh_corner_type_panel=lambda: calls.append("render"),
    )
    return host, calls


def test_api_and_root_export_identify_engine_typed_corner_owner():
    assert api.propose_operator_saved_manual_corner_snapshot is owner.propose_operator_saved_manual_corner_snapshot
    assert ae_engine.propose_operator_saved_manual_corner_snapshot is owner.propose_operator_saved_manual_corner_snapshot
    assert "propose_operator_saved_manual_corner_snapshot" in ae_engine.__all__


@pytest.mark.parametrize("model", ("自訂", "金庫型", "受電箱"))
def test_gui_saved_corner_restore_matches_public_engine_and_retains_part_aliases(model):
    state, pairs = _seed()
    saved = {
        "head": {
            "top_left": {"type_id": "C02", "rotation_quadrants": 1},
            "top_right": "OVERLAY",
            "bottom_left": {"type_id": "BAD_CORNER"},
        },
        "tail": {"top_left": {"type_id": "CROSS", "cross_mode": "extra_cut",
                              "direction": "both", "amount_t": 0.5}},
        "missing_part": {"top_left": "INSERT"},
    }
    saved_pairs = {"head": {"top": False}, "tail": {"bottom": True}}
    saved_before = deepcopy((saved, saved_pairs))
    original = deepcopy((state, pairs))
    family = model if model != "自訂" else "金庫型"
    expected = api.propose_operator_saved_manual_corner_snapshot(
        state, pairs, saved, saved_pairs, baseline_model=model, cabinet_family=family,
    )
    aliases = {part: (state[part], pairs[part]) for part in state}
    host, renders = _gui(state, pairs, model=model)
    lifecycle._apply_manual_corner_snapshot(host, saved, saved_pairs)
    assert (state, pairs) == expected
    assert (saved, saved_pairs) == saved_before
    assert renders == ["render"]
    for part in aliases:
        assert state[part] is aliases[part][0]
        assert pairs[part] is aliases[part][1]
    if model == "自訂":
        assert state["head"]["top_left"].type_id is CornerTypeId.C02
        assert state["head"]["top_left"].rotation_quadrants == 1
        assert state["head"]["bottom_left"] == original[0]["head"]["bottom_left"]
        assert pairs["head"]["top"] is False
        # Return to saved raw wire does not alter the source.
        wire = api.endcap_corner_selection_to_raw(state["head"]["top_left"])
        assert api.endcap_corner_selection_from_raw(wire) == state["head"]["top_left"]


@pytest.mark.parametrize("bad_pairs", ({"tail": ["not-an-object"]}, {"tail": object()}))
def test_invalid_late_saved_pair_cannot_commit_earlier_good_corner(bad_pairs):
    state, pairs = _seed()
    host, renders = _gui(state, pairs, model="自訂")
    before = deepcopy((state, pairs))
    refs = (state["head"], pairs["head"])
    with pytest.raises((AttributeError, TypeError, ValueError)):
        lifecycle._apply_manual_corner_snapshot(
            host, {"head": {"top_left": "OVERLAY"}}, bad_pairs,
        )
    assert (state, pairs) == before
    assert state["head"] is refs[0] and pairs["head"] is refs[1]
    assert renders == []


def test_corrupt_certified_known_family_source_rolls_back_entire_restore():
    state, pairs = _seed()
    state["tail"].pop("bottom_right")
    prior = deepcopy((state, pairs))
    host, calls = _gui(state, pairs, model="金庫型")
    with pytest.raises((KeyError, ValueError)):
        lifecycle._apply_manual_corner_snapshot(
            host, {"head": {"top_left": "OVERLAY"}}, {"head": {"top": False}},
        )
    assert (state, pairs) == prior
    assert calls == []


def test_unsupported_saved_payload_type_fails_without_source_mutation():
    state, pairs = _seed()
    before = deepcopy((state, pairs))
    with pytest.raises(ValueError, match="SAVED_CORNER_SNAPSHOT_SOURCE_INVALID"):
        api.propose_operator_saved_manual_corner_snapshot(
            state, pairs, saved_corner_state=["invalid"],
        )
    assert (state, pairs) == before


def test_real_gui_restore_no_longer_implements_private_corner_decode_or_commit():
    tree = ast.parse(Path("gui_modules/application/lifecycle.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_apply_manual_corner_snapshot")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    assert any(isinstance(c.func, ast.Attribute)
               and isinstance(c.func.value, ast.Name)
               and c.func.value.id == "manufacturing_api"
               and c.func.attr == "propose_operator_saved_manual_corner_snapshot"
               for c in calls)
    assert not any(isinstance(c.func, ast.Name)
                   and c.func.id in {"CornerTypeSelection", "CornerTypeId", "normalize_corner_selection"}
                   for c in calls)
