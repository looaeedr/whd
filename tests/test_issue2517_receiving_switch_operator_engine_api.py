# -*- coding: utf-8 -*-
"""#2517 Receiving Switch editor topology is exclusively Engine-operated."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.receiving_switch_layout_adapter import (
    ReceivingSwitchLayoutAdapter,
)


def _source():
    return manufacturing_api.normalize_receiving_switch_operator_layout(None)


def test_headless_add_remove_real_layers_preserve_stable_identity_and_source():
    source = _source()
    frozen = deepcopy(source)
    added, changed = manufacturing_api.apply_receiving_switch_operator_action(
        source, operation="add_layer",
    )
    assert changed is True and source == frozen
    assert [x["stable_id"] for x in added["layers"]] == [
        "receiving:switch-layer:1", "receiving:switch-layer:2",
    ]
    shrunk, changed = manufacturing_api.apply_receiving_switch_operator_action(
        added, operation="remove_layer",
    )
    assert changed and shrunk == source
    same, changed = manufacturing_api.apply_receiving_switch_operator_action(
        shrunk, operation="remove_layer",
    )
    assert not changed and same == source


def test_headless_delta_never_zeroes_or_overwrites_other_physical_tiers():
    source, _ = manufacturing_api.apply_receiving_switch_operator_action(
        _source(), operation="add_layer",
    )
    original = deepcopy(source)
    updated, changed = manufacturing_api.apply_receiving_switch_operator_action(
        source, operation="resize_connections", layer_index=1, delta=4,
    )
    assert changed and updated["layers"][1]["connection_count"] == 5
    assert updated["layers"][0] == original["layers"][0]
    minimum, changed = manufacturing_api.apply_receiving_switch_operator_action(
        updated, operation="resize_connections", layer_index=1, delta=-100,
    )
    assert changed and minimum["layers"][1]["connection_count"] == 1
    same, changed = manufacturing_api.apply_receiving_switch_operator_action(
        minimum, operation="resize_connections", layer_index=1, delta=-3,
    )
    assert not changed and same == minimum
    assert source == original


def test_brand_change_is_real_source_transition_only():
    source = _source()
    updated, changed = manufacturing_api.apply_receiving_switch_operator_action(
        source, operation="set_brand", brand="三菱",
    )
    assert changed and updated["switch_brand"] == "三菱"
    assert source["switch_brand"] == "士林"
    again, changed = manufacturing_api.apply_receiving_switch_operator_action(
        updated, operation="set_brand", brand="三菱",
    )
    assert not changed and again == updated


@pytest.mark.parametrize("operation,index,delta", [
    ("resize_connections", True, 1), ("resize_connections", 0, True),
    ("resize_connections", -1, 1), ("resize_connections", 2, 1),
    ("bogus", 0, 1),
])
def test_invalid_physical_operator_actions_fail_without_mutation(operation, index, delta):
    source = _source()
    original = deepcopy(source)
    with pytest.raises((ValueError, IndexError)):
        manufacturing_api.apply_receiving_switch_operator_action(
            source, operation=operation, layer_index=index, delta=delta,
        )
    assert source == original


def test_gui_existing_string_inputs_delegate_one_engine_action(monkeypatch):
    adapter = ReceivingSwitchLayoutAdapter(None)
    real = manufacturing_api.apply_receiving_switch_operator_action
    calls = []
    def tracked(*args, **kwargs):
        calls.append(kwargs.get("operation"))
        return real(*args, **kwargs)
    monkeypatch.setattr(
        manufacturing_api, "apply_receiving_switch_operator_action", tracked,
    )
    assert adapter.resize_connections("0", "+2") is True
    assert adapter.connection_count(0) == 3
    assert adapter.resize_connections("0", "-9") is True
    assert adapter.connection_count(0) == 1
    assert adapter.remove_layer() is False
    adapter.add_layer()
    assert adapter.connection_counts() == (1, 1)
    assert adapter.set_brand("三菱") is True
    assert calls == [
        "resize_connections", "resize_connections", "remove_layer",
        "add_layer", "set_brand",
    ]
