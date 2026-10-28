# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
import os

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
from gui_modules.application.fold_designer_composition_receiving import (
    resize_receiving_bays as native_gui_resize_receiving_bays,
)

from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingDestructiveEditConfirmationRequired,
    ReceivingSetBayAdapter,
    ReceivingSwitchProjectionAdapter,
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

    # The current Receiving Family supports a transient, source-derived
    # full-size door for a Bay without its own authored door_state. An old
    # assertion requiring rejection merely because Bay2 is W900 was superseded
    # by this legitimate per-Bay projection, not by relaxed validation.
    before = deepcopy(snap)
    source_derived = project_receiving_bay_legacy_aliases(
        snap, set_index=0, bay_index=1,
    )
    assert source_derived["w"] == pytest.approx(900)
    assert source_derived["door_layout_columns"][0][0] == pytest.approx(900)
    assert snap == before

    # A *genuinely authored* W800 door partition on physical Bay2 W900
    # must STILL fail the original manufacturing validation, with Bay scope.
    stale = deepcopy(snap)
    stale["receiving_layout"] = update_receiving_bay(
        layout, set_index=0, bay_index=1, door_state={
            "multi_door_enabled": True,
            "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        },
    )
    with pytest.raises(ReceivingBayProjectionError) as exc:
        project_receiving_bay_legacy_aliases(stale, set_index=0, bay_index=1)
    assert RECEIVING_BAY_COMMON_STATE_INVALID in str(exc.value)
    assert "Set1/Bay2" in str(exc.value)
    assert "expected W=900" in str(exc.value)


def test_t015_transient_current_bay_projection_never_mutates_persisted_layout_or_input_snapshot():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, width=930, height=1800, depth=500, back_panel_mode="HALF")
    from ae_engine.receiving_layout import ensure_receiving_layout
    snap = ensure_receiving_layout(_snapshot(layout))
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
    import inspect
    from gui_modules.application import fold_designer_composition_receiving as composition_receiving
    owner_source = inspect.getsource(composition_receiving.refresh_receiving_set_bay_control)
    assert 'required("refresh_receiving_layer_rows")' in owner_source
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


def test_issue1817_multi_bay_dimension_batch_normalizes_once_and_matches_legacy(
    monkeypatch,
):
    import ae_engine.receiving_layout as layout_owner
    import gui_modules.application.receiving_set_bay_adapter as adapter_owner

    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=4)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1,
                                  width=950, height=1750, depth=480)
    before = deepcopy(layout)
    expected = update_receiving_bay(layout, set_index=0, bay_index=0,
                                    width=900, height=1700, depth=390)
    expected = update_receiving_bay(expected, set_index=0, bay_index=2,
                                    width=900, height=1700, depth=390)
    adapter = ReceivingSetBayAdapter(layout)
    actual_normalize = layout_owner.normalize_receiving_layout
    calls = []
    def counted(raw):
        calls.append(1)
        return actual_normalize(raw)
    monkeypatch.setattr(layout_owner, 'normalize_receiving_layout', counted)
    monkeypatch.setattr(adapter_owner, 'normalize_receiving_layout', counted)
    count = adapter.apply_dimensions_to_bays(
        0, (0, 2), width=900, height=1700, depth=390, expected_count=2)
    assert count == 2
    assert len(calls) == 1, 'batch must commit exactly one validated layout'
    assert adapter.layout == expected
    assert before['sets'][0]['bays'][1] == adapter.layout['sets'][0]['bays'][1]
    assert before['sets'][0]['bays'][3] == adapter.layout['sets'][0]['bays'][3]
    assert before['sets'][0]['joints'] == adapter.layout['sets'][0]['joints']
    assert adapter._session_dirty_ids == {
        before['sets'][0]['bays'][0]['stable_id'],
        before['sets'][0]['bays'][2]['stable_id'],
    }


def test_issue1817_noop_dimension_confirmation_skips_all_normalization(monkeypatch):
    import ae_engine.receiving_layout as layout_owner
    import gui_modules.application.receiving_set_bay_adapter as adapter_owner
    adapter = ReceivingSetBayAdapter(_layout())
    original = layout_owner.normalize_receiving_layout
    calls = []
    def counted(raw):
        calls.append(1)
        return original(raw)
    monkeypatch.setattr(layout_owner, 'normalize_receiving_layout', counted)
    monkeypatch.setattr(adapter_owner, 'normalize_receiving_layout', counted)
    before = adapter.layout
    assert adapter.apply_dimensions_to_bays(
        0, (0,), width=800, height=1600, depth=350, expected_count=1) == 0
    assert len(calls) == 0
    assert adapter.layout == before
    assert not adapter._session_dirty_ids


def test_issue1817_batch_invalid_late_door_partition_is_atomic():
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        door_state={'door_layout_columns': [[400, [1000, 600]], [400, [1000, 600]]]})
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout
    with pytest.raises(ValueError, match='第2連 W 不符合門分割'):
        adapter.apply_dimensions_to_bays(
            0, (0, 1), width=350, height=1700, depth=400, expected_count=2)
    assert adapter.layout == before
    assert not adapter._session_dirty_ids


