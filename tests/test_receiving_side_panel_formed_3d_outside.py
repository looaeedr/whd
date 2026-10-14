# -*- coding: utf-8 -*-
"""Receiving: operator outside length must be the actual formed 3D solid envelope.

The editor's -24 mm is an OUTSIDE dimension.  The 22 mm flat material
interval does not authorize a 22/23 mm finished solid in either 3D view.
"""
from __future__ import annotations

import pytest

from ae_engine.cabinet_types import receiving
from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot


def _world_skin_band_bounds(world, key, start, end, axis=0):
    faces = (
        skin for skin in world["mapped_skin_triangles_by_part"][key]
        if start + 1e-6 < sum(v[0] for v in skin.flat) / 3.0 < end - 1e-6
    )
    values = [float(point[axis]) for face in faces for point in face.world]
    assert values, (key, start, end)
    return min(values), max(values)


@pytest.mark.parametrize("thickness", (1.5, 2.0, 3.0))
def test_receiving_left_zl1_finished_solid_measures_operator_outside(thickness):
    snap = _snapshot()
    snap["t"] = thickness
    body = _body_part(snap)
    left = next(piece for piece in body.render_data.pieces if piece.role == "left_side")
    zl1, adjacent = left.fold_profile[:2]
    assert zl1.phase6_key == "zl1"
    assert zl1.angle == pytest.approx(90)
    assert zl1.formed_length == pytest.approx(abs(snap["zl1"]))
    assert zl1.length == pytest.approx(abs(snap["zl1"]) - thickness)
    assert adjacent.phase6_key == "zl2"

    world = _phase6_build_joint_world_geometry(
        (body,), (snap["w"], snap["h"], snap["d"]), thickness
    )
    key = "box_body:left_side"
    adjacent_min, adjacent_max = _world_skin_band_bounds(
        world, key, zl1.length, zl1.length + adjacent.length
    )
    _tip_min, tip_max = _world_skin_band_bounds(world, key, 0.0, zl1.length)

    # Physical formed/outside of first FRONT leg is measured from zl2's
    # actual outer skin, not the D main plane (-W/2) nor a BEND midline.
    assert adjacent_max - adjacent_min == pytest.approx(thickness, abs=1e-5)
    assert tip_max - adjacent_min == pytest.approx(
        abs(snap["zl1"]), abs=1e-5
    ), ("formed outside differs from 3D skin", tip_max, adjacent_min)


def test_receiving_left_formed_outside_keeps_certified_divider_collision_clear():
    snap = _snapshot()
    body = _body_part(snap)
    _divider, divider_part = _divider_part(snap)
    from fold_designer_bridge import _phase6_resolve_family_divider_reliefs

    solved, diagnostics, _ = _phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"], clearance=0.0,
    )
    assert solved
    assert diagnostics and diagnostics[0].illegal_penetration is False
    post = dict(diagnostics[0].evidence["post"])
    assert post["verified"] is True
    assert int(post["true_thickness_penetrating_band_count"]) == 0


def test_receiving_active_3d_editor_render_is_thick_formed_solid_not_22_flat_skin():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from types import SimpleNamespace
    from ae_engine.assembly_geometry import folded_mesh_with_flat_uv_from_polygon
    from ae_engine.assembly_geometry_folded_mesh import fit_receiving_left_zl1_formed_outside
    from ae_engine.box_body_structure import project_side_back_3d_input_fold_to_physical
    from fold_designer_bridge import _phase6_box_body_piece_part_profiles
    from phase6_final_scene_contracts import FinalSceneViewRequest
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer

    snap = _snapshot()
    body = _body_part(snap)
    piece = next(p for p in body.render_data.pieces if p.role == "left_side")
    source = _phase6_box_body_piece_part_profiles(body.render_data, snap)
    x = project_side_back_3d_input_fold_to_physical(
        source["box_body:left_side"]["X"],
        role="left_side", receiving=True, thickness=snap["t"]
    )
    y = source["box_body:left_side"]["Y"]
    material = piece.render_data.material
    mapped = folded_mesh_with_flat_uv_from_polygon(
        material, x, y, fold_guides=tuple(piece.render_data.fold_guides or ())
    )
    fitted = fit_receiving_left_zl1_formed_outside(
        x, mapped, tuple(item.local for item in mapped),
        thickness=snap["t"], axis=2,
    )
    first = [
        point[2] for item, tri in zip(mapped, fitted)
        if sum(p[0] for p in item.flat) / 3 < x[0]["len"] - 1e-6
        for point in tri
    ]
    # In original non-mirrored local 3D, zl2 is the actual folded datum.
    # The reference is its OUTER sheet skin, not local zero.
    second = [
        pt[2] for item, tri in zip(mapped, fitted)
        if x[0]["len"] + 1e-6 < sum(p[0] for p in item.flat) / 3
        < x[0]["len"] + x[1]["len"] - 1e-6
        for pt in tri
    ]
    assert max(first) - (min(second) - snap["t"] / 2) == pytest.approx(
        abs(snap["zl1"]), abs=1e-6
    )

    fig = plt.figure()
    try:
        ax = fig.add_subplot(111, projection="3d")
        renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
        triangles = renderer.render(FinalSceneViewRequest(
            render_data=piece.render_data,
            x_profile=tuple(x), y_profile=tuple(y),
            part_key="box_body:left_side",
            finished_dimensions=(snap["w"],snap["h"],snap["d"]),
            thickness=snap["t"],
        ))
        assert len(triangles) > len(fitted) * 2
        assert max(point[2] for tri in triangles for point in tri) >= abs(snap["zl1"]) - snap["t"]/2 - 1e-6
    finally:
        plt.close(fig)
