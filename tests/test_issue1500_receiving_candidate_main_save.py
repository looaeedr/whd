# -*- coding: utf-8 -*-
"""#1500 regression: native GUI-created Receiving candidates survive main Save/Reload."""
from copy import deepcopy
from types import SimpleNamespace

from ae_engine.receiving_inner_door_candidates import (
    create_inner_candidate, inner_config, inner_versions,
)
from ae_engine.receiving_hole_candidates import normalize_candidates
from gui_modules.application.lifecycle import (
    _compose_phase6_project_snapshot_from_main_gui,
    _merge_live_receiving_candidate_libraries,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_receiving_fresh_family_autosource import (
    _fresh_set, _two_tier_candidate_with_real_csv,
)


def _live_host(source, *, active=True, window_alive=True):
    """Small main GUI host with the actual Receiving candidate editor authority."""
    original = deepcopy(source)
    # The 2D host's cached snapshot deliberately lacks the newly created
    # candidate; this is exactly the old native Save As failure.
    original.pop("receiving_inner_door_candidates", None)
    original.pop("receiving_hole_candidates", None)
    state = {
        "existing_parts": list(original.get("existing_parts") or ()),
        "part_profiles": deepcopy(original.get("part_profiles") or {}),
        "box_body_structure": deepcopy(original.get("box_body_structure") or {}),
        "box_body_profile": deepcopy(original.get("box_body_profile") or []),
    }
    return SimpleNamespace(
        _make_original_fold_designer_snapshot=lambda: deepcopy(original),
        workspace_controller=SimpleNamespace(
            workspace_snapshot=lambda: deepcopy(state),
        ),
        fold_designer_app=(
            SimpleNamespace(_phase6_input_snapshot=deepcopy(source))
            if active else None
        ),
        fold_designer_window=(
            SimpleNamespace(winfo_exists=lambda: window_alive)
            if active else None
        ),
        endcap_fw_state={},
        endcap_bottom_wrap_state={},
    )


def _source_with_saved_version():
    original = _fresh_set()
    candidate_config, part_id = _two_tier_candidate_with_real_csv(original)
    library, version_id = create_inner_candidate(None, candidate_config)
    source = deepcopy(original)
    source["receiving_inner_door_candidates"] = library
    source["receiving_hole_candidates"] = normalize_candidates(None)
    return source, candidate_config, part_id, version_id


def test_issue1500_main_gui_project_snapshot_carries_live_version_library():
    source, _, _, version = _source_with_saved_version()
    host = _live_host(source)
    composed = _compose_phase6_project_snapshot_from_main_gui(host)

    assert [row["id"] for row in inner_versions(
        composed["receiving_inner_door_candidates"]
    )] == [version]
    assert "receiving_hole_candidates" in composed
    assert "receiving_inner_door_candidates" not in host._make_original_fold_designer_snapshot()
    # Capture is a copy; modifying the .p6fold candidate cannot mutate live UI.
    composed["receiving_inner_door_candidates"]["versions"].clear()
    assert len(source["receiving_inner_door_candidates"]["versions"]) == 1


def test_issue1500_native_candidate_main_save_reload_second_bay_apply(tmp_path):
    source, original_candidate, part_id, version_id = _source_with_saved_version()
    host = _live_host(source)
    main_snapshot = _compose_phase6_project_snapshot_from_main_gui(host)
    output = tmp_path / "issue1500_v5_main_gui_version_library.p6fold"
    write_project(output, {
        "schema": PROJECT_SCHEMA,
        "saved_at": "2026-10-27T19:20:00+08:00",
        "snapshot": main_snapshot,
        "final_geometry": {},
    })

    reopened = read_project(output)["snapshot"]
    library = reopened["receiving_inner_door_candidates"]
    assert inner_config(library, version_id) == original_candidate
    assert reopened["receiving_layout"]["sets"][0]["bays"][0]["nfb_config_submitted"] is True

    adapter = ReceivingSetBayAdapter(reopened["receiving_layout"])
    adapter.set_bay_count(2)
    first_before = deepcopy(adapter.layout["sets"][0]["bays"][0])
    assert adapter.apply_inner_door_candidate_to_bays(
        inner_config(library, version_id), 0, (1,), version_id=version_id,
    ) == (1,)
    bays = adapter.layout["sets"][0]["bays"]
    assert bays[0] == first_before
    assert bays[1]["nfb_config_submitted"] is True
    assert bays[1]["nfb_config"]["layer_count"] == 2
    left = {hole["physical_hole_id"] for hole in bays[0]["nfb_config"]["holes"]}
    right = {hole["physical_hole_id"] for hole in bays[1]["nfb_config"]["holes"]}
    assert right.isdisjoint(left)
    assert all(hole.startswith(bays[1]["stable_id"] + ":") for hole in right)
    assert len(bays[1]["nfb_config"]["holes"]) == 2
    assert all(hole["manual_x_state"] != "CONFIRMED"
               for hole in bays[1]["nfb_config"]["holes"])
    assert part_id in inner_config(library, version_id)["features"]


def test_issue1500_live_candidate_delete_never_resurrects_stale_host_copy():
    source, _, _, _ = _source_with_saved_version()
    host = _live_host(source)
    stale = deepcopy(source)
    host._make_original_fold_designer_snapshot = lambda: deepcopy(stale)
    del host.fold_designer_app._phase6_input_snapshot["receiving_inner_door_candidates"]
    merged = _compose_phase6_project_snapshot_from_main_gui(host)
    assert "receiving_inner_door_candidates" not in merged
    assert "receiving_hole_candidates" in merged


def test_issue1500_closed_or_absent_designer_does_not_overwrite_main_state():
    source, _, _, _ = _source_with_saved_version()
    for active, exists in ((False, False), (True, False)):
        host = _live_host(source, active=active, window_alive=exists)
        cached = deepcopy(source)
        host._make_original_fold_designer_snapshot = lambda: deepcopy(cached)
        actual = _compose_phase6_project_snapshot_from_main_gui(host)
        assert actual["receiving_inner_door_candidates"] == (
            source["receiving_inner_door_candidates"]
        )


def test_issue1500_different_family_does_not_import_stale_receiving_versions():
    source, _, _, _ = _source_with_saved_version()
    host = _live_host(source)
    vault = {"model": "金庫型", "some_field": True}
    assert _merge_live_receiving_candidate_libraries(host, vault) is vault
    assert "receiving_inner_door_candidates" not in vault
