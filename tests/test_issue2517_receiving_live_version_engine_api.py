# -*- coding: utf-8 -*-
"""#2517 Receiving highlighted Live version writes are Engine-owned."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_shared_settings import (
    edit_setting, share_setting, setting_value,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from phase6_project_file import _encode, _decode


def _layout():
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1200, depth=350),
    )
    adapter.set_bay_count(3)
    adapter.set_set_count(2)
    return adapter.layout


def test_head_live_apply_preserves_other_bays_shared_source_and_other_roles():
    layout = _layout()
    layout = edit_setting(
        layout, set_index=0, bay_index=0,
        kind="head_version_id", value="head-v2",
    )
    layout = share_setting(
        layout, set_index=0, bay_indices=(0, 1, 2),
        source_bay_index=0, kind="head_version_id",
    )
    layout = edit_setting(
        layout, set_index=0, bay_index=0,
        kind="tail_version_id", value="tail-v1",
    )
    frozen = deepcopy(layout)
    out, selected, ids = manufacturing_api.mark_receiving_bays_live_version(
        layout, "head", 0, (2, 1, 1),
    )
    assert selected == (1, 2)
    assert ids == tuple(out["sets"][0]["bays"][i]["stable_id"] for i in selected)
    assert layout == frozen
    assert setting_value(out["sets"][0], 0, "head_version_id") == "head-v2"
    assert [setting_value(out["sets"][0], i, "head_version_id") for i in selected] == ["", ""]
    assert setting_value(out["sets"][0], 0, "tail_version_id") == "tail-v1"
    assert out["sets"][1] == frozen["sets"][1]
    assert _decode(_encode({"receiving_layout": out}))["receiving_layout"] == out


@pytest.mark.parametrize("role", ("head", "tail", "inner-door"))
def test_live_api_accepts_all_three_real_version_roles(role):
    layout = _layout()
    result, selected, ids = manufacturing_api.mark_receiving_bays_live_version(
        layout, role, 1, (0,),
    )
    assert selected == (0,)
    assert ids == (result["sets"][1]["bays"][0]["stable_id"],)
    kind = role.replace("-", "_") + "_version_id"
    assert setting_value(result["sets"][1], 0, kind) == ""
    assert setting_value(layout["sets"][1], 0, kind) is None


@pytest.mark.parametrize("role,set_index,selection", (
    ("door", 0, (0,)), ("head", True, (0,)), ("head", 9, (0,)),
    ("head", 0, (True,)), ("head", 0, (9,)),
    ("head", 0, ([1],)), ("head", 0, ()),
))
def test_live_api_rejects_bad_input_without_mutation(role, set_index, selection):
    layout = _layout()
    frozen = deepcopy(layout)
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.mark_receiving_bays_live_version(
            layout, role, set_index, selection,
        )
    assert layout == frozen


def test_gui_live_apply_delegates_engine_once_without_reselect(monkeypatch):
    adapter = ReceivingSetBayAdapter(_layout())
    original = deepcopy(adapter.layout)
    selected = adapter.selection
    real = manufacturing_api.mark_receiving_bays_live_version
    calls = []

    def recorded(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(manufacturing_api, "mark_receiving_bays_live_version", recorded)
    assert adapter.mark_live_version_for_bays("inner-door", 0, (1,)) == (1,)
    assert len(calls) == 1 and calls[0][0][1] == "inner-door"
    assert adapter.selection == selected
    assert adapter.layout["sets"][1] == original["sets"][1]
    assert setting_value(adapter.layout["sets"][0], 1, "inner_door_version_id") == ""
