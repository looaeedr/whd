# -*- coding: utf-8 -*-
"""#2517: Receiving NFB parent-brand manufacturing proof belongs to Engine."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import (
    append_receiving_set, new_receiving_layout, update_receiving_bay,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1112_receiving_set_bay_editor import (
    _ac40_submitted_parent_brand_config,
)


def _layout_with_submitted_nfb(two_sets=False):
    layout = new_receiving_layout(
        width=800, height=1600, depth=350, back_panel_mode="FULL",
    )
    if two_sets:
        layout = append_receiving_set(layout)
    for si in range(2 if two_sets else 1):
        layout = update_receiving_bay(
            layout, set_index=si, bay_index=0,
            nfb_config_submitted=True,
            nfb_config=_ac40_submitted_parent_brand_config(),
        )
    return layout


def test_engine_api_detaches_set_and_revokes_only_confirmed_inherited_physical_x():
    source = _layout_with_submitted_nfb()["sets"][0]
    frozen = deepcopy(source)
    updated, changed = manufacturing_api.rebase_receiving_set_parent_nfb_brand(
        source, "三菱",
    )
    assert changed is True
    assert source == frozen
    assert updated["switch_brand"] == "三菱"
    old_holes = frozen["bays"][0]["nfb_config"]["holes"]
    new_holes = updated["bays"][0]["nfb_config"]["holes"]
    assert new_holes[0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert new_holes[0]["manual_x_mm"] == old_holes[0]["manual_x_mm"]
    assert new_holes[0]["model_filename"] == old_holes[0]["model_filename"]
    assert new_holes[0]["source_brand"] == old_holes[0]["source_brand"]
    assert new_holes[1] == old_holes[1]
    restored, changed_back = manufacturing_api.rebase_receiving_set_parent_nfb_brand(
        updated, "士林",
    )
    assert changed_back is True
    assert restored["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"


def test_engine_api_noop_and_invalid_brand_fail_without_mutating_source():
    source = _layout_with_submitted_nfb()["sets"][0]
    frozen = deepcopy(source)
    same, changed = manufacturing_api.rebase_receiving_set_parent_nfb_brand(
        source, "士林",
    )
    assert changed is False and same == frozen and same is not source
    with pytest.raises(ValueError, match="廠牌"):
        manufacturing_api.rebase_receiving_set_parent_nfb_brand(source, "不存在廠牌")
    assert source == frozen


def test_gui_set_and_global_brand_delegate_to_public_engine_api(monkeypatch):
    initial = _layout_with_submitted_nfb(two_sets=True)
    frozen = deepcopy(initial)
    expected, _ = manufacturing_api.rebase_receiving_set_parent_nfb_brand(
        initial["sets"][0], "三菱",
    )
    real = manufacturing_api.rebase_receiving_set_parent_nfb_brand
    calls = []

    def recorded(set_row, brand):
        calls.append((set_row["stable_id"], brand))
        return real(set_row, brand)

    monkeypatch.setattr(manufacturing_api, "rebase_receiving_set_parent_nfb_brand", recorded)
    adapter = ReceivingSetBayAdapter(initial)
    adapter.set_brand("三菱")
    assert len(calls) == 1
    assert adapter.layout["sets"][0] == expected
    assert adapter.layout["sets"][1] == frozen["sets"][1]
    assert initial == frozen

    calls.clear()
    assert adapter.set_global_brand("三菱") is True
    assert len(calls) == 2
    assert [r["switch_brand"] for r in adapter.layout["sets"]] == ["三菱", "三菱"]
    assert adapter.set_global_brand("三菱") is False
    assert initial == frozen
