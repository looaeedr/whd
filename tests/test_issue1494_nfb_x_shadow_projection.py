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
    W800_THREE_DATUM_REVISION,
    WHD_PART_DATUM_VERIFIED,
    resolve_w800_three_whd_x,
    reverse_w800_three_whd_x,
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
    (800, 2, (360.0,)), (800, 3, (180.0, 180.0)),
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


@pytest.mark.parametrize("w,source_sha,outer_width,side_widths,pitch,delta", [
    (600, "cb6f200eb5339bd8abd994eee01ad405c7e0bd004984ac5b4f1be3a2b6e1bc76", 524, (57, 57), 180, 1),
    (750, "892cd8a391e41937e6cff74696294342d06894c1b4c47d51874da1309075da49", 674, (50, 50), 310, 1),
    (800, "a2de69b4dba64ee8d22d42d79b7a67bdc94f561181bc232d3193f6ce9afc41e7", 723, (57, 28), 325, 0),
])
def test_user_original_two_slot_x_sources_are_evidence_not_world_x(
    w, source_sha, outer_width, side_widths, pitch, delta,
):
    evidence = fixture("tests/fixtures/receiving_nfb_nominal_x_native_observations.json")
    assert evidence["source_dxf_bytes_not_committed"] is True
    assert evidence["scope"] == "ORIGINAL_SOURCE_GEOMETRY_ONLY_NOT_WORLD_X_NOT_MANUFACTURING"
    row, = (r for r in evidence["records"]
            if r["box_outer_width_mm"] == w and r["nfb_count"] == 2)
    assert row["source_sha256"] == source_sha
    assert row["source_outer_span_mm"] == outer_width
    left, right = row["source_outer_side_x_mm"]
    assert right - left == pytest.approx(outer_width)
    assert len(set(row["source_outer_side_handles"])) == 2
    assert len(row["source_cutout_side_handles"]) == 2
    centers = []
    for pair, handles, side_width in zip(
        row["cutout_side_x_mm"], row["source_cutout_side_handles"], side_widths
    ):
        assert len(set(handles)) == 2
        assert pair[1] - pair[0] == pytest.approx(side_width)
        center = sum(pair) / 2
        assert left < center < right
        centers.append(center)
    assert centers == pytest.approx(row["observed_centers_source_x_mm"])
    assert [x - left for x in centers] == pytest.approx(
        row["observed_centers_relative_to_source_left_mm"]
    )
    assert centers[1] - centers[0] == pytest.approx(pitch)
    assert row["observed_pitch_mm"] == pitch
    # Raw uploaded 800x2 DXF really measured 325. The CURRENT operator
    # corrected W800 double-row design pitch to 360, independently. Do not
    # rewrite historic DXF bytes, nor silently re-certify the absolute X.
    current_pitch = 360.0 if w == 800 else pitch
    assert nominal_nfb_x_group(w, 2).adjacent_distances_mm == (current_pitch,)
    # Preserve native dimensions solely as source observations. A source drawing
    # may be stale: its 1-mm difference MUST NOT become WHD blank authority.
    assert outer_width - row["conditional_current_t2_gap35_blank_width_mm"] == delta
    assert row["conditional_source_span_delta_mm"] == delta
    assert row["source_outline_is_manufacturing_dimension_authority"] is False
    assert row["canonical_whd_t2_blank_width_mm"] == w - 77
    assert row["source_span_difference_is_release_blocker"] is False
    documented, = (entry for entry in fixture("docs/receiving-nfb-x-evidence.json")["records"]
                   if entry["box_outer_width_mm"] == w and entry["nfb_count"] == 2)
    assert documented["source_dxf_sha256"] == source_sha
    assert documented["source_outline_handles"] == row["source_outer_side_handles"]
    assert documented["source_layout_observation"]["observed_center_pitch_mm"] == pitch
    assert documented["nominal_adjacent_center_distances_mm"] == [current_pitch]
    assert documented["source_layout_observation"]["status"] == "SOURCE_PITCH_OBSERVED_ONLY"
    assert documented["source_layout_observation"]["source_span_is_dimension_authority"] is False
    assert documented["source_layout_observation"]["source_span_difference_is_release_blocker"] is False
    assert documented["canonical_whd_inner_door_blank_width_mm"] == w - 77
    assert documented["source_layout_observation"]["physical_blank_to_source_identical"] is False
    assert documented["source_layout_observation"]["model_main_hole_authenticated"] is False
    assert documented["certified_x_revision"] is None
    assert documented["x_status"] == PREVIEW_ONLY
    group = nominal_nfb_x_group(w, 2)
    assert group.status == PREVIEW_ONLY
    assert group.absolute_centers_mm is None
    assert group.certified_x_revision is None
    assert group.manufacturing_ready is False


