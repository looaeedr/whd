# -*- coding: utf-8 -*-
"""#2517: Receiving Head/Tail quantity Apply through public Engine API."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_shared_settings import setting_value
from tests.test_receiving_quantity_allocation_20261011 import _fixture
from phase6_project_file import _encode, _decode


def _assigned(v1, v2):
    return {
        (0, 0): v2, (0, 1): v2, (0, 2): v1,
        (1, 0): v2, (1, 1): v1,
    }


def test_headless_two_set_head_and_tail_versions_are_independent_and_save_safe():
    adapter, library, v1, v2, tail = _fixture()
    before = adapter.layout
    saved_library = deepcopy(library)
    result, ids = manufacturing_api.apply_receiving_endcap_quantity_configuration(
        before, "head", library, {v1: 2, v2: 3}, _assigned(v1, v2),
        expected_counts=(3, 2),
    )
    assert len(ids) == len(set(ids)) == 5
    assert before == adapter.layout and library == saved_library
    assert ids == tuple(bay["stable_id"] for row in result["sets"] for bay in row["bays"])
    assert [setting_value(row, bi, "head_version_id")
            for row in result["sets"] for bi in range(len(row["bays"]))] == [
                v2, v2, v1, v2, v1,
            ]
    assert all(setting_value(row, bi, "tail_features") == []
               for row in result["sets"] for bi in range(len(row["bays"])))
    targets = {(si, bi): tail for si, row in enumerate(result["sets"])
               for bi in range(len(row["bays"]))}
    new_result, changed = manufacturing_api.apply_receiving_endcap_quantity_configuration(
        result, "tail", library, {tail: 5}, targets, expected_counts=(3, 2),
    )
    assert changed == ids
    assert all(setting_value(row, bi, "tail_version_id") == tail
               for row in new_result["sets"] for bi in range(len(row["bays"])))
    assert [setting_value(row, bi, "head_version_id")
            for row in new_result["sets"] for bi in range(len(row["bays"]))] == [
                v2, v2, v1, v2, v1,
            ]
    assert _decode(_encode({"receiving_layout": new_result}))["receiving_layout"] == new_result


def test_headless_rejects_stale_topology_and_bool_bay_key_atomically():
    adapter, library, v1, v2, _ = _fixture()
    before = deepcopy(adapter.layout)
    assigned = _assigned(v1, v2)
    with pytest.raises(ValueError, match="總連數"):
        manufacturing_api.apply_receiving_endcap_quantity_configuration(
            before, "head", library, {v1: 2, v2: 3}, assigned,
            expected_counts=(5,),
        )
    malformed = dict(assigned)
    malformed[(0, True)] = malformed.pop((0, 1))
    with pytest.raises(ValueError, match="配置連位"):
        manufacturing_api.apply_receiving_endcap_quantity_configuration(
            before, "head", library, {v1: 2, v2: 3}, malformed,
            expected_counts=(3, 2),
        )
    assert adapter.layout == before


def test_gui_head_tail_quantity_apply_delegates_exactly_once(monkeypatch):
    adapter, library, v1, v2, _ = _fixture()
    original = deepcopy(adapter.layout)
    selection = adapter.selection
    actual = manufacturing_api.apply_receiving_endcap_quantity_configuration
    calls = []
    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return actual(*args, **kwargs)
    monkeypatch.setattr(
        manufacturing_api, "apply_receiving_endcap_quantity_configuration", spy,
    )
    assert adapter.apply_quantity_configuration(
        "head", library, {v1: 2, v2: 3}, _assigned(v1, v2),
        expected_counts=(3, 2),
    ) == 5
    assert len(calls) == 1 and calls[0][0][1] == "head"
    assert adapter.selection == selection
    assert original != adapter.layout
    assert all(setting_value(row, bi, "head_version_id") is not None
               for row in adapter.layout["sets"] for bi in range(len(row["bays"])))
