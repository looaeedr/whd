# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.contracts import (
    BoxBodyPartSpec,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from ae_engine.manufacturing_api import build_box_body_structure_render_data
from ae_engine.receiving_joint_marking import (
    _owner_render_data,
    _replace_owner_render_data,
)
from ae_engine.receiving_layout import (
    RECEIVING_RUNTIME_SELECTION_KEY,
    new_receiving_layout,
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
    update_receiving_bay,
)
import ae_engine.receiving_pairing_marking as pairing
from ae_engine.receiving_pairing_marking import (
    PAIRING_SYMBOL_INSET,
    RECEIVING_PAIRING_MARK_CONFLICT,
    RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS,
    pairing_symbol_size,
    resolve_receiving_pairing_marking,
)
from ae_engine.assembly_marking_geometry import backproject_mapped_skin_world_points
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
from phase6_manufacturing_geometry import (
    _phase6_assembly_placement_for_part,
    _phase6_build_joint_world_geometry,
)
import phase6_project_file


def _layout(*, bay_count=1, selected_mode="FULL", selected_bay=0, depth=350.0, height=1600.0):
    layout = new_receiving_layout(
        width=800.0, height=height, depth=depth, back_panel_mode="FULL"
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=bay_count)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=selected_bay,
        back_panel_mode=selected_mode, depth=depth, height=height,
    )
    return layout


def _projected_snapshot(layout, *, bay_index=0):
    snapshot = {
        "model": "受電箱",
        "t": 2.0,
        "fw": 29.0,
        "zl1": 24.0,
        "zl2": 24.0,
        "zr1": 17.0,
        "zr2": 18.0,
        "z_comp": 0.0,
        "box_body_structure": receiving.resolve_box_body_structure_state(None),
        "receiving_layout": layout,
    }
    return project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=bay_index, validate_common=False
    )


