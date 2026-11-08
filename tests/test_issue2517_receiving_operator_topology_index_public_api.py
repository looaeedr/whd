# -*- coding: utf-8 -*-
"""#2517: Receiving Set/Bay/Joint operator indices must be Engine validated."""
from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_operator_topology_integer,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _layout():
    return new_receiving_layout(width=800, height=1600, depth=350)


def test_public_facade_and_root_keep_one_receiving_topology_integer_owner():
    assert api.normalize_receiving_operator_topology_integer is normalize_receiving_operator_topology_integer
    assert ae_engine.normalize_receiving_operator_topology_integer is normalize_receiving_operator_topology_integer
    source = inspect.getsource(__import__(
        "gui_modules.application.receiving_set_bay_adapter", fromlist=["_operator_integer"],
    )._operator_integer)
    assert "manufacturing_api.normalize_receiving_operator_topology_integer(" in source
    assert "int(" not in source


@pytest.mark.parametrize(("raw", "expected"), [
    (0, 0), (2, 2), (-1, -1), ("0", 0), ("2", 2), ("-1", -1),
    ("02", 2), ("+2", 2),
])
def test_engine_retains_integer_and_legacy_decimal_tk_text(raw, expected):
    assert api.normalize_receiving_operator_topology_integer(raw, name="Set index") == expected


@pytest.mark.parametrize("bad", [
    True, False, 2.0, 1.5, None, [], {}, "", " ", "1_0",
    " 2", "2 ", "2\n", "0x2", "1.0", "１",
])
def test_engine_rejects_noncanonical_set_bay_joint_index_sources(bad):
    with pytest.raises(ValueError, match="integer"):
        api.normalize_receiving_operator_topology_integer(bad, name="Bay count")


@pytest.mark.parametrize(("method", "args"), [
    ("select_set", ("1_0",)),
    ("select_bay", ("1_0",)),
    ("bay_count", ("1_0",)),
    ("set_set_count", ("1_0",)),
    ("set_bay_count", ("1_0",)),
    ("resize_connections", (0, "1_0")),
    ("current_joint_editability", ("1_0",)),
    ("update_joint_alignment", ("1_0",)),
])
def test_gui_rejects_underscore_alias_before_any_topology_or_selection_commit(method, args):
    adapter = ReceivingSetBayAdapter(_layout())
    before_layout, before_selection = deepcopy(adapter.layout), adapter.selection
    with pytest.raises(ValueError, match="integer"):
        getattr(adapter, method)(*args)
    assert adapter.layout == before_layout
    assert adapter.selection == before_selection


def test_valid_operator_text_commits_same_engine_layout_and_json_roundtrip():
    adapter = ReceivingSetBayAdapter(_layout())
    assert adapter.select_set("2") is True
    adapter.set_bay_count("2")
    adapter.select_bay("2")
    assert adapter.selection.set_index == 1
    assert adapter.selection.bay_index == 1
    saved = json.loads(json.dumps(adapter.layout, ensure_ascii=False))
    assert api.normalize_receiving_layout(saved) == adapter.layout
