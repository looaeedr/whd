# -*- coding: utf-8 -*-
"""#2517: a trusted CSV editor X requires the exact original physical opening."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from math import cos, hypot, pi, sin

import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.receiving_nfb_committed_final_scene import (
    _source_world_x_from_committed_editor_feature, _submitted_csv_holes,
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path, model_spec
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
    _current_single_tier_csv_holes,
)
from ae_engine.sheetmetal_feature_core import (
    FeatureAnchor, ProfileFeature, _rotate_local_point,
)
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current


def _saved_editor_source(*, rotation: int = 0, tamper: str | None = None):
    snap = _current()
    holes, _, _ = _current_single_tier_csv_holes(snap, "upper")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    panel = next(
        p for p in derive_inner_door_panels(snap)
        if p.stable_id == proof.part_id
    )
    row = snap["nfb_config"]["holes"][0]
    spec = model_spec("士林", "2P400")
    assert spec is not None and spec.opening_corners_xy_mm is not None
    corners = spec.opening_corners_xy_mm
    if tamper == "sheared_same_edges":
        # Actual parallelogram with exactly the same 57, 96, 57, 96 edges.
        w, h = spec.opening_mm
        dx, dy = h * cos(pi / 3), h * sin(pi / 3)
        points = ((0., 0.), (w, 0.), (w + dx, dy), (dx, dy))
        centre = (sum(x for x, _ in points) / 4,
                  sum(y for _, y in points) / 4)
        local = tuple(Vec2(x - centre[0], y - centre[1])
                      for x, y in points)
    else:
        actual_rotation = 90 if tamper == "wrong_rotation" else rotation
        local = tuple(
            _rotate_local_point(Vec2(x, y), actual_rotation)
            for x, y in corners
        )
    # The real canonical trial is used for the actual panel and physical
    # source centre. No GUI-bbox or guessed world-X basis is substituted.
    opening = proof.patterns[0].opening_uv_mm
    centre_uv_x = sum(x for x, _ in opening) / 4
    centre_uv_y = sum(y for _, y in opening) / 4
    alias = ProfileFeature(
        points=local,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(
            centre_uv_x - panel.fold_left + panel.thickness,
            centre_uv_y - panel.fold_bottom + panel.thickness,
        ),
        layer="CUTTING", source_type="NFB_CSV_SOURCE",
        source_params=(
            ("part_id", panel.stable_id), ("brand", "士林"),
            ("model", "2P400"),
            ("csv_sha256", sha256(brand_csv_path("士林").read_bytes()).hexdigest()),
            ("layer_index", 0), ("slot_index", row["slot_index"]),
        ),
    )
    snap["part_features"] = {panel.stable_id: (alias,)}
    row["rotation_deg"] = rotation
    row["manual_x_state"] = "UNVERIFIED_BASIS"
    row["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    return snap, panel, row, alias, spec


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_original_csv_rectangle_at_committed_rotation_can_recover_real_world_x(rotation):
    snap, panel, row, _, _ = _saved_editor_source(rotation=rotation)
    before = deepcopy(snap)
    world_x = _source_world_x_from_committed_editor_feature(
        snap, panel, row, brand="士林", model="2P400",
    )
    assert world_x == pytest.approx(-150.)
    sourced = _submitted_csv_holes(snap)
    assert sourced[0] == "upper"
    assert sourced[1][0].world_x_mm == pytest.approx(-150.)
    assert sourced[1][0].rotation_deg == rotation
    assert snap == before  # Source inspection cannot mutate the saved Bay.


@pytest.mark.parametrize("tamper", ("sheared_same_edges", "wrong_rotation"))
def test_same_lengths_but_wrong_csv_shape_or_rotation_never_grant_world_x(tamper):
    snap, panel, row, alias, spec = _saved_editor_source(tamper=tamper)
    # The former gate accepted exactly these same edge lengths; this proves
    # that the source shape/rotation check is independently necessary.
    points = tuple(
        (v.x + alias.offset.x, v.y + alias.offset.y) for v in alias.points
    )
    source = spec.opening_corners_xy_mm
    edges = sorted(round(hypot(points[(i+1) % 4][0] - points[i][0],
                               points[(i+1) % 4][1] - points[i][1]), 6)
                   for i in range(4))
    original_edges = sorted(round(hypot(source[(i+1) % 4][0] - source[i][0],
                                        source[(i+1) % 4][1] - source[i][1]), 6)
                            for i in range(4))
    assert edges == original_edges
    before = deepcopy(snap)
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_OPENING_SHAPE_DIFFERS_FROM_SOURCE"):
        _source_world_x_from_committed_editor_feature(
            snap, panel, row, brand="士林", model="2P400",
        )
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_OPENING_SHAPE_DIFFERS_FROM_SOURCE"):
        _submitted_csv_holes(snap)
    # No canonical source-derived base screw CUTTING or fabricated FinalScene.
    with pytest.raises(ValueError, match="NFB_CSV_EDITOR_OPENING_SHAPE_DIFFERS_FROM_SOURCE"):
        apply_committed_csv_v5_to_canonical_parts(snap, (_make(snap),))
    assert snap == before
