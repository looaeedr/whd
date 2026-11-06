# -*- coding: utf-8 -*-
"""#2517 Receiving new real-Bay Family defaults are an Engine contract."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import receiving
from ae_engine.receiving_layout import (
    new_receiving_layout, update_receiving_bay, resize_receiving_bays,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _source():
    return new_receiving_layout(width=800, height=1600, depth=350)


def test_engine_new_bays_take_live_family_defaults_without_rewriting_custom_source(monkeypatch):
    original = update_receiving_bay(_source(), set_index=0, bay_index=0,
                                    width=750, height=1700, depth=420)
    snapshot = deepcopy(original)
    monkeypatch.setitem(receiving.BOX_BODY_DEFAULTS, "w", 910.0)
    result = manufacturing_api.resize_receiving_bays_with_family_defaults(
        original, set_index=0, bay_count=3,
    )
    assert original == snapshot
    assert result["sets"][0]["bays"][0] == snapshot["sets"][0]["bays"][0]
    assert [bay["width"] for bay in result["sets"][0]["bays"]] == [750.0, 910.0, 910.0]
    assert len(result["sets"][0]["joints"]) == 2
    assert len({bay["stable_id"] for bay in result["sets"][0]["bays"]}) == 3
    assert result["sets"][0]["bays"][1]["height"] == receiving.BOX_BODY_DEFAULTS["h"]
    assert result["sets"][0]["bays"][1]["depth"] == receiving.BOX_BODY_DEFAULTS["d"]


def test_engine_shrink_preserves_canonical_tail_only_deletion():
    expanded = resize_receiving_bays(_source(), set_index=0, bay_count=3)
    before = deepcopy(expanded)
    result = manufacturing_api.resize_receiving_bays_with_family_defaults(
        expanded, set_index=0, bay_count=1,
    )
    assert expanded == before
    assert result == resize_receiving_bays(expanded, set_index=0, bay_count=1)


def test_invalid_family_default_never_commits_new_bay(monkeypatch):
    source = _source()
    before = deepcopy(source)
    monkeypatch.setitem(receiving.BOX_BODY_DEFAULTS, "w", 910.5)
    with pytest.raises(ValueError, match="受電箱預設"):
        manufacturing_api.resize_receiving_bays_with_family_defaults(
            source, set_index=0, bay_count=2,
        )
    assert source == before


def test_native_gui_resizing_delegates_one_engine_call(monkeypatch):
    layout = _source()
    adapter = ReceivingSetBayAdapter(layout)
    real = manufacturing_api.resize_receiving_bays_with_family_defaults
    calls = []
    def recorded(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(
        manufacturing_api, "resize_receiving_bays_with_family_defaults", recorded,
    )
    adapter.set_bay_count(2)
    assert len(calls) == 1
    assert adapter.layout["sets"][0]["bays"][1]["width"] == float(
        receiving.BOX_BODY_DEFAULTS["w"]
    )
    assert adapter.layout["sets"][0]["bays"][0] == layout["sets"][0]["bays"][0]
    assert adapter.selection.bay_index == 0
