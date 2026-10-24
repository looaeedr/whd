"""R6 manual source check: restored side/back physical values are finite."""
from math import inf, nan

import pytest

from ae_engine.box_body_structure import resolve_box_body_structure
from phase6_box_body_structure import (
    BoxBodyStructureType, default_box_body_structure_state,
    set_active_structure, set_side_back_geometry,
    side_rear_bend_material_length, side_rear_bend_outside_length,
)
from phase6_fold_profiles import build_box_body_profile


def _source():
    snapshot = {
        "w": 1200., "h": 1600., "d": 400., "t": 2., "fw": 25.,
        "zl1": 15., "zl2": 20., "zr1": 15., "zr2": 20.,
    }
    state = set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )
    return snapshot, state


def _resolve(snapshot, state, back_contract=None):
    return resolve_box_body_structure(
        build_box_body_profile(snapshot),
        w=snapshot["w"], h=snapshot["h"], t=snapshot["t"],
        structure_state=state, back_panel_contract=back_contract,
    )


@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf, "NaN"])
def test_r6_stored_back_width_compensation_cannot_be_nonfinite_or_bool(bad):
    snapshot, state = _source()
    cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg["back_width_comp_t"] = bad
    with pytest.raises(ValueError, match="後面板寬補償"):
        _resolve(snapshot, state)


@pytest.mark.parametrize("key", ["panel_width", "material_height", "formed_y_offset"])
@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf, "NaN"])
def test_r6_back_contract_fields_reject_nonfinite_and_bool_before_assembly(key, bad):
    snapshot, state = _source()
    # Other contract fields use the exact current physical source dimensions.
    valid = _resolve(snapshot, state).pieces[1]
    contract = {
        "panel_width": valid.structural.width,
        "material_height": valid.structural.height / 2.,
        "formed_y_offset": valid.structural.height / 4.,
    }
    contract[key] = bad
    with pytest.raises(ValueError, match="後面板 contract"):
        _resolve(snapshot, state, contract)


def test_r6_valid_full_and_partial_back_skins_keep_source_dimensions_and_offset():
    snapshot, state = _source()
    base = _resolve(snapshot, state)
    assert [p.role for p in base.pieces] == ["left_side", "back", "right_side"]
    back = base.pieces[1]
    assert back.structural.width == pytest.approx(1199.)
    assert back.formed_y_offset == pytest.approx(0.)

    contracted = _resolve(snapshot, state, {
        "panel_width": back.structural.width,
        "material_height": back.structural.height / 2.,
        "formed_y_offset": back.structural.height / 4.,
    })
    projected = contracted.pieces[1]
    assert projected.structural.width == pytest.approx(back.structural.width)
    assert projected.structural.height == pytest.approx(back.structural.height / 2.)
    assert projected.formed_y_offset == pytest.approx(back.structural.height / 4.)


@pytest.mark.parametrize("key", ["side_rear_bend", "back_width_comp_t"])
@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf, "NaN"])
def test_r6_operator_side_back_source_rejects_nonfinite_or_bool(key, bad):
    _snapshot, state = _source()
    with pytest.raises(ValueError, match="必須為有限數值"):
        set_side_back_geometry(state, **{key: bad})


@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf, "NaN"])
def test_r6_restored_rear_bend_cannot_poison_material_or_outside_conversion(bad):
    _snapshot, state = _source()
    cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg["side_rear_bend"] = bad
    with pytest.raises(ValueError, match="側板後折"):
        side_rear_bend_material_length(state, 2.)
    with pytest.raises(ValueError, match="側板後折"):
        side_rear_bend_outside_length(state, 2.)


def test_r6_rear_bend_material_and_outside_authority_stays_reversible():
    _snapshot, state = _source()
    material = set_side_back_geometry(
        state, side_rear_bend=18.,
        side_rear_bend_dimension_space="MATERIAL", back_width_comp_t=1.,
    )
    assert side_rear_bend_material_length(material, 2.) == pytest.approx(18.)
    assert side_rear_bend_outside_length(material, 2.) == pytest.approx(20.)
    outside = set_side_back_geometry(
        state, side_rear_bend=20.,
        side_rear_bend_dimension_space="OUTSIDE", back_width_comp_t=1.,
    )
    assert side_rear_bend_material_length(outside, 2.) == pytest.approx(18.)
    assert side_rear_bend_outside_length(outside, 2.) == pytest.approx(20.)
    with pytest.raises(ValueError, match="板厚"):
        side_rear_bend_material_length(outside, True)
