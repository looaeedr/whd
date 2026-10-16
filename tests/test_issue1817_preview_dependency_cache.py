# -*- coding: utf-8 -*-
"""#1817: Receiving per-Bay preview cache respects real spatial dependencies."""
from copy import deepcopy

from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    update_receiving_joint_alignment, project_receiving_bay_legacy_aliases,
    receiving_bay_assembly_offsets,
)
from gui_modules.application.fold_designer_composition_receiving import (
    _receiving_bay_preview_fingerprint_snapshot,
)
from phase6_sync_envelope import stable_fingerprint


def _layout(count=4):
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=count,
    )


def _key(layout, bay_index, *, selective=True, **extra):
    projected = project_receiving_bay_legacy_aliases(
        {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":layout, **extra},
        set_index=0, bay_index=bay_index, validate_common=False,
    )
    key_input = (_receiving_bay_preview_fingerprint_snapshot(
        projected, set_index=0, bay_index=bay_index) if selective else projected)
    return stable_fingerprint(key_input)


def test_issue1817_distant_trailing_dimension_change_reuses_earlier_preview():
    original = _layout()
    copy_before = deepcopy(original)
    edited = update_receiving_bay(
        original, set_index=0, bay_index=3, width=950, height=1800, depth=415)
    assert original == copy_before
    assert _key(original, 0, selective=False) != _key(edited, 0, selective=False)
    assert _key(original, 0) == _key(edited, 0)
    assert _key(original, 1) == _key(edited, 1)
    # Bay3's right Joint and Bay4's own sheet must still re-resolve.
    assert _key(original, 2) != _key(edited, 2)
    assert _key(original, 3) != _key(edited, 3)
    for i in (0, 1):
        assert receiving_bay_assembly_offsets(original)[i] == (
            receiving_bay_assembly_offsets(edited)[i])


def test_issue1817_left_neighbor_and_prefix_dimension_changes_are_not_reused():
    original = _layout()
    edited = update_receiving_bay(
        original, set_index=0, bay_index=1, width=980, height=1900, depth=480)
    for i in range(4):
        assert _key(original, i) != _key(edited, i)
    assert receiving_bay_assembly_offsets(original)[2] != (
        receiving_bay_assembly_offsets(edited)[2])


def test_issue1817_joint_metadata_non_dimension_data_and_topology_invalidate():
    original = _layout()
    key = _key(original, 0)
    # Keep all joint records even if a changed joint is distant.
    changed = update_receiving_bay(original, set_index=0, bay_index=3, depth=460)
    changed = update_receiving_joint_alignment(
        changed, set_index=0, joint_index=2, depth_alignment="REAR")
    assert _key(changed, 0) != key
    changed = update_receiving_bay(
        original, set_index=0, bay_index=3,
        door_state={"multi_door_enabled":False})
    assert _key(changed, 0) != key
    changed = resize_receiving_bays(original, set_index=0, bay_count=5)
    assert _key(changed, 0) != key


def test_issue1817_key_projection_never_mutates_authority_and_fails_closed():
    source = {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":_layout()}
    before = deepcopy(source)
    reduced = _receiving_bay_preview_fingerprint_snapshot(
        source, set_index=0, bay_index=0)
    assert source == before
    assert "width" not in reduced["receiving_layout"]["sets"][0]["bays"][3]
    assert "width" in reduced["receiving_layout"]["sets"][0]["bays"][1]
    for candidate in (
        {**source, "active_mode":"quantity"},
        {**source, "model":"金庫型"},
        {**source, "receiving_layout":{"schema":"unknown","sets":[]}},
    ):
        assert _receiving_bay_preview_fingerprint_snapshot(
            candidate, set_index=0, bay_index=0) == candidate


def test_issue1817_noop_and_global_geometry_inputs_preserve_cache_key_policy():
    original = _layout()
    same = update_receiving_bay(
        original, set_index=0, bay_index=3, width=800, height=1600, depth=350)
    assert _key(original, 0) == _key(same, 0)
    assert _key(original, 0, t=2) != _key(original, 0, t=3)
    assert _key(original, 0, assembly_joints=[]) != (
        _key(original, 0, assembly_joints=[{"subject_part":"head"}]))
