# -*- coding: utf-8 -*-
"""#1494: original customer W800x3 X evidence vs true inner-door manufacturing.

All candidate world X values are SHADOW, not approved machining positions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.receiving_nfb_x_projection import (
    RULE_REVISION,
    PREVIEW_ONLY,
    SHADOW_ONLY,
    nominal_nfb_x_group,
    reverse_shadow_w800_three_source_x,
    shadow_w800_three_source_x,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def originals():
    return (
        fixture("tests/fixtures/receiving_nfb_w800_three_source.json"),
        fixture("tests/fixtures/receiving_nfb_closed_cutting_reference.json"),
    )


def snapshot(*, left_neighbor=None, t=2.0, upper=1100.0):
    total_w = 800.0+(left_neighbor or 0.0)
    state = apply_family_defaults({
        "model": "受電箱", "w": total_w, "h": 1600.0, "d": 350.0,
        "t": t, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    if left_neighbor is None:
        columns = [[800.0, [upper, 1600.0-upper]]]
        cell_key = "0:0"
    else:
        columns = [[left_neighbor, [1100.0, 500.0]],
                   [800.0, [upper, 1600.0-upper]]]
        cell_key = "1:0"
    state.update({
        # apply_family_defaults supplies the W800 fresh-family nominal width.
        # Multi-column tests must restore the actual assembled cabinet W.
        "w": total_w,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": columns,
        "inner_doors": [{"stable_id": "upper", "cell_key": cell_key,
                         "included_frame_sides": ["top", "left", "right"]}],
    })
    return state


@pytest.mark.parametrize("w,count,pitch", [
    (600, 1, None), (750, 1, None), (800, 1, None),
    (600, 2, (180.0,)), (750, 2, (310.0,)),
    (800, 2, (325.0,)), (800, 3, (180.0, 180.0)),
])
def test_each_spec_group_only_nominal_distances_no_absolute_x(w, count, pitch):
    group = nominal_nfb_x_group(w, count)
    assert group.rule_id == f"RECEIVING-NFB-OPEN-X-{w}-{count}"
    assert group.revision == RULE_REVISION
    assert group.gate == ("OPEN-X-ONE" if count == 1 else "OPEN-X-ROW")
    assert group.adjacent_distances_mm == pitch
    assert group.status == PREVIEW_ONLY
    assert group.absolute_centers_mm is None
    assert group.certified_x_revision is None
    assert group.manufacturing_ready is False
    row = next(r for r in fixture("docs/receiving-nfb-x-evidence.json")["records"]
               if r["box_outer_width_mm"] == w and r["nfb_count"] == count)
    assert row["nominal_adjacent_center_distances_mm"] == (
        list(pitch) if pitch is not None else None
    )
    assert row["x_status"] == PREVIEW_ONLY


@pytest.mark.parametrize("w,count", [
    (600, 3), (750, 3), (800, 4), (400, 1), (800, 0), (800, True),
    (800.0, 2), (True, 1),
])
def test_no_unapproved_size_or_single_unit_center_defaults(w, count):
    with pytest.raises(ValueError, match="OPEN-X"):
        nominal_nfb_x_group(w, count)


@pytest.mark.parametrize(
    "neighbor,box_center,expected_world,expected_face",
    [
        (None, 0.0, (-180.0, 0.0, 180.0), (164.5, 344.5, 524.5)),
        (400.0, 200.0, (20.0, 200.0, 380.0), (164.5, 344.5, 524.5)),
    ]
)
def test_w800_source_a1_to_whd_real_cutting_to_face_to_box_is_reversible_shadow(
    neighbor, box_center, expected_world, expected_face,
):
    state = snapshot(left_neighbor=neighbor)
    before = deepcopy(state)
    source, closed = originals()
    for idx, want_source in enumerate((5474.49589, 5654.49589, 5834.49589)):
        result = shadow_w800_three_source_x(
            state, "upper", slot_index=idx, original_source=source,
            closed_cutting_reference=closed,
        )
        assert result.status == SHADOW_ONLY
        assert result.rule_id == "RECEIVING-NFB-OPEN-X-800-3"
        assert result.revision == RULE_REVISION
        assert result.certified_x_revision is None
        assert result.manufacturing_ready is False
        assert result.part_id == "inner_door:upper:panel"
        assert result.cell_key == ("0:0" if neighbor is None else "1:0")
        assert result.source_dxf_sha256 == source["source_sha256"]
        assert result.closed_reference_sha256 == closed["source_sha256"]
        assert result.source_center_x_mm == pytest.approx(want_source)
        assert result.source_left_x_mm == pytest.approx(5292.99589)
        assert result.source_right_x_mm == pytest.approx(6015.99589)
        assert result.unfolded_blank_width_mm == pytest.approx(723)
        assert result.folded_core_width_mm == pytest.approx(685)
        assert result.blank_uv_x_mm-result.blank_cutting_min_x_mm == pytest.approx(
            (181.5, 361.5, 541.5)[idx]
        )
        assert result.finished_face_x_from_left_mm == pytest.approx(expected_face[idx])
        assert result.candidate_box_world_x_mm == pytest.approx(expected_world[idx])
        assert reverse_shadow_w800_three_source_x(
            state, "upper", candidate_world_x_mm=result.candidate_box_world_x_mm,
            original_source=source, closed_cutting_reference=closed,
        ) == pytest.approx(want_source)
    assert state == before
    # Document status and physical NFB CUTTING remain CLOSED.
    evidence = fixture("docs/receiving-nfb-x-evidence.json")
    assert evidence["w800_t2_three_hole_observation"]["box_world_centers_mm"] is None
    assert evidence["w800_t2_three_hole_observation"]["certified_x_revision"] is None


def test_existing_actual_manufacturing_blank_not_changed_by_shadow_queries():
    from ae_engine.cabinet_types import policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data

    state = snapshot()
    panel = policy.derive_inner_door_panels(state)[0]
    before = build_inner_door_panel_render_data(panel)
    src, closed = originals()
    for i in range(3):
        shadow_w800_three_source_x(
            state, "upper", slot_index=i,
            original_source=src, closed_cutting_reference=closed,
        )
    after = build_inner_door_panel_render_data(policy.derive_inner_door_panels(state)[0])
    assert before.scene.primitives == after.scene.primitives
    assert before.metadata == after.metadata
    assert before.unfolded_topology == after.unfolded_topology


@pytest.mark.parametrize("changed,reason", [
    ({"t":3.0}, "only witnessed"),
    ({"model":"金庫型"}, "requires enabled"),
    ({"multi_door_enabled":False}, "requires enabled"),
])
def test_unwitnessed_physical_context_fails_closed(changed, reason):
    state = snapshot()
    state.update(changed)
    with pytest.raises(ValueError, match=reason):
        shadow_w800_three_source_x(
            state,"upper",slot_index=0,
            original_source=originals()[0],
            closed_cutting_reference=originals()[1],
        )


def test_unwitnessed_upper_cell_height_and_duplicate_owner_fail_closed():
    state = snapshot(upper=1000.0)
    with pytest.raises(ValueError,match="only witnessed"):
        shadow_w800_three_source_x(
            state,"upper",slot_index=0,
            original_source=originals()[0],
            closed_cutting_reference=originals()[1],
        )
    state = snapshot()
    state["inner_doors"].append(dict(state["inner_doors"][0]))
    with pytest.raises(ValueError,match="unique inner-door"):
        shadow_w800_three_source_x(
            state,"upper",slot_index=0,
            original_source=originals()[0],
            closed_cutting_reference=originals()[1],
        )


@pytest.mark.parametrize("idx", [-1,3,True,0.5])
def test_invalid_slot_is_not_rounded_or_implicitly_created(idx):
    source, closed = originals()
    with pytest.raises(ValueError,match="slot index"):
        shadow_w800_three_source_x(
            snapshot(),"upper",slot_index=idx,
            original_source=source,closed_cutting_reference=closed,
        )


def test_source_or_cutting_reference_mutation_never_silently_moves_hole():
    source, closed = originals()
    tampered = deepcopy(source)
    for row in tampered["entities"]:
        if row["handle"] == "A1":
            row["start"][0] += 1.0
            row["end"][0] += 1.0
            break
    for bad_source, bad_closed in [
        (tampered,closed),
        (source,{**closed,"source_sha256":"f"*64}),
        (source,{**closed,"source_a1_segment_identical_to_closed_cutting":False}),
    ]:
        with pytest.raises(ValueError,match="OPEN-X"):
            shadow_w800_three_source_x(
                snapshot(),"upper",slot_index=0,
                original_source=bad_source,
                closed_cutting_reference=bad_closed,
            )


def test_reverse_nonfinite_or_far_outside_physical_core_rejected():
    src,closed = originals()
    for x in (float("nan"),float("inf"),-1e8):
        with pytest.raises(ValueError,match="shadow world X"):
            reverse_shadow_w800_three_source_x(
                snapshot(),"upper",candidate_world_x_mm=x,
                original_source=src,closed_cutting_reference=closed,
            )


@pytest.mark.parametrize("tamper", ["source_y", "closed_y", "source_color"])
def test_original_aperture_requires_identical_closed_cutting_xy_identity(tamper):
    """The six-hole reference has repeated X columns in two different Y rows."""
    source, closed = originals()
    source, closed = deepcopy(source), deepcopy(closed)
    if tamper == "source_y":
        side = next(e for e in source["entities"] if e["handle"] == "B6")
        side["end"][1] -= 2.0
    elif tamper == "closed_y":
        # The lower-row footprint of slot zero must be byte-evidence identical.
        lower = next(h for h in closed["rectangular_holes"]
                     if abs(h["bbox"][0] - 5460.49589) < 1e-6
                     and abs(h["bbox"][1] - 1544.0) < 1e-6)
        lower["bbox"][1] += 1.0
    else:
        side = next(e for e in source["entities"] if e["handle"] == "B6")
        side["color"] = 3
    with pytest.raises(ValueError, match="OPEN-X-W800x3 source aperture"):
        shadow_w800_three_source_x(
            snapshot(), "upper", slot_index=0,
            original_source=source, closed_cutting_reference=closed,
        )

def test_physical_column_width_mismatch_rejected_before_world_x_shadow():
    state = snapshot(left_neighbor=400.0)
    assert state["w"] == pytest.approx(1200.0)
    state["w"] = 800.0  # malformed physical topology, not a 1200-mm cabinet
    source, closed = originals()
    with pytest.raises(ValueError, match="column widths do not equal cabinet world width"):
        shadow_w800_three_source_x(
            state, "upper", slot_index=0,
            original_source=source, closed_cutting_reference=closed,
        )
