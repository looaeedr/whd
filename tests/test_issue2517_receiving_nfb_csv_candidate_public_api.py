# -*- coding: utf-8 -*-
"""#2517: public WHD NFB CSV Apply owns the complete source/Bay transaction.

The CADSplit source bridge must not implement its own Bay commit loop.  This
tests the shared Engine contract without making CSV candidate source a
certified CUTTING / world-X manufacturing result.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.sheetmetal_feature_core import FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue1503_csv_committed_config import PART, _feature


def _layout():
    return manufacturing_api.resize_receiving_bays_with_family_defaults(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )


def _source():
    ref = numeric_model_ref("士林", "2P400")
    return {
        "layers": 2,
        "models": [ref, ref],
        "layer_heights_mm": [300., 800.],
        "features": {PART: [_feature(0), _feature(1)]},
    }


def test_public_csv_apply_matches_existing_engine_ports_and_keeps_bays_distinct():
    original = _layout()
    untouched = deepcopy(original)
    source = _source()

    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        original, set_index=0, bay_indices=(1, 0), source=source,
    )
    assert original == untouched
    assert applied is not original

    csv = manufacturing_api.candidate_committed_csv_nfb_config(source)
    manufacturing_api.validate_candidate_nfb_replacement(
        original, ((0, 1), (0, 0)), source, csv,
    )
    # The old public CSV Apply returned only NFBConfig, dropping the native
    # Hole Editor features needed by the ordinary FinalScene world-X path.
    # It must equal the existing complete inner-door Engine transaction.
    expected, selected, physical_ids = (
        manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
            original, source, 0, (1, 0),
        )
    )
    assert selected == (0, 1)
    assert physical_ids == tuple(
        expected["sets"][0]["bays"][i]["stable_id"] for i in selected
    )
    assert applied == expected

    bays = applied["sets"][0]["bays"]
    ids = [
        {hole["physical_hole_id"] for hole in bay["nfb_config"]["holes"]}
        for bay in bays
    ]
    assert len(ids[0]) == len(ids[1]) == 2
    assert ids[0].isdisjoint(ids[1])
    assert all(bay["nfb_config_submitted"] is True for bay in bays)
    assert all(
        hole["manual_x_state"] == "UNVERIFIED_BASIS"
        and hole["manual_x_mm"] is None
        for bay in bays for hole in bay["nfb_config"]["holes"]
    )
    assert manufacturing_api.apply_receiving_nfb_csv_candidate(
        applied, set_index=0, bay_indices=(1, 0), source=source,
    ) == applied


@pytest.mark.parametrize("set_index,bays,reason", (
    (True, (0,), "RECEIVING_SET_SELECTION_INVALID"),
    (2, (0,), "RECEIVING_SET_SELECTION_INVALID"),
    (0, (), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (True,), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (0, 2), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (0, 0), "RECEIVING_BAY_SELECTION_DUPLICATE"),
    (0, None, "RECEIVING_BAY_SELECTION_INVALID"),
))
def test_public_csv_apply_rejects_invalid_bay_selection_without_partial_commit(
    set_index, bays, reason,
):
    original = _layout()
    before = deepcopy(original)
    with pytest.raises(ValueError, match=reason):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=set_index, bay_indices=bays,
            source=_source(),
        )
    assert original == before


def test_public_csv_apply_requires_real_csv_candidate_not_just_a_nfb_model():
    original = _layout()
    before = deepcopy(original)
    source = _source()
    source["features"] = {}
    with pytest.raises(ValueError, match="RECEIVING_NFB_CSV_SOURCE_REQUIRED"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0,), source=source,
        )
    assert original == before


def test_public_csv_apply_rejects_incomplete_or_mixed_cutting_without_partial_commit():
    original = _layout()
    before = deepcopy(original)

    incomplete = _source()
    incomplete["features"] = {PART: [_feature(0)]}
    with pytest.raises(ValueError, match="NFB_CSV_COMMIT_MISSING_CONFIRMED_HOLE"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=incomplete,
        )

    mixed = _source()
    mixed["features"] = {
        PART: [_feature(0), _feature(1), replace(_feature(0), source_type="MANUAL")],
    }
    with pytest.raises(ValueError, match="CUTTING"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=mixed,
        )
    assert original == before

def test_package_public_api_reexports_same_atomic_csv_apply():
    """Both supported import paths must expose one real Engine transaction."""
    import ae_engine

    assert "apply_receiving_nfb_csv_candidate" in ae_engine.__all__
    public_apply = ae_engine.apply_receiving_nfb_csv_candidate
    assert public_apply is manufacturing_api.apply_receiving_nfb_csv_candidate

    layout = _layout()
    source = _source()
    expected = manufacturing_api.apply_receiving_nfb_csv_candidate(
        layout, set_index=0, bay_indices=(0, 1), source=source,
    )
    actual = public_apply(
        layout, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert actual == expected


@pytest.mark.parametrize("tamper,expected_code", (
    (lambda feature: replace(feature, layer="MARKING"),
     "NFB_CSV_COMMIT_FINISHED_FACE_CUTTING_REQUIRED"),
    (lambda feature: replace(feature, layer="BEND"),
     "NFB_CSV_COMMIT_FINISHED_FACE_CUTTING_REQUIRED"),
    (lambda feature: replace(feature, anchor=FeatureAnchor.PANEL_CENTER),
     "NFB_CSV_COMMIT_FINISHED_FACE_CUTTING_REQUIRED"),
    (lambda feature: replace(feature, layered_profiles=(
        ("CUTTING", tuple(feature.points), True),
     )),
     "NFB_CSV_COMMIT_FINISHED_FACE_CUTTING_REQUIRED"),
    (lambda feature: replace(feature, offset=Vec2(float("nan"), 0.0)),
     "NFB_CSV_COMMIT_FINITE_PHYSICAL_PROFILE_REQUIRED"),
    (lambda feature: replace(feature, offset=Vec2(0.0, float("inf"))),
     "NFB_CSV_COMMIT_FINITE_PHYSICAL_PROFILE_REQUIRED"),
    (lambda feature: replace(feature, points=(
        Vec2(float("nan"), feature.points[0].y),
     ) + feature.points[1:]),
     "NFB_CSV_COMMIT_FINITE_PHYSICAL_PROFILE_REQUIRED"),
))
def test_csv_candidate_must_be_physical_finished_face_cutting_before_any_bay_commit(
    tamper, expected_code,
):
    # A forged NFB_CSV_SOURCE tag or matching source SHA alone is not a
    # physical opening. Refuse even a source-only Apply, atomically.
    original = _layout()
    before = deepcopy(original)
    source = _source()
    source["features"][PART][0] = tamper(source["features"][PART][0])
    with pytest.raises(ValueError, match=expected_code):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=source,
        )
    assert original == before


def test_valid_original_csv_source_remains_applicable_to_two_distinct_bays():
    original = _layout()
    source = _source()
    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        original, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert all(
        row["nfb_config_submitted"] is True
        for row in applied["sets"][0]["bays"]
    )
    assert original["sets"][0]["bays"][0].get("nfb_config_submitted") is not True


@pytest.mark.parametrize("distortion", (
    "one_vertex_moved",
    "sheared_rectangle",
    "crossed_vertex_order",
    "wrong_model_rectangle",
))
def test_csv_candidate_rejects_forged_opening_shape_before_either_bay_is_submitted(
    distortion,
):
    # Source SHA and model identity stay genuine: only the actual physical
    # native Hole Editor contour is changed. Previously the source commit
    # accepted all four and marked both real Bays as submitted, discarding
    # the false geometry evidence until the later FinalScene gate.
    layout = _layout()
    before = deepcopy(layout)
    source = _source()
    feature = source["features"][PART][0]
    points = feature.points
    if distortion == "one_vertex_moved":
        wrong = (Vec2(points[0].x + 7.0, points[0].y),) + points[1:]
    elif distortion == "sheared_rectangle":
        wrong = (
            points[0], points[1],
            Vec2(points[2].x + 13.0, points[2].y),
            Vec2(points[3].x + 13.0, points[3].y),
        )
    elif distortion == "crossed_vertex_order":
        wrong = (points[0], points[2], points[1], points[3])
    else:
        wrong = tuple(Vec2(p.x * 1.25, p.y) for p in points)
    source["features"][PART][0] = replace(feature, points=wrong)
    with pytest.raises(
        ValueError, match="NFB_CSV_COMMIT_OPENING_SHAPE_DIFFERS_FROM_SOURCE",
    ):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            layout, set_index=0, bay_indices=(0, 1), source=source,
        )
    assert layout == before


def test_original_csv_editor_placed_rotated_and_reordered_contour_stays_legal():
    # The native editor MAY translate X/Y or rotate the actual source polygon.
    # Neither location nor orientation is an inferred manufacturing X proof.
    layout = _layout()
    source = _source()
    first = source["features"][PART][0]
    source["features"][PART][0] = replace(
        first,
        points=first.points[1:] + first.points[:1],
        offset=Vec2(17.25, -5.0),
        rotation_deg=90,
    )
    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        layout, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert len(applied["sets"][0]["bays"]) == 2
    assert all(bay["nfb_config_submitted"] is True
               for bay in applied["sets"][0]["bays"])
    assert all(
        h["manual_x_state"] == "UNVERIFIED_BASIS"
        and h["manual_x_mm"] is None
        for bay in applied["sets"][0]["bays"]
        for h in bay["nfb_config"]["holes"]
    )
    assert all(
        bay["nfb_config"]["holes"][0]["rotation_deg"] == 90
        for bay in applied["sets"][0]["bays"]
    )


def test_csv_apply_retains_original_editor_features_for_each_real_bay_finalscene_source():
    """A committed NFBConfig alone is NOT a full physical FinalScene source."""
    from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
    from ae_engine.receiving_shared_settings import setting_value

    original = _layout()
    source = _source()
    frozen_source = deepcopy(source)
    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        original, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert source == frozen_source

    for bay_index in (0, 1):
        selected = applied["sets"][0]
        assert setting_value(selected, bay_index, "inner_door_layers") == 2
        assert setting_value(selected, bay_index, "inner_door_models") == source["models"]
        assert setting_value(selected, bay_index, "inner_door_layer_heights_mm") == (
            source["layer_heights_mm"]
        )
        assert setting_value(selected, bay_index, "inner_door_features") == source["features"]
        projected = project_receiving_bay_legacy_aliases(
            {"model": "受電箱", "t": 2.0, "receiving_layout": applied},
            set_index=0, bay_index=bay_index, validate_common=False,
        )
        assert projected["part_features"][PART] == source["features"][PART]
        assert projected["nfb_config_submitted"] is True
        assert projected["nfb_config"] == selected["bays"][bay_index]["nfb_config"]
        assert projected["_receiving_runtime_selection"]["bay_id"] == (
            selected["bays"][bay_index]["stable_id"]
        )


def test_csv_apply_isolates_selected_bay_features_from_unselected_linked_sibling():
    """A previously shared physical source ref must not alter unselected Bays."""
    from ae_engine.receiving_shared_settings import setting_value

    original = manufacturing_api.resize_receiving_bays_with_family_defaults(
        _layout(), set_index=0, bay_count=3,
    )
    linked = manufacturing_api.share_receiving_shared_setting(
        original, set_index=0, source_bay_index=0, bay_indices=(0, 2),
        kind="inner_door_features",
    )
    before = deepcopy(linked)
    source = _source()
    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        linked, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert linked == before
    assert all(
        applied["sets"][0]["bays"][i]["nfb_config_submitted"] is True
        for i in (0, 1)
    )
    assert applied["sets"][0]["bays"][2].get("nfb_config_submitted") is not True
    assert setting_value(applied["sets"][0], 2, "inner_door_features") == {}
    assert setting_value(applied["sets"][0], 0, "inner_door_features") == source["features"]
    refs = applied["sets"][0]["settings"]["inner_door_features"]["refs"]
    assert refs[applied["sets"][0]["bays"][0]["stable_id"]] != (
        refs[applied["sets"][0]["bays"][2]["stable_id"]]
    )


def test_csv_apply_invalid_extra_editor_payload_cannot_leave_nfb_submission_without_features():
    """The public API checks the complete candidate schema in one transaction."""
    source = _source()
    source["features"] = dict(source["features"])
    source["features"][PART] = tuple(source["features"][PART])
    source["unexpected_field"] = {"no": "candidate source"}
    original = _layout()
    before = deepcopy(original)
    with pytest.raises(ValueError, match="內門版本設定"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=source,
        )
    assert original == before
