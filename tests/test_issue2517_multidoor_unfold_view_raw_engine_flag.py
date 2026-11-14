# -*- coding: utf-8 -*-
"""#2517 2D Door-cell view selection uses raw public Engine boolean semantics."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui import Phase6ApplicationHost


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeCanvas:
    def __init__(self):
        self.actions = []

    def delete(self, tag):
        self.actions.append(("delete", tag))

    def unbind(self, name):
        self.actions.append(("unbind", name))

    def bind(self, name, callback):
        self.actions.append(("bind", name, callback))


def _host(raw, calls):
    return SimpleNamespace(
        multi_door_enabled_var=Var(raw),
        fold_designer_app=object(),
        on_door_canvas_press=lambda e: None,
        on_door_canvas_drag=lambda e: None,
        on_door_canvas_release=lambda e: None,
        draw_door_layout_overview=lambda **kw:
            calls.append(("overview", kw)) or "COMPOSITE_VIEW",
    )


@pytest.mark.parametrize("raw", ["false", "False", "0", "off", "", 0, False])
def test_saved_false_cannot_select_multi_door_composite_geometry(
    monkeypatch, raw,
):
    import fold_designer_bridge as bridge

    def forbidden(*args, **kwargs):
        pytest.fail("disabled Door source must not request composite geometry")
    monkeypatch.setattr(bridge, "_phase6_corner_data_part_keys", forbidden)
    monkeypatch.setattr(bridge, "_phase6_corner_data_unfold_projections", forbidden)
    events = []
    host = _host(raw, events)
    canvas = FakeCanvas()
    saved = json.loads(json.dumps({"multi_door_enabled": raw}))
    assert api.normalize_operator_settings_boolean(saved["multi_door_enabled"]) is False
    result = Phase6ApplicationHost._render_fold_designer_corner_data_view(
        host, canvas, "door_c1_r1", None,
    )
    assert result is None
    assert canvas.actions == [("delete", "all")]
    assert events == [] and host.multi_door_enabled_var.get() == raw


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "on", 1, True])
def test_true_multidoor_uses_existing_engine_resolved_part_view(
    monkeypatch, raw,
):
    import fold_designer_bridge as bridge

    sources = []
    selected = object()
    sibling = object()
    designer = object()
    monkeypatch.setattr(
        bridge, "_phase6_corner_data_part_keys",
        lambda app: sources.append(("keys", app)) or
            ("door_c1_r1", "door_c1_r2", "head"),
    )
    monkeypatch.setattr(
        bridge, "_phase6_corner_data_unfold_projections",
        lambda app, keys: sources.append(("projections", app, keys)) or
            (SimpleNamespace(part_key="door_c1_r1", render_data=selected),
             SimpleNamespace(part_key="door_c1_r2", render_data=sibling)),
    )
    events = []
    host = _host(raw, events)
    host.fold_designer_app = designer
    canvas = FakeCanvas()
    assert api.normalize_operator_settings_boolean(raw) is True
    result = Phase6ApplicationHost._render_fold_designer_corner_data_view(
        host, canvas, "door_c1_r1", None,
    )
    assert result == "COMPOSITE_VIEW"
    assert sources == [
        ("keys", designer),
        ("projections", designer, ("door_c1_r1", "door_c1_r2")),
    ]
    assert len(events) == 1 and events[0][0] == "overview"
    assert events[0][1]["render_data_by_part_key"] == {
        "door_c1_r1": selected, "door_c1_r2": sibling,
    }
    assert not any(event[0] == "delete" for event in canvas.actions)
    assert sum(event[0] == "bind" for event in canvas.actions) == 3


@pytest.mark.parametrize("bad", [
    "invalid", "2", 2, None, [], {},
    float("nan"), float("inf"), 0.5,
])
def test_invalid_door_source_is_rejected_before_any_canvas_or_geometry_change(
    monkeypatch, bad,
):
    import fold_designer_bridge as bridge
    monkeypatch.setattr(
        bridge, "_phase6_corner_data_part_keys",
        lambda *a: pytest.fail("invalid source cannot reach Door geometry"),
    )
    events = []
    host = _host(bad, events)
    canvas = FakeCanvas()
    with pytest.raises(ValueError, match="布林"):
        Phase6ApplicationHost._render_fold_designer_corner_data_view(
            host, canvas, "door_c1_r1", None,
        )
    assert canvas.actions == [] and events == []


def test_unrelated_part_display_does_not_consume_invalid_door_only_flag():
    calls = []
    canvas = FakeCanvas()
    host = _host("invalid", calls)
    assert Phase6ApplicationHost._render_fold_designer_corner_data_view(
        host, canvas, "head", None,
    ) is None
    assert canvas.actions == [("delete", "all")]
    assert calls == []


def test_missing_optional_multidoor_control_keeps_normal_part_view():
    host = SimpleNamespace()
    canvas = FakeCanvas()
    assert Phase6ApplicationHost._render_fold_designer_corner_data_view(
        host, canvas, "door_c1_r1", None,
    ) is None
    assert canvas.actions == [("delete", "all")]


def test_gui_view_only_uses_public_engine_decoded_raw_flag():
    source = inspect.getsource(
        Phase6ApplicationHost._render_fold_designer_corner_data_view
    )
    assert "manufacturing_api.normalize_operator_settings_boolean(" in source
    assert "multi_door_enabled = bool(" not in source
    assert "multi_door_var.get()" in source