def test_issue1817_batch_reflows_existing_door_state_same_as_sequential_updates():
    from ae_engine.sheetmetal_part_adapters import complete_partition
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=3)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        door_state={'door_layout_columns': [[400, [1000, 600]], [400, [1000, 600]]]})
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=2,
        door_state={'door_layout_columns': [[400, [1000, 600]], [400, [1000, 600]]]})
    # The existing accepted UI contract adjusts only the final partition
    # cell, preserving the explicit first width and layer heights.
    assert complete_partition([400], 850).valid
    adapter = ReceivingSetBayAdapter(layout)
    changed = adapter.apply_dimensions_to_bays(
        0, (0, 2), width=850, height=1650, depth=420, expected_count=2)
    assert changed == 2
    result = adapter.layout
    for bay_index in (0, 2):
        assert result['sets'][0]['bays'][bay_index]['door_state']['door_layout_columns'] == [
            [400.0, [1000.0, 650.0]], [450.0, [1000.0, 650.0]]]
    assert result['sets'][0]['bays'][1] == layout['sets'][0]['bays'][1]


def test_batch_operator_width_change_demotes_only_selected_confirmed_nfb_x(monkeypatch):
    """Real highlighted-Bay W/H/D operator may not bypass NFB datum invalidation."""
    import gui_modules.application.receiving_set_bay_adapter as adapter_owner
    from tests.test_issue1499_nfb_persistence import _config

    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=3)
    for index in range(3):
        layout = update_receiving_bay(
            layout, set_index=0, bay_index=index,
            nfb_config_submitted=True, nfb_config=_config(x=index * 100),
        )
    original = deepcopy(layout)
    adapter = ReceivingSetBayAdapter(layout)

    # Preserve #1817's one-normalize-per-atomic-batch performance rule.
    real = adapter_owner.normalize_receiving_layout
    calls = []
    def counted(raw):
        calls.append(1)
        return real(raw)
    monkeypatch.setattr(adapter_owner, "normalize_receiving_layout", counted)

    assert adapter.apply_dimensions_to_bays(
        0, (0, 2), width=900, height=1600, depth=350, expected_count=2
    ) == 2
    assert calls == [1]
    bays = adapter.layout["sets"][0]["bays"]
    for index in (0, 2):
        old = original["sets"][0]["bays"][index]["nfb_config"]["holes"][0]
        new = bays[index]["nfb_config"]["holes"][0]
        assert bays[index]["width"] == 900
        assert bays[index]["nfb_config_submitted"] is True
        assert new["manual_x_state"] == "RECONFIRM_REQUIRED"
        assert new["manual_x_mm"] == old["manual_x_mm"]
        assert new["datum_snapshot"] == old["datum_snapshot"]
        assert new["model_filename"] == old["model_filename"]
    assert bays[1] == original["sets"][0]["bays"][1]
    assert original == layout

    assert adapter.apply_dimensions_to_bays(
        0, (0, 2), width=900, height=1600, depth=350, expected_count=2
    ) == 0
    assert calls == [1]
    assert all(adapter.layout["sets"][0]["bays"][i]["nfb_config"]["holes"][0][
        "manual_x_state"] == "RECONFIRM_REQUIRED" for i in (0, 2))


@pytest.mark.parametrize("response", (1, "yes", [], None, 0, False))
@pytest.mark.parametrize("kind", ("bay", "set"))
def test_issue1504_protected_receiving_tail_requires_literal_true(
    kind, response,
):
    """Deleting persisted Receiving/NFB data needs explicit boolean consent."""
    if kind == "bay":
        original = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    else:
        original = append_receiving_set(_layout())
    before = deepcopy(original)
    called = []

    def reply(protected):
        called.append(protected)
        return response

    adapter = ReceivingSetBayAdapter(
        original, persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=reply,
    )
    with pytest.raises(ReceivingDestructiveEditConfirmationRequired):
        if kind == "bay":
            adapter.set_bay_count(1)
        else:
            adapter.set_set_count(1)
    assert len(called) == 1 and called[0]
    assert adapter.layout == before
    assert original == before
    assert adapter.selection.set_index == 0
    assert adapter.selection.bay_index == 0


@pytest.mark.parametrize("bad_indices", (
    None, 0, (True,), (False,), (0, True), (0, []),
    ([],), ("0",), (-1,), (50,), (0, 0),
))
def test_issue1504_dimension_batch_rejects_nonphysical_highlights_before_io(bad_indices):
    """Malformed multi-Bay selection must not alter sizes or any NFB X basis."""
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout
    selected = adapter.selection
    expected_count = 2 if isinstance(bad_indices, tuple) and len(bad_indices) == 2 else 1
    with pytest.raises(ValueError, match="高亮"):
        adapter.apply_dimensions_to_bays(
            0, bad_indices, width=900, height=1700, depth=400,
            expected_count=expected_count,
        )
    assert adapter.layout == before
    assert adapter.selection == selected
    assert adapter._session_dirty_ids == set()


