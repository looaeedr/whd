"""#2517: Corner Data rear-panel control eligibility belongs only to Engine."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.box_body_structure_state import (
    BoxBodyStructureType, default_box_body_structure_state, set_active_structure,
)
from ae_engine.cabinet_types import policy as family_policy
from gui_modules.application import fold_designer_composition_assembly_corner as corner_ui
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter


def _side_back_structure():
    return set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )


def test_public_root_and_facade_reuse_engine_family_owner():
    assert (
        api.operator_corner_data_back_panel_mode_applicable
        is family_policy.corner_data_back_panel_mode_applicable
    )
    assert (
        ae_engine.operator_corner_data_back_panel_mode_applicable
        is family_policy.corner_data_back_panel_mode_applicable
    )
    assert "operator_corner_data_back_panel_mode_applicable" in ae_engine.__all__


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING"))
def test_real_receiving_family_and_back_piece_are_eligible_without_source_mutation(family):
    source = {"model": family}
    state = api.operator_resolve_box_body_structure_state(source, None)
    before = deepcopy((source, state))
    assert state["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    assert api.operator_corner_data_back_panel_mode_applicable(
        source, state, selected_part_key="box_body:back"
    ) is True
    assert (source, state) == before


@pytest.mark.parametrize("family", ("金庫型", "自訂", ""))
def test_other_families_cannot_enable_receiving_rear_panel_control(family):
    assert api.operator_corner_data_back_panel_mode_applicable(
        {"model": family}, _side_back_structure(), selected_part_key="box_body:back"
    ) is False


@pytest.mark.parametrize("part_key", (
    None, "", "box_body", "box_body:left", "box_body:right", "head", "base_plate",
))
def test_other_parts_cannot_open_receiving_rear_panel_control(part_key):
    assert api.operator_corner_data_back_panel_mode_applicable(
        {"model": "受電箱"}, _side_back_structure(), selected_part_key=part_key
    ) is False


@pytest.mark.parametrize("mode", (
    BoxBodyStructureType.INTEGRAL,
    BoxBodyStructureType.TWO_PIECE_W_SPLIT,
    BoxBodyStructureType.THREE_PIECE_W_SPLIT,
))
def test_other_box_body_topologies_not_eligible(mode):
    state = set_active_structure(default_box_body_structure_state(), mode)
    assert api.operator_corner_data_back_panel_mode_applicable(
        "受電箱", state, selected_part_key="box_body:back"
    ) is False


@pytest.mark.parametrize("bad", (None, [], "side-back", True))
def test_invalid_structure_source_fails_closed_and_does_not_modify_request(bad):
    source = {"model": "受電箱"}
    old = deepcopy((source, bad))
    with pytest.raises(ValueError, match="BoxBody structure source"):
        api.operator_corner_data_back_panel_mode_applicable(
            source, bad, selected_part_key="box_body:back"
        )
    assert (source, bad) == old


def test_legacy_unrecognized_structure_is_not_promoted_to_side_back():
    state = {"active_type": "legacy-unknown"}
    before = deepcopy(state)
    assert api.operator_corner_data_back_panel_mode_applicable(
        {"model": "受電箱"}, state, selected_part_key="box_body:back"
    ) is False
    assert state == before


def test_gui_delegates_original_source_and_selected_part_without_policy_math(monkeypatch):
    source = {"model": "RECEIVING", "other": 42}
    state = _side_back_structure()
    selected = "box_body:back"
    observed = []
    token = object()

    def fake_owner(family_source, box_state, *, selected_part_key):
        observed.append((family_source, box_state, selected_part_key))
        return token

    monkeypatch.setattr(api, "operator_corner_data_back_panel_mode_applicable", fake_owner)
    app = SimpleNamespace(_phase6_input_snapshot=source)
    composition = SimpleNamespace(
        app=app,
        corner_data_view=lambda: SimpleNamespace(selected_part_key=selected),
        _required=lambda _namespace, name: (
            (lambda _app: state) if name == "_phase6_box_structure_state" else None
        ),
    )
    assert corner_ui.corner_data_back_panel_mode_is_applicable(composition, {}) is token
    assert observed == [(source, state, selected)]
    body = inspect.getsource(corner_ui.corner_data_back_panel_mode_is_applicable)
    assert "operator_corner_data_back_panel_mode_applicable" in body
    assert "THREE_PIECE_SIDE_BACK_SPLIT" not in body
    assert "operator_canonical_family_name" not in body


def test_corner_data_view_remains_presentation_only():
    source = inspect.getsource(Phase6CornerDataViewAdapter)
    assert "def back_panel_mode_is_applicable" not in source
    assert '"box_body:back"' not in source
    assert "THREE_PIECE_SIDE_BACK_SPLIT" not in source
