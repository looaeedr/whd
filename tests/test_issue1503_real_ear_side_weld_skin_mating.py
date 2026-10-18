# -*- coding: utf-8 -*-
"""#1503: true source-W800 physical side/EAR T2 flange mating, no fake weld."""
from dataclasses import replace

import pytest

from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from ae_engine.receiving_fixed_plate_side_contact import (
    derive_receiving_ear_side_contact_from_formed_skin,
)
from ae_engine.receiving_fixed_plate_weld_skin_mating import (
    verify_receiving_ear_side_skin_mating,
    resolve_receiving_ear_side_skin_mating_witnesses,
)
from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
from tests.test_issue1050_receiving_mother_plate_marking import (
    _snapshot as _box_snapshot,
    _full_receiving_geometry,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _real_world(factory):
    snapshot = _box_snapshot()
    snapshot.update(factory())
    geom = _full_receiving_geometry(snapshot)
    world = _phase6_build_joint_world_geometry(
        geom.parts, (800., 1600., 350.), 2.,
    )
    return snapshot, world


@pytest.mark.parametrize("factory,count", ((_assembled, 2), (_two_tier, 4)))
def test_real_source_body_side_and_formed_ear_make_complete_signed_skin_contact(factory, count):
    snapshot, world = _real_world(factory)
    results = resolve_receiving_ear_side_skin_mating_witnesses(
        snapshot, world_geometry=world,
    )
    assert len(results) == count
    assert len({r.ear_part_id for r in results}) == count
    assert [r.side_piece_id for r in results] == [
        "box_body:left_side", "box_body:right_side",
    ]*(count//2)
    assert [r.nfb_layer_index for r in results] == (
        [0,0,1,1] if count == 4 else [0,0]
    )
    for row in results:
        assert row.physical_contact_area_mm2 == pytest.approx(5632, abs=1.)
        assert row.flange_skin_normal_opposed
        assert row.panel_inside_skin_source_verified
        assert row.full_contact_material_coverage_verified
        assert row.no_through_side_skin_penetration_verified
        assert not row.welding_workmanship_certified
        assert not row.manufacturing_ready


def test_missing_real_side_plane_and_wrong_skin_normal_do_not_verify_weld():
    snapshot, world = _real_world(_assembled)
    part_id = "base_plate:fixing_plate:left"
    formed = build_receiving_formed_fixing_plate_skins(snapshot, part_id)
    contact = derive_receiving_ear_side_contact_from_formed_skin(formed)
    rows = tuple(world["mapped_skin_triangles_by_part"][contact.side_piece_id])
    with pytest.raises(ValueError, match="OPPOSED_NORMAL_OR_SKIN_MISSING"):
        verify_receiving_ear_side_skin_mating(contact, formed, ())
    flipped = tuple(replace(skin, side=-skin.side) for skin in rows)
    # The other real SIDE physical skin is already present in the source
    # mapping; flipping every sidedness cannot masquerade as an inside face.
    with pytest.raises(ValueError, match="OPPOSED_NORMAL_OR_SKIN_MISSING"):
        verify_receiving_ear_side_skin_mating(contact, formed, flipped)


def test_actual_flange_must_have_opposed_solid_skin_and_no_wall_penetration():
    snapshot, world = _real_world(_assembled)
    part_id = "base_plate:fixing_plate:left"
    formed = build_receiving_formed_fixing_plate_skins(snapshot, part_id)
    contact = derive_receiving_ear_side_contact_from_formed_skin(formed)
    rows = world["mapped_skin_triangles_by_part"][contact.side_piece_id]
    forged_faces = tuple(replace(face, side=-face.side)
                         for face in formed.mapped_world_skins)
    with pytest.raises(ValueError, match="OPPOSED_NORMAL_OR_SKIN_MISSING"):
        verify_receiving_ear_side_skin_mating(
            contact, replace(formed, mapped_world_skins=forged_faces), rows,
        )
    # Displace the opposite physical leg face into the SIDE's material
    # volume, while retaining the face that sits on x=-398.
    forged = []
    for face in formed.mapped_world_skins:
        if all(abs(p[0]-contact.side_inside_skin_world_x_mm) <= 1e-5
               for p in face.world):
            forged.append(face)
        else:
            forged.append(replace(face, world=tuple(
                (float(p[0])-4., float(p[1]), float(p[2]))
                for p in face.world
            )))
    with pytest.raises(ValueError, match="THROUGH_WALL_PENETRATION"):
        verify_receiving_ear_side_skin_mating(
            contact, replace(formed, mapped_world_skins=tuple(forged)), rows,
        )


def test_contact_owner_or_source_bend_forgery_rejected():
    snapshot, world = _real_world(_assembled)
    formed = build_receiving_formed_fixing_plate_skins(
        snapshot, "base_plate:fixing_plate:right",
    )
    contact = derive_receiving_ear_side_contact_from_formed_skin(formed)
    rows = world["mapped_skin_triangles_by_part"][contact.side_piece_id]
    with pytest.raises(ValueError, match="FORM_OR_OWNER_UNVERIFIED"):
        verify_receiving_ear_side_skin_mating(
            replace(contact, nfb_layer_index=1), formed, rows,
        )
    with pytest.raises(ValueError, match="FORM_OR_OWNER_UNVERIFIED"):
        verify_receiving_ear_side_skin_mating(
            contact, replace(formed, source_bend_verified=False), rows,
        )
