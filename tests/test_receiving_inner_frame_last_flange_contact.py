"""Receiving inner frame contact must use the last folded 22-mm real skins."""
from __future__ import annotations
import pytest
from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.inner_door_frames import derive_inner_door_frames
from ae_engine.receiving_joint_marking import (
    _last_frame_flange_skins,
    _physical_mating_contact,
)


def _skin(x, side, flat_x=75.0, y=0.0):
    # Winding makes +X; side identifies an outward physical surface.
    return MappedSkinTriangle(
        flat=((flat_x, 0.0), (flat_x + 1.0, 0.0), (flat_x, 10.0)),
        world=((x, y, 0.0), (x, y + 10.0, 0.0), (x, y, 10.0)),
        side=side,
    )


def _contact(shift=0.0, y=0.0):
    return _physical_mating_contact(
        locator_id="box_body:left_side",
        attached_id="inner_door:upper:left_frame",
        locator_mapping=(_skin(0.0, 1), _skin(-2.0, -1)),
        attached_mapping=(_skin(shift, -1, y=y), _skin(shift + 2.0, 1, y=y)),
    )


def test_real_physical_skin_contact_uses_same_support_plane():
    contact = _contact()
    assert contact.evidence["contact_mode"] == "VERIFIED_LAST_22_MM_PHYSICAL_SKIN"
    assert contact.evidence["projection_distance"] == pytest.approx(0.0)
    assert contact.evidence["overlap_area"] > 0


@pytest.mark.parametrize("displacement", [-3.0, -1.0, 0.5, 4.0, 50.0])
def test_parallel_non_contact_is_not_a_mark(displacement):
    with pytest.raises(ValueError, match="no real coplanar"):
        _contact(displacement)


def test_no_overlapping_skin_region_is_not_a_contact():
    with pytest.raises(ValueError, match="no real coplanar"):
        _contact(0.0, y=25.0)


def test_only_last_22_mm_flat_band_is_mating_flange():
    left = derive_inner_door_frames(
        "upper", spans={"left": 100.0}, thickness=2.0, included_sides=("left",)
    )[0]
    assert left.material_lengths == (22.0, 20.0, 46.0, 22.0)
    rows = (_skin(0.0, 1, flat_x=60.0), _skin(0.0, 1, flat_x=96.0))
    assert _last_frame_flange_skins(left, rows) == (rows[1],)