def _base_geometry(snapshot):
    box_profile = build_box_body_profile(snapshot)
    structure_state = receiving.resolve_box_body_structure_state(
        snapshot.get("box_body_structure")
    )
    render = build_box_body_structure_render_data(
        BoxBodyPartSpec(
            width=float(snapshot["w"]),
            height=float(snapshot["h"]),
            depth=float(snapshot["d"]),
            thickness=float(snapshot["t"]),
            frame_width=float(snapshot["fw"]),
            model_name="受電箱",
            zl1=float(snapshot["zl1"]),
            zl2=float(snapshot["zl2"]),
            zr1=float(snapshot["zr1"]),
            zr2=float(snapshot["zr2"]),
            z_comp=float(snapshot.get("z_comp", 0.0)),
            fold_profile=profile_to_fold_segments(box_profile),
            structure_state=structure_state,
        )
    )
    placement, offset = _phase6_assembly_placement_for_part(snapshot, "box_body")
    part = ResolvedManufacturingPart(
        part_key="box_body",
        render_data=render,
        placement=placement,
        offset=tuple(offset),
    )
    geometry = ResolvedManufacturingGeometry(parts=(part,))
    world = _phase6_build_joint_world_geometry(
        (part,),
        (float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
        float(snapshot["t"]),
    )
    return geometry, world


def _resolve(*, bay_count=1, mode="FULL", bay_index=0, depth=350.0, height=1600.0, symbol_inset=PAIRING_SYMBOL_INSET):
    layout = _layout(
        bay_count=bay_count, selected_mode=mode, selected_bay=bay_index,
        depth=depth, height=height,
    )
    snapshot = _projected_snapshot(layout, bay_index=bay_index)
    geometry, world = _base_geometry(snapshot)
    result = resolve_receiving_pairing_marking(
        snapshot, geometry, world_geometry=world, symbol_inset=symbol_inset
    )
    return snapshot, geometry, world, result


def _piece(geometry, role):
    body = geometry.part("box_body").render_data
    return next(
        piece.render_data
        for piece in tuple(body.pieces or ())
        if str(piece.role) == str(role)
    )


def _pairing_rows(render_data):
    return tuple(dict(render_data.metadata or {}).get("receiving_pairing_markings") or ())


def _pairing_primitives(render_data):
    rows = _pairing_rows(render_data)
    signatures = {tuple(row["primitive_signature"]) for row in rows}
    return tuple(
        primitive
        for primitive in tuple(render_data.scene.primitives or ())
        if pairing._primitive_signature(primitive) in signatures
    )


def _role_map(render_data):
    rows = _pairing_rows(render_data)
    by_sig = {tuple(row["primitive_signature"]): str(row["role"]) for row in rows}
    return {
        by_sig[pairing._primitive_signature(primitive)]: primitive
        for primitive in _pairing_primitives(render_data)
    }


def test_t004_single_bay_left_side_has_x_and_no_pairing_mark_on_right_or_back():
    _snapshot, _base, _world, result = _resolve(bay_count=1, mode="FULL")
    assert result.result.status == "EMITTED"
    assert result.result.right_locked is False

    left = _piece(result.geometry, "left_side")
    roles = set(_role_map(left))
    assert roles == {"frame_full", "right_unlock_x_a", "right_unlock_x_b"}
    assert all(str(p.layer).upper() == "MARKING" for p in _pairing_primitives(left))
    assert _pairing_rows(_piece(result.geometry, "right_side")) == ()
    assert _pairing_rows(_piece(result.geometry, "back")) == ()


@pytest.mark.parametrize(
    ("mode", "expected_roles"),
    [
        ("FULL", {"frame_full", "right_lock_circle"}),
        ("HALF", {"frame_top", "right_lock_circle"}),
        ("BACK_OPENING", {"frame_full", "right_lock_circle", "back_opening_glyph"}),
    ],
)
def test_t013_variants_circle_layer_and_cabinet_top_bottom_binding(mode, expected_roles):
    _snapshot, _base, world, result = _resolve(bay_count=2, mode=mode, bay_index=0)
    assert result.result.status == "EMITTED"
    assert result.result.right_locked is True

    left = _piece(result.geometry, "left_side")
    role_map = _role_map(left)
    assert set(role_map) == expected_roles
    assert all(str(p.layer).upper() == "MARKING" for p in role_map.values())

    rows = {str(row["role"]): row for row in _pairing_rows(left)}
    bounds = tuple(result.result.evidence["formed_face_bounds"])
    _min_z, min_y, _max_z, max_y = map(float, bounds)
    center_y = (min_y + max_y) / 2.0
    circle_row = rows["right_lock_circle"]
    assert float(circle_row["world_center"][1]) > center_y

    if mode == "BACK_OPENING":
        opening = rows["back_opening_glyph"]
        avg_y = sum(float(p[1]) for p in opening["world_points"]) / 4.0
        assert avg_y < center_y

    # R-026: the stored flat primitive must be exactly the result of the
    # authoritative mapped-skin world->flat projection; no second mirror/rotate.
    frame_role = "frame_top" if mode == "HALF" else "frame_full"
    frame_row = rows[frame_role]
    direct = backproject_mapped_skin_world_points(
        world["mapped_skin_triangles_by_part"]["box_body:left_side"],
        frame_row["world_points"],
    )
    assert direct.status == "RESOLVED"
    frame = role_map[frame_role]
    assert isinstance(frame, PolylinePrimitive)
    actual_flat = tuple((float(p.x), float(p.y)) for p in frame.points)
    assert len(actual_flat) == len(direct.flat_points)
    for actual, expected in zip(actual_flat, direct.flat_points):
        assert actual[0] == pytest.approx(expected[0])
        assert actual[1] == pytest.approx(expected[1])

    assert _pairing_rows(_piece(result.geometry, "right_side")) == ()
    assert _pairing_rows(_piece(result.geometry, "back")) == ()


def test_t013_last_bay_uses_x_even_in_multi_bay_set():
    _snapshot, _base, _world, result = _resolve(bay_count=2, mode="FULL", bay_index=1)
    assert result.result.status == "EMITTED"
    assert result.result.right_locked is False
    assert set(_role_map(_piece(result.geometry, "left_side"))) == {
        "frame_full", "right_unlock_x_a", "right_unlock_x_b"
    }


def test_t014_symbol_formula_is_centered_and_open02_is_locked_to_5mm():
    _snapshot, _base, _world, result = _resolve(bay_count=2, mode="FULL", bay_index=0)
    assert PAIRING_SYMBOL_INSET == pytest.approx(5.0)
    size = pairing_symbol_size(inset=PAIRING_SYMBOL_INSET)
    assert size == pytest.approx(50.0 - 2.0 * PAIRING_SYMBOL_INSET)
    assert result.result.evidence["symbol_size"] == pytest.approx(40.0)

    left = _piece(result.geometry, "left_side")
    metadata = dict(left.metadata or {})
    assert "receiving_pairing_mark_provisional" not in metadata
    assert metadata["receiving_pairing_mark_authority"] == {
        "PAIRING_SYMBOL_INSET": pytest.approx(5.0),
        "status": "OWNER_CONFIRMED",
        "issue": 1116,
    }
    rows = {str(row["role"]): row for row in _pairing_rows(left)}
    circle = _role_map(left)["right_lock_circle"]
    assert isinstance(circle, CirclePrimitive)
    assert float(rows["right_lock_circle"]["world_radius"]) == pytest.approx(size / 2.0)

    frame = rows["frame_full"]["world_points"]
    top_center_y = (max(float(p[1]) for p in frame) + min(float(p[1]) for p in frame)) / 2.0 + 25.0
    assert float(rows["right_lock_circle"]["world_center"][1]) == pytest.approx(top_center_y)
    assert float(rows["right_lock_circle"]["world_center"][2]) == pytest.approx(
        sum(float(p[2]) for p in frame) / 4.0
    )


def test_t014_invalid_inset_and_undersized_formed_face_fail_closed_without_clipping():
    _snapshot, _base, _world, inset_result = _resolve(
        bay_count=1, mode="FULL", symbol_inset=0.0
    )
    assert inset_result.result.status == "BLOCKED"
    assert inset_result.result.diagnostic_code == RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS
    assert _pairing_rows(_piece(inset_result.geometry, "left_side")) == ()

    _snapshot, _base, _world, small_result = _resolve(
        bay_count=1, mode="FULL", depth=40.0, height=1600.0
    )
    assert small_result.result.status == "BLOCKED"
    assert small_result.result.diagnostic_code == RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS
    assert _pairing_rows(_piece(small_result.geometry, "left_side")) == ()


def test_t014_back_opening_30x20_is_fixed_and_oversize_injection_fails_closed(monkeypatch):
    _snapshot, _base, _world, result = _resolve(bay_count=1, mode="BACK_OPENING")
    assert result.result.status == "EMITTED"
    row = next(
        row for row in _pairing_rows(_piece(result.geometry, "left_side"))
        if row["role"] == "back_opening_glyph"
    )
    points = tuple(row["world_points"])
    d_span = max(float(p[2]) for p in points) - min(float(p[2]) for p in points)
    h_span = max(float(p[1]) for p in points) - min(float(p[1]) for p in points)
    assert d_span == pytest.approx(30.0)
    assert h_span == pytest.approx(20.0)

    monkeypatch.setattr(pairing, "BACK_OPENING_GLYPH_WIDTH", 60.0)
    _snapshot, _base, _world, blocked = _resolve(bay_count=1, mode="BACK_OPENING")
    assert blocked.result.status == "BLOCKED"
    assert blocked.result.diagnostic_code == RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS
    assert _pairing_rows(_piece(blocked.geometry, "left_side")) == ()


def _inject_left_primitive(geometry, primitive):
    left = _owner_render_data(geometry, "box_body:left_side")
    scene = DrawingScene()
    scene.extend(tuple(left.scene.primitives or ()))
    scene.add(primitive)
    return _replace_owner_render_data(
        geometry, "box_body:left_side", replace(left, scene=scene)
    )


@pytest.mark.parametrize("kind", ["CUTTING", "BLIND_HOLE", "MARKING"])
def test_pairing_mark_zero_clearance_tangent_or_endpoint_contact_conflicts(kind):
    snapshot, base, world, success = _resolve(bay_count=2, mode="FULL", bay_index=0)
    circle = _role_map(_piece(success.geometry, "left_side"))["right_lock_circle"]
    assert isinstance(circle, CirclePrimitive)

    if kind in {"CUTTING", "BLIND_HOLE"}:
        radius = 4.0
        existing = CirclePrimitive(
            center=Vec2(
                float(circle.center.x) + float(circle.radius) + radius,
                float(circle.center.y),
            ),
            radius=radius,
            layer=kind,
            source_type="test_existing",
            source_id=f"{kind.lower()}-tangent",
        )
    else:
        touch_x = float(circle.center.x) + float(circle.radius)
        existing = LinePrimitive(
            Vec2(touch_x, float(circle.center.y)),
            Vec2(touch_x + 10.0, float(circle.center.y)),
            "MARKING",
            211,
        )

    geometry = _inject_left_primitive(base, existing)
    blocked = resolve_receiving_pairing_marking(
        snapshot, geometry, world_geometry=world
    )
    assert blocked.result.status == "BLOCKED"
    assert blocked.result.diagnostic_code == RECEIVING_PAIRING_MARK_CONFLICT
    assert blocked.result.evidence["conflicting_feature_ids"]
    assert _pairing_rows(_piece(blocked.geometry, "left_side")) == ()


def test_runtime_bay_selection_is_transient_and_never_persisted_as_project_authority():
    layout = _layout(bay_count=2, selected_mode="HALF", selected_bay=1)
    projected = _projected_snapshot(layout, bay_index=1)
    assert projected[RECEIVING_RUNTIME_SELECTION_KEY]["bay_index"] == 1
    materialized = phase6_project_file._materialize_project_snapshot(projected)
    assert RECEIVING_RUNTIME_SELECTION_KEY not in materialized
    assert materialized["receiving_layout"] == projected["receiving_layout"]
