# -*- coding: utf-8 -*-
"""#1495 OPEN-Y-PROJECTION: fixed 1100-upper-inner-door source-golden cases."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.receiving_nfb_y_projection import (
    RULE_ID,
    REVISION,
    approved_nominal_y_mm,
    invert_nfb_inner_door_unfolded_y,
    project_nfb_inner_door_nominal_y,
)


def receiving_snapshot(*, upper=1100.0, t=2.0, gap_h=3.5, left_col=None):
    w = 800.0 if left_col is None else 800.0 + left_col
    state = apply_family_defaults({
        "model": "受電箱", "w": w, "h": 1600.0, "d": 350.0,
        "t": t, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": gap_h,
    })
    columns = [[800.0, [upper, 1600.0-upper]]]
    col = "0:0"
    if left_col is not None:
        columns = [[left_col, [1100.0, 500.0]], *columns]
        col = "1:0"
    # apply_family_defaults installs its own fresh W800 values. Explicitly
    # restore the physical measured width for multi-column 400+800 layouts.
    state.update({
        "w": w,
        "multi_door_enabled": True, "door_layout_scope": "receiving-main",
        "door_layout_columns": columns,
        "inner_doors": [
            {"stable_id": "upper", "cell_key": col,
             "included_frame_sides": ["top", "left", "right"]},
        ],
    })
    return state


@pytest.mark.parametrize(
    "count,slot,nominal,world_y,finished_from_bottom,blank_v,blank_from_top",
    [
        (1, 0, 550.0, 250.0, 546.5, 563.5, 511.5),
        (2, 0, 290.0, 510.0, 806.5, 823.5, 251.5),
        (2, 1, 790.0, 10.0, 306.5, 323.5, 751.5),
    ],
)
def test_approved_nominal_box_top_y_maps_to_real_1075_blank(
    count, slot, nominal, world_y, finished_from_bottom, blank_v, blank_from_top,
):
    state = receiving_snapshot()
    raw_before = deepcopy(state)
    actual = project_nfb_inner_door_nominal_y(
        state, "upper", layer_count=count, slot_index=slot,
    )
    assert state == raw_before  # no change of any prior Hole Editor feature
    assert actual.rule_id == RULE_ID == "OPEN-Y-PROJECTION"
    assert actual.revision == REVISION
    assert actual.status == "GEOMETRY_ONLY_NOT_NFB_CUTTING_CERTIFIED"
    assert actual.part_id == "inner_door:upper:panel"
    assert actual.cell_key == "0:0"
    assert actual.nominal_y_from_box_top_mm == pytest.approx(nominal)
    assert actual.box_world_y_mm == pytest.approx(world_y)
    assert actual.finished_face_y_from_bottom_mm == pytest.approx(finished_from_bottom)
    assert actual.unfolded_uv_y_mm == pytest.approx(blank_v)
    assert actual.unfolded_uv_y_from_top_mm == pytest.approx(blank_from_top)
    assert actual.unfolded_blank_height_mm == pytest.approx(1075.0)
    assert actual.finished_panel_height_mm == pytest.approx(1041.0)
    assert actual.unfolded_uv_y_mm + actual.unfolded_uv_y_from_top_mm == pytest.approx(1075.0)
    reverse = invert_nfb_inner_door_unfolded_y(
        state, "upper", unfolded_uv_y_mm=actual.unfolded_uv_y_mm,
    )
    assert reverse == pytest.approx(nominal)


def test_layout_api_exposes_only_approved_slot_counts():
    assert approved_nominal_y_mm(1) == (550.0,)
    assert approved_nominal_y_mm(2) == (290.0, 790.0)
    for invalid in (0, 3, 4, True, None):
        with pytest.raises(ValueError, match="unsupported NFB layer count"):
            approved_nominal_y_mm(invalid)


def test_multiple_columns_preserve_box_top_nominal_y_and_actual_owner():
    state = receiving_snapshot(left_col=400.0)
    one = project_nfb_inner_door_nominal_y(state, "upper", layer_count=1, slot_index=0)
    assert one.cell_key == "1:0"
    assert one.box_world_y_mm == pytest.approx(250.0)
    assert one.unfolded_uv_y_mm == pytest.approx(563.5)
    assert invert_nfb_inner_door_unfolded_y(
        state, "upper", unfolded_uv_y_mm=one.unfolded_uv_y_mm,
    ) == pytest.approx(550.0)


def test_non_default_thickness_gap_folds_use_actual_part_core_not_fixed_36p5():
    state = receiving_snapshot(t=3.0, gap_h=5.0)
    item = project_nfb_inner_door_nominal_y(
        state, "upper", layer_count=1, slot_index=0,
    )
    assert item.finished_panel_height_mm == pytest.approx(1038.0)
    assert item.unfolded_blank_height_mm == pytest.approx(1070.0)
    # Manufacturing source: top frame formed occupation + T, no bottom
    # frame deduction, two physical 5-mm clearances. T3 -> H1038;
    # unfolded blank = finished - 2*T + 19+19 -> H1070.
    assert item.finished_panel_height_mm == pytest.approx(1100.0 - 52.0 - 10.0)
    assert item.unfolded_blank_height_mm == pytest.approx(
        item.finished_panel_height_mm - 2*state["t"] + 38.0
    )
    assert item.box_world_y_mm == pytest.approx(250.0)
    assert item.unfolded_uv_y_mm == pytest.approx(561.0)
    assert invert_nfb_inner_door_unfolded_y(
        state, "upper", unfolded_uv_y_mm=item.unfolded_uv_y_mm,
    ) == pytest.approx(550.0)


def test_fold_length_change_moves_uv_not_box_world_y():
    state = receiving_snapshot()
    state["door_fold_b"] = 23.0
    state["door_fold_t"] = 17.0
    actual = project_nfb_inner_door_nominal_y(
        state, "upper", layer_count=1, slot_index=0,
    )
    assert actual.box_world_y_mm == pytest.approx(250.0)
    # Same formed 1037 core, moved bottom fold 19 -> 23.
    assert actual.unfolded_uv_y_mm == pytest.approx(567.5)
    assert actual.unfolded_blank_height_mm == pytest.approx(1077.0)
    assert invert_nfb_inner_door_unfolded_y(
        state, "upper", unfolded_uv_y_mm=actual.unfolded_uv_y_mm,
    ) == pytest.approx(550.0)


@pytest.mark.parametrize("upper", [900.0, 1000.0, 1200.0])
def test_non_1100_upper_y_is_unapproved_not_silently_scaled(upper):
    state = receiving_snapshot(upper=upper)
    with pytest.raises(ValueError, match="unapproved cell height"):
        project_nfb_inner_door_nominal_y(
            state, "upper", layer_count=1, slot_index=0,
        )


def test_not_a_box_top_cell_or_no_unique_inner_owner_fails_closed():
    state = receiving_snapshot()
    state["inner_doors"][0]["cell_key"] = "0:1"
    with pytest.raises(ValueError, match="unapproved cell height"):
        project_nfb_inner_door_nominal_y(state, "upper", layer_count=1, slot_index=0)
    state = receiving_snapshot()
    state["inner_doors"][0]["stable_id"] = "other"
    with pytest.raises(ValueError, match="unresolved or duplicate"):
        project_nfb_inner_door_nominal_y(state, "upper", layer_count=1, slot_index=0)
    state = receiving_snapshot()
    state["inner_doors"] *= 2
    with pytest.raises(ValueError, match="unresolved or duplicate"):
        project_nfb_inner_door_nominal_y(state, "upper", layer_count=1, slot_index=0)


def test_rejects_invalid_slot_core_bound_and_unrelated_family():
    state = receiving_snapshot()
    for count, slot in [(1, -1), (1, 1), (2, 2), (2, True)]:
        with pytest.raises(ValueError, match="invalid NFB layer slot"):
            project_nfb_inner_door_nominal_y(
                state, "upper", layer_count=count, slot_index=slot,
            )
    for bad in (-1.0, float("nan"), 0.0, 1075.0, 1e5):
        with pytest.raises(ValueError, match="outside inner-door face core"):
            invert_nfb_inner_door_unfolded_y(state, "upper", unfolded_uv_y_mm=bad)
    state["model"] = "金庫型"
    with pytest.raises(ValueError, match="requires Receiving family"):
        project_nfb_inner_door_nominal_y(state, "upper", layer_count=1, slot_index=0)


def test_y_projection_does_not_modify_baseline_cutting_or_add_fake_nfb_apertures():
    from ae_engine.cabinet_types import policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    state = receiving_snapshot()
    panel = policy.derive_inner_door_panels(state)[0]
    before = build_inner_door_panel_render_data(panel)
    project_nfb_inner_door_nominal_y(state, "upper", layer_count=2, slot_index=0)
    project_nfb_inner_door_nominal_y(state, "upper", layer_count=2, slot_index=1)
    after = build_inner_door_panel_render_data(policy.derive_inner_door_panels(state)[0])
    assert before.scene.primitives == after.scene.primitives
    cuts = [p for p in after.scene.primitives
            if isinstance(p, PolylinePrimitive) and p.closed and p.layer.upper() == "CUTTING"]
    assert len(cuts) == 1
    ys = [point.y for point in cuts[0].points]
    assert max(ys) - min(ys) == pytest.approx(1075.0)
