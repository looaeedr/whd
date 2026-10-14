# -*- coding: utf-8 -*-
"""Guard the Receiving first fold's original program 3D orientation.

Evidence: pre-DXF Git revision 3624a0e6a6b642efbcaa63d71f0903263745b3fd
(confirmed original program-generated 3D, before commit ac2e831f
introduced Receiving left/right/rear source DXFs).

This test guards first-fold identity and visible orientation only.
It does NOT waive or replace FW, formed-outside and divider collision gates.
"""
import pytest
from tests.test_issue39_divider_relief import _body_part, _snapshot
from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry


def test_original_program_left_zl1_is_front_and_inward_without_middle_mirror():
    snap = _snapshot()
    body = _body_part(snap)
    left = next(piece for piece in body.render_data.pieces if piece.role == "left_side")
    assert tuple(row.phase6_key for row in left.fold_profile) == (
        "zl1", "zl2", "fw_left", "d_left", "side_rear_bend_left",
    )
    first = left.fold_profile[0]
    assert snap["zl1"] == pytest.approx(-24.)
    assert first.length == pytest.approx(22.)
    assert first.formed_length == pytest.approx(24.)
    assert first.angle == pytest.approx(90.)

    world = _phase6_build_joint_world_geometry(
        (body,), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    skins = world["mapped_skin_triangles_by_part"]["box_body:left_side"]
    first_skins = [
        tri for tri in skins
        if 1e-6 < sum(p[0] for p in tri.flat) / 3.0 < first.length - 1e-6
    ]
    assert first_skins
    x = [p[0] for tri in first_skins for p in tri.world]
    z = [p[2] for tri in first_skins for p in tri.world]
    # As independently measured from original pre-DXF program 3D:
    # first fold at the FRONT +Z and extends into the box in +X.
    assert (min(x), max(x)) == pytest.approx((-372., -350.))
    assert (min(z), max(z)) == pytest.approx((152., 154.))
