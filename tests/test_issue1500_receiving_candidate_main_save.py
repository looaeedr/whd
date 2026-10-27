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


def test_issue1500_real_native_gui_version_apply_save_as_reload(tmp_path, monkeypatch):
    """Reproduce the Windows finding with the real main GUI Save As callback.

    The old implementation persisted Bay1's version_id but lost the global
    inner-door version library. Do not substitute a ProjectController-only
    serialization for the real GUI boundary.
    """
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from gui_modules import project_actions
    from tests.test_issue1503_multi_candidate_nfb_apply_gui import (
        add, buttons, pump, select_two, state_frame,
    )

    root = tk.Tk()
    root.withdraw()
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        pump(root)
        designer = main.open_original_fold_designer()
        pump(root)
        settings = bridge._phase6_open_receiving_multi_settings(designer)
        pump(root)
        assert settings._receiving_multi_apply(0)
        listing = settings._receiving_multi_setting_list
        listing.selection_clear(0, tk.END)
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        pump(root)
        buttons(settings._receiving_multi_settings_host, "編輯")[0].invoke()
        pump(root)
        editor = main.last_unified_hole_editor
        tabs = editor._receiving_config_tabs
        tabs.select(1)
        pump(root)
        modal, state = state_frame(editor)
        select_two(root, modal, state)
        add(root, modal, state, 1)
        buttons(modal, "確定")[0].invoke()
        pump(root)
        assert len(editor._receiving_pending_features()) == 2
        buttons(editor, "確定全部")[0].invoke()
        pump(root)

        library = designer._phase6_input_snapshot["receiving_inner_door_candidates"]
        assert len(inner_versions(library)) == 1
        version = inner_versions(library)[0]["id"]
        selector = settings._receiving_multi_candidate_combos["inner-door"]
        values = tuple(selector["values"])
        assert len(values) > 1
        selector.set(values[-1])
        selector.event_generate("<<ComboboxSelected>>")
        pump(root)
        buttons(settings._receiving_multi_settings_host, "套用")[0].invoke()
        pump(root)
        assert designer._phase6_input_snapshot["receiving_layout"]["sets"][0][
            "bays"
        ][0]["nfb_config"]["layer_count"] == 2

        settings._receiving_multi_close()
        pump(root)
        target = tmp_path / "current_gui_save_as.p6fold"
        monkeypatch.setattr(
            project_actions.filedialog, "asksaveasfilename",
            lambda **_kw: str(target),
        )
        assert main.save_phase6_project_as()
        saved = read_project(target)["snapshot"]
        assert inner_versions(saved["receiving_inner_door_candidates"])[0]["id"] == version
        assert saved["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"][
            "layer_count"
        ] == 2
        adapter = ReceivingSetBayAdapter(saved["receiving_layout"])
        adapter.set_bay_count(2)
        adapter.apply_inner_door_candidate_to_bays(
            inner_config(saved["receiving_inner_door_candidates"], version),
            0, (1,), version_id=version,
        )
        bays = adapter.layout["sets"][0]["bays"]
        assert bays[1]["nfb_config"]["layer_count"] == 2
        assert {h["physical_hole_id"] for h in bays[0]["nfb_config"]["holes"]}.isdisjoint(
            {h["physical_hole_id"] for h in bays[1]["nfb_config"]["holes"]}
        )
    finally:
        root.destroy()


def test_issue1500_main_gui_save_after_editor_close_uses_committed_project():
    source, _, _, version = _source_with_saved_version()
    host = _live_host(source, active=False)
    # The main GUI is a 2D projection and has no candidate in its own
    # reconstructed snapshot. The existing ProjectController owns the last
    # committed complete project once the Fold Designer window is closed.
    host.project_controller = SimpleNamespace(
        committed_snapshot=lambda: deepcopy(source),
    )
    saved = _compose_phase6_project_snapshot_from_main_gui(host)
    assert [row["id"] for row in inner_versions(
        saved["receiving_inner_door_candidates"]
    )] == [version]


def test_issue1500_previous_project_must_not_leak_candidates_after_load():
    source, _, _, _ = _source_with_saved_version()
    host = _live_host(source, active=False)
    host.project_controller = SimpleNamespace(
        committed_snapshot=lambda: {
            "model": "金庫型",
            "receiving_inner_door_candidates": source["receiving_inner_door_candidates"],
        },
    )
    saved = _compose_phase6_project_snapshot_from_main_gui(host)
    assert "receiving_inner_door_candidates" not in saved
