# -*- coding: utf-8 -*-
"""#2517 box-body finished outside height is owned by one Engine policy."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
import gui
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_corner_policy import (
    box_body_height_from_corner_policies as canonical,
)
from ae_engine.certified_relief_registry import certified_corner_policy_for_part

GUI = Path(__file__).resolve().parents[1] / "gui.py"


def test_public_finished_height_is_original_engine_callable():
    assert api.project_operator_box_body_finished_height is canonical
    assert ae_engine.project_operator_box_body_finished_height is canonical
    assert "project_operator_box_body_finished_height" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("h,t", ((1600.0, 2.0), (700.0, 1.5)))
def test_real_family_policy_height_parity_and_gui_forwarding(family, h, t):
    policy = certified_corner_policy_for_part(family, "head", fw=25)
    tail = certified_corner_policy_for_part(family, "tail", fw=25)
    values = {"h": h, "t": t, "fw": 25.0}
    before = deepcopy(values)
    owner = SimpleNamespace(_box_body_corner_policies=lambda fw: (policy, tail))
    expected = canonical(
        h, t, head_corner_policy=policy, tail_corner_policy=tail,
    )
    assert api.project_operator_box_body_finished_height(
        h, t, head_corner_policy=policy, tail_corner_policy=tail,
    ) == expected
    assert gui.Phase6ApplicationHost._box_body_finished_height(owner, values) == expected
    assert values == before


def test_legacy_no_policy_uses_same_engine_default_without_gui_formula():
    values = {"h": 1600.0, "t": 2.0, "fw": 25.0}
    owner = SimpleNamespace(_box_body_corner_policies=lambda fw: (None, None))
    assert gui.Phase6ApplicationHost._box_body_finished_height(owner, values) == canonical(1600, 2)
    assert values == {"h": 1600.0, "t": 2.0, "fw": 25.0}


@pytest.mark.parametrize("h,t", (
    (0.0, 2.0), (2.0, 2.0), (-1.0, 2.0), (1600.0, 0.0),
    (1600.0, True), (float("nan"), 2.0), (float("inf"), 2.0),
    (1600.0, float("nan")), (1600.0, float("inf")),
))
def test_invalid_height_or_thickness_rejected_without_source_mutation(h, t):
    values = {"h": h, "t": t, "fw": 25.0}
    owner = SimpleNamespace(_box_body_corner_policies=lambda fw: (None, None))
    with pytest.raises((TypeError, ValueError)):
        gui.Phase6ApplicationHost._box_body_finished_height(owner, values)
    assert values["h"] is h and values["t"] is t and values["fw"] == 25.0


def test_gui_height_does_not_own_geometry_arithmetic():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    method = next(
        node for cls in ast.walk(tree)
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6ApplicationHost"
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "_box_body_finished_height"
    )
    calls = [
        node.func.attr for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "project_operator_box_body_finished_height" in calls
    assert not any(isinstance(n, (ast.Add, ast.Sub, ast.Mult, ast.Div)) for n in ast.walk(method))
    assert "box_body_vertical_offsets" not in GUI.read_text(encoding="utf-8")