@pytest.mark.parametrize("width,expected_finished,expected_blank", [
    (600, 489.0, 523.0),
    (750, 639.0, 673.0),
    (800, 689.0, 723.0),
])
def test_inner_door_blank_authority_is_live_w800_723_formula_not_source_dxf(
    width, expected_finished, expected_blank,
):
    """Use the actual Receiving family -> folded panel -> CUTTING, not source bbox."""
    from ae_engine.cabinet_types import policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    state = apply_family_defaults({
        "model": "受電箱", "w": width, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    state.update({
        "w": float(width),
        "door_layout_columns": [[float(width), [1100.0, 500.0]]],
        "multi_door_enabled": True,
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    panel, = policy.derive_inner_door_panels(state)
    assert panel.width == pytest.approx(expected_finished)
    assert panel.unfolded_width == pytest.approx(expected_blank)
    actual = build_inner_door_panel_render_data(panel)
    outlines = [
        primitive for primitive in actual.scene.primitives
        if isinstance(primitive, PolylinePrimitive)
        and primitive.closed and primitive.layer.upper() == "CUTTING"
    ]
    assert len(outlines) == 1
    xx = [float(point.x) for point in outlines[0].points]
    assert max(xx) - min(xx) == pytest.approx(expected_blank)

    # Historical native DXF left/right endpoints are NOT manufacturing datums:
    witnesses = fixture("tests/fixtures/receiving_nfb_nominal_x_native_observations.json")
    witness, = (row for row in witnesses["records"]
                if row["box_outer_width_mm"] == width and row["nfb_count"] == 2)
    assert witness["source_outline_is_manufacturing_dimension_authority"] is False
    assert witness["canonical_whd_t2_blank_width_mm"] == expected_blank
    assert witness["source_span_difference_is_release_blocker"] is False
    assert nominal_nfb_x_group(width, 2).manufacturing_ready is False


@pytest.mark.parametrize(
    "neighbor,center,world",
    [(None, 0.0, (-180.0, 0.0, 180.0)),
     (400.0, 200.0, (20.0, 200.0, 380.0))],
)
def test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly(
    neighbor, center, world,
):
    """#1494 X datum golden must NOT need a customer's source DXF."""
    state = snapshot(left_neighbor=neighbor)
    before = deepcopy(state)
    rows = [
        resolve_w800_three_whd_x(state, "upper", slot_index=i)
        for i in range(3)
    ]
    assert [r.revision for r in rows] == [W800_THREE_DATUM_REVISION] * 3
    assert [r.status for r in rows] == [WHD_PART_DATUM_VERIFIED] * 3
    assert [r.rule_id for r in rows] == ["RECEIVING-NFB-OPEN-X-800-3"] * 3
    assert [r.slot_index for r in rows] == [0, 1, 2]
    assert [r.part_id for r in rows] == ["inner_door:upper:panel"] * 3
    assert [r.cell_key for r in rows] == [("0:0" if neighbor is None else "1:0")] * 3
    assert all(r.x_direction == "WHD_CUTTING_POSITIVE_X_EQUALS_BOX_WORLD_POSITIVE_X"
               for r in rows)
    assert [r.blank_x_from_cutting_left_mm for r in rows] == pytest.approx(
        (181.5, 361.5, 541.5)
    )
    assert [r.blank_uv_x_mm-r.blank_cutting_left_x_mm for r in rows] == pytest.approx(
        (181.5, 361.5, 541.5)
    )
    assert [r.finished_face_x_from_left_mm for r in rows] == pytest.approx(
        (164.5, 344.5, 524.5)
    )
    assert [r.box_world_x_mm for r in rows] == pytest.approx(world)
    assert [r.box_world_panel_center_x_mm for r in rows] == pytest.approx([center]*3)
    assert all(r.unfolded_blank_width_mm == pytest.approx(723) for r in rows)
    assert all(r.folded_core_width_mm == pytest.approx(685) for r in rows)
    assert all(r.manufacturing_ready is False and r.certified_x_revision is None
               for r in rows)
    for row in rows:
        assert reverse_w800_three_whd_x(
            state, "upper", slot_index=row.slot_index,
            box_world_x_mm=row.box_world_x_mm,
        ) == pytest.approx(row.blank_x_from_cutting_left_mm)
    assert state == before


def test_original_dxf_wrong_outer_width_cannot_shift_whd_authoritative_x():
    """Raw DXF is corroboration only, never the origin of WHD's own blank."""
    state = snapshot()
    expected = tuple(
        resolve_w800_three_whd_x(state, "upper", slot_index=i)
        for i in range(3)
    )
    source, closed = originals()
    bad = deepcopy(source)
    left = next(row for row in bad["entities"] if row["handle"] == "A1")
    left["start"][0] += 1
    left["end"][0] += 1
    with pytest.raises(ValueError, match="OPEN-X-W800x3 source"):
        shadow_w800_three_source_x(
            state, "upper", slot_index=0,
            original_source=bad, closed_cutting_reference=closed,
        )
    assert tuple(
        resolve_w800_three_whd_x(state, "upper", slot_index=i)
        for i in range(3)
    ) == expected


@pytest.mark.parametrize("slot,x", [
    (-1, 0.0), (3, 0.0), (True, 0.0), (1, -180.0),
    (0, float("inf")), (0, float("nan")), (0, -179.0),
])
def test_w800_canonical_inverse_rejects_invalid_or_other_slot(slot, x):
    with pytest.raises(ValueError, match="OPEN-X-W800x3"):
        reverse_w800_three_whd_x(
            snapshot(), "upper", slot_index=slot, box_world_x_mm=x,
        )


def test_w800_canonical_datum_rejects_unwitnessed_physical_context():
    for change in (
        {"t":3.0},
        {"door_gap_w":4.0},
        {"w":799.0},
        {"multi_door_enabled":False},
    ):
        state = snapshot()
        state.update(change)
        with pytest.raises(ValueError, match="OPEN-X-W800x3"):
            resolve_w800_three_whd_x(state, "upper", slot_index=0)


def test_w800_inner_door_datum_stays_fixed_when_outer_door_folds_change():
    # Receiving inner-door flanges are independently fixed at four 19-mm
    # folds; changing the outer door's bends must not revoke its valid NFB
    # physical datum or silently change its manufactured blank.
    state = snapshot()
    expected = resolve_w800_three_whd_x(state, "upper", slot_index=0)
    state.update({"door_fold_l": 18.0, "door_fold_r": 20.0,
                  "door_fold_t": 23.0, "door_fold_b": 17.0})
    actual = resolve_w800_three_whd_x(state, "upper", slot_index=0)
    assert actual == expected


def test_w800_canonical_x_rejects_reversed_assembly_axes(monkeypatch):
    from ae_engine import receiving_nfb_x_projection as projected
    from ae_engine.assembly_placement import resolve_inner_door_panel_placement

    real_resolve = resolve_inner_door_panel_placement

    def reversed_placement(state, part_id):
        return replace(real_resolve(state, part_id), rotation=(0.0, 0.0, 180.0))

    monkeypatch.setattr(projected, "resolve_inner_door_panel_placement", reversed_placement)
    with pytest.raises(ValueError, match="physical part/rotation"):
        projected.resolve_w800_three_whd_x(snapshot(), "upper", slot_index=0)
