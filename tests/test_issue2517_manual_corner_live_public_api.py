# -*- coding: utf-8 -*-
"""#2517: GUI's typed CornerType live editor uses its public Engine owner."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import (
    apply_manual_corner_selection,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    policy_from_corner_state,
    set_manual_corner_pair_same,
)
from ae_engine.endcap_factory_fold import selection_from_raw, selection_to_raw
from ae_engine.sheetmetal_geometry import (
    CornerDirection, CornerTypeId, CornerTypeSelection, CrossCornerMode,
)


def _source():
    return new_manual_corner_state(("head",))["head"], (
        new_manual_corner_pair_same_state(("head",))["head"]
    )


def test_public_live_corner_editor_is_same_canonical_callable_and_gui_uses_it():
    assert api.operator_apply_manual_corner_selection is apply_manual_corner_selection
    assert api.operator_set_manual_corner_pair_same is set_manual_corner_pair_same
    assert ae_engine.operator_apply_manual_corner_selection is apply_manual_corner_selection
    assert ae_engine.operator_set_manual_corner_pair_same is set_manual_corner_pair_same

    source = Path(__file__).resolve().parents[1].joinpath("gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    ]
    assert calls.count("operator_set_manual_corner_pair_same") == 1
    assert calls.count("operator_apply_manual_corner_selection") == 3
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ae_engine.corner_type_ui":
            assert not {
                "set_manual_corner_pair_same", "apply_manual_corner_selection"
            }.intersection(alias.name for alias in node.names)


@pytest.mark.parametrize("pair,type_id", [
    ("top", CornerTypeId.INSERT_OVERLAY),
    ("bottom", CornerTypeId.OVERLAY),
])
def test_public_gui_corner_selection_matches_direct_engine_and_saved_codec(pair, type_id):
    first_state, first_pairs = _source()
    direct_state, direct_pairs = deepcopy(first_state), deepcopy(first_pairs)
    selection = CornerTypeSelection(type_id)

    api.operator_apply_manual_corner_selection(first_state, first_pairs, pair, selection)
    apply_manual_corner_selection(direct_state, direct_pairs, pair, selection)
    assert (first_state, first_pairs) == (direct_state, direct_pairs)

    api.operator_set_manual_corner_pair_same(first_state, first_pairs, pair, False)
    set_manual_corner_pair_same(direct_state, direct_pairs, pair, False)
    left, right = ("top_left", "top_right") if pair == "top" else ("bottom_left", "bottom_right")
    different = CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH, amount_t=0.5,
    )
    api.operator_apply_manual_corner_selection(first_state, first_pairs, right, different)
    apply_manual_corner_selection(direct_state, direct_pairs, right, different)
    assert first_state[left] != first_state[right]
    api.operator_set_manual_corner_pair_same(first_state, first_pairs, pair, True)
    set_manual_corner_pair_same(direct_state, direct_pairs, pair, True)
    assert first_state == direct_state
    assert first_pairs == direct_pairs
    assert first_state[left] == first_state[right] == selection

    # Real persisted Corner selection codec still round-trips unchanged.
    saved = json.loads(json.dumps({key: selection_to_raw(value) for key, value in first_state.items()}))
    restored = {key: selection_from_raw(value) for key, value in saved.items()}
    assert restored == first_state
    assert policy_from_corner_state(restored, fw=25) == policy_from_corner_state(first_state, fw=25)


def test_invalid_live_corner_requests_never_partially_mutate_source():
    state, pairs = _source()
    state.pop("top_left")
    original_state, original_pairs = deepcopy(state), deepcopy(pairs)
    with pytest.raises(KeyError):
        api.operator_set_manual_corner_pair_same(state, pairs, "top", True)
    assert (state, pairs) == (original_state, original_pairs)

    with pytest.raises(ValueError, match="未知的截角成對位置"):
        api.operator_set_manual_corner_pair_same(state, pairs, "not-a-pair", True)
    assert (state, pairs) == (original_state, original_pairs)

    state, pairs = _source()
    originals = (deepcopy(state), deepcopy(pairs))
    api.operator_set_manual_corner_pair_same(state, pairs, "top", False)
    split = (deepcopy(state), deepcopy(pairs))
    with pytest.raises(ValueError, match="已拆分"):
        api.operator_apply_manual_corner_selection(
            state, pairs, "top", CornerTypeSelection(CornerTypeId.OVERLAY),
        )
    assert (state, pairs) == split

    with pytest.raises(ValueError, match="未知的截角目標"):
        api.operator_apply_manual_corner_selection(
            state, pairs, "not-a-corner", CornerTypeSelection(CornerTypeId.OVERLAY),
        )
    assert (state, pairs) == split

    with pytest.raises((TypeError, ValueError)):
        api.operator_apply_manual_corner_selection(state, pairs, "top_left", "bad-type")
    assert (state, pairs) == split
    assert originals[0] == _source()[0]
