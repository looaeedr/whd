"""#2517: Receiving fixing-plate original DXF flat source is Engine-owned."""
from dataclasses import replace
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_base_fixing_plate_geometry import (
    LARGE_PATTERN, SOURCE_DXF_SHA256, _outline, _slot,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _ticket():
    tickets = receiving_base_fixing_plate_previews(
        _two_tier(), available_parts=("base_plate",)
    )
    assert len(tickets) == 4
    return tickets[0]


def test_real_t2_original_contour_slots_and_bend_in_single_engine_projection():
    plane = api.project_receiving_fixing_plate_source_2d(_ticket())
    assert plane.thickness_mm == 2
    assert (plane.width_mm, plane.height_mm) == (256, 105)
    assert plane.outline_xy_mm == _outline(LARGE_PATTERN)
    assert plane.outline_xy_mm == ((0., 0.), (256., 0.), (256., 105.), (0., 105.))
    assert plane.slots_xy_mm == tuple(
        _slot(cx, cy, 25, 11) for cx, cy in LARGE_PATTERN.slot_centers
    )
    assert len(plane.slots_xy_mm) == 4
    assert plane.bend_line_xy_mm == ((0., 23.), (256., 23.))
    assert plane.selected_pitch_mm == 140
    assert plane.source_dxf_sha256 == SOURCE_DXF_SHA256
    assert plane.manufacturing_ready is False


def test_source_pair_210_or_unconfigured_does_not_claim_manufacturing():
    ticket = _ticket()
    outer = api.project_receiving_fixing_plate_source_2d(
        replace(ticket, applicable_slot_pair_indexes=(0, 3))
    )
    none = api.project_receiving_fixing_plate_source_2d(
        replace(ticket, applicable_slot_pair_indexes=None)
    )
    assert outer.selected_pitch_mm == 210
    assert none.selected_pitch_mm is None
    assert not outer.manufacturing_ready and not none.manufacturing_ready


@pytest.mark.parametrize("change", (
    {"stock_thickness_mm": 3},
    {"source_top_corner_radius_mm": 5},
    {"nominal_source_slot_centers_mm": ((23., 84.),)},
    {"nominal_fold_from_weld_edge_mm": 24},
    {"applicable_slot_pair_indexes": (0, 2)},
))
def test_changed_source_and_invalid_hole_pair_fail_closed(change):
    with pytest.raises(ValueError, match="FIXING_PLATE_PREVIEW_"):
        api.project_receiving_fixing_plate_source_2d(replace(_ticket(), **change))


def test_tk_adapter_only_presents_engine_contours_not_own_math_or_false_t3():
    source = (Path(__file__).resolve().parents[1] /
              "phase6_navigation_view_adapter.py").read_text(encoding="utf-8")
    span = source.split("def show_receiving_base_fixing_plate_preview(", 1)[1].split(
        "\ndef refresh_part_selector(", 1
    )[0]
    assert "manufacturing_api.project_receiving_fixing_plate_source_2d(preview)" in span
    assert all(s in span for s in (
        "plane.outline_xy_mm", "plane.slots_xy_mm", "plane.bend_line_xy_mm"))
    assert "math.cos" not in span and "math.sin" not in span
    assert "range(0, 91" not in span
    assert "板厚 T3" not in span and "尚無正式折線" not in span
