# -*- coding: utf-8 -*-
"""#2517 shared-setting unlink uses canonical Engine refs for physical dirty IDs."""
from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import (
    unlink_setting, unlink_setting_with_affected_ids as owner,
    setting_value,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application.fold_designer_composition_receiving import receiving_settings_ports


def _source():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=5,
    )


def _linked():
    return api.share_receiving_shared_setting(
        _source(), set_index=0, source_bay_index=0,
        bay_indices=(0, 1, 3, 4), kind="back_panel_mode",
    )


def _expected_ids(layout):
    return tuple(layout["sets"][0]["bays"][i]["stable_id"] for i in (0, 1, 3, 4))


def test_public_root_facade_and_existing_unlink_semantics():
    assert api.unlink_receiving_shared_setting_with_affected_ids is owner
    assert ae_engine.unlink_receiving_shared_setting_with_affected_ids is owner
    assert "unlink_receiving_shared_setting_with_affected_ids" in ae_engine.__all__
    raw = _linked()
    before = deepcopy(raw)
    candidate, affected = owner(
        raw, set_index=0, bay_index=1, kind="back_panel_mode",
    )
    assert candidate == unlink_setting(
        raw, set_index=0, bay_index=1, kind="back_panel_mode",
    )
    assert affected == _expected_ids(raw)
    assert raw == before
    assert setting_value(candidate["sets"][0], 1, "back_panel_mode") == "FULL"
    modified = api.edit_receiving_shared_setting(
        candidate, set_index=0, bay_index=0,
        kind="back_panel_mode", value="HALF",
    )
    assert setting_value(modified["sets"][0], 1, "back_panel_mode") == "FULL"


def test_engine_already_independent_noop_returns_no_dirty_ids():
    raw = _source()
    before = deepcopy(raw)
    candidate, affected = owner(
        raw, set_index=0, bay_index=2, kind="back_panel_mode",
    )
    assert affected == ()
    assert candidate == api.unlink_receiving_shared_setting(
        raw, set_index=0, bay_index=2, kind="back_panel_mode",
    )
    assert raw == before


def test_noop_does_not_misclassify_unrelated_equal_values_as_shared_refs():
    layout = _linked()
    candidate, ids = owner(
        layout, set_index=0, bay_index=2, kind="back_panel_mode",
    )
    assert ids == ()  # equal FULL values are independent physical refs
    assert candidate == layout


def test_gui_unlink_tracks_every_former_linked_bay_and_noop_does_not_dirty():
    original = _linked()
    adapter = ReceivingSetBayAdapter(original)
    adapter.select_bay(2)
    assert adapter.unlink_setting("back_panel_mode") is True
    assert adapter._session_dirty_ids == set(_expected_ids(original))
    result = adapter.layout
    assert adapter.unlink_setting("back_panel_mode") is False
    assert adapter._session_dirty_ids == set(_expected_ids(original))
    assert adapter.layout == result
    assert original != result


def test_real_gui_ports_noop_skips_geometry_commit_and_one_unlink_commits_once():
    adapter = ReceivingSetBayAdapter(_linked())
    events = []
    app = SimpleNamespace(
        _phase6_input_snapshot={},
        submit_update_intent=lambda *a, **kw: events.append("intent"),
    )

    class Host:
        def __init__(self):
            self.app = app

        def receiving_adapter(self, namespace):
            return adapter

        def sync_receiving_current_bay(self, namespace):
            events.append("sync")

    ports = receiving_settings_ports(Host(), None, 0)
    ports["select"](2)  # 0-based Bay3 has never shared a ref
    before = deepcopy(adapter.layout)
    assert ports["unlink"]("back_panel_mode") is False
    assert events == []
    assert adapter.layout == before
    assert app._phase6_input_snapshot == {}
    ports["select"](1)  # real Bay2 shares the source ref
    assert ports["unlink"]("back_panel_mode") is True
    assert events == ["sync", "intent"]
    assert app._phase6_input_snapshot["receiving_layout"] == adapter.layout
    assert adapter._session_dirty_ids == set(_expected_ids(_linked()))
    assert ports["unlink"]("back_panel_mode") is False
    assert events == ["sync", "intent"]


@pytest.mark.parametrize("set_index,bay_index,kind", (
    (True, 0, "back_panel_mode"),
    (0, True, "back_panel_mode"),
    (99, 0, "back_panel_mode"),
    (0, -1, "back_panel_mode"),
    (0, 0, "unknown_setting"),
))
def test_invalid_source_fails_closed_without_writing_layout(set_index, bay_index, kind):
    source = _linked()
    before = deepcopy(source)
    with pytest.raises((ValueError, IndexError, KeyError)):
        owner(source, set_index=set_index, bay_index=bay_index, kind=kind)
    assert source == before


def test_saved_unlinked_real_ref_relationship_survives_project_reload(tmp_path):
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project, read_project

    raw = _linked()
    detached, _ids = owner(raw, set_index=0, bay_index=1, kind="back_panel_mode")
    path = write_project(
        tmp_path / "unlink.p6fold", {
            "schema": PROJECT_SCHEMA_V2,
            "snapshot": {"model": "受電箱", "t": 2,
                         "receiving_layout": detached},
            "final_geometry": {},
        },
    )
    loaded = read_project(path)["snapshot"]["receiving_layout"]
    assert loaded == api.normalize_receiving_layout(detached)
    original_ref = loaded["sets"][0]["settings"]["back_panel_mode"]["refs"]
    assert original_ref[loaded["sets"][0]["bays"][1]["stable_id"]] != original_ref[loaded["sets"][0]["bays"][0]["stable_id"]]
    assert original_ref[loaded["sets"][0]["bays"][3]["stable_id"]] == original_ref[loaded["sets"][0]["bays"][0]["stable_id"]]


def test_gui_seams_do_not_guess_refs_or_always_mark_current_bay():
    gui = getsource(ReceivingSetBayAdapter.unlink_setting)
    assert "manufacturing_api.unlink_receiving_shared_setting_with_affected_ids(" in gui
    assert "self._session_dirty_ids.update(affected_ids)" in gui
    assert '["refs"]' not in gui
    assert "self.mark_current_bay_dirty()" not in gui
    source = getsource(receiving_settings_ports)
    assert 'if not adapter.unlink_setting(kind):' in source