@pytest.mark.parametrize("bad_set", (True, False, "0", 0.0, None, [], {}))
def test_issue1504_dimension_batch_rejects_noninteger_set_identity(bad_set):
    """Boolean and coerced Set identifiers can never authorize a Bay edit."""
    adapter = ReceivingSetBayAdapter(_layout())
    before = adapter.layout
    selected = adapter.selection
    with pytest.raises(ValueError, match="套不存在"):
        adapter.apply_dimensions_to_bays(
            bad_set, (0,), width=900, height=1700, depth=400,
            expected_count=1,
        )
    assert adapter.layout == before
    assert adapter.selection == selected
    assert adapter._session_dirty_ids == set()


@pytest.mark.parametrize("axis", ("width", "height", "depth"))
def test_issue1504_dimension_batch_huge_axis_is_atomic(axis):
    """Physical dimensions must reject unrepresentable integers before mutation."""
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout
    selection = adapter.selection
    dimensions = {"width": 900, "height": 1700, "depth": 400}
    dimensions[axis] = 10 ** 400
    with pytest.raises(ValueError, match="超出可表示尺寸"):
        adapter.apply_dimensions_to_bays(
            0, (0, 1), expected_count=2, **dimensions,
        )
    assert adapter.layout == before
    assert adapter.selection == selection
    assert adapter._session_dirty_ids == set()


@pytest.mark.parametrize("bad_indices", (
    None, 1, [0, []], [[], 0], [0, True], [0, 1.0],
    [0, "1"], [0, {"id": 1}], [0, 999], [0, -1],
))
def test_issue1504_shared_setting_rejects_bad_real_bay_highlights(bad_indices):
    """Sharing physical Bay settings never hashes malformed source selection."""
    from ae_engine.receiving_shared_settings import share_setting

    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    before = deepcopy(layout)
    with pytest.raises(IndexError, match="連選取超出範圍"):
        share_setting(
            layout, set_index=0, source_bay_index=0,
            bay_indices=bad_indices, kind="inner_door_layers",
        )
    assert layout == before


@pytest.mark.parametrize("bad_source", (None, True, False, 0.0, [], {}))
def test_issue1504_shared_setting_rejects_bad_source_bay_identity(bad_source):
    from ae_engine.receiving_shared_settings import share_setting

    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    before = deepcopy(layout)
    with pytest.raises(IndexError, match="連選取超出範圍"):
        share_setting(
            layout, set_index=0, source_bay_index=bad_source,
            bay_indices=(0, 1), kind="inner_door_layers",
        )
    assert layout == before


def test_issue1504_shared_setting_preserves_valid_multi_bay_reference_sharing():
    from ae_engine.receiving_shared_settings import share_setting, setting_value

    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=3)
    before = deepcopy(layout)
    # Valid duplicate selection is still deduplicated, not interpreted as a
    # request to share a different physical Bay.
    changed = share_setting(
        layout, set_index=0, source_bay_index=0,
        bay_indices=(2, 0, 2), kind="inner_door_layers",
    )
    row = changed["sets"][0]
    assert row["settings"]["inner_door_layers"]["refs"][
        row["bays"][0]["stable_id"]
    ] == row["settings"]["inner_door_layers"]["refs"][
        row["bays"][2]["stable_id"]
    ]
    assert row["settings"]["inner_door_layers"]["refs"][
        row["bays"][1]["stable_id"]
    ] != row["settings"]["inner_door_layers"]["refs"][
        row["bays"][0]["stable_id"]
    ]
    assert setting_value(row, 2, "inner_door_layers") == 1
    assert layout == before



@pytest.mark.parametrize("bad", (True, False, 1.5, 2.0, "1.5", [], {}, [1]))
@pytest.mark.parametrize("method", (
    "select_set", "select_bay", "set_bay_count", "set_set_count", "bay_count",
))
def test_ac07_selection_and_counts_reject_noninteger_alias_without_side_effect(
    bad, method,
):
    """A bool/fraction/list must never become a real Set/Bay or deletion count."""
    original = resize_receiving_bays(_layout(), set_index=0, bay_count=2)
    asked = []
    adapter = ReceivingSetBayAdapter(
        original,
        persisted_ids=receiving_layout_stable_ids(original),
        confirm_destructive=lambda ids: asked.append(ids) or True,
    )
    before_layout = adapter.layout
    before_selection = adapter.selection
    with pytest.raises((ValueError, IndexError), match="integer|index"):
        getattr(adapter, method)(bad)
    assert adapter.layout == before_layout
    assert adapter.selection == before_selection
    assert asked == []




