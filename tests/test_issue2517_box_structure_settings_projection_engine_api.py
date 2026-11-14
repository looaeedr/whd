"""#2517 BoxBody split operator settings must come from public Engine API."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.box_body_structure_state import side_rear_bend_outside_length
from phase6_settings_transitions import (
    activate_box_structure, reconcile_width_structure, toggle_box_structure_lock,
)


@pytest.mark.parametrize("locked,expected", [
    ("false", True), ("0", True), (False, True),
    ("true", False), ("1", False), (True, False),
])
def test_saved_legacy_lock_toggle_uses_engine_bool_roundtrip(locked, expected):
    state = api.default_box_body_structure_state()
    state["locked"] = locked
    witness = deepcopy(state)
    result = api.operator_toggle_box_body_structure_lock(state)
    assert result["locked"] is expected
    assert state == witness
    assert toggle_box_structure_lock(state) == result
    assert api.normalize_box_body_structure_state({"locked": result["locked"]})["locked"] is expected
    assert api.operator_toggle_box_body_structure_lock(result)["locked"] is (not expected)


@pytest.mark.parametrize("kind,keys,widths", [
    (api.BoxBodyStructureType.INTEGRAL, (), ()),
    (api.BoxBodyStructureType.TWO_PIECE_W_SPLIT,
     ("box_body:left", "box_body:right"), (400., 400.)),
    (api.BoxBodyStructureType.THREE_PIECE_W_SPLIT,
     ("box_body:left", "box_body:middle", "box_body:right"), (50., 700., 50.)),
])
def test_public_projection_uses_saved_engine_split_widths(kind, keys, widths):
    old = api.default_box_body_structure_state()
    state = activate_box_structure(old, kind, 800.)
    witness = deepcopy(state)
    rows = api.project_operator_box_body_structure_settings(
        state, 800., snapshot={"model": "金庫型", "t": 2.}
    )
    assert tuple(rows["piece_values"]) == keys
    assert tuple(v[2] for v in rows["piece_values"].values()) == widths
    assert rows["active_type"] is kind
    assert rows["mode"] == {
        api.BoxBodyStructureType.INTEGRAL: "integral",
        api.BoxBodyStructureType.TWO_PIECE_W_SPLIT: "two_w",
        api.BoxBodyStructureType.THREE_PIECE_W_SPLIT: "three_w",
    }[kind]
    assert len(rows["advanced_fields"]) == (0 if kind is api.BoxBodyStructureType.INTEGRAL else 4)
    assert state == witness
    assert old["active_type"] == api.BoxBodyStructureType.INTEGRAL.value


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_side_back_source_datum_and_saved_reload_match_engine(model):
    state = activate_box_structure(
        api.default_box_body_structure_state(),
        api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT, 800.,
    )
    state = api.set_side_back_geometry(
        state, side_rear_bend=15., side_rear_bend_dimension_space="MATERIAL",
        back_width_comp_t=0.75,
    )
    witness = deepcopy(state)
    source = {"model": model, "t": 2.0}
    row = api.project_operator_box_body_structure_settings(state, 800., snapshot=source)
    rear = (
        side_rear_bend_outside_length(state, 2.)
        if family_policy.box_body_profile_uses_outside_dimensions(source)
        else 15.
    )
    assert row["mode"] == "side_back"
    assert row["piece_values"] == {
        "box_body:left_side": ("rear_bend", "後折", rear, "mm", "side_rear_bend"),
        "box_body:back": ("width_comp_t", "寬補償", 0.75, "T", "back_width_comp_t"),
        "box_body:right_side": ("rear_bend", "後折", rear, "mm", "side_rear_bend"),
    }
    assert row["advanced_fields"] == ()
    assert state == witness
    reloaded = api.normalize_box_body_structure_state(deepcopy(state))
    assert api.project_operator_box_body_structure_settings(reloaded, 800., snapshot=source) == row


def test_invalid_saved_two_piece_widths_fail_closed():
    state = api.default_box_body_structure_state()
    state["active_type"] = api.BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    state["configs"][state["active_type"]].update(left_w=300., right_w=600.)
    with pytest.raises(ValueError, match="不一致"):
        api.project_operator_box_body_structure_settings(state, 800., snapshot={"model": "金庫型"})


def test_gui_only_delegates_structure_physical_state_and_toggles():
    source = Path("gui_modules/application/fold_designer_composition_settings.py").read_text(encoding="utf-8")
    segment = source.split("    def box_structure_projection():", 1)[1].split(
        "    def bottom_wrap_projection(", 1
    )[0]
    assert "manufacturing_api.project_operator_box_body_structure_settings(" in segment
    for forbidden in ("resolve_two_piece_widths", "resolve_three_piece_widths",
                      "side_rear_bend_outside_length", "cfg.get(", "width_comp_t =",
                      "box_body_profile_uses_outside_dimensions"):
        assert forbidden not in segment
    transitions = Path("phase6_settings_transitions.py").read_text(encoding="utf-8")
    assert "manufacturing_api.operator_toggle_box_body_structure_lock(state)" in transitions
    assert "manufacturing_api.activate_structure_with_defaults(" in transitions
    assert "manufacturing_api.reconcile_box_body_structure_for_total_w_change(" in transitions
    assert "not bool(dict(state).get(" not in transitions
    engine = Path("ae_engine/operator_box_body_settings_projection.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine


def test_reconcile_width_delegates_canonical_w_driver_with_no_gui_copy():
    state = activate_box_structure(
        api.default_box_body_structure_state(),
        api.BoxBodyStructureType.TWO_PIECE_W_SPLIT, 800.
    )
    state = api.set_two_piece_width(state, 800., "left", 300.)
    expected = api.reconcile_box_body_structure_for_total_w_change(state, 900.)
    assert reconcile_width_structure(state, 900.) == expected
    assert api.resolve_two_piece_widths(expected, 900.) == (300., 600.)


@pytest.mark.parametrize("bad_t", [True, False, None, 0, -1, "nan", "inf", "oops"])
def test_receiving_side_back_projection_requires_raw_positive_finite_thickness(bad_t):
    state = api.default_box_body_structure_state()
    state["active_type"] = api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    saved = deepcopy(state)
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_operator_box_body_structure_settings(
            state, 800., snapshot={"model": "受電箱", "t": bad_t},
        )
    assert state == saved


def test_receiving_side_back_projection_requires_thickness_when_missing():
    state = api.default_box_body_structure_state()
    state["active_type"] = api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_operator_box_body_structure_settings(
            state, 800., snapshot={"model": "受電箱"},
        )


def test_side_back_projection_preserves_decimal_thickness_and_legacy_material_space():
    state = api.default_box_body_structure_state()
    state["active_type"] = api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    snapshot = {"model": "受電箱", "t": "2.25"}
    saved_state = deepcopy(state)
    saved_snapshot = deepcopy(snapshot)
    outside = api.project_operator_box_body_structure_settings(state, 800., snapshot=snapshot)
    assert outside["piece_values"]["box_body:left_side"][2] == 17.25
    assert outside["piece_values"]["box_body:right_side"][2] == 17.25
    assert api.project_operator_box_body_structure_settings(
        json.loads(json.dumps(state)), 800.,
        snapshot=json.loads(json.dumps(snapshot)),
    ) == outside
    legacy = api.project_operator_box_body_structure_settings(
        state, 800., snapshot={"model": "金庫型"},
    )
    assert legacy["piece_values"]["box_body:left_side"][2] == 15.
    assert state == saved_state and snapshot == saved_snapshot


@pytest.mark.parametrize("field,bad", [
    ("side_rear_bend", True), ("side_rear_bend", "nan"),
    ("side_rear_bend", 0), ("back_width_comp_t", True),
    ("back_width_comp_t", "inf"), ("back_width_comp_t", -0.5),
])
def test_side_back_saved_material_and_compensation_cannot_be_faked(field, bad):
    state = api.default_box_body_structure_state()
    kind = api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    state["active_type"] = kind
    state["configs"][kind][field] = bad
    witness = deepcopy(state)
    with pytest.raises(ValueError):
        api.project_operator_box_body_structure_settings(
            state, 800., snapshot={"model": "金庫型"},
        )
    assert state == witness

@pytest.mark.parametrize("space", ["MATERIAL", "OUTSIDE"])
@pytest.mark.parametrize("resolver", [
    "side_rear_bend_material_length", "side_rear_bend_outside_length",
])
@pytest.mark.parametrize("bad_t", [
    True, False, None, 0, -1, "-0.125", "nan", "inf", float("-inf"),
])
def test_public_rear_flange_both_directions_reject_invalid_raw_thickness(
    space, resolver, bad_t,
):
    state = api.set_side_back_geometry(
        api.default_box_body_structure_state(),
        side_rear_bend=15., side_rear_bend_dimension_space=space,
    )
    witness = deepcopy(state)
    with pytest.raises(ValueError):
        getattr(api, resolver)(state, bad_t)
    assert state == witness


@pytest.mark.parametrize("space", ["MATERIAL", "OUTSIDE"])
@pytest.mark.parametrize("resolver", [
    "side_rear_bend_material_length", "side_rear_bend_outside_length",
])
@pytest.mark.parametrize("bad_saved", [True, False, None, 0, -1, "nan", "inf"])
def test_public_rear_flange_both_directions_reject_corrupt_saved_source(
    space, resolver, bad_saved,
):
    state = api.default_box_body_structure_state()
    cfg = state["configs"][api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg["side_rear_bend_dimension_space"] = space
    cfg["side_rear_bend"] = bad_saved
    witness = deepcopy(state)
    with pytest.raises(ValueError):
        getattr(api, resolver)(state, "2.25")
    assert state == witness


@pytest.mark.parametrize("outside_length", [0.5, 2.0, "2.25"])
@pytest.mark.parametrize("resolver", [
    "side_rear_bend_material_length", "side_rear_bend_outside_length",
])
def test_outside_rear_flange_must_leave_positive_material_in_both_directions(
    outside_length, resolver,
):
    state = api.set_side_back_geometry(
        api.default_box_body_structure_state(),
        side_rear_bend=outside_length,
        side_rear_bend_dimension_space="OUTSIDE",
    )
    before = deepcopy(state)
    with pytest.raises(ValueError, match="料尺寸"):
        getattr(api, resolver)(state, 2.25)
    assert state == before


def test_public_rear_flange_material_outside_fractional_roundtrip_and_projection():
    original = api.default_box_body_structure_state()
    material = api.set_side_back_geometry(
        original, side_rear_bend="15.125",
        side_rear_bend_dimension_space="MATERIAL",
    )
    outside = api.set_side_back_geometry(
        original, side_rear_bend="17.375",
        side_rear_bend_dimension_space="OUTSIDE",
    )
    witnesses = deepcopy((original, material, outside))
    for state in (material, outside):
        assert api.side_rear_bend_material_length(state, "2.25") == pytest.approx(15.125)
        assert api.side_rear_bend_outside_length(state, "2.25") == pytest.approx(17.375)
        reloaded = json.loads(json.dumps(state, allow_nan=False))
        assert api.side_rear_bend_material_length(reloaded, 2.25) == pytest.approx(15.125)
        assert api.side_rear_bend_outside_length(reloaded, 2.25) == pytest.approx(17.375)
        projection = api.project_operator_box_body_structure_settings(
            {**state, "active_type": api.BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value},
            800., snapshot={"model": "受電箱", "t": "2.25"},
        )
        assert projection["piece_values"]["box_body:left_side"][2] == pytest.approx(17.375)
        assert projection["piece_values"]["box_body:right_side"][2] == pytest.approx(17.375)
    assert (original, material, outside) == witnesses
