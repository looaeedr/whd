# -*- coding: utf-8 -*-
"""#2517: native CSV Hole Editor source must match actual NFB CUTTING geometry.

A same-edge-length skew is not the manufacturer's 57x96 rectangular source.
It must not be promoted to world-X, FinalScene, or an independently reopened
manufacturing DXF. Keep genuine native-editor X translation/quarter-turns.
"""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from math import sqrt

import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
from ae_engine.receiving_nfb_committed_final_scene import (
    _source_world_x_from_committed_editor_feature,
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
    _current_single_tier_csv_holes,
)
from ae_engine.sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current


def _physical_saved_editor():
    snap = _current()
    holes, _, _ = _current_single_tier_csv_holes(snap, "upper")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    panel = next(p for p in derive_inner_door_panels(snap)
                 if p.stable_id == proof.part_id)
    features = []
    for row, pattern in zip(snap["nfb_config"]["holes"], proof.patterns):
        features.append(ProfileFeature(
            points=tuple(
                Vec2(float(x)-panel.fold_left+panel.thickness,
                     float(y)-panel.fold_bottom+panel.thickness)
                for x, y in pattern.opening_uv_mm
            ),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0., 0.), layer="CUTTING",
            source_type="NFB_CSV_SOURCE",
            source_params=(
                ("part_id", panel.stable_id),
                ("brand", pattern.brand), ("model", pattern.model),
                ("csv_sha256",
                 sha256(brand_csv_path(pattern.brand).read_bytes()).hexdigest()),
                ("layer_index", 0),
                ("slot_index", row["slot_index"]),
            ),
        ))
    # Original editor is the placed source, never a fabricated confirmed X.
    for row in snap["nfb_config"]["holes"]:
        row["manual_x_state"] = "UNVERIFIED_BASIS"
        row["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    snap["part_features"] = {panel.stable_id: tuple(features)}
    return snap, panel, tuple(features), proof


def _world_x(snap, panel):
    return _source_world_x_from_committed_editor_feature(
        snap, panel, snap["nfb_config"]["holes"][0],
        brand="士林", model="2P400",
    )


def test_true_placed_editor_opening_reaches_one_finalscene_and_reopened_dxf(tmp_path):
    snap, panel, features, original_proof = _physical_saved_editor()
    assert _world_x(snap, panel) == pytest.approx(-150.0)
    raw = deepcopy(snap)

    door = AssemblyScenePart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., 0., 0.),
    )
    result = apply_committed_csv_v5_to_canonical_parts(
        snap, (door, _make(snap)),
    )
    assert result[0].part_key == panel.stable_id
    assert result[0].render_data.material.symmetric_difference(
        original_proof.render_data.material
    ).area < 1e-6
    assert result[0].render_data.scene.primitives == (
        original_proof.render_data.scene.primitives
    )
    output = tmp_path / "same-canonical-inner-door.dxf"
    save_scene_dxf(output, result[0].render_data.scene)
    assert verify_saved_part_render_data_dxf(
        result[0].render_data, output,
    ).ok
    assert snap == raw


def test_same_four_edge_lengths_but_sheared_source_rejected_before_finalscene(tmp_path):
    snap, panel, features, _proof = _physical_saved_editor()
    first = features[0]
    xs = [float(p.x) for p in first.points]
    ys = [float(p.y) for p in first.points]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    width, height = max(xs)-min(xs), max(ys)-min(ys)
    drift = 30.0
    rise = sqrt(height*height - drift*drift)
    sheared = (
        Vec2(cx-width/2, cy-rise/2),
        Vec2(cx+width/2, cy-rise/2),
        Vec2(cx+width/2+drift, cy+rise/2),
        Vec2(cx-width/2+drift, cy+rise/2),
    )
    from math import hypot
    edge_lengths = lambda pts: sorted(
        round(hypot(pts[(i+1)%4].x-pts[i].x,
                    pts[(i+1)%4].y-pts[i].y), 6)
        for i in range(4)
    )
    assert edge_lengths(sheared) == edge_lengths(first.points)
    bad = replace(first, points=sheared)
    snap["part_features"] = {
        panel.stable_id: (bad,) + features[1:],
    }
    original = deepcopy(snap)
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_OPENING_SHAPE_DIFFERS_FROM_SOURCE"):
        _world_x(snap, panel)
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_OPENING_SHAPE_DIFFERS_FROM_SOURCE"):
        apply_committed_csv_v5_to_canonical_parts(snap, (_make(snap),))
    assert snap == original
    assert not tuple(tmp_path.glob("*.dxf"))


def test_editor_angle_cannot_disagree_with_saved_physical_nfb_rotation():
    snap, panel, features, _proof = _physical_saved_editor()
    first = features[0]
    # Same absolute opening after transforming both storage and rotation:
    # earlier verification accepted this, silently losing operator orientation.
    disguised = replace(
        first,
        points=tuple(Vec2(-p.x, -p.y) for p in first.points),
        rotation_deg=180,
    )
    snap["part_features"] = {panel.stable_id: (disguised,) + features[1:]}
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_ROTATION_DIFFERS_FROM_SOURCE"):
        _world_x(snap, panel)


def test_true_quarter_turn_and_translated_editor_position_remain_supported():
    snap, panel, features, _proof = _physical_saved_editor()
    first = features[0]
    moved = replace(first, offset=Vec2(12., 0.))
    snap["part_features"] = {panel.stable_id: (moved,) + features[1:]}
    assert _world_x(snap, panel) == pytest.approx(-138.)

    cx = sum(p.x for p in first.points) / 4
    cy = sum(p.y for p in first.points) / 4
    physical_turn = tuple(
        Vec2(cx - (p.y-cy), cy + (p.x-cx))
        for p in first.points
    )
    # The editor's transform rotates around the datum origin; undo it in the
    # stored source coordinates so that the actual physical contour is a true
    # rotated CSV rectangle about the original opening centre.
    transformed = replace(
        first,
        points=tuple(Vec2(p.y, -p.x) for p in physical_turn),
        rotation_deg=90,
    )
    snap["nfb_config"]["holes"][0]["rotation_deg"] = 90
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    snap["part_features"] = {panel.stable_id: (transformed,) + features[1:]}
    assert _world_x(snap, panel) == pytest.approx(-150.)
