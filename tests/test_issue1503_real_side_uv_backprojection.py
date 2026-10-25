# -*- coding: utf-8 -*-
"""#1503: real formed EAR -> owner SIDE physical skin -> flat UV receipt tests."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon, box

from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.manufacturing_render_data import FoldGuide
from ae_engine.receiving_fixed_plate_side_contact import (
    resolve_receiving_ear_side_contact_surfaces,
    receiving_ear_installation_world_segment,
)
from ae_engine.receiving_fixed_plate_side_uv_marking import (
    project_receiving_ear_contact_to_side_uv,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _source_side_skin(x):
    """Two triangles with *SIDE-owned* folded-world->source-flat UV identity.

    The projection under test consumes the actual source-formed EAR contact
    from product 3D; synthetic side UV permits deterministic negative tests.
    """
    flat = ((0., 0.), (1500., 0.), (1500., 1500.), (0., 1500.))
    world = (
        (x, -500., -1000.),
        (x, 1000., -1000.),
        (x, 1000., 500.),
        (x, -500., 500.),
    )
    return tuple(
        MappedSkinTriangle(
            flat=tuple(flat[i] for i in ids),
            world=tuple(world[i] for i in ids),
            side=1,
        )
        for ids in ((0, 1, 2), (0, 2, 3))
    )


def _project(contact, *, mapping=None, material=None, guides=()):
    return project_receiving_ear_contact_to_side_uv(
        contact,
        side_mapped_skins=(_source_side_skin(contact.side_inside_skin_world_x_mm)
                           if mapping is None else mapping),
        side_final_material=(box(0., 0., 1500., 1500.)
                             if material is None else material),
        side_fold_guides=guides,
    )


@pytest.mark.parametrize("factory,count", ((_assembled, 2), (_two_tier, 4)))
def test_real_forming_contact_projects_to_its_own_side_flat_marking(factory, count):
    contacts = resolve_receiving_ear_side_contact_surfaces(factory())
    receipts = tuple(_project(contact) for contact in contacts)
    assert len(receipts) == count
    assert len({r.ear_part_id for r in receipts}) == count
    assert [r.side_piece_id for r in receipts] == [
        "box_body:left_side", "box_body:right_side",
    ] * (count // 2)
    assert [r.nfb_layer_index for r in receipts] == ([0, 0, 1, 1] if count == 4 else [0, 0])
    for contact, receipt in zip(contacts, receipts):
        assert receipt.base_part_id == contact.base_part_id
        assert receipt.world_boundary == contact.world_surface_boundary
        assert len(receipt.marking_segments) == 1
        assert receipt.side_flat_uv_backprojection_verified
        assert receipt.side_final_material_coverage_verified
        assert receipt.side_bend_intersection_rejected
        assert not receipt.weld_contact_verified
        assert not receipt.manufacturing_ready
        patch = Polygon(receipt.side_source_flat_boundary)
        assert patch.area == pytest.approx(256 * 22, abs=1.)
        assert (receipt.side_source_flat_boundary[1][0]
                - receipt.side_source_flat_boundary[0][0]) == pytest.approx(256., abs=0.02)
        assert (receipt.side_source_flat_boundary[3][1]
                - receipt.side_source_flat_boundary[0][1]) == pytest.approx(22., abs=0.02)


def test_installation_line_is_base_lower_edge_and_not_fold_length():
    # Real physical contact is still the full source weld-leg skin. Only the
    # visible side MARKING is reduced to one horizontal parent-base datum.
    contact = resolve_receiving_ear_side_contact_surfaces(_assembled())[0]
    a, b = receiving_ear_installation_world_segment(contact)
    assert a[2] == b[2] == pytest.approx(contact.base_lower_world_z_mm)
    assert b[1] - a[1] == pytest.approx(256.0)
    receipt = _project(contact)
    assert len(receipt.marking_segments) == 1
    assert receipt.world_boundary == contact.world_surface_boundary

    # The free formed leg may be longer/shorter; its LOWER z cannot drive
    # the upper installation datum. This is an isolated helper contract,
    # not a forged contact released to manufacturing.
    older_boundary = tuple(
        (p[0], p[1], p[2] - 9.0 if index < 2 else p[2])
        for index, p in enumerate(contact.world_surface_boundary)
    )
    extended = replace(contact, world_surface_boundary=older_boundary)
    assert receiving_ear_installation_world_segment(extended) == (a, b)

    # A BasePlate lower edge forged independently of the real T2 contact
    # must not become a freely chosen marking position.
    with pytest.raises(ValueError, match="BASE_LOWER_EDGE_CONTACT_MISMATCH"):
        receiving_ear_installation_world_segment(
            replace(contact, base_lower_world_z_mm=contact.base_lower_world_z_mm + 3)
        )


def test_side_uv_denies_material_cutting_hole_and_bend_crossing():
    contact = resolve_receiving_ear_side_contact_surfaces(_assembled())[0]
    receipt = _project(contact)
    patch = Polygon(receipt.side_source_flat_boundary)
    cx, cy = patch.centroid.x, patch.centroid.y
    with pytest.raises(ValueError, match="CUTTING_OR_MATERIAL_CONFLICT"):
        _project(contact, material=box(0, 0, 1500, 1500).difference(
            box(cx - 2, cy - 2, cx + 2, cy + 2)
        ))
    with pytest.raises(ValueError, match="SIDE_BEND_INTERSECTION"):
        _project(contact, guides=(FoldGuide("x", cx, 0., 1500.),))


def test_side_uv_denies_mismatched_world_skin_and_unmapped_extrapolation():
    contact = resolve_receiving_ear_side_contact_surfaces(_assembled())[0]
    wrong = _source_side_skin(contact.side_inside_skin_world_x_mm + 1.)
    with pytest.raises(ValueError, match="NO_AUTHENTIC_INSIDE_SIDE_SKIN"):
        _project(contact, mapping=wrong)
    # A small legitimate co-planar patch cannot be used to extrapolate
    # a 256 x 22 world footprint outside actual side mapped material.
    x = contact.side_inside_skin_world_x_mm
    tiny = (
        MappedSkinTriangle(
            flat=((100., 100.), (110., 100.), (100., 110.)),
            world=((x, -400., -900.), (x, -390., -900.), (x, -400., -890.)),
            side=1,
        ),
    )
    with pytest.raises(ValueError, match="OUTSIDE_ACTUAL_SIDE_SKIN"):
        _project(contact, mapping=tiny)


def test_side_uv_denies_wrong_owner_and_early_manufacture():
    contact = resolve_receiving_ear_side_contact_surfaces(_assembled())[0]
    for fake in (
        replace(contact, side_piece_id="box_body:right_side"),
        replace(contact, weld_contact_verified=True),
        replace(contact, manufacturing_ready=True),
        replace(contact, side_flat_uv_backprojection_verified=True),
    ):
        with pytest.raises(ValueError, match="EAR_SIDE_UV_"):
            _project(fake)