@pytest.mark.parametrize("method", (
    "select_set", "select_bay", "set_bay_count", "set_set_count",
))
def test_ac07_none_is_invalid_except_explicit_current_set_lookup(method):
    """None is the documented default only for bay_count(set_index=None)."""
    adapter = ReceivingSetBayAdapter(_layout())
    before = adapter.layout
    with pytest.raises(ValueError, match="integer"):
        getattr(adapter, method)(None)
    assert adapter.layout == before
    assert adapter.bay_count(None) == 1


@pytest.mark.parametrize("method,value", (
    ("select_set", 0),
    ("select_bay", 0),
    ("bay_count", -1),
    ("bay_count", 999),
))
def test_ac07_set_bay_real_selection_never_uses_negative_python_alias(method, value):
    adapter = ReceivingSetBayAdapter(
        resize_receiving_bays(_layout(), set_index=0, bay_count=2),
    )
    before = adapter.layout
    selection = adapter.selection
    with pytest.raises(IndexError):
        getattr(adapter, method)(value)
    assert adapter.layout == before
    assert adapter.selection == selection


def test_ac07_exact_decimal_text_retains_existing_ui_compatibility():
    """The original UI may pass a typed integer string, never a decimal float."""
    adapter = ReceivingSetBayAdapter(_layout())
    assert adapter.select_set("2") is True
    assert adapter.selection.set_index == 1
    adapter.set_bay_count("2")
    adapter.select_bay("2")
    assert adapter.selection.bay_index == 1
    assert adapter.bay_count("1") == 2
    adapter.set_set_count("2")
    assert len(adapter.layout["sets"]) == 2



def _ac40_submitted_parent_brand_config():
    """Two physical V5 holes: following Set brand vs explicit factory override."""
    from ae_engine.receiving_nfb_model_identity import numeric_model_ref
    model = numeric_model_ref("士林", "2P400")
    return {"layer_count": 1, "holes": [
        {
            "physical_hole_id": "nfb:real-bay:unit-1",
            "unit_id": "unit-1",
            "model_filename": model,
            "source_brand": "士林",
            "brand_mode": "INHERIT",
            "manual_x_mm": 0,
            "manual_x_state": "CONFIRMED",
            "datum_revision": "operator-approved-w800",
            "datum_snapshot": {
                "width": 800, "rotation_deg": 0, "model_filename": model,
            },
            "rotation_deg": 0,
        },
        {
            "physical_hole_id": "nfb:real-bay:unit-2",
            "unit_id": "unit-2",
            "model_filename": model,
            "source_brand": "士林",
            "brand_mode": "OVERRIDE",
            "manual_x_mm": 100,
            "manual_x_state": "CONFIRMED",
            "datum_revision": "operator-approved-w800-explicit",
            "datum_snapshot": {
                "width": 800, "rotation_deg": 0, "model_filename": model,
            },
            "rotation_deg": 0,
        },
    ]}


