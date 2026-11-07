# -*- coding: utf-8 -*-
"""#2517: a selected Receiving Set's saved NFB brand is one public transaction."""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, ReceivingSwitchProjectionAdapter,
)
from tests.test_issue2517_receiving_nfb_brand_engine_api import (
    _layout_with_submitted_nfb,
)


def test_root_public_api_is_same_engine_owner():
    from ae_engine.receiving_nfb_brand_transition import (
        update_receiving_one_set_nfb_parent_brand as owner,
    )
    assert api.update_receiving_one_set_nfb_parent_brand is owner
    assert ae_engine.update_receiving_one_set_nfb_parent_brand is owner
    assert "update_receiving_one_set_nfb_parent_brand" in ae_engine.__all__


@pytest.mark.parametrize("set_index", (0, 1))
def test_real_submitted_two_set_brand_isolation_and_inherited_x_revocation(set_index):
    source = _layout_with_submitted_nfb(two_sets=True)
    original = deepcopy(source)
    result, changed = api.update_receiving_one_set_nfb_parent_brand(
        source, set_index, "三菱",
    )
    assert changed is True
    assert source == original
    assert result is not source
    assert result["sets"][1 - set_index] == original["sets"][1 - set_index]
    assert result["sets"][set_index]["switch_brand"] == "三菱"
    holes_before = original["sets"][set_index]["bays"][0]["nfb_config"]["holes"]
    holes_after = result["sets"][set_index]["bays"][0]["nfb_config"]["holes"]
    assert holes_after[0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert holes_after[0]["manual_x_mm"] == holes_before[0]["manual_x_mm"]
    assert holes_after[0]["model_filename"] == holes_before[0]["model_filename"]
    assert holes_after[1] == holes_before[1]
    expected_row, changed_row = api.rebase_receiving_set_parent_nfb_brand(
        original["sets"][set_index], "三菱",
    )
    assert changed_row is True
    assert result["sets"][set_index] == expected_row


def test_noop_is_detached_and_original_layout_is_unchanged():
    source = _layout_with_submitted_nfb(two_sets=True)
    before = deepcopy(source)
    result, changed = api.update_receiving_one_set_nfb_parent_brand(
        source, 0, "士林",
    )
    assert changed is False
    assert result is not source
    assert result == api.normalize_receiving_layout(source)
    assert source == before


@pytest.mark.parametrize("bad_index", (
    True, False, 0.0, 1.0, "0", None, -1, 2, [], {},
))
def test_malformed_set_identity_rejected_without_partially_rebasing_source(bad_index):
    source = _layout_with_submitted_nfb(two_sets=True)
    before = deepcopy(source)
    with pytest.raises((ValueError, IndexError)):
        api.update_receiving_one_set_nfb_parent_brand(
            source, bad_index, "三菱",
        )
    assert source == before


def test_invalid_brand_and_later_set_source_are_fail_closed():
    source = _layout_with_submitted_nfb(two_sets=True)
    before = deepcopy(source)
    with pytest.raises(ValueError, match="不支援的開關品牌"):
        api.update_receiving_one_set_nfb_parent_brand(source, 0, "假品牌")
    assert source == before
    broken = deepcopy(source)
    broken["sets"][1]["switch_brand"] = "假品牌"
    broken_before = deepcopy(broken)
    with pytest.raises(ValueError):
        api.update_receiving_one_set_nfb_parent_brand(broken, 1, "三菱")
    assert broken == broken_before
    assert broken["sets"][0] == before["sets"][0]


def test_gui_selected_set_and_legacy_switch_port_use_only_public_engine_layout():
    source = _layout_with_submitted_nfb(two_sets=True)
    before = deepcopy(source)
    adapter = ReceivingSetBayAdapter(source)
    adapter.select_set(2)
    selection = adapter.selection
    port = ReceivingSwitchProjectionAdapter(adapter)
    assert port.set_brand("三菱") is True
    expected, _ = api.update_receiving_one_set_nfb_parent_brand(
        source, 1, "三菱",
    )
    assert adapter.layout == expected
    assert adapter.selection == selection
    assert source == before
    assert port.set_brand("三菱") is False
    assert adapter.layout == expected
    assert adapter._session_dirty_ids == set()

    gui_method = getsource(ReceivingSetBayAdapter.set_brand)
    assert "manufacturing_api.update_receiving_one_set_nfb_parent_brand(" in gui_method
    assert "rebase_receiving_set_parent_nfb_brand(" not in gui_method
    assert '["sets"]' not in gui_method
    assert "deepcopy(" not in gui_method
