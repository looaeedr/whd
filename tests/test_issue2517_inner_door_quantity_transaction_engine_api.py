# -*- coding: utf-8 -*-
"""#2517: Whole Receiving inner-door quantity Apply belongs to Engine, not GUI."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_inner_door_candidates import create_inner_candidate
from ae_engine.receiving_layout import append_receiving_set
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version
from phase6_project_file import _encode, _decode


def _two_set_csv_allocation():
    source, config, part_id, version = _source_with_saved_version()
    layout = append_receiving_set(source["receiving_layout"])
    library = source["receiving_inner_door_candidates"]
    assignments = {(0, 0): version, (1, 0): version}
    return layout, library, config, part_id, version, assignments


def test_headless_two_set_csv_allocation_real_bay_ids_and_save_reload():
    layout, library, config, part_id, version, assigned = _two_set_csv_allocation()
    unchanged_layout, unchanged_library = deepcopy(layout), deepcopy(library)
    result, ids = manufacturing_api.apply_receiving_inner_door_quantity_configuration(
        layout, library, {version: 2}, assigned, expected_counts=(1, 1),
    )
    assert len(ids) == len(set(ids)) == 2
    assert ids == tuple(row["bays"][0]["stable_id"] for row in result["sets"])
    assert layout == unchanged_layout and library == unchanged_library
    all_hole_ids = []
    for row in result["sets"]:
        bay = row["bays"][0]
        assert bay["nfb_config_submitted"] is True
        assert setting_value(row, 0, "inner_door_version_id") == version
        assert setting_value(row, 0, "inner_door_layers") == config["layers"]
        assert setting_value(row, 0, "inner_door_models") == config["models"]
        for hole in bay["nfb_config"]["holes"]:
            assert hole["manual_x_state"] != "CONFIRMED"
            assert hole["physical_hole_id"].startswith(bay["stable_id"] + ":")
            all_hole_ids.append(hole["physical_hole_id"])
    assert len(all_hole_ids) == len(set(all_hole_ids)) == 4
    roundtrip = _decode(_encode({"receiving_layout": result}))
    assert roundtrip["receiving_layout"] == result


def test_headless_allocation_rejects_topology_drift_and_bool_keys_atomically():
    layout, library, _, _, version, assigned = _two_set_csv_allocation()
    before = deepcopy((layout, library, assigned))
    with pytest.raises(ValueError, match="總連數"):
        manufacturing_api.apply_receiving_inner_door_quantity_configuration(
            layout, library, {version: 2}, assigned, expected_counts=(2,),
        )
    bogus = {(True, 0): version, (1, 0): version}
    with pytest.raises(ValueError, match="配置連位"):
        manufacturing_api.apply_receiving_inner_door_quantity_configuration(
            layout, library, {version: 2}, bogus, expected_counts=(1, 1),
        )
    assert (layout, library, assigned) == before


def test_headless_rejects_untrusted_replacement_before_any_bay_write():
    layout, library, config, part_id, version, assigned = _two_set_csv_allocation()
    untrusted = deepcopy(config)
    untrusted["features"][part_id] = [
        replace(feature, source_type="MANUAL")
        for feature in untrusted["features"][part_id]
    ]
    other_library, other_version = create_inner_candidate(None, untrusted)
    bad_assigned = {(0, 0): version, (1, 0): other_version}
    combined, first_version = create_inner_candidate(None, config)
    combined, second_version = create_inner_candidate(combined, untrusted)
    bad_assigned = {(0, 0): first_version, (1, 0): second_version}
    before = deepcopy((layout, combined))
    with pytest.raises(ValueError, match="雙重 CUTTING"):
        manufacturing_api.apply_receiving_inner_door_quantity_configuration(
            layout, combined, {first_version: 1, second_version: 1},
            bad_assigned, expected_counts=(1, 1),
        )
    assert (layout, combined) == before


def test_gui_adapter_delegates_allocation_to_engine_and_commits_once(monkeypatch):
    layout, library, _, _, version, assigned = _two_set_csv_allocation()
    adapter = ReceivingSetBayAdapter(layout)
    initial_selection = adapter.selection
    original = deepcopy(layout)
    actual = manufacturing_api.apply_receiving_inner_door_quantity_configuration
    calls = []
    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return actual(*args, **kwargs)
    monkeypatch.setattr(
        manufacturing_api, "apply_receiving_inner_door_quantity_configuration",
        record,
    )
    assert adapter.apply_inner_door_quantity_configuration(
        library, {version: 2}, assigned, expected_counts=(1, 1),
    ) == 2
    assert len(calls) == 1
    assert adapter.selection == initial_selection
    assert layout == original
    assert all(row["bays"][0]["nfb_config_submitted"] is True
               for row in adapter.layout["sets"])