def test_ac40_set_parent_brand_revokes_only_matching_inherited_confirmed_x(tmp_path):
    """A changed global Set brand cannot silently retain old inherited WORLD-X."""
    from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project

    initial = update_receiving_bay(
        _layout(), set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=_ac40_submitted_parent_brand_config(),
    )
    frozen = deepcopy(initial)
    adapter = ReceivingSetBayAdapter(initial)
    adapter.set_brand("三菱")
    row = adapter.layout["sets"][0]
    assert row["switch_brand"] == "三菱"
    actual = row["bays"][0]
    assert actual["nfb_config_submitted"] is True
    following, override = actual["nfb_config"]["holes"]
    assert following["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert following["manual_x_mm"] == 0
    assert following["source_brand"] == "士林"
    assert following["model_filename"] == frozen["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["model_filename"]
    assert override == frozen["sets"][0]["bays"][0]["nfb_config"]["holes"][1]
    assert initial == frozen

    # Switching back must never silently re-approve an old X datum.
    adapter.set_brand("士林")
    assert adapter.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"

    saved = write_project(tmp_path / "brand-stale-x.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "受電箱", "active_mode": "set_bay",
            "receiving_layout": adapter.layout,
        },
    })
    reloaded = read_project(saved)["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert reloaded["nfb_config_submitted"] is True
    assert [h["manual_x_state"] for h in reloaded["nfb_config"]["holes"]] == [
        "RECONFIRM_REQUIRED", "CONFIRMED",
    ]


def test_ac40_global_brand_reconfirms_each_real_set_without_carrying_other_brand():
    original = append_receiving_set(_layout())
    for si in (0, 1):
        original = update_receiving_bay(
            original, set_index=si, bay_index=0,
            nfb_config_submitted=True, nfb_config=_ac40_submitted_parent_brand_config(),
        )
    frozen = deepcopy(original)
    adapter = ReceivingSetBayAdapter(original)
    before_selection = adapter.selection
    assert adapter.set_global_brand("三菱") is True
    assert [s["switch_brand"] for s in adapter.layout["sets"]] == ["三菱", "三菱"]
    for set_row in adapter.layout["sets"]:
        holes = set_row["bays"][0]["nfb_config"]["holes"]
        assert [h["manual_x_state"] for h in holes] == [
            "RECONFIRM_REQUIRED", "CONFIRMED",
        ]
        assert [h["manual_x_mm"] for h in holes] == [0, 100]
    assert adapter.selection == before_selection
    assert adapter.set_global_brand("三菱") is False
    assert original == frozen
    with pytest.raises(ValueError, match="開關品牌"):
        adapter.set_global_brand("無效廠牌")
    assert [s["switch_brand"] for s in adapter.layout["sets"]] == ["三菱", "三菱"]



@pytest.mark.parametrize("bad_index", (
    True, False, 1.0, 1.5, -1, 2, "1.5", None, [], {},
))
def test_ac07_native_layer_resize_rejects_aliases_before_selection_and_dirty(bad_index):
    """Original GUI must never select a different physical Set via int() alias."""
    adapter = ReceivingSetBayAdapter(_layout())
    switch = ReceivingSwitchProjectionAdapter(adapter)
    calls = []
    service = SimpleNamespace(
        receiving_switch_adapter=lambda _: switch,
        mark_receiving_switch_layout_dirty=lambda *args: calls.append("dirty"),
        refresh_receiving_set_bay_control=lambda *args: calls.append("refresh"),
    )
    frozen = adapter.layout
    old_selection = adapter.selection
    with pytest.raises((IndexError, ValueError, TypeError)):
        native_gui_resize_receiving_bays(service, None, bad_index, 1)
    assert adapter.layout == frozen
    assert adapter.selection == old_selection
    assert calls == []


@pytest.mark.parametrize("bad_delta", (
    True, False, 1.0, 1.5, "1.5", None, [], {},
))
def test_ac07_native_layer_resize_rejects_bad_delta_without_touching_set(bad_delta):
    """Delta validation must precede both Set selection and destructive resize."""
    adapter = ReceivingSetBayAdapter(append_receiving_set(_layout()))
    switch = ReceivingSwitchProjectionAdapter(adapter)
    calls = []
    service = SimpleNamespace(
        receiving_switch_adapter=lambda _: switch,
        mark_receiving_switch_layout_dirty=lambda *args: calls.append("dirty"),
        refresh_receiving_set_bay_control=lambda *args: calls.append("refresh"),
    )
    before = adapter.layout
    selection = adapter.selection
    with pytest.raises((TypeError, ValueError)):
        native_gui_resize_receiving_bays(service, None, 1, bad_delta)
    assert adapter.layout == before
    assert adapter.selection == selection
    assert calls == []


def test_ac07_native_layer_resize_keeps_exact_integer_text_and_actual_bays():
    """Textual integer UI arguments are allowed, without silently aliasing IDs."""
    adapter = ReceivingSetBayAdapter(_layout())
    switch = ReceivingSwitchProjectionAdapter(adapter)
    calls = []
    service = SimpleNamespace(
        receiving_switch_adapter=lambda _: switch,
        mark_receiving_switch_layout_dirty=lambda *args: calls.append("dirty"),
        refresh_receiving_set_bay_control=lambda *args: calls.append("refresh"),
    )
    assert native_gui_resize_receiving_bays(service, None, "0", "1") is True
    assert switch.connection_counts() == (2,)
    assert adapter.selection.set_index == 0
    assert calls == ["dirty", "refresh"]
    assert native_gui_resize_receiving_bays(service, None, 0, 0) is False
    assert calls == ["dirty", "refresh"]
    for bad in (-1, 1, True, 0.5):
        with pytest.raises((IndexError, ValueError)):
            switch.connection_count(bad)
    assert switch.connection_count("0") == 2



@pytest.mark.parametrize("invalid_joint", (
    True, False, 0.5, 1.0, 1.5, "1.5", None, [], {}, -1, 2,
))
def test_ac07_joint_operator_rejects_bool_fraction_or_nested_without_moving_mating_joint(
    invalid_joint,
):
    """The original Receiving topology has physical Joints, not Python aliases."""
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=3)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, depth=500, height=1800)
    layout = update_receiving_bay(layout, set_index=0, bay_index=2, depth=620, height=1900)
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout
    with pytest.raises((IndexError, ValueError), match="integer|out of range"):
        adapter.current_joint_editability(invalid_joint)
    with pytest.raises((IndexError, ValueError), match="integer|out of range"):
        adapter.update_joint_alignment(
            invalid_joint, depth_alignment="REAR", height_alignment="TOP",
        )
    assert adapter.layout == before
    assert adapter.selection.set_index == 0
    assert adapter.selection.bay_index == 0


