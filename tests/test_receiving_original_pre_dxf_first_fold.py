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
    # The first leg remains at the original FRONT +Z, facing +X.
    # Its actual skin now honors the 24 outside distance from zl2 skin
    # (the old sharp-middle-face renderer let its hinge drift by 2mm).
    assert min(x) >= -snap["w"] / 2
    assert max(x) > min(x)
    assert (min(z), max(z)) == pytest.approx((152., 154.))
    second = [
        p[0] for face in skins
        if first.length + 1e-6 < sum(v[0] for v in face.flat) / 3
        < first.length + left.fold_profile[1].length - 1e-6
        for p in face.world
    ]
    assert max(x) - min(second) == pytest.approx(24.)
