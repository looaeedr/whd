"""Physical-skin guard: registration cannot turn a detached frame into a mate.

These small synthetic planes isolate the geometry contract from Receiving GUI,
outer-door width and any historical fixture coordinates.
"""
from __future__ import annotations

import pytest

from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.receiving_joint_marking import _projected_mating_contact


def _mapped_plane(x: float, *, outward_side: int, y0: float = 0.0):
    # Vertex winding yields +X; side selects the real outward skin normal.
    points = (
        (float(x), float(y0), 0.0),
        (float(x), float(y0) + 10.0, 0.0),
        (float(x), float(y0), 10.0),
    )
    return (
        MappedSkinTriangle(
            flat=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
            world=points,
            side=outward_side,
        ),
    )


def _contact(attached_midplane_x: float, *, frame_y: float = 0.0):
    return _projected_mating_contact(
        locator_id="box_body:left_side",
        attached_id="inner_door:upper:left_frame",
        locator_mapping=_mapped_plane(0.0, outward_side=1),
        attached_mapping=_mapped_plane(
            attached_midplane_x, outward_side=-1, y0=frame_y
        ),
        sheet_thickness=2.0,
    )


def test_opposed_physical_skins_mate_only_when_actual_skin_planes_coincide():
    result = _contact(0.0)
    assert result.evidence["contact_mode"] == (
        "VERIFIED_SKIN_TO_SKIN_CONTACT_UV_REGISTRATION"
    )
    assert result.evidence["physical_skin_clearance"] == pytest.approx(0.0)
    assert float(result.evidence["overlap_area"]) > 0


@pytest.mark.parametrize("skin_plane_x", [-1.0, 1.0, 3.0, 50.0])
def test_projection_must_not_certify_non_coplanar_physical_skins(skin_plane_x):
    with pytest.raises(ValueError, match="no physical mother-plate/frame face contact"):
        _contact(skin_plane_x)


def test_projection_must_not_certify_parallel_non_overlapping_skins():
    with pytest.raises(ValueError, match="no physical mother-plate/frame face contact"):
        _contact(0.0, frame_y=20.0)
