"""Manual R6 contact-frame check: corrupt XYZ never escapes fail-closed."""
from types import SimpleNamespace

import pytest

from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.assembly_marking_geometry import (
    resolve_contact_local_frame, resolve_side_boundary_pair,
)
from ae_engine.contracts import ResolvedLegalContact


WORLD = ((0., 0., 0.), (4., 0., 0.), (4., 2., 0.), (0., 2., 0.))
MAPPING = (
    MappedSkinTriangle(
        flat=((0., 0.), (4., 0.), (0., 2.)),
        world=((0., 0., 0.), (4., 0., 0.), (0., 2., 0.)),
        side=1,
    ),
    MappedSkinTriangle(
        flat=((4., 0.), (4., 2.), (0., 2.)),
        world=((4., 0., 0.), (4., 2., 0.), (0., 2., 0.)),
        side=1,
    ),
)


def _contact(world):
    return ResolvedLegalContact(
        locator_part_id="locator",
        attached_part_id="attached",
        locator_region=SimpleNamespace(flat_mapping=MAPPING),
        attached_region=None,
        contact_plane=((0., 0., 0.), (0., 0., 1.)),
        locator_outward_normal=(0., 0., 1.),
        attached_outward_normal=(0., 0., -1.),
        overlap_world=world,
        locator_flat_mapping=MAPPING,
    )


def _frame(contact):
    return resolve_contact_local_frame(
        contact, longitudinal_flat_axis="+X", cross_flat_axis="+Y",
    )


def test_r6_contact_frame_and_semantic_pair_preserve_valid_xyz_geometry():
    contact = _contact(WORLD)
    frame = _frame(contact)
    assert frame.status == "RESOLVED", frame
    assert frame.frame is not None
    boundary = resolve_side_boundary_pair(contact, frame.frame)
    assert boundary.status == "RESOLVED", boundary
    assert boundary.pair is not None


@pytest.mark.parametrize("world", [
    ((0., 0.), (4., 0., 0.), (4., 2., 0.), (0., 2., 0.)),
    ((0., 0., 0.), (4., 0., 0.), (4., 2., 0.), (0., 2.)),
    ((0., 0., float("nan")), (4., 0., 0.), (4., 2., 0.), (0., 2., 0.)),
    ((0., 0., 0.), (4., 0., 0.), (4., float("inf"), 0.), (0., 2., 0.)),
    ((0., 0., 0.), (4., 0., 0.), (4., 2., 0.), (0., 2., True)),
    ((0., 0., 0.), (4., 0., 0.), (4., 2., 0.)),
])
def test_r6_bad_xyz_never_produces_a_resolved_contact_frame_or_pair(world):
    # All 3D boundary coordinates must be physical XYZ values, not partial
    # tuples or non-finite values. No 2D/Z guess may become manufactured.
    contact = _contact(world)
    frame = _frame(contact)
    assert frame.status == "SKIPPED_FAIL_CLOSED", frame
    assert frame.frame is None
    assert frame.diagnostic_code == "BOUNDARY_FRAME_UNRESOLVED"

    valid = _frame(_contact(WORLD))
    assert valid.status == "RESOLVED"
    boundary = resolve_side_boundary_pair(contact, valid.frame)
    assert boundary.status == "SKIPPED_FAIL_CLOSED", boundary
    assert boundary.pair is None
    assert boundary.diagnostic_code == "BOUNDARY_PAIR_AMBIGUOUS"
