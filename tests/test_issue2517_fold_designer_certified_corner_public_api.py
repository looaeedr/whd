# -*- coding: utf-8 -*-
"""#2517 Fold Designer certified baseline corner projection owns no private API."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import known_model_corner_state
from ae_engine.certified_relief_registry import lookup_certified_corner_state
from fold_designer_bridge import _phase6_known_model_corner_state

BRIDGE = Path(__file__).resolve().parents[1] / "fold_designer_bridge.py"
PARTS = ("head", "tail", "door", "base_plate", "indicator_box")


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_public_corner_baseline_is_exact_original_certified_engine_owner(family):
    assert api.operator_known_model_corner_state is known_model_corner_state
    assert ae_engine.operator_known_model_corner_state is known_model_corner_state
    assert "operator_known_model_corner_state" in ae_engine.__all__
    parts = list(PARTS)
    before = deepcopy(parts)
    projected = api.operator_known_model_corner_state(parts, cabinet_family=family)
    assert projected == known_model_corner_state(parts, cabinet_family=family)
    assert projected == lookup_certified_corner_state(
        cabinet_family=family, part_keys=tuple(parts)
    )
    assert "head" in projected and "tail" in projected
    assert set(projected["head"]) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    assert parts == before


@pytest.mark.parametrize("family", ("UNKNOWN_FAMILY", "", None))
def test_no_unverified_family_invents_a_certified_corner(family):
    parts = ["head", "tail"]
    original = deepcopy(parts)
    assert api.operator_known_model_corner_state(parts, cabinet_family=family) == {}
    assert parts == original
    assert api.operator_known_model_corner_state(
        ["not_certified_part"], cabinet_family="受電箱"
    ) == {}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_real_fold_designer_bridge_projects_same_certified_family_state(family):
    parts = list(PARTS)
    host = SimpleNamespace(
        _phase6_input_snapshot={"model": family},
        baseline_model_var=SimpleNamespace(get=lambda: ""),
        available_parts=parts,
    )
    before = deepcopy(host._phase6_input_snapshot)
    assert _phase6_known_model_corner_state(host) == known_model_corner_state(
        parts, cabinet_family=family
    )
    assert host._phase6_input_snapshot == before


def test_fold_designer_does_not_call_private_certified_corner_owner():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    private_imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.corner_type_ui"
        and any(alias.name == "known_model_corner_state" for alias in node.names)
    ]
    assert not private_imports
    public_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
        and node.func.attr == "operator_known_model_corner_state"
    ]
    assert len(public_calls) == 1
