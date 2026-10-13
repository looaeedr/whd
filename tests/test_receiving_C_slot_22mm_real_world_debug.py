# -*- coding: utf-8 -*-
"""Receiving /debug physical witness: 22-mm side fold must own C's 7-mm slot.

This test was added after the old suite falsely accepted a full certified
CROSS cut even though the source LEFT 22-mm fold was hundreds of millimetres
behind the physically assembled Divider. It intentionally uses the ORIGINAL
uncut authoritative world triangles. Merely comparing FW coplanarity, the
CUTTING polygon or a post-cut zero-penetration flag is not acceptance.
"""
from __future__ import annotations

import pytest

from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot
from tests.test_issue74_divider_side_front_penetration import _piece_bands


def _assembled_original_parts():
    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    world = _phase6_build_joint_world_geometry(
        (body, divider_part),
        (snapshot["w"], snapshot["h"], snapshot["d"]),
        snapshot["t"],
    )
    return snapshot, body, divider, divider_part, world


def test_real_22_mm_left_fold_occupies_C_divider_slot_world_location():
    """Independent world-axis witness: a missing Z intersection must FAIL."""
    snap, body, divider, divider_part, world = _assembled_original_parts()
    left = next(piece for piece in body.render_data.pieces
                if piece.role == "left_side")
    assert [round(seg.length, 6) for seg in left.fold_profile[:1]] == [22.0]
    assert left.fold_profile[0].angle == pytest.approx(-90.0)

    # Use the actual mapped THREE-D solid surface, NOT the flat reference
    # bend coordinate, renderer's triangle boxes or inverse notch formula.
    first_u0, first_u1 = next(
        (u0, u1) for name, u0, u1 in
        _piece_bands(body)["box_body:left_side"]
        if name == "zl1"
    )
    first = [
        vertex
        for skin in world["mapped_skin_triangles_by_part"]["box_body:left_side"]
        if first_u0 + 1e-5 < sum(v[0] for v in skin.flat) / 3 < first_u1 - 1e-5
        for vertex in skin.world
    ]
    middle = [
        vertex
        for skin in world["mapped_skin_triangles_by_part"][divider.stable_id]
        for vertex in skin.world
    ]
    assert first and middle
    axes = "XYZ"
    ranges = [
        ((min(p[i] for p in first), max(p[i] for p in first)),
         (min(p[i] for p in middle), max(p[i] for p in middle)))
        for i in range(3)
    ]
    for axis, (a, b) in zip(axes, ranges):
        assert max(a[0], b[0]) < min(a[1], b[1]), (
            f"Receiving C's 7mm U-slot cannot avoid the 22mm left fold: "
            f"no physical {axis}-axis encounter. left22={a}, C={b}. "
            "Do not mark post-cut zero-collision as successful mating."
        )


def test_C_seven_mm_slot_end_identifies_the_fold_it_avoids():
    """The 7-mm notch may not select its end by an unrelated zl2 fold."""
    from ae_engine.divider_manufacturing import _divider_object_mating_fold_signs

    _snap, body, _divider, part, _world = _assembled_original_parts()
    orientation = _divider_object_mating_fold_signs(part, body)
    slots = dict(orientation["evidence"])
    assert slots["MIN_Y"]["phase6_key"] == "zl1", (
        "7mm notch was positioned from zl2 although it must avoid LEFT 22mm zl1"
    )
    assert orientation["sign_by_end"]["MIN_Y"] < 0
