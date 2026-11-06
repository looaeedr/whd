# -*- coding: utf-8 -*-
"""#2517 Engine owns Receiving highlighted multi-Bay dimension manufacturing state."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1499_nfb_persistence import _config


def _layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )


def test_headless_batch_detached_ids_and_noop_preserve_other_bay():
    source = _layout()
    before = deepcopy(source)
    result, ids = manufacturing_api.apply_receiving_bay_dimensions(
        source, 0, (2, 0), width=900, height=1700, depth=400, expected_count=2,
    )
    assert source == before
    assert ids == (source["sets"][0]["bays"][2]["stable_id"],
                   source["sets"][0]["bays"][0]["stable_id"])
    assert result["sets"][0]["bays"][1] == source["sets"][0]["bays"][1]
    assert all(result["sets"][0]["bays"][i]["width"] == 900.0 for i in (0, 2))
    again, unchanged = manufacturing_api.apply_receiving_bay_dimensions(
        result, 0, (0, 2), width=900, height=1700, depth=400, expected_count=2,
    )
    assert again is result and unchanged == ()


def test_headless_reflows_only_selected_door_partitions():
    source = _layout()
    source = update_receiving_bay(source, set_index=0, bay_index=2,
        door_state={"door_layout_columns": [[400, [1000, 600]], [400, [1000, 600]]]})
    result, ids = manufacturing_api.apply_receiving_bay_dimensions(
        source, 0, (2,), width=850, height=1650, depth=420, expected_count=1,
    )
    assert len(ids) == 1
    assert result["sets"][0]["bays"][2]["door_state"]["door_layout_columns"] == [
        [400.0, [1000.0, 650.0]], [450.0, [1000.0, 650.0]],
    ]
    assert result["sets"][0]["bays"][0] == source["sets"][0]["bays"][0]


@pytest.mark.parametrize("indices", [None, (True,), (0, []), (0, 0), (9,)])
def test_bad_selection_fails_closed_without_mutation(indices):
    source = _layout()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="高亮"):
        manufacturing_api.apply_receiving_bay_dimensions(
            source, 0, indices, width=900, height=1700, depth=400,
            expected_count=2 if isinstance(indices, tuple) and len(indices) == 2 else 1,
        )
    assert source == before


def test_headless_width_change_revokes_only_selected_physical_nfb_x():
    source = _layout()
    for i in range(3):
        source = update_receiving_bay(
            source, set_index=0, bay_index=i,
            nfb_config_submitted=True, nfb_config=_config(x=i * 100),
        )
    before = deepcopy(source)
    updated, ids = manufacturing_api.apply_receiving_bay_dimensions(
        source, 0, (0, 2), width=900, height=1600, depth=350, expected_count=2,
    )
    assert len(ids) == 2 and source == before
    for i in (0, 2):
        old = before["sets"][0]["bays"][i]["nfb_config"]["holes"][0]
        new = updated["sets"][0]["bays"][i]["nfb_config"]["holes"][0]
        assert new["manual_x_state"] == "RECONFIRM_REQUIRED"
        assert new["manual_x_mm"] == old["manual_x_mm"]
        assert new["datum_snapshot"] == old["datum_snapshot"]
    assert updated["sets"][0]["bays"][1] == before["sets"][0]["bays"][1]


def test_gui_dimensions_delegate_one_public_engine_transaction(monkeypatch):
    layout = _layout()
    adapter = ReceivingSetBayAdapter(layout)
    real = manufacturing_api.apply_receiving_bay_dimensions
    calls = []
    def tracked(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setattr(manufacturing_api, "apply_receiving_bay_dimensions", tracked)
    assert adapter.apply_dimensions_to_bays(
        0, (0, 2), width=900, height=1700, depth=400, expected_count=2,
    ) == 2
    assert calls == [1]
    assert adapter.layout["sets"][0]["bays"][1] == layout["sets"][0]["bays"][1]
