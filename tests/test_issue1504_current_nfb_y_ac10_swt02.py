# -*- coding: utf-8 -*-
"""#1504 direct AC-10/SWT-02 nominal-vs-explicit NFB Y acceptance.

Original 2026-10-10 legacy 1100-cell defaults are retained ONLY when no
current operator height is supplied. Current operator 330/830 heights project
through the real inner-door part/placement/unfolding, not a second formula.
"""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_ui1a import (
    PREVIEW_ONLY, new_nfb_ui1a_draft, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_x_projection import nominal_nfb_x_group
from ae_engine.receiving_nfb_y_projection import (
    REVISION, OPERATOR_HEIGHT_REVISION, approved_nominal_y_mm,
    project_nfb_inner_door_nominal_y, invert_nfb_inner_door_unfolded_y,
)
from tests.test_issue1495_receiving_nfb_y_projection import receiving_snapshot

LEGACY = "400_140X257_107.dxf"


def _draft(count):
    return new_nfb_ui1a_draft(
        set_brand="士林", layer_count=count,
        model_layers=([LEGACY, LEGACY], [LEGACY] if count == 2 else ""),
    )


def test_swt_ac02_legacy_nominal_and_unknown_non1100_y_never_guess():
    """Old saved projects remain reversible, never manufacturing-ready."""
    approved = {1: (550.0,), 2: (290.0, 790.0)}
    for count, expected in approved.items():
        draft = _draft(count)
        snapshot = receiving_snapshot()
        before = deepcopy(snapshot)
        preview = nfb_ui1a_preview(
            draft, bay_width_mm=800, upper_cell_height_mm=1100,
        )
        assert approved_nominal_y_mm(count) == expected
        assert tuple(row["nominal_y_from_top_mm"] for row in preview["layers"]) == expected
        assert preview["status"] == PREVIEW_ONLY
        assert preview["can_manufacture"] is False
        assert preview["has_absolute_x"] is False
        for i, nominal in enumerate(expected):
            actual = project_nfb_inner_door_nominal_y(
                snapshot, "upper", layer_count=count, slot_index=i,
            )
            assert actual.revision == REVISION
            assert actual.nominal_y_from_box_top_mm == nominal
            assert actual.status == "GEOMETRY_ONLY_NOT_NFB_CUTTING_CERTIFIED"
            assert invert_nfb_inner_door_unfolded_y(
                snapshot, "upper", unfolded_uv_y_mm=actual.unfolded_uv_y_mm,
            ) == pytest.approx(nominal)
        assert snapshot == before

        for upper in (900., 1000., 1200.):
            unknown = nfb_ui1a_preview(
                draft, bay_width_mm=800, upper_cell_height_mm=upper,
            )
            assert all(r["nominal_y_from_top_mm"] is None
                       for r in unknown["layers"])
            assert not unknown["is_1100_y_known"]
            assert unknown["can_manufacture"] is False
            with pytest.raises(ValueError, match="unapproved cell height"):
                project_nfb_inner_door_nominal_y(
                    receiving_snapshot(upper=upper), "upper",
                    layer_count=count, slot_index=0,
                )


@pytest.mark.parametrize(
    "count,slot,source_y,world_y,unfolded_uv",
    [(1,0,330.,470.,783.5), (2,0,330.,470.,783.5),
     (2,1,830.,-30.,283.5)],
)
def test_nfb_ac10_current_330_830_operator_y_roundtrips_real_panel(
    count, slot, source_y, world_y, unfolded_uv,
):
    """The actual operator datum beats legacy 550/290/790 nominal defaults."""
    state = receiving_snapshot()
    state["receiving_inner_door_layer_heights_mm"] = [330., 830.]
    before = deepcopy(state)
    draft = _draft(count)
    preview = nfb_ui1a_preview(
        draft, bay_width_mm=800, upper_cell_height_mm=1100,
        layer_heights_mm=state["receiving_inner_door_layer_heights_mm"],
    )
    assert tuple(r["nominal_y_from_top_mm"] for r in preview["layers"]) == (
        (330., 830.) if count == 2 else (330.,)
    )
    assert preview["can_manufacture"] is False
    actual = project_nfb_inner_door_nominal_y(
        state, "upper", layer_count=count, slot_index=slot,
    )
    assert actual.revision == OPERATOR_HEIGHT_REVISION
    assert actual.part_id == "inner_door:upper:panel"
    assert actual.nominal_y_from_box_top_mm == source_y
    assert actual.box_world_y_mm == pytest.approx(world_y)
    assert actual.unfolded_uv_y_mm == pytest.approx(unfolded_uv)
    assert actual.unfolded_blank_height_mm == pytest.approx(1075.)
    assert actual.unfolded_uv_y_from_top_mm + actual.unfolded_uv_y_mm == pytest.approx(1075.)
    assert invert_nfb_inner_door_unfolded_y(
        state, "upper", unfolded_uv_y_mm=actual.unfolded_uv_y_mm,
    ) == pytest.approx(source_y)
    assert state == before


@pytest.mark.parametrize(
    "width,count,pitch",
    [(600,1,None), (750,1,None), (800,1,None),
     (600,2,(180.,)), (750,2,(310.,)),
     (800,2,(360.,)), (800,3,(180.,180.))],
)
def test_nfb_ac10_only_approved_nominal_pitch_and_no_world_x(width,count,pitch):
    group = nominal_nfb_x_group(width,count)
    assert group.adjacent_distances_mm == pitch
    assert group.absolute_centers_mm is None
    assert group.certified_x_revision is None
    assert group.manufacturing_ready is False
    draft = new_nfb_ui1a_draft(
        set_brand="士林", model_layers=([LEGACY]*count, ""),
    )
    preview = nfb_ui1a_preview(
        draft, bay_width_mm=width, upper_cell_height_mm=1100,
    )
    assert preview["layers"][0]["adjacent_x_mm"] == pitch
    assert preview["layers"][0]["absolute_x_mm"] is None
    assert all(u["absolute_x_mm"] is None for u in preview["layers"][0]["slots"])
    assert preview["can_manufacture"] is False


def test_nfb_ac10_outside_source_matrix_remains_unknown_not_centered():
    for width,count in ((825,2),(800,4),(750,3),(600,3)):
        with pytest.raises(ValueError, match="unsupported combination"):
            nominal_nfb_x_group(width,count)
        draft = new_nfb_ui1a_draft(
            set_brand="士林", model_layers=([LEGACY]*count, ""),
        )
        preview = nfb_ui1a_preview(
            draft, bay_width_mm=width, upper_cell_height_mm=1100,
        )
        assert preview["layers"][0]["adjacent_x_mm"] is None
        assert preview["layers"][0]["absolute_x_mm"] is None
        assert preview["can_manufacture"] is False
