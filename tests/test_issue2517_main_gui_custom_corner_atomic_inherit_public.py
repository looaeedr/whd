"""#2517: known-family -> Custom corner snapshot uses the Engine atomic draft."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import (
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
)
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from gui_modules.application import cabinet_controller


PARTS = ("head", "tail", "door", "base_plate")


def _source():
    state = new_manual_corner_state(PARTS)
    pairs = new_manual_corner_pair_same_state(PARTS)
    state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.C02)
    pairs["head"]["top"] = False
    pairs["tail"]["bottom"] = False
    return state, pairs


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_live_custom_inherit_is_exact_public_engine_draft_and_keeps_gui_aliases(family):
    state, pairs = _source()
    before = deepcopy((state, pairs))
    expected = api.propose_operator_known_model_corner_draft(
        state, pairs, baseline_model=family, cabinet_family=family, reset_all=True,
    )
    aliases = {part: (state[part], pairs[part]) for part in PARTS}
    host = SimpleNamespace(
        manual_corner_state=state,
        manual_corner_pair_same=pairs,
        _current_cabinet_type_name=lambda: family,
    )
    cabinet_controller._inherit_known_corner_state_into_custom(host)
    assert (state, pairs) == expected
    for part in PARTS:
        assert (state[part], pairs[part]) == (expected[0][part], expected[1][part])
        assert state[part] is aliases[part][0]
        assert pairs[part] is aliases[part][1]
    assert before != (state, pairs)


@pytest.mark.parametrize("broken", ("missing_final_corner", "invalid_pair"))
def test_bad_later_part_does_not_partially_commit_earlier_custom_corners(broken):
    state, pairs = _source()
    if broken == "missing_final_corner":
        state["tail"].pop("bottom_right")
    else:
        pairs["tail"] = None
    before = deepcopy((state, pairs))
    refs = (state["head"], state["tail"], pairs["head"])
    host = SimpleNamespace(
        manual_corner_state=state,
        manual_corner_pair_same=pairs,
        _current_cabinet_type_name=lambda: "金庫型",
    )
    with pytest.raises((KeyError, ValueError)):
        cabinet_controller._inherit_known_corner_state_into_custom(host)
    assert (state, pairs) == before
    assert (state["head"], state["tail"], pairs["head"]) == refs
    assert state["head"] is refs[0]
    assert state["tail"] is refs[1]
    assert pairs["head"] is refs[2]


def test_real_gui_custom_inherit_does_not_mutate_source_before_public_engine_refusal(monkeypatch):
    state, pairs = _source()
    before = deepcopy((state, pairs))
    host = SimpleNamespace(
        manual_corner_state=state,
        manual_corner_pair_same=pairs,
        _current_cabinet_type_name=lambda: "金庫型",
    )
    def refuse(*args, **kwargs):
        assert args[0] is state and args[1] is pairs
        assert kwargs == {
            "baseline_model": "金庫型",
            "cabinet_family": "金庫型",
            "reset_all": True,
        }
        raise ValueError("CERTIFIED_CORNER_SOURCE_INVALID")
    monkeypatch.setattr(api, "propose_operator_known_model_corner_draft", refuse)
    with pytest.raises(ValueError, match="CERTIFIED_CORNER_SOURCE_INVALID"):
        cabinet_controller._inherit_known_corner_state_into_custom(host)
    assert (state, pairs) == before


def test_cabinet_custom_transition_has_no_direct_known_corner_mutation_logic():
    tree = ast.parse(
        Path("gui_modules/application/cabinet_controller.py").read_text(encoding="utf-8")
    )
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef)
              and node.name == "_inherit_known_corner_state_into_custom")
    assert any(isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name)
               and node.func.value.id == "manufacturing_api"
               and node.func.attr == "propose_operator_known_model_corner_draft"
               for node in ast.walk(fn))
    assert not any(isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "_known_corner_state_for_current_family"
                   for node in ast.walk(fn))