def test_ac07_joint_operator_preserves_exact_integer_text_and_physical_mating():
    """Do not change placement geometry; only validate original physical Joint ID."""
    layout = resize_receiving_bays(_layout(), set_index=0, bay_count=3)
    layout = update_receiving_bay(layout, set_index=0, bay_index=1, depth=500, height=1800)
    layout = update_receiving_bay(layout, set_index=0, bay_index=2, depth=620, height=1900)
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout
    assert adapter.current_joint_editability("1") == {
        "depth_alignment": True,
        "height_alignment": True,
    }
    adapter.update_joint_alignment("1", depth_alignment="REAR", height_alignment="TOP")
    after = adapter.layout
    assert after["sets"][0]["joints"][0] == before["sets"][0]["joints"][0]
    assert after["sets"][0]["joints"][1]["depth_alignment"] == "REAR"
    assert after["sets"][0]["joints"][1]["height_alignment"] == "TOP"
    assert [x["stable_id"] for x in after["sets"][0]["joints"]] == [
        x["stable_id"] for x in before["sets"][0]["joints"]
    ]


def test_native_receiving_bay_wh_edit_recompletes_last_door_cells():
    """W800→820 entered in the real Receiving GUI must not break FinalScene."""
    authored = update_receiving_bay(
        _layout(), set_index=0, bay_index=0,
        door_state={
            "multi_door_enabled": True,
            "door_layout_scope": "receiving-main",
            "door_layout_columns": [
                [300.0, [1100.0, 500.0]],
                [500.0, [800.0, 800.0]],
            ],
            "inner_doors": [],
        },
    )
    original = deepcopy(authored)
    adapter = ReceivingSetBayAdapter(authored)
    assert adapter.update_current_bay(width=820, height=1700)
    actual = adapter.current_bay()
    assert actual["width"] == pytest.approx(820)
    assert actual["height"] == pytest.approx(1700)
    assert actual["door_state"]["door_layout_columns"] == [
        [300.0, [1100.0, 600.0]],
        [520.0, [800.0, 900.0]],
    ]
    # Real current-Bay projection must accept the updated Door, not the stale
    # W800 door that caused the user's native 3D load failure.
    projected = project_receiving_bay_legacy_aliases(
        _snapshot(adapter.layout), set_index=0, bay_index=0,
    )
    assert (projected["w"], projected["h"]) == pytest.approx((820, 1700))
    assert projected["door_layout_columns"] == actual["door_state"]["door_layout_columns"]
    assert authored == original


def test_native_receiving_bay_dimension_edit_rejects_impossible_existing_door():
    authored = update_receiving_bay(
        _layout(), set_index=0, bay_index=0,
        door_state={
            "multi_door_enabled": True,
            "door_layout_columns": [[300.0, [1100.0, 500.0]], [500.0, [800.0, 800.0]]],
        },
    )
    adapter = ReceivingSetBayAdapter(authored)
    original = deepcopy(adapter.layout)
    # Operator-owned first column/row must NOT be silently shrunk to force fit.
    with pytest.raises(ValueError, match="新 W 不符合門分割"):
        adapter.update_current_bay(width=250)
    assert adapter.layout == original
    with pytest.raises(ValueError, match="新 H 不符合門分割"):
        adapter.update_current_bay(height=900)
    assert adapter.layout == original


