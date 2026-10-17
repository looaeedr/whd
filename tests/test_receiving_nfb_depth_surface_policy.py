# -*- coding: utf-8 -*-
"""#1502/#1503: user's non-folded physical-face inference (NOT center planes)."""
import pytest

from ae_engine.receiving_nfb_depth_surface_policy import (
    FIRST_SIDE_FOLD_MM,
    receiving_nfb_second_side_fold_mm,
    resolve_receiving_nfb_surface_chain,
)


def test_shihlin_107_72_real_skin_positions_and_33_second_return():
    chain = resolve_receiving_nfb_surface_chain(
        inner_door_outer_face_from_front_mm=80,
        inner_door_thickness_mm=2,
        base_plate_thickness_mm=2,
        fixing_plate_thickness_mm=3,
        reference_nfb_depth_mm=107,
        secondary_nfb_depth_mm=72,
    )
    assert FIRST_SIDE_FOLD_MM == -40
    assert chain.inner_door_outer_face_mm == 80
    assert chain.inner_door_inner_face_mm == 82
    assert chain.reference_base_nfb_face_mm == 189
    assert chain.reference_base_back_face_mm == 191
    assert chain.fixing_plate_contact_face_mm == 191
    assert chain.fixing_plate_back_face_mm == 194
    assert chain.secondary_base_nfb_face_mm == 154
    assert chain.secondary_base_back_face_mm == 156
    assert chain.nfb_face_step_mm == 35
    assert chain.second_side_fold_mm == 33
    # Never confuse the physical 35-mm face step with the 33-mm return.
    assert chain.reference_base_nfb_face_mm - chain.secondary_base_nfb_face_mm == 35
    assert chain.reference_base_nfb_face_mm - chain.secondary_base_back_face_mm == 33
    # Fixing-plate contact needs MARKING at the actual common Z.
    assert chain.fixing_plate_contact_mark_from_front_mm == 191


def test_tungyuan_103_68_and_other_depth_pairs_not_hardcoded_33():
    assert receiving_nfb_second_side_fold_mm(
        reference_nfb_depth_mm=103, secondary_nfb_depth_mm=68,
        base_plate_thickness_mm=2,
    ) == 33
    assert receiving_nfb_second_side_fold_mm(
        reference_nfb_depth_mm=105, secondary_nfb_depth_mm=75,
        base_plate_thickness_mm=2,
    ) == 28


def test_flat_base_reference_only_no_invented_fold_or_secondary_surface():
    chain = resolve_receiving_nfb_surface_chain(
        inner_door_outer_face_from_front_mm=80,
        inner_door_thickness_mm=2,
        base_plate_thickness_mm=2,
        fixing_plate_thickness_mm=3,
        reference_nfb_depth_mm=107,
    )
    assert chain.reference_base_nfb_face_mm == 189
    assert chain.fixing_plate_contact_face_mm == 191
    assert chain.second_side_fold_mm is None
    assert chain.secondary_base_nfb_face_mm is None


def test_relative_geometry_independent_of_outer_reference_and_ear_t():
    a = resolve_receiving_nfb_surface_chain(
        inner_door_outer_face_from_front_mm=80,
        inner_door_thickness_mm=2,
        base_plate_thickness_mm=2,
        fixing_plate_thickness_mm=3,
        reference_nfb_depth_mm=107, secondary_nfb_depth_mm=72,
    )
    b = resolve_receiving_nfb_surface_chain(
        inner_door_outer_face_from_front_mm=95,
        inner_door_thickness_mm=2,
        base_plate_thickness_mm=2,
        fixing_plate_thickness_mm=4,
        reference_nfb_depth_mm=107, secondary_nfb_depth_mm=72,
    )
    assert b.reference_base_nfb_face_mm - a.reference_base_nfb_face_mm == 15
    assert b.fixing_plate_contact_face_mm - a.fixing_plate_contact_face_mm == 15
    assert b.second_side_fold_mm == a.second_side_fold_mm == 33
    assert b.fixing_plate_back_face_mm - a.fixing_plate_back_face_mm == 16


@pytest.mark.parametrize("deep,shallow,t", [
    (107, 107, 2), (72, 107, 2), (107, 106, 2),
    (107, 72, 0), (float("nan"), 72, 2), (107, float("inf"), 2),
])
def test_invalid_depths_cannot_silently_make_a_manufacturable_fold(deep, shallow, t):
    with pytest.raises(ValueError):
        receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=deep, secondary_nfb_depth_mm=shallow,
            base_plate_thickness_mm=t,
        )


def test_exact_selected_brand_csv_depths_are_source_not_a_global_magic_constant():
    from ae_engine.receiving_nfb_numeric_catalog import model_spec
    shihlin_deep = model_spec("士林", "3P400SN")
    shihlin_shallow = model_spec("士林", "3P125SN")
    tungyuan_deep = model_spec("東元", "3P400SN")
    tungyuan_shallow = model_spec("東元", "3P125SN")
    assert (shihlin_deep.depth_mm, shihlin_shallow.depth_mm) == (107, 72)
    assert (tungyuan_deep.depth_mm, tungyuan_shallow.depth_mm) == (103, 68)
    assert receiving_nfb_second_side_fold_mm(
        reference_nfb_depth_mm=shihlin_deep.depth_mm,
        secondary_nfb_depth_mm=shihlin_shallow.depth_mm,
        base_plate_thickness_mm=2,
    ) == 33


def test_selected_brand_model_csv_drives_depth_pair_not_fixed_literal():
    from ae_engine.receiving_nfb_depth_surface_policy import (
        selected_receiving_nfb_depth_pair_mm,
    )
    assert selected_receiving_nfb_depth_pair_mm(
        "士林", ["400_140X257_107.dxf", "125_90X155_72.dxf"]
    ) == (107.0, 72.0)
    assert selected_receiving_nfb_depth_pair_mm(
        "東元", ["140X260_103.dxf", "90X155_68.dxf"]
    ) == (103.0, 68.0)
    assert selected_receiving_nfb_depth_pair_mm(
        "士林", ["nfbv5:士林:3P400SN", "nfbv5:士林:3P125SN"]
    ) == (107.0, 72.0)


@pytest.mark.parametrize("brand, refs", [
    ("士林", ["nfbv5:東元:3P400SN", "nfbv5:士林:3P125SN"]),
    ("東元", ["400_Type.dxf", "90X155_68.dxf"]),  # depth missing
    ("士林", ["missing.dxf", "125_90X155_72.dxf"]),
    ("士林", ["400_140X257_107.dxf"]),
])
def test_unknown_or_foreign_model_never_auto_selects_other_brand_depth(brand, refs):
    from ae_engine.receiving_nfb_depth_surface_policy import (
        selected_receiving_nfb_depth_pair_mm,
    )
    with pytest.raises(ValueError):
        selected_receiving_nfb_depth_pair_mm(brand, refs)
