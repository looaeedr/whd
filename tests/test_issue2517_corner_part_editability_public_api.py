"""#2517: Fold Designer CornerType and parameter eligibility only from Engine."""
from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_model_choices import (
    OperatorCornerPartEditability,
    project_operator_corner_part_editability as owner,
)
import fold_designer_bridge as bridge


def test_root_facade_and_original_engine_share_exact_projection_owner():
    assert ae_engine.project_operator_corner_part_editability is owner
    assert api.project_operator_corner_part_editability is owner
    assert ae_engine.OperatorCornerPartEditability is OperatorCornerPartEditability
    assert api.OperatorCornerPartEditability is OperatorCornerPartEditability
    assert "project_operator_corner_part_editability" in ae_engine.__all__


@pytest.mark.parametrize("model_editable", (True, False))
@pytest.mark.parametrize("part_key", (
    "head", "tail", "door", "base_plate", "box_body",
    "global", "indicator_box", "indicator_door", "legacy-part",
))
def test_engine_preserves_existing_corner_type_and_unlockable_part_rules(
    model_editable, part_key,
):
    result = owner(part_key, model_corner_type_editable=model_editable)
    assert isinstance(result, OperatorCornerPartEditability)
    assert result.type_editable is (
        model_editable and part_key not in {"indicator_box", "indicator_door"}
    )
    assert result.parameters_unlockable is (
        part_key not in {"global", "box_body", "indicator_box", "indicator_door"}
    )
    assert api.project_operator_corner_part_editability(
        part_key, model_corner_type_editable=model_editable
    ) == result


@pytest.mark.parametrize("invalid", (None, True, 3, [], {"part": "head"}))
def test_invalid_part_identity_fails_without_input_mutation(invalid):
    before = deepcopy(invalid)
    with pytest.raises(ValueError, match="part key"):
        owner(invalid, model_corner_type_editable=True)
    assert invalid == before


@pytest.mark.parametrize("invalid", (None, 0, 1, "false", (), {}))
def test_invalid_editability_flag_fails_closed(invalid):
    before = deepcopy(invalid)
    with pytest.raises(ValueError, match="must be boolean"):
        owner("head", model_corner_type_editable=invalid)
    assert invalid == before


@pytest.mark.parametrize("editable", (True, False))
def test_bridge_uses_public_engine_for_both_presentation_and_action_guards(
    monkeypatch, editable,
):
    original = SimpleNamespace(_corner_editable=editable)
    calls = []
    token = SimpleNamespace(type_editable=object(), parameters_unlockable=object())

    def fake_owner(part_key, *, model_corner_type_editable):
        calls.append((part_key, model_corner_type_editable))
        return token

    monkeypatch.setattr(api, "project_operator_corner_part_editability", fake_owner)
    assert bridge._phase6_corner_type_editable(original, "head") is token.type_editable
    assert bridge._phase6_corner_parameters_unlockable(original, "head") is token.parameters_unlockable
    assert calls == [("head", editable), ("head", editable)]
    assert original._corner_editable is editable

    for function in (
        bridge._phase6_corner_type_editable,
        bridge._phase6_corner_parameters_unlockable,
    ):
        body = getsource(function)
        assert "manufacturing_api.project_operator_corner_part_editability(" in body
        assert "indicator_box" not in body
        assert "indicator_door" not in body


def test_existing_transient_parameter_lock_remains_a_view_toggle():
    state = SimpleNamespace(_corner_editable=False, _phase6_parameters_unlocked=False)
    assert bridge._phase6_corner_type_editable(state, "head") is False
    assert bridge._phase6_corner_parameters_unlockable(state, "head") is True
    assert bridge._phase6_corner_parameters_editable(state, "head") is False
    state._phase6_parameters_unlocked = True
    assert bridge._phase6_corner_parameters_editable(state, "head") is True
    assert bridge._phase6_corner_type_editable(state, "head") is False
    assert bridge._phase6_corner_parameters_editable(state, "indicator_door") is False
