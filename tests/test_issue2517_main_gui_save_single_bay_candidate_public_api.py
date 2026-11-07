"""#2517 main GUI saved singleton Bay and candidate libraries use public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_hole_candidates import normalize_candidates
from ae_engine.receiving_inner_door_candidates import normalize_inner_candidates
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
)
from gui_modules.application import lifecycle as gui


def _source():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        door_state={"inner_doors": [{"offset_mm": 80}], "multi_door_enabled": False},
    )
    return {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
        "inner_doors": [{"offset_mm": 70}, {"offset_mm": 105}],
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [800.0, 800.0]]],
        "door_handle_edges": {"door_c0_r0": "LEFT"},
        "door_layout_scope": "main",
        "door_nameplate_center_datum_top": 85.0,
    }


def _save_host(source):
    workspace = {
        "existing_parts": ["box_body", "head", "tail", "door"],
        "active_part": "door",
        "part_profiles": {},
        "box_body_structure": {},
        "receiving_layout": deepcopy(source.get("receiving_layout")),
    }
    return SimpleNamespace(
        _make_original_fold_designer_snapshot=lambda: deepcopy(source),
        workspace_controller=SimpleNamespace(workspace_snapshot=lambda: deepcopy(workspace)),
        endcap_fw_state={},
        fold_designer_app=None,
        fold_designer_window=None,
        project_controller=SimpleNamespace(committed_snapshot=lambda: None),
    )


def test_engine_root_facade_normalizers_share_original_owners():
    assert ae_engine.normalize_receiving_hole_candidates is api.normalize_receiving_hole_candidates
    assert api.normalize_receiving_hole_candidates is normalize_candidates
    assert ae_engine.normalize_receiving_inner_door_candidates is api.normalize_receiving_inner_door_candidates
    assert api.normalize_receiving_inner_door_candidates is normalize_inner_candidates
    for public, original in (
        (api.normalize_receiving_hole_candidates, normalize_candidates),
        (api.normalize_receiving_inner_door_candidates, normalize_inner_candidates),
    ):
        raw = original()
        before = deepcopy(raw)
        assert public(raw) == original(raw)
        assert raw == before


def test_main_gui_save_matches_engine_singleton_door_state_without_borrowing_source():
    source = _source()
    before = deepcopy(source)
    expected = api.project_receiving_single_bay_door_controls(source)
    saved = gui._compose_phase6_project_snapshot_from_main_gui(_save_host(source))
    assert source == before
    assert saved["receiving_layout"] == expected
    door = saved["receiving_layout"]["sets"][0]["bays"][0]["door_state"]
    assert door["inner_doors"] == source["inner_doors"]
    assert door["door_nameplate_center_datum_top"] == 85.0
    door["inner_doors"][0]["offset_mm"] = 999
    assert source == before


@pytest.mark.parametrize("change", ("multi_bay", "quantity", "vault", "no_door"))
def test_main_gui_save_does_not_replace_non_owned_bay_door_source(change):
    source = _source()
    if change == "multi_bay":
        source["receiving_layout"] = resize_receiving_bays(
            source["receiving_layout"], set_index=0, bay_count=2,
        )
    elif change == "quantity":
        source["active_mode"] = "quantity"
    elif change == "vault":
        source["model"] = "金庫型"
    else:
        source["inner_doors"] = []
    original_layout = deepcopy(source["receiving_layout"])
    saved = gui._compose_phase6_project_snapshot_from_main_gui(_save_host(source))
    assert saved["receiving_layout"] == original_layout


def test_main_gui_singleton_corrupt_source_fails_closed_without_changing_input():
    source = _source()
    source["receiving_layout"]["sets"][0] = "invalid"
    before = deepcopy(source)
    with pytest.raises(ValueError, match="SINGLE_BAY_SET_SOURCE_INVALID"):
        gui._compose_phase6_project_snapshot_from_main_gui(_save_host(source))
    assert source == before


def _live_host(live=None, committed=None):
    return SimpleNamespace(
        fold_designer_app=(
            SimpleNamespace(_phase6_input_snapshot=live) if live is not None else None
        ),
        fold_designer_window=(
            SimpleNamespace(winfo_exists=lambda: True) if live is not None else None
        ),
        project_controller=SimpleNamespace(committed_snapshot=lambda: committed),
    )


def test_main_gui_live_candidate_save_uses_public_normalizers_and_detached_results(monkeypatch):
    hole = api.normalize_receiving_hole_candidates()
    inner = api.normalize_receiving_inner_door_candidates()
    live = {
        "model": "受電箱",
        "receiving_hole_candidates": hole,
        "receiving_inner_door_candidates": inner,
    }
    observed = []
    real_hole = api.normalize_receiving_hole_candidates
    real_inner = api.normalize_receiving_inner_door_candidates

    def track_hole(raw):
        observed.append("hole")
        return real_hole(raw)

    def track_inner(raw):
        observed.append("inner")
        return real_inner(raw)

    monkeypatch.setattr(api, "normalize_receiving_hole_candidates", track_hole)
    monkeypatch.setattr(api, "normalize_receiving_inner_door_candidates", track_inner)
    saved = {"model": "受電箱"}
    assert gui._merge_live_receiving_candidate_libraries(
        _live_host(live=live), saved,
    ) is saved
    assert observed == ["hole", "inner"]
    assert saved["receiving_hole_candidates"] == hole
    assert saved["receiving_inner_door_candidates"] == inner
    saved["receiving_hole_candidates"]["head"]["next_number"] = 99
    assert live["receiving_hole_candidates"] == hole


def test_candidate_library_pair_rejects_invalid_second_without_partial_write():
    old = {"model": "受電箱",
           "receiving_hole_candidates": {"original": "hole"},
           "receiving_inner_door_candidates": {"original": "inner"}}
    before = deepcopy(old)
    live = {
        "model": "受電箱",
        "receiving_hole_candidates": api.normalize_receiving_hole_candidates(),
        "receiving_inner_door_candidates": {"invalid": "candidate"},
    }
    with pytest.raises(ValueError):
        gui._merge_live_receiving_candidate_libraries(_live_host(live=live), old)
    assert old == before
    with pytest.raises(ValueError):
        gui._merge_live_receiving_candidate_libraries(
            _live_host(committed=live), old,
        )
    assert old == before


def test_missing_live_candidate_deletes_old_version_but_committed_fallback_only_copies():
    saved = {
        "model": "受電箱",
        "receiving_hole_candidates": {"stale": "hole"},
        "receiving_inner_door_candidates": {"stale": "inner"},
    }
    live = {
        "model": "受電箱",
        "receiving_hole_candidates": api.normalize_receiving_hole_candidates(),
    }
    gui._merge_live_receiving_candidate_libraries(_live_host(live=live), saved)
    assert saved["receiving_hole_candidates"] == live["receiving_hole_candidates"]
    assert "receiving_inner_door_candidates" not in saved

    old_inner = {"stale": "inner"}
    closed = {"model": "受電箱", "receiving_inner_door_candidates": old_inner}
    gui._merge_live_receiving_candidate_libraries(_live_host(committed=live), closed)
    assert closed["receiving_inner_door_candidates"] is old_inner
    assert closed["receiving_hole_candidates"] == live["receiving_hole_candidates"]


def test_main_gui_saved_receiving_door_survives_real_project_save_reload(tmp_path):
    import phase6_project_file as project

    source = _source()
    source.update({"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 25.0})
    saved = gui._compose_phase6_project_snapshot_from_main_gui(_save_host(source))
    target = project.write_project(
        tmp_path / "receiving-single-bay.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    restored = project.read_project(target)
    door = restored["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]["door_state"]
    assert door["inner_doors"] == source["inner_doors"]
    assert door["door_nameplate_center_datum_top"] == 85.0


def test_main_gui_door_and_candidates_have_no_private_engine_mutation_imports():
    save_source = inspect.getsource(gui._compose_phase6_project_snapshot_from_main_gui)
    assert "manufacturing_api.project_receiving_single_bay_door_controls(" in save_source
    assert "update_receiving_bay(" not in save_source
    assert "RECEIVING_DOOR_STATE_KEYS" not in save_source
    candidate_source = inspect.getsource(gui._merge_live_receiving_candidate_libraries)
    assert "manufacturing_api.normalize_receiving_hole_candidates" in candidate_source
    assert "manufacturing_api.normalize_receiving_inner_door_candidates" in candidate_source
    assert "from ae_engine.receiving_" not in candidate_source
