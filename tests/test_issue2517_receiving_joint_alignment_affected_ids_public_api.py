"""#2517 Receiving Joint edit affects only genuinely changed Engine-owned IDs."""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    update_receiving_joint_alignment, receiving_bay_assembly_offsets,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _layout(*, unequal=True, three=False):
    source = new_receiving_layout(width=800, height=1600, depth=350)
    source = resize_receiving_bays(
        source, set_index=0, bay_count=(3 if three else 2),
    )
    if unequal:
        source = update_receiving_bay(
            source, set_index=0, bay_index=1, depth=500, height=1800,
        )
    return source


def test_public_root_and_facade_use_same_engine_joint_transaction():
    assert ae_engine.update_receiving_joint_alignment_with_affected_ids is (
        api.update_receiving_joint_alignment_with_affected_ids
    )
    assert "update_receiving_joint_alignment_with_affected_ids" in ae_engine.__all__


def test_real_joint_change_has_only_its_canonical_physical_id():
    source = _layout()
    original = deepcopy(source)
    expected = update_receiving_joint_alignment(
        source, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    candidate, changed = api.update_receiving_joint_alignment_with_affected_ids(
        source, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    assert candidate == expected
    assert changed == (candidate["sets"][0]["joints"][0]["stable_id"],)
    assert receiving_bay_assembly_offsets(candidate) != receiving_bay_assembly_offsets(source)
    assert source == original


def test_dimension_locked_axes_and_identical_values_do_not_create_false_dirty():
    source = _layout(unequal=False)
    before = deepcopy(source)
    candidate, changed = api.update_receiving_joint_alignment_with_affected_ids(
        source, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    assert candidate == source and changed == ()
    assert source == before
    changed_source = _layout()
    first, affected = api.update_receiving_joint_alignment_with_affected_ids(
        changed_source, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    again, second = api.update_receiving_joint_alignment_with_affected_ids(
        first, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    assert affected and again == first and second == ()


@pytest.mark.parametrize("index,direction", [
    (True, "REAR"), (-1, "REAR"), (3, "REAR"), ("0", "REAR"),
    (0, "INVALID"), (0, []),
])
def test_invalid_usable_joint_target_or_alignment_keeps_source(index, direction):
    source = _layout()
    before = deepcopy(source)
    with pytest.raises((TypeError, ValueError, IndexError)):
        api.update_receiving_joint_alignment_with_affected_ids(
            source, set_index=0, joint_index=index,
            depth_alignment=direction,
        )
    assert source == before


def test_bad_set_identity_fails_without_any_source_change():
    source = _layout()
    prior = deepcopy(source)
    with pytest.raises((TypeError, ValueError, IndexError)):
        api.update_receiving_joint_alignment_with_affected_ids(
            source, set_index=True, joint_index=0,
            depth_alignment="REAR",
        )
    assert source == prior


def test_live_gui_adapter_marks_noop_only_when_real_joint_changes():
    source = _layout(unequal=False)
    adapter = ReceivingSetBayAdapter(source)
    before = adapter.layout
    assert "manufacturing_api.update_receiving_joint_alignment_with_affected_ids(" in (
        getsource(ReceivingSetBayAdapter.update_joint_alignment)
    )
    adapter.update_joint_alignment("0", depth_alignment="REAR", height_alignment="TOP")
    assert adapter.layout == before and adapter._session_dirty_ids == set()
    changed_layout = _layout(three=True)
    adapter = ReceivingSetBayAdapter(changed_layout)
    expected_joint = changed_layout["sets"][0]["joints"][0]["stable_id"]
    adapter.update_joint_alignment("0", depth_alignment="REAR", height_alignment="TOP")
    assert adapter._session_dirty_ids == {expected_joint}
    assert changed_layout["sets"][0]["joints"][0]["depth_alignment"] == "FRONT"
    current = adapter.layout
    adapter.update_joint_alignment(0, depth_alignment="REAR", height_alignment="TOP")
    assert adapter.layout == current
    assert adapter._session_dirty_ids == {expected_joint}


def test_saved_joint_alignment_reload_preserves_engine_assembly_offsets(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
    source = _layout()
    edited, _ = api.update_receiving_joint_alignment_with_affected_ids(
        source, set_index=0, joint_index=0,
        depth_alignment="REAR", height_alignment="TOP",
    )
    snapshot = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2.0,
        "receiving_layout": edited,
    }
    path = write_project(tmp_path / "joint-affected.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": snapshot,
    })
    loaded = read_project(path)["snapshot"]["receiving_layout"]
    assert api.normalize_receiving_layout(loaded) == edited
    assert receiving_bay_assembly_offsets(loaded) == receiving_bay_assembly_offsets(edited)
