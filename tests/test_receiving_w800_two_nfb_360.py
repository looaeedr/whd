# -*- coding: utf-8 -*-
"""Current owner-corrected W800 two-NFB centre pitch, with historical evidence retained.

This is a source-backed *editable* opening placement. It does not certify the
absolute origin or permit screw CUTTING / whole-cabinet manufacturing.
"""
import json
from pathlib import Path

import pytest

from ae_engine.cabinet_types import policy
from ae_engine.receiving_nfb_committed_final_scene import (
    _source_world_x_from_committed_editor_feature,
)
from ae_engine.receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_x_projection import nominal_nfb_x_group
from phase6_receiving_modes import fresh_receiving_mode


def _w800_editor_two():
    source = fresh_receiving_mode("quantity", {"w": 800, "h": 1600, "d": 350})
    model = numeric_model_ref("士林", "2P400")
    selected = {
        "layers": 1,
        "layer_heights_mm": [330, 830],
        "models": [[model, model], ""],
    }
    panel = next(p for p in policy.derive_inner_door_panels(source)
                 if str(p.cell_key).endswith(":0"))
    return source, panel, selected


def _center_x(feature):
    xs = tuple(float(p.x) + float(feature.offset.x) for p in feature.points)
    return (min(xs) + max(xs)) / 2.0


def test_w800_two_switch_nominal_is_360_and_old_dxf_325_is_only_observation():
    assert nominal_nfb_x_group(800, 2).adjacent_distances_mm == (360.0,)
    evidence = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/receiving-nfb-x-evidence.json")
        .read_text(encoding="utf-8")
    )
    record = next(r for r in evidence["records"]
                  if (r["box_outer_width_mm"], r["nfb_count"]) == (800, 2))
    assert record["nominal_adjacent_center_distances_mm"] == [360]
    assert record["nominal_source"]["current_override"].startswith("USER_CONFIRMED_")
    assert record["source_layout_observation"]["observed_center_pitch_mm"] == 325
    assert record["x_status"] == "PREVIEW_ONLY"
    assert record["certified_x_revision"] is None


def test_real_w800_original_editor_initial_centers_are_360_apart():
    snapshot, panel, selected = _w800_editor_two()
    features = editor_nfb_features_from_csv(snapshot, selected)
    assert len(features) == 2
    assert [dict(f.source_params)["slot_index"] for f in features] == [0, 1]
    assert all(dict(f.source_params)["placement"] == "native_editor_initial"
               for f in features)
    centres = [_center_x(f) for f in features]
    assert centres[1] - centres[0] == pytest.approx(360.0)
    assert sum(centres) == pytest.approx(float(panel.width))
    assert all(f.source_type == "NFB_CSV_SOURCE" and f.layer == "CUTTING"
               for f in features)


def test_committed_editor_centers_project_360_without_moving_base_or_guessing_x():
    snapshot, panel, selected = _w800_editor_two()
    features = editor_nfb_features_from_csv(snapshot, selected)
    # The existing original-editor feature is the physical placement source,
    # not the nominal table's unverified origin.
    committed = dict(snapshot)
    committed["part_features"] = {panel.stable_id: list(features)}
    world_x = [
        _source_world_x_from_committed_editor_feature(
            committed, panel,
            {
                "physical_hole_id": f"{panel.stable_id}:nfb:layer:0:slot:{index}",
                "layer_count": 1,
                "layer_index": 0,
                "slot_index": index,
            },
            brand="士林", model="2P400",
        )
        for index in range(2)
    ]
    assert world_x[0] is not None and world_x[1] is not None
    assert world_x[1] - world_x[0] == pytest.approx(360.0)
