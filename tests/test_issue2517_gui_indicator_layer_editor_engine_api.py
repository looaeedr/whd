"""#2517: both GUI Indicator layer editors delegate physical count to Engine."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import normalize_operator_indicator_layer_count as public_count
from ae_engine.contracts import ManufacturingContext
from gui_modules.parts.panels import indicator_box, door


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Widget:
    def __init__(self, *args, **kwargs):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True

    def pack(self, **kwargs):
        pass

    def bind(self, *args, **kwargs):
        pass


def _editor(value, part):
    old = Widget()
    holder = SimpleNamespace(winfo_children=lambda: [old])
    controls = [Var("2") for _ in range(6)]
    host = SimpleNamespace(
        COLOR_PANEL="#000", COLOR_TEXT="#fff", COLOR_INPUT_BG="#111",
        indicator_l_var=Var(value), indicator_layer_g_vars=controls,
        layers_config_frame=holder,
        door_indicator_l_var=Var(value), door_indicator_layer_g_vars=controls,
        door_layers_config_frame=holder,
        _request_phase6_update=lambda *args: None,
    )
    fn = indicator_box.rebuild_layers_config_ui if part == "box" else door.rebuild_door_layers_config_ui
    return host, old, fn


@pytest.mark.parametrize("raw", [
    True, False, 0, -1, "0", "7", 7, "2.5", 2.5, None, "",
    "bad", float("nan"), float("inf"), [], {},
])
def test_untrusted_live_layer_source_rejected_by_public_engine(raw):
    for fn in (api.normalize_operator_indicator_layer_count, public_count):
        with pytest.raises(ValueError, match="指示燈"):
            fn(raw)


@pytest.mark.parametrize("part", ("box", "door"))
@pytest.mark.parametrize("raw", [True, "0", "7", "2.5", None, "bad"])
def test_invalid_live_editor_keeps_existing_widgets_untouched(part, raw):
    host, old, rebuild = _editor(raw, part)
    with pytest.raises(ValueError, match="指示燈"):
        rebuild(host)
    assert not old.destroyed
    assert host.indicator_l_var.get() == raw


@pytest.mark.parametrize("part", ("box", "door"))
@pytest.mark.parametrize("raw,expected", [
    ("1", 1), (" 3 ", 3), ("6", 6), (2, 2), ("+2", 2),
])
def test_valid_live_editor_uses_engine_count(monkeypatch, part, raw, expected):
    host, old, rebuild = _editor(raw, part)
    module = indicator_box if part == "box" else door
    created = []
    def new_frame(*args, **kwargs):
        frame = Widget()
        created.append(frame)
        return frame
    monkeypatch.setattr(module.tk, "Frame", new_frame)
    monkeypatch.setattr(module.tk, "Label", Widget)
    monkeypatch.setattr(module.ttk, "Combobox", Widget)
    assert api.normalize_operator_indicator_layer_count(raw) == public_count(raw) == expected
    rebuild(host)
    assert old.destroyed
    assert len(created) == expected
    assert host.indicator_l_var.get() == raw


def test_layer_editor_json_source_and_real_indicator_dxf_reopen(tmp_path):
    payload = {"layers": "3", "groups": ["2", "3", "1"]}
    reload = json.loads(json.dumps(payload))
    count = public_count(reload["layers"])
    groups = api.normalize_fold_designer_indicator_groups(reload["groups"][:count])
    assert (count, groups) == (3, (2, 3, 1))
    assert reload == payload
    spec = api.build_indicator_box_operator_part_spec({"t": 2.0}, groups, features=())
    rendered = api.build_part_render_data(spec, ManufacturingContext())
    path = tmp_path / "indicator-source.dxf"
    api.save_part_render_data_dxf(rendered, path, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(rendered, path).ok


def test_gui_has_no_second_layer_count_parser():
    for fn in (indicator_box.rebuild_layers_config_ui, door.rebuild_door_layers_config_ui):
        src = inspect.getsource(fn)
        assert "manufacturing_api.normalize_operator_indicator_layer_count(" in src
        assert "int(host." not in src
        assert "except ValueError:" not in src
        assert src.index("normalize_operator_indicator_layer_count(") < src.index(".destroy()")