def test_explicit_new_receiving_door_partition_keeps_canonical_validation():
    authored = update_receiving_bay(
        _layout(), set_index=0, bay_index=0,
        door_state={
            "multi_door_enabled": True,
            "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        },
    )
    # A caller directly authoring a stale W800 partition while moving to
    # W820 must still be rejected, not 'fixed' behind the operator's back.
    invalid = update_receiving_bay(
        authored, set_index=0, bay_index=0, width=820,
        door_state={"multi_door_enabled": True, "door_layout_columns": [[800.0, [1100.0, 500.0]]]},
    )
    with pytest.raises(ReceivingBayProjectionError, match="expected W=820"):
        project_receiving_bay_legacy_aliases(_snapshot(invalid), set_index=0, bay_index=0)


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="native Windows Tk or Linux display required",
)
def test_native_receiving_designer_cold_start_does_not_commit_provisional_500_600():
    """Original MainApp's cold-start render is not a Bay dimension transaction."""
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    main = gui.BoxCalculatorGUI(root)
    try:
        main.baseline_var.set("受電箱")
        root.update()
        designer = main.open_original_fold_designer()
        root.update()
        bay = designer._phase6_input_snapshot["receiving_layout"]["sets"][0]["bays"][0]
        assert (bay["width"], bay["height"], bay["depth"]) == pytest.approx(
            (800.0, 1600.0, 350.0)
        )
        # This must not trigger the W500/H600 stale partition rejection
        # observed in CI before the _phase6_sync_ready bootstrap guard.
        projected = project_receiving_bay_legacy_aliases(
            designer._phase6_input_snapshot, set_index=0, bay_index=0
        )
        assert projected["w"] == pytest.approx(800.0)
        assert projected["h"] == pytest.approx(1600.0)
    finally:
        try:
            if main.fold_designer_window is not None:
                main.fold_designer_window.destroy()
        except tk.TclError:
            pass
        root.destroy()


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="native Windows Tk or Linux display required",
)
def test_native_receiving_w820_divider_profile_real_world_cross_green():
    """Original native Tk W800→820 must refold physical Divider at 816, not 796."""
    import time
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    main = gui.BoxCalculatorGUI(root)
    try:
        main.baseline_var.set("受電箱")
        root.update()
        designer = main.open_original_fold_designer()
        root.update()
        divider_keys = tuple(
            key for key in designer.designer_workspace.available_parts
            if key.startswith("box_body:divider:") and ":HORIZONTAL:" in key
        )
        assert len(divider_keys) == 1
        key = divider_keys[0]
        assert designer.designer_workspace.profiles_for(key)["Y"][0]["len"] == pytest.approx(796)
        designer.v_w.set("820")
        for _ in range(9):
            root.update()
            time.sleep(0.08)
        bay = designer._phase6_input_snapshot["receiving_layout"]["sets"][0]["bays"][0]
        assert bay["width"] == pytest.approx(820)
        assert sum(
            row[0] for row in bay["door_state"]["door_layout_columns"]
        ) == pytest.approx(820)
        assert designer.designer_workspace.profiles_for(key)["Y"][0]["len"] == pytest.approx(816)
        # Source-certified CROSS stays enabled: assert the actual native
        # renderer no longer reports its genuine 3D contact failure.
        visible = "\\n".join(
            text.get_text() for axis in designer.fig.axes for text in axis.texts
        )
        assert "inverse CROSS leaves real 3D collision unrelieved" not in visible
        assert "3D Final Part Geometry 載入失敗" not in visible
        assert "中隔：展開外框 158 × 816 mm" in visible
    finally:
        try:
            if main.fold_designer_window is not None:
                main.fold_designer_window.destroy()
        except tk.TclError:
            pass
        root.destroy()


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="native Tk display required",
)
def test_native_receiving_thickness_change_keeps_committed_bay_whd_and_custom():
    """Real Tk W820/H1700/D360 then T2.5 must never revive old W800/D350.

    Regression from actual Windows R5-2600 116-item GUI UAT. The failure was
    Settings-flush save_current_part() reading a stale box-body fold editor,
    even though the committed Bay and live Box were already W820/D360.
    """
    import time
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    main = gui.BoxCalculatorGUI(root)
    try:
        main.baseline_var.set("受電箱")
        root.update()
        designer = main.open_original_fold_designer()
        root.update()
        for axis, value in (("w", "820"), ("h", "1700"), ("d", "360")):
            getattr(designer, "v_" + axis).set(value)
            root.update()
        for _ in range(6):
            time.sleep(.14)
            root.update()
        source = designer._phase6_input_snapshot
        assert tuple(float(source[k]) for k in ("w", "h", "d")) == (820, 1700, 360)
        assert tuple(float(designer._phase6_box_whd[k]) for k in ("w", "h", "d")) == (820, 1700, 360)
        assert tuple(float(designer._settings_values[k]) for k in ("w", "h", "d")) == (800, 1600, 350)

        # This is a real, operator-writable Tk control, not fabricated source.
        designer.left_global_vars["t"].set("2.5")
        for _ in range(6):
            time.sleep(.14)
            root.update()
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t")) == (
            820, 1700, 360, 2.5
        )
        assert tuple(float(designer._phase6_box_whd[k]) for k in ("w", "h", "d")) == (820, 1700, 360)
        assert tuple(float(getattr(designer, "v_" + k).get()) for k in ("w", "h", "d")) == (820, 1700, 360)

        designer.baseline_model_var.set("自訂")
        root.update()
        assert tuple(float(designer._phase6_input_snapshot[k]) for k in ("w", "h", "d", "t")) == (
            820, 1700, 360, 2.5
        )
    finally:
        try:
            if main.fold_designer_window is not None:
                main.fold_designer_window.destroy()
        except tk.TclError:
            pass
        root.destroy()


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="real native Windows Tk or Linux Xvfb required",
)
@pytest.mark.parametrize("commit", [True, False], ids=["confirm", "cancel"])
def test_audit116_primary_receiving_door_cell_session_return_is_authoritative(
    monkeypatch, tmp_path, commit,
):
    """Real PRIMARY Tk cell owner + actual WHD Session: commit/rollback is atomic.

    This captures the normal hole editor's feature-list and sync callback, but
    does not emulate external CADCraft mouse actions or certify manufacturing.
    The legacy main.surface_features setter is explicitly not the input.
    """
    import tkinter as tk

    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession

    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.fold_designer_app
        assert app._phase6_primary_workspace is True
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()

        physical_key = "door_c1_r1"
        assert physical_key in designer.designer_workspace.available_parts
        captured = {}

        def capture_real_editor_call(part_key, title, surface, width, height, **kwargs):
            assert part_key == "door"
            assert "C1-R1" in title
            assert width > 0 and height > 0
            captured["features"] = kwargs["feature_list_override"]
            captured["sync"] = kwargs["sync_callback"]

        monkeypatch.setattr(app, "_open_unified_hole_editor", capture_real_editor_call)
        app.open_door_layout_cell_editor(0, 0)
        assert callable(captured.get("sync"))
        features = captured["features"]
        assert features == designer.designer_workspace.features_for(physical_key)
        before = list(features)

        session = Phase6HoleEditorSession("door", features)
        new_hole = CircleFeature(
            diameter=12.0,
            anchor=FeatureAnchor.PANEL_CENTER,
            offset=Vec2(-20.0, 0.0),
            layer="CUTTING",
        )
        session.execute(HoleEditorAction.insert(new_hole))
        session.execute(HoleEditorAction.commit_active())
        session.finish(commit=commit)
        # The actual hole editor calls this callback on both Confirm and
        # Cancel; the Session has already committed or rolled back by then.
        captured["sync"]()
        root.update_idletasks()
        root.update()
        expected = [*before, new_hole] if commit else before

        assert features == expected
        assert designer.designer_workspace.features_for(physical_key) == expected
        assert app.surface_features.get(physical_key, []) == expected
        assert app.workspace_controller.part_features_snapshot()[physical_key] == expected
        project = app._compose_phase6_project_snapshot_from_main_gui()
        assert project["part_features"][physical_key] == expected

        if commit:
            from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
            project_path = tmp_path / "primary-receiving-cell-confirmed.p6fold"
            write_project(project_path, {
                "schema": PROJECT_SCHEMA,
                "saved_at": "2026-10-28T11:00:00+08:00",
                "snapshot": project,
                "final_geometry": {},
            })
            reopened = read_project(project_path)["snapshot"]
            assert reopened["part_features"][physical_key] == expected
    finally:
        # The primary FoldDesigner shares the root and may already have
        # destroyed it through a legitimate source/session update.
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="real native Windows Tk or Linux Xvfb required",
)
@pytest.mark.parametrize("confirm_deletion", [True, False], ids=["delete-confirm", "delete-cancel"])
def test_audit116_bug2_primary_door_hole_delete_does_not_resurrect_stale_source(
    monkeypatch, tmp_path, confirm_deletion,
):
    """Original audit BUG #2: real PRIMARY cell delete/Cancel survives source sync + reload.

    Drive the actual production Receiving cell entry and committed Session
    callback, not the old BoxCalculatorGUI.surface_features surrogate.
    External CADCraft mouse/NC/visual sign-off is deliberately not claimed.
    """
    import tkinter as tk

    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.fold_designer_app
        assert app._phase6_primary_workspace is True
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()

        physical_key = "door_c1_r1"
        assert physical_key in designer.designer_workspace.available_parts
        calls = []

        def capture_editor(part_key, title, surface, width, height, **kwargs):
            assert part_key == "door"
            assert "C1-R1" in title and width > 0 and height > 0
            assert callable(kwargs["sync_callback"])
            calls.append((kwargs["feature_list_override"], kwargs["sync_callback"]))

        monkeypatch.setattr(app, "_open_unified_hole_editor", capture_editor)
        app.open_door_layout_cell_editor(0, 0)
        assert len(calls) == 1
        initial_features, initial_sync = calls[-1]
        before = list(initial_features)
        hole = CircleFeature(
            diameter=13.0, anchor=FeatureAnchor.PANEL_CENTER,
            offset=Vec2(-35.0, -10.0), layer="CUTTING",
        )
        add_session = Phase6HoleEditorSession("door", initial_features)
        add_session.execute(HoleEditorAction.insert(hole))
        add_session.execute(HoleEditorAction.commit_active())
        add_session.finish(commit=True)
        initial_sync()
        root.update_idletasks()
        root.update()

        present = [*before, hole]
        assert designer.designer_workspace.features_for(physical_key) == present
        assert app.surface_features.get(physical_key, []) == present
        assert app.workspace_controller.part_features_snapshot()[physical_key] == present

        # Reopen the *same* real cell rather than overwriting an old fake alias.
        app.open_door_layout_cell_editor(0, 0)
        assert len(calls) == 2
        current_features, current_sync = calls[-1]
        assert current_features == present
        removal = Phase6HoleEditorSession("door", current_features)
        removal.execute(HoleEditorAction.select(len(before)))
        removal.execute(HoleEditorAction.delete_selected())
        removal.finish(commit=confirm_deletion)
        current_sync()
        root.update_idletasks()
        root.update()

        expected = before if confirm_deletion else present
        assert current_features == expected
        assert designer.designer_workspace.features_for(physical_key) == expected
        assert app.surface_features.get(physical_key, []) == expected
        assert app.workspace_controller.part_features_snapshot()[physical_key] == expected
        project = app._compose_phase6_project_snapshot_from_main_gui()
        assert project["part_features"][physical_key] == expected

        output = tmp_path / (
            "audit116-bug2-delete-confirmed.p6fold"
            if confirm_deletion else "audit116-bug2-delete-cancelled.p6fold"
        )
        write_project(output, {
            "schema": PROJECT_SCHEMA,
            "saved_at": "2026-10-28T12:00:00+08:00",
            "snapshot": project,
            "final_geometry": {},
        })
        reopened = read_project(output)["snapshot"]
        assert reopened["part_features"][physical_key] == expected
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
