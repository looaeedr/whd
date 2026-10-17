# -*- coding: utf-8 -*-
"""#1502: an NFB depth pair must reach real BasePlatePartSpec manufacturing."""
import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_scene_orchestration import _unfolded_topology_for_spec
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER


def _spec(pair):
    return BasePlatePartSpec(
        width=800, height=320, thickness=2,
        shrink_top=55, shrink_bottom=55,
        shrink_left=85, shrink_right=85,
        bend=20, model_name="受電箱",
        receiving_bend_pattern=RECEIVING_BASE_PATTERN_CENTER,
        physical_id="base_plate",
        receiving_nfb_depth_pair_mm=pair,
    )


@pytest.mark.parametrize("pair, expected_side, expected_total", [
    ((107, 72), 71, 772),
    ((103, 68), 71, 772),
    ((105, 75), 66, 762),
])
def test_final_manufacturing_unfolded_topology_tracks_nfb_depth(pair, expected_side, expected_total):
    layout = _unfolded_topology_for_spec(_spec(pair))
    assert layout is not None
    assert layout.width == expected_total
    assert [x.length for x in layout.x_segments] == [
        expected_side, 630, expected_side,
    ]
    assert [y.length for y in layout.y_segments] == [20, 170, 20]


def test_unselected_legacy_preview_retains_original_width_but_not_nfb_proof():
    layout = _unfolded_topology_for_spec(_spec(None))
    assert layout.width == 772


@pytest.mark.parametrize("pair", [(107, 107), (107, 106), (72, 107)])
def test_invalid_depth_pair_is_rejected_through_actual_part_spec(pair):
    with pytest.raises(ValueError):
        _unfolded_topology_for_spec(_spec(pair))
