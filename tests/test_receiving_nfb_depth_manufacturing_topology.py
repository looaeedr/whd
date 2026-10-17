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


def test_alternative_nfb_depth_reaches_finalscene_ear_slots_and_preserves_670_assembled():
    """Regression: original 732 unfolded ear pitch MUST vary with second fold."""
    from ae_engine.manufacturing_api import build_part_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    spec = _spec((105, 75))  # depth step30, second28 instead of 33
    render = build_part_render_data(spec)
    assert render.unfolded_topology.width == 762
    cut = [v for v in render.scene.primitives
           if isinstance(v, PolylinePrimitive) and v.layer == "CUTTING"
           and v.closed]
    assert len(cut) == 5  # actual CENTER silhouette + four ear slots
    ear_slots = cut[1:]
    x_centers = sorted(set(round(
        (min(p.x for p in part.points)+max(p.x for p in part.points))/2, 6)
        for part in ear_slots
    ))
    assert x_centers == [20, 742]
    assert x_centers[1] - x_centers[0] == 722
    # In the real source topology, side returns = 66 with first fold 40:
    # 722 - 2*(66-40) = 670, unchanged assembled hole pitch.
    side_return = render.unfolded_topology.x_segments[0].length
    assert side_return == 66
    assert (x_centers[1]-x_centers[0])-2*(side_return-40) == 670
    assert render.metadata["receiving_nfb_base_mfg2_release_approved"] is False
