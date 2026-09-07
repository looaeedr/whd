from __future__ import annotations

from types import SimpleNamespace

import pytest

# RED: Fold Designer part_dimensions must consume cabinet-family Door FW semantics.
import fold_designer_bridge as bridge


def _receiving_snapshot():
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "part_dimensions": {},
    }


def test_receiving_multi_door_dimension_projection_uses_formed_fw_29_without_adding_2t_again():
    rows = bridge._phase6_door_part_projections(_receiving_snapshot())
    assert [row.part_key for row in rows] == ["door_c1_r1", "door_c1_r2"]
    assert [(row.formed_width, row.formed_height) for row in rows] == pytest.approx([
        (735.0, 1064.0),
        (735.0, 435.0),
    ])


def test_receiving_recalculate_part_dimensions_publishes_correct_upper_and_lower_door_sizes():
    snapshot = _receiving_snapshot()
    holder = SimpleNamespace(
        _settings_values={
            "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
            "door_gap_w": 3.5, "door_gap_h": 3.5,
            "base_plate_shrink_left": 55.0, "base_plate_shrink_right": 55.0,
            "base_plate_shrink_top": 55.0, "base_plate_shrink_bottom": 55.0,
        },
        _phase6_input_snapshot=snapshot,
    )

    dims = bridge._phase6_recalculate_part_dimensions(holder)

    assert dims["door_c1_r1"] == pytest.approx({"width": 735.0, "height": 1064.0})
    assert dims["door_c1_r2"] == pytest.approx({"width": 735.0, "height": 435.0})


def test_vault_single_door_projection_keeps_material_fw_25_plus_2t_semantics():
    snapshot = {
        "model": "金庫型",
        "w": 400.0,
        "h": 600.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": False,
        "part_dimensions": {},
    }
    holder = SimpleNamespace(_settings_values=dict(snapshot), _phase6_input_snapshot=snapshot)

    dims = bridge._phase6_recalculate_part_dimensions(holder)

    assert dims["door"] == pytest.approx({"width": 335.0, "height": 535.0})
