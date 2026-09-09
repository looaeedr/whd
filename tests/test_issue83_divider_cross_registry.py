# -*- coding: utf-8 -*-
import pytest

from ae_engine.certified_relief_registry import (
    evaluate_divider_cross_formula_record,
    lookup_certified_divider_cross_relief,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    placed_corner_cut_polygons,
    resolve_corner_relief,
)


def _receiving_reference_variables():
    return {
        "T": 2.0,
        "core_start": 41.0,
        "divider_first_outside": 18.0,
        "divider_fw_outside": 29.0,
        "divider_fw_material": 25.0,
        "divider_last_outside": 17.0,
        "box_zl1_formed": 24.0,
    }


def test_cross_slot_parameters_keep_fold_u_fold_v_as_primary_basis():
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.STANDARD,
        slot_width=7.0,
        slot_straight_depth=24.0,
        slot_radius=3.5,
    )
    relief = resolve_corner_relief(
        selection,
        fold_u=66.0,
        fold_v=27.0,
        thickness=2.0,
        fw=25.0,
    )
    assert relief.primary_u == pytest.approx(66.0)
    assert relief.primary_v == pytest.approx(27.0)
    assert relief.slot_width == pytest.approx(7.0)
    assert relief.slot_straight_depth == pytest.approx(24.0)
    assert relief.slot_radius == pytest.approx(3.5)


def test_cross_slot_geometry_matches_normalized_divider_dxf_local_shape():
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.STANDARD,
        slot_width=7.0,
        slot_straight_depth=24.0,
        slot_radius=3.5,
    )
    relief = resolve_corner_relief(
        selection, fold_u=66.0, fold_v=27.0, thickness=2.0, fw=25.0,
    )
    cut = placed_corner_cut_polygons(
        corner_name="bottom_left", relief=relief, width=158.0, height=596.0,
    )
    merged = cut[0]
    for item in cut[1:]:
        merged = merged.union(item)
    minx, miny, maxx, maxy = merged.bounds
    assert (minx, miny) == pytest.approx((0.0, 0.0))
    assert maxx == pytest.approx(66.0)
    # primary 27 + straight 24 + R3.5 rounded cap
    assert maxy == pytest.approx(54.5)


def test_receiving_divider_registry_formula_derives_dxf_values_from_parameters():
    record = {
        "formula": {
            "min_y_fold_u": "core_start + divider_fw_material",
            "max_y_fold_u": "core_start + divider_last_outside + T",
            "fold_v": "divider_fw_outside - T",
            "slot_width": "divider_fw_material - divider_first_outside",
            "slot_straight_depth": "box_zl1_formed",
            "slot_radius": "(divider_fw_material - divider_first_outside) / 2",
        }
    }
    values = evaluate_divider_cross_formula_record(record, _receiving_reference_variables())
    assert values == pytest.approx({
        "min_y_fold_u": 66.0,
        "max_y_fold_u": 60.0,
        "fold_v": 27.0,
        "slot_width": 7.0,
        "slot_straight_depth": 24.0,
        "slot_radius": 3.5,
    })


def test_receiving_divider_registry_hit_is_cross_plus_parameters():
    result = lookup_certified_divider_cross_relief(
        cabinet_family="受電箱",
        variables=_receiving_reference_variables(),
    )
    assert result is not None
    assert result.rule.rule_id == "RECEIVING_DIVIDER_CROSS_STANDARD_V1"
    assert result.rule.corner_type == "CROSS"
    assert result.min_y.primary_u == pytest.approx(66.0)
    assert result.min_y.primary_v == pytest.approx(27.0)
    assert result.min_y.slot_width == pytest.approx(7.0)
    assert result.min_y.slot_straight_depth == pytest.approx(24.0)
    assert result.min_y.slot_radius == pytest.approx(3.5)
    assert result.max_y.primary_u == pytest.approx(60.0)
    assert result.max_y.primary_v == pytest.approx(27.0)
    assert result.max_y.slot_width is None
