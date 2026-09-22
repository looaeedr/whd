from __future__ import annotations

import pytest


def _snapshot(*, upper=1100.0, lower=500.0):
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": upper + lower,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [float(upper), float(lower)]]],
    }


def _state(mode):
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import set_side_back_back_panel_mode

    state = receiving.resolve_box_body_structure_state(None)
    return set_side_back_back_panel_mode(state, mode)


def _contract(mode, *, upper=1100.0, lower=500.0):
    from ae_engine.cabinet_types import receiving

    snapshot = _snapshot(upper=upper, lower=lower)
    return receiving.resolve_back_panel_contract(
        snapshot,
        structure_state=_state(mode),
        panel_width=795.0,
        full_panel_height=float(snapshot["h"]) - 4.0,
    )


def _render(mode):
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    snapshot = _snapshot()
    state = _state(mode)
    contract = receiving.resolve_back_panel_contract(
        snapshot,
        structure_state=state,
        panel_width=795.0,
        full_panel_height=1596.0,
    )
    spec = BoxBodyPartSpec(
        width=800.0,
        height=1600.0,
        depth=350.0,
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
        back_panel_contract=contract,
    )
    data = build_box_body_structure_render_data(spec)
    return data, next(piece for piece in data.pieces if piece.role == "back")


def _cutting_closed(render_data):
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    return [
        primitive
        for primitive in tuple(render_data.scene.primitives)
        if isinstance(primitive, PolylinePrimitive)
        and str(primitive.layer) == "CUTTING"
        and primitive.closed
    ]


def _bounds(polyline):
    xs = [float(point.x) for point in polyline.points]
    ys = [float(point.y) for point in polyline.points]
    return min(xs), min(ys), max(xs), max(ys)


def test_receiving_back_panel_state_defaults_full_and_persists_one_of_three_modes():
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import (
        BackPanelMode,
        back_panel_mode,
        set_side_back_back_panel_mode,
    )

    state = receiving.resolve_box_body_structure_state(None)
    assert back_panel_mode(state) is BackPanelMode.FULL

    for mode in (BackPanelMode.FULL, BackPanelMode.HALF, BackPanelMode.BACK_OPENING):
        changed = set_side_back_back_panel_mode(state, mode)
        assert back_panel_mode(changed) is mode
        from phase6_box_body_structure import BoxBodyStructureType
        key = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        assert changed["configs"][key]["back_panel_mode"] == mode.value


def test_receiving_1100_half_contract_uses_certified_fixed_position_and_four_slot_datums():
    contract = _contract("HALF")

    assert contract["mode"] == "HALF"
    assert contract["full_panel_height"] == pytest.approx(1596.0)
    assert contract["material_height"] == pytest.approx(1124.0)
    assert contract["formed_y_offset"] == pytest.approx(236.0)
    assert contract["opening"] is None
    assert tuple(contract["fixed_slot_datums"]) == pytest.approx((
        (120.0, 1004.0),
        (675.0, 1004.0),
        (120.0, 120.0),
        (675.0, 120.0),
    ))

    changed = _contract("HALF", upper=900.0, lower=700.0)
    assert changed["material_height"] == pytest.approx(924.0)


def test_receiving_full_and_back_opening_contracts_use_four_holes_and_fixed_650x200_opening():
    full = _contract("FULL")
    opened = _contract("BACK_OPENING")

    expected_slots = (
        (120.0, 1476.0),
        (675.0, 1476.0),
        (120.0, 120.0),
        (675.0, 120.0),
    )
    assert tuple(full["fixed_slot_datums"]) == pytest.approx(expected_slots)
    assert tuple(opened["fixed_slot_datums"]) == pytest.approx(expected_slots)
    assert full["opening"] is None
    assert tuple(opened["opening"]) == pytest.approx((72.5, 248.0, 722.5, 448.0))


@pytest.mark.parametrize(
    ("mode", "expected_height", "extra_cut_count"),
    (("FULL", 1596.0, 4), ("HALF", 1124.0, 4), ("BACK_OPENING", 1596.0, 5)),
)
def test_back_panel_finalscene_uses_mode_height_four_reference_slots_and_optional_opening(
    mode, expected_height, extra_cut_count
):
    data, back = _render(mode)

    minx, miny, maxx, maxy = map(float, back.render_data.material.bounds)
    assert maxx - minx == pytest.approx(795.0)
    assert maxy - miny == pytest.approx(expected_height)

    cutting = _cutting_closed(back.render_data)
    # primary back-panel boundary + four reference slots (+ fixed rear opening)
    assert len(cutting) == 1 + extra_cut_count

    secondary = cutting[1:]
    if mode == "BACK_OPENING":
        opening = max(secondary, key=lambda row: (_bounds(row)[2] - _bounds(row)[0]))
        assert _bounds(opening) == pytest.approx((72.5, 248.0, 722.5, 448.0))
        secondary.remove(opening)

    assert len(secondary) == 4
    assert all((_bounds(row)[2] - _bounds(row)[0]) == pytest.approx(16.0, abs=0.03) for row in secondary)
    assert all((_bounds(row)[3] - _bounds(row)[1]) == pytest.approx(23.5, abs=0.03) for row in secondary)


def test_half_back_panel_3d_keeps_original_top_edge_instead_of_recentering_shorter_panel():
    from phase6_final_scene_view import _phase6_box_body_structure_meshes

    full_data, _ = _render("FULL")
    half_data, half_back = _render("HALF")
    full_meshes = _phase6_box_body_structure_meshes(full_data, thickness=2.0)
    half_meshes = _phase6_box_body_structure_meshes(half_data, thickness=2.0)

    def y_bounds(meshes, role):
        points = [
            point
            for piece, triangles in meshes
            if piece.role == role
            for triangle in triangles
            for point in triangle
        ]
        return min(p[1] for p in points), max(p[1] for p in points)

    full_back = y_bounds(full_meshes, "back")
    half_back_bounds = y_bounds(half_meshes, "back")
    side_bounds = y_bounds(half_meshes, "left_side")

    assert half_back.formed_y_offset == pytest.approx(236.0)
    assert half_back_bounds[1] == pytest.approx(full_back[1])
    assert half_back_bounds[1] == pytest.approx(side_bounds[1])
    assert half_back_bounds[0] > full_back[0]
