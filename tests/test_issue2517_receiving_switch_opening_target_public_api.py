# -*- coding: utf-8 -*-
"""#2517: Receiving Switch opening confirmation checks real Engine cell identity."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_switch_layout import (
    validate_receiving_switch_opening_target as owner_validate,
)
from gui_modules.application import fold_designer_composition_receiving as gui
from gui_modules.application.receiving_switch_layout_adapter import ReceivingSwitchLayoutAdapter


def _layout():
    source = api.normalize_receiving_switch_operator_layout(None)
    return api.apply_receiving_switch_operator_action(
        source, operation="resize_connections", layer_index=0, delta=2,
    )[0]


def _host(layout, resolver):
    intentions = []
    host = SimpleNamespace(
        app=SimpleNamespace(
            _phase6_receiving_switch_opening_resolver=resolver,
            submit_update_intent=lambda *a, **kw: intentions.append((a, kw)),
        ),
        receiving_switch_adapter=lambda _namespace: ReceivingSwitchLayoutAdapter(layout),
    )
    return host, intentions


def test_public_engine_and_root_expose_single_canonical_opening_target_owner():
    assert api.validate_receiving_switch_opening_target is owner_validate
    assert ae_engine.validate_receiving_switch_opening_target is owner_validate
    assert "validate_receiving_switch_opening_target" in ae_engine.__all__


@pytest.mark.parametrize(("layer", "connection", "expected"), [
    (0, 0, (0, 0)), (0, 2, (0, 2)),
    ("0", "1", (0, 1)), (" 0 ", "02", (0, 2)),
])
def test_headless_valid_existing_target_is_detached_and_json_stable(layer, connection, expected):
    layout = _layout()
    before = deepcopy(layout)
    target = api.validate_receiving_switch_opening_target(
        layout, layer_index=layer, connection_index=connection, brand="士林",
    )
    assert (target["layer_index"], target["connection_index"]) == expected
    assert target["brand"] == "士林"
    assert json.loads(json.dumps(target)) == target
    assert layout == before


@pytest.mark.parametrize(("layer", "connection"), [
    (True, 0), (0, True), (False, 0), (0, False),
    (0.5, 0), (0, 1.9), (1.0, 0), (-1, 0), (0, -1),
    (1, 0), (0, 3), ("bad", 0), (0, "1.0"), (None, 0),
])
def test_bad_or_stale_cell_never_reaches_gui_resolver_or_geometry_intent(layer, connection):
    layout = _layout()
    before = deepcopy(layout)
    calls = []
    host, intents = _host(layout, lambda **kw: (calls.append(kw), True)[1])
    with pytest.raises(ValueError, match="Receiving switch"):
        api.validate_receiving_switch_opening_target(
            layout, layer_index=layer, connection_index=connection, brand="士林",
        )
    with pytest.raises(ValueError, match="Receiving switch"):
        gui.confirm_receiving_opening(host, None, layer, connection, "士林")
    assert calls == [] and intents == []
    assert layout == before


def test_valid_gui_real_callback_forwards_engine_target_without_manufacturing_invention():
    layout = _layout()
    calls = []
    host, intents = _host(layout, lambda **kw: (calls.append(kw), True)[1])
    assert gui.confirm_receiving_opening(host, None, "0", "2", "士林") is True
    assert calls == [{"layer_index": 0, "connection_index": 2, "brand": "士林"}]
    assert intents == [(("geometry",), {"commit": True})]
    assert layout == _layout()


@pytest.mark.parametrize("brand", [True, 1, None, "", "不存在的品牌"])
def test_invalid_brand_never_reaches_opening_resolver(brand):
    calls = []
    host, intents = _host(_layout(), lambda **kw: (calls.append(kw), True)[1])
    with pytest.raises(ValueError):
        gui.confirm_receiving_opening(host, None, 0, 0, brand)
    assert calls == [] and intents == []


def test_valid_target_does_not_self_certify_cutting_or_trigger_intent_without_commit():
    calls = []
    host, intents = _host(_layout(), lambda **kw: (calls.append(kw), False)[1])
    assert gui.confirm_receiving_opening(host, None, 0, 0, "士林") is False
    assert calls == [{"layer_index": 0, "connection_index": 0, "brand": "士林"}]
    assert intents == []


def test_real_gui_function_does_not_precoerce_physical_cell_indices():
    source = inspect.getsource(gui.confirm_receiving_opening)
    assert "manufacturing_api.validate_receiving_switch_opening_target(" in source
    assert "layer_index=int(" not in source
    assert "connection_index=int(" not in source
    assert "resolver(**target)" in source
