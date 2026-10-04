# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.receiving_layout import (
    RECEIVING_BAY_COMMON_STATE_INVALID,
    ReceivingBayProjectionError,
    append_receiving_set,
    new_receiving_layout,
    project_receiving_bay_legacy_aliases,
    receiving_joint_alignment_editability,
    resize_receiving_bays,
    update_receiving_bay,
    update_receiving_joint_alignment,
    strip_legacy_receiving_aliases,
)
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingDestructiveEditConfirmationRequired,
    ReceivingSetBayAdapter,
    receiving_layout_stable_ids,
)


def _layout():
    return new_receiving_layout(width=800, height=1600, depth=350, back_panel_mode="FULL")


def _snapshot(layout=None):
    snap = receiving.apply_family_defaults({"t": 2.0})
    snap["receiving_layout"] = deepcopy(layout or _layout())
    return snap


def test_t003_progressive_set_surface_starts_with_set1_and_next_set2_only():
    adapter = ReceivingSetBayAdapter(_layout())
    assert adapter.visible_set_numbers() == (1, 2)
    assert adapter.selection.set_index == 0
    assert adapter.current_bay()["stable_id"] == "receiving:set:1:bay:1"

    assert adapter.select_set(2) is True
    assert adapter.visible_set_numbers() == (1, 2, 3)
    assert adapter.selection.set_index == 1
    assert adapter.current_bay()["stable_id"] == "receiving:set:2:bay:1"

    with pytest.raises(IndexError, match="progressively"):
        adapter.select_set(4)


def test_t005_bay_append_clones_previous_by_value_and_truncate_is_tail_only():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=920, depth=410, back_panel_mode="HALF")
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)

    bays = layout["sets"][0]["bays"]
    assert [row["stable_id"] for row in bays] == [
        "receiving:set:1:bay:1",
        "receiving:set:1:bay:2",
        "receiving:set:1:bay:3",
    ]
    assert bays[2]["width"] == pytest.approx(920)
    assert bays[2]["depth"] == pytest.approx(410)
    assert bays[2]["back_panel_mode"] == "HALF"

    changed = update_receiving_bay(layout, set_index=0, bay_index=2, width=999)
    assert changed["sets"][0]["bays"][1]["width"] == pytest.approx(920)

    truncated = resize_receiving_bays(changed, set_index=0, bay_count=2)
    assert [row["stable_id"] for row in truncated["sets"][0]["bays"]] == [
        "receiving:set:1:bay:1",
        "receiving:set:1:bay:2",
    ]
    assert len(truncated["sets"][0]["joints"]) == 1


def test_t005_destructive_confirmation_only_for_persisted_or_session_dirty_tail():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    persisted = receiving_layout_stable_ids(layout)
    adapter = ReceivingSetBayAdapter(layout, persisted_ids=persisted)

    with pytest.raises(ReceivingDestructiveEditConfirmationRequired) as exc:
        adapter.set_bay_count(1)
    assert "receiving:set:1:bay:2" in exc.value.stable_ids

    confirmations = []
    adapter = ReceivingSetBayAdapter(
        layout,
        persisted_ids=persisted,
        confirm_destructive=lambda ids: confirmations.append(ids) or True,
    )
    adapter.set_bay_count(1)
    assert confirmations and "receiving:set:1:bay:2" in confirmations[0]

    # A new untouched tail Bay is session-only and can be undone without a prompt.
    clean = ReceivingSetBayAdapter(_layout())
    clean.set_bay_count(2)
    clean.set_bay_count(1)
    assert clean.bay_count() == 1


def test_t005_set_tail_truncation_cascades_later_sets_only():
    adapter = ReceivingSetBayAdapter(_layout())
    adapter.set_set_count(3)
    assert [row["stable_id"] for row in adapter.layout["sets"]] == [
        "receiving:set:1",
        "receiving:set:2",
        "receiving:set:3",
    ]
    adapter.set_set_count(2)
    assert [row["stable_id"] for row in adapter.layout["sets"]] == [
        "receiving:set:1",
        "receiving:set:2",
    ]
    with pytest.raises(ValueError, match="Set1"):
        adapter.set_set_count(0)


def test_t005a_new_set_bay1_always_samples_set1_bay1_at_creation_time():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=1234, depth=777)
    layout = update_receiving_bay(layout, set_index=0, bay_index=0, width=810, height=1700, depth=420, back_panel_mode="BACK_OPENING")

    layout = append_receiving_set(layout)
    set2_bay1 = layout["sets"][1]["bays"][0]
    assert set2_bay1 == {
        "stable_id": "receiving:set:2:bay:1",
        "width": pytest.approx(810),
        "height": pytest.approx(1700),
        "depth": pytest.approx(420),
        "back_panel_mode": "BACK_OPENING",
    }

    # Existing Set2 is a value copy; later Set1 edits do not live-link into it.
    layout = update_receiving_bay(layout, set_index=0, bay_index=0, width=830)
    assert layout["sets"][1]["bays"][0]["width"] == pytest.approx(810)
    layout = append_receiving_set(layout)
    assert layout["sets"][2]["bays"][0]["width"] == pytest.approx(830)


