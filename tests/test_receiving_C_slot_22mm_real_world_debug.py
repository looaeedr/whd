# -*- coding: utf-8 -*-
"""Receiving /debug: left 22mm X encounter, C notch source, FW Z are separate.

User mechanical authority (2026-10-14):
- The first 22mm LEFT side fold is an X-axis interference/overlap witness.
- Side/Divider 29mm FW is a separate Z-axis assembly/alignment requirement.
- The 7mm notch in the C-divider source must remain on the LEFT end and
  correspond to the real folded 22mm component, not a presumed Z crossing.
"""
from __future__ import annotations

import pytest
import ezdxf
from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot
from tests.test_issue74_divider_side_front_penetration import _piece_bands
from ae_engine.receiving_frame_baseline import frame_source_file


def _source_world():
    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, part = _divider_part(snapshot)
    world = _phase6_build_joint_world_geometry(
        (body, part),
        (snapshot["w"], snapshot["h"], snapshot["d"]),
        snapshot["t"],
    )
    return snapshot, body, divider, part, world


def test_first_22mm_left_fold_has_actual_X_contact_at_C_notched_end():
    """The X crossing is the specification; no unsupported Z collision oracle."""
    _, body, divider, part, world = _source_world()
    left = next(x for x in body.render_data.pieces if x.role == "left_side")
    assert left.fold_profile[0].length == pytest.approx(22.)
    assert left.fold_profile[0].angle == pytest.approx(90.)  # original front-facing local fold
    u0, u1 = next(
        (start, end) for name, start, end in
        _piece_bands(body)["box_body:left_side"] if name == "zl1"
    )
    skins = world["mapped_skin_triangles_by_part"]["box_body:left_side"]
    first = [
        p for face in skins
        if u0 + 1e-6 < sum(v[0] for v in face.flat)/3 < u1 - 1e-6
        for p in face.world
    ]
    c = [p for skin in world["mapped_skin_triangles_by_part"][divider.stable_id]
         for p in skin.world]
    assert first and c

    # C source's LEFT 7-mm step occupies the first 51mm of its X span.
    # Read the real certified 10-vertex C CUTTING rather than inventing
    # a local-X offset from collision backprojection.
    ms = ezdxf.readfile(frame_source_file()).modelspace()
    contours = [
        ent for ent in ms
        if ent.dxftype() == "LWPOLYLINE"
        and ent.closed and ent.dxf.layer == "CUTTING" and len(ent) == 10
    ]
    assert len(contours) == 1
    pts = [(float(v[0]), float(v[1])) for v in contours[0].get_points()]
    xmin = min(x for x, _ in pts)
    seven = [
        (a, b) for a, b in zip(pts, pts[1:] + pts[:1])
        if abs(a[0] - b[0]) < 1e-6
        and abs(abs(a[1]-b[1])-7.) < 1e-6
    ]
    assert len(seven) == 1, "Certified C must retain its 7-mm notch"
    notch_offset = seven[0][0][0] - xmin
    c_left_x = min(p[0] for p in c)
    notch_x = (c_left_x, c_left_x + notch_offset)
    first_x = (min(p[0] for p in first), max(p[0] for p in first))
    # Before CUTTING the certified 7-mm C relief, the first 22-mm
    # left-side component must actually OVERLAP the notched end on X.
    # Merely sharing an X boundary does not prove that the notch is needed.
    # This is an X-only pre-cut witness; the FW29 Z mating and post-cut
    # no-penetration must be independently verified in their own tests.
    assert max(first_x[0], notch_x[0]) < min(first_x[1], notch_x[1]) - 1e-6, (
        "Left 22mm does not reach C's 7mm notched END on X: "
        f"left22 X={first_x}, notch X={notch_x}, C X="
        f"{(c_left_x, max(p[0] for p in c))}"
    )


def test_divider_29_and_both_side_29_fw_world_Z_stations_align_separately():
    """Confirm the actual FW bands' Z skins; no zl1 Z-overlap assertion."""
    from ae_engine.divider_manufacturing import resolve_divider_placement_evidence
    _, body, divider, part, world = _source_world()
    placement = resolve_divider_placement_evidence(part, body, world)
    assert placement.expected_fw_formed_occupation == pytest.approx(29.)
    assert placement.box_body_left_fw_formed_occupation == pytest.approx(29.)
    assert placement.box_body_right_fw_formed_occupation == pytest.approx(29.)
    assert placement.box_body_left_fw_planes == pytest.approx(
        placement.box_body_right_fw_planes
    )
    assert placement.divider_fw_planes == pytest.approx(
        placement.box_body_left_fw_planes
    )
    assert placement.fw_face_flush
    # The first 22mm's Z depth is NOT the acceptance datum for FW mating.


def test_C_seven_mm_notch_keeps_left_22mm_identity():
    from ae_engine.divider_manufacturing import _divider_object_mating_fold_signs
    _snap, body, _divider, part, _world = _source_world()
    orientation = _divider_object_mating_fold_signs(part, body)
    slots = dict(orientation["evidence"])
    assert slots["MIN_Y"]["phase6_key"] == "zl1"
    assert orientation["sign_by_end"]["MIN_Y"] < 0


def test_receiving_settings_preview_2d_shares_exact_true_world_skins_with_manufacturing():
    """A viewer must display the *same* placed physical pieces as manufacturing.

    The old viewer folded zero-thickness strips and skipped the Receiving
    25-material -> 29-outside FW physical correction, so apparent FW/Z mating
    could disagree with the validated world while tests stayed green.
    """
    from phase6_final_scene_contracts import AssemblySceneRenderData, FinalSceneViewRequest
    from gui_modules.application.receiving_settings_preview_2d import _assembly_world_meshes

    snap, body, _divider, part, world = _source_world()
    request = FinalSceneViewRequest(
        AssemblySceneRenderData((body, part)), (), (), "assembly",
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        thickness=snap["t"],
    )
    visual = {role: tuple(tris) for role, _stable, tris in _assembly_world_meshes(request)}
    for role in ("left_side", "right_side", "back"):
        ref = tuple(world["world_triangles_by_part"]["box_body:" + role])
        assert visual[role] == ref, (
            f"{role} 2D/3D settings preview differs from true-thickness "
            "source-mapped manufacturing 3D world; cannot trust visual FW/Z."
        )


def test_receiving_full_3d_renderer_displays_exact_manufacturing_world_triangles():
    """Actual 3D scene sink (not only helper) must show the real T=2 skins."""
    from types import SimpleNamespace
    from phase6_final_scene_renderer import (
        Phase6FinalSceneRenderer, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from tests.test_phase6_assembly_3d_view import Axis

    snap, body, _divider, part, world = _source_world()
    req = FinalSceneViewRequest(
        AssemblySceneRenderData(
            assembly_parts=(body, part),
            visible_part_keys=("box_body",),
        ),
        (), (), "assembly", finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        thickness=snap["t"],
    )
    renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=Axis()))
    shown = tuple(renderer.render(req))
    canonical = tuple(
        triangle for piece in body.render_data.pieces
        for triangle in world["world_triangles_by_part"]["box_body:"+piece.role]
    )
    assert shown == canonical, (
        "Assembly 3D displayed old zero-thickness strips, not manufactured "
        "FW=29mm true-thickness world solids."
    )
