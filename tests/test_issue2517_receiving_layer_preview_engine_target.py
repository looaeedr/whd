# -*- coding: utf-8 -*-
"""#2517: Receiving 2D Set/Bay layer preview uses Engine physical identity."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    project_receiving_operator_set_preview_target as owner_project,
)
from gui_modules.application import fold_designer_composition_receiving as gui
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, ReceivingSwitchProjectionAdapter,
)


def _layout():
    # The actual GUI uses receiving-layout-v1 Sets/Bays, NOT the separate
    # receiving-switch-layout-v1 used when confirming switch CUTTING.
    source = api.operator_new_receiving_layout(width=800, height=1600, depth=400)
    source = api.append_receiving_set(source)
    source["sets"][1]["switch_brand"] = "東元"
    return api.normalize_receiving_layout(source)


def _host():
    layout = _layout()
    switch = ReceivingSwitchProjectionAdapter(ReceivingSetBayAdapter(layout))
    renders, opens, settings = [], [], []
    parts = (SimpleNamespace(part_key="test:physical-set-bay"),)

    def render(_namespace, layer_index, connection_index):
        renders.append((layer_index, connection_index))
        return SimpleNamespace(render_data=SimpleNamespace(assembly_parts=parts))

    def open_window(*args, **kwargs):
        opens.append((args, kwargs))
        return True

    def required(_namespace, name):
        if name == "original":
            return SimpleNamespace(tk=object(), ttk=object())
        if name == "open_receiving_layer_preview":
            return open_window
        raise AssertionError(f"unexpected UI dependency: {name}")

    host = SimpleNamespace(
        app=SimpleNamespace(receiving_layer_controls=object(), root=None),
        receiving_switch_adapter=lambda _namespace: switch,
        receiving_bay_preview_request=render,
        receiving_settings_ports=lambda _namespace, index: settings.append(index) or {"set": index},
        _required=required,
    )
    host.receiving_layer_preview_payload = (
        lambda namespace, index: gui.receiving_layer_preview_payload(host, namespace, index)
    )
    return host, layout, renders, opens, settings


def test_public_engine_and_root_share_real_receiving_layout_owner():
    assert api.project_receiving_operator_set_preview_target is owner_project
    assert ae_engine.project_receiving_operator_set_preview_target is owner_project
    assert "project_receiving_operator_set_preview_target" in ae_engine.__all__


@pytest.mark.parametrize("raw", [
    True, False, 1.0, 1.9, 0.5, None, [], -1, "2", "-1", "1.0", "unknown", " 1 ", "1_0",
])
def test_invalid_physical_set_never_renders_or_mutates(raw):
    host, layout, renders, opens, settings = _host()
    before = deepcopy(layout)
    with pytest.raises(ValueError, match="Receiving Set preview"):
        gui.receiving_layer_preview_payload(host, None, raw)
    assert renders == [] and opens == [] and settings == []
    assert layout == before


@pytest.mark.parametrize(("raw", "index", "brand"), [
    (0, 0, "士林"), (1, 1, "東元"),
    ("0", 0, "士林"), ("01", 1, "東元"),
    ("+1", 1, "東元"),
])
def test_valid_set_preview_projects_exact_engine_identity(raw, index, brand):
    host, layout, renders, opens, settings = _host()
    before = deepcopy(layout)
    target = api.project_receiving_operator_set_preview_target(layout, raw)
    assert target == {
        "set_index": index, "set_id": layout["sets"][index]["stable_id"],
        "connection_count": 1, "brand": brand,
    }
    assert json.loads(json.dumps(target)) == target
    payload = gui.receiving_layer_preview_payload(host, None, raw)
    assert payload["layer_index"] == index
    assert payload["brand"] == brand
    assert payload["connection_count"] == 1
    assert payload["assembly_part_keys"] == ("test:physical-set-bay",)
    assert renders == [(index, 0)]
    assert opens == [] and settings == [] and layout == before


def test_real_set_bay_projection_brand_is_not_current_selection_brand():
    # GUI is still on Set1; preview requested Set2 must display Set2's brand.
    host, layout, _, _, _ = _host()
    assert host.receiving_switch_adapter(None).brand == "士林"
    assert gui.receiving_layer_preview_payload(host, None, 1)["brand"] == "東元"
    assert layout["sets"][1]["switch_brand"] == "東元"


def test_legacy_open_preview_forwards_engine_set_index_and_brand():
    host, layout, renders, opens, settings = _host()
    assert gui.open_receiving_layer_preview(host, None, "1") is True
    assert renders == [(1, 0)]
    assert settings == [1] and len(opens) == 1
    kwargs = opens[0][1]
    assert kwargs["layer_index"] == 1
    assert kwargs["brand"] == "東元"
    assert kwargs["connection_count"] == 1
    assert kwargs["bay_requests"] == (kwargs["render_request"],)
    assert layout["sets"][1]["stable_id"] == "receiving:set:2"


def test_legacy_open_preview_rejects_bool_without_window_or_render(monkeypatch):
    import tkinter.messagebox
    warnings = []
    monkeypatch.setattr(
        tkinter.messagebox, "showwarning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )
    host, layout, renders, opens, settings = _host()
    original = deepcopy(layout)
    assert gui.open_receiving_layer_preview(host, None, True) is False
    assert len(warnings) == 1
    assert renders == [] and opens == [] and settings == []
    assert layout == original


def test_cross_schema_switch_layout_cannot_be_used_as_set_authority():
    wrong = api.normalize_receiving_switch_operator_layout(None)
    with pytest.raises(ValueError, match="Receiving layout schema"):
        api.project_receiving_operator_set_preview_target(wrong, 0)


def test_preview_gui_never_precoerces_physical_set_before_engine():
    payload_source = inspect.getsource(gui.receiving_layer_preview_payload)
    open_source = inspect.getsource(gui.open_receiving_layer_preview)
    assert "manufacturing_api.project_receiving_operator_set_preview_target(" in payload_source
    assert "index = int(layer_index)" not in payload_source
    assert "int(layer_index)" not in open_source