def test_t006a_first_joint_defaults_front_bottom_then_new_joint_inherits_previous_alignment():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    joint1 = layout["sets"][0]["joints"][0]
    assert joint1["depth_alignment"] == "FRONT"
    assert joint1["height_alignment"] == "BOTTOM"

    layout = update_receiving_bay(layout, set_index=0, bay_index=1, depth=500, height=1800)
    layout = update_receiving_joint_alignment(
        layout,
        set_index=0,
        joint_index=0,
        depth_alignment="REAR",
        height_alignment="TOP",
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    joint2 = layout["sets"][0]["joints"][1]
    assert joint2["depth_alignment"] == "REAR"
    assert joint2["height_alignment"] == "TOP"


def test_t006a_equal_dimensions_disable_or_noop_corresponding_alignment_axis():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    assert receiving_joint_alignment_editability(layout, set_index=0, joint_index=0) == {
        "depth_alignment": False,
        "height_alignment": False,
    }
    unchanged = update_receiving_joint_alignment(
        layout,
        set_index=0,
        joint_index=0,
        depth_alignment="REAR",
        height_alignment="TOP",
    )
    assert unchanged["sets"][0]["joints"][0]["depth_alignment"] == "FRONT"
    assert unchanged["sets"][0]["joints"][0]["height_alignment"] == "BOTTOM"

    unequal = update_receiving_bay(layout, set_index=0, bay_index=1, depth=500)
    assert receiving_joint_alignment_editability(unequal, set_index=0, joint_index=0) == {
        "depth_alignment": True,
        "height_alignment": False,
    }


def test_t007_each_bay_reuses_existing_common_door_validation_and_fails_closed_with_diagnostic():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=900)
    snap = _snapshot(layout)
    snap["multi_door_enabled"] = True
    snap["door_layout_columns"] = [[800.0, [1100.0, 500.0]]]

    projected = project_receiving_bay_legacy_aliases(snap, set_index=0, bay_index=0)
    assert projected["w"] == pytest.approx(800)

    with pytest.raises(ReceivingBayProjectionError) as exc:
        project_receiving_bay_legacy_aliases(snap, set_index=0, bay_index=1)
    assert RECEIVING_BAY_COMMON_STATE_INVALID in str(exc.value)
    assert "Set1/Bay2" in str(exc.value)
    assert "expected W=900" in str(exc.value)


def test_t015_transient_current_bay_projection_never_mutates_persisted_layout_or_input_snapshot():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=930, height=1800, depth=500, back_panel_mode="HALF")
    snap = _snapshot(layout)
    before = deepcopy(snap)

    projected = project_receiving_bay_legacy_aliases(
        snap,
        set_index=0,
        bay_index=1,
        validate_common=False,
    )
    assert projected["w"] == pytest.approx(930)
    assert projected["h"] == pytest.approx(1800)
    assert projected["d"] == pytest.approx(500)
    assert projected["receiving_layout"] == before["receiving_layout"]
    assert snap == before

    persisted = strip_legacy_receiving_aliases(projected)
    assert persisted["receiving_layout"] == before["receiving_layout"]
    assert all(key not in persisted for key in ("w", "h", "d"))


def test_bridge_projects_receiving_layers_as_rows_without_legacy_set_bay_selectors():
    from pathlib import Path

    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "ReceivingSetBayAdapter" in source
    assert "self.receiving_set_bay_control" in source
    assert "self.receiving_layer_controls" in source
    assert "self.receiving_switch_brand_selector" in source
    assert "refresh_receiving_layer_rows(" in source
    assert "self.receiving_set_selector" not in source
    assert "self.receiving_bay_selector" not in source
    assert "_phase6_confirm_receiving_opening" in source
    assert "_phase6_open_receiving_layer_preview" in source
    # +/- connection changes are configuration-only and must not redraw 3D.
    start = source.index("def _phase6_resize_receiving_bays")
    end = source.index("def _phase6_confirm_receiving_opening", start)
    resize_source = source[start:end]
    assert "self.do_update()" not in resize_source
    assert "submit_update_intent" not in resize_source
    assert "_phase6_sync_receiving_current_bay" not in resize_source
    # Selection remains UI/session state; no persisted selector index is introduced.
    assert '"current_set_index"' not in source
    assert '"current_bay_index"' not in source
