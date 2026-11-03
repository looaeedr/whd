"""#2517 Door-layout Indicator component editor uses Engine-owned physical scenes."""
from __future__ import annotations

import inspect
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
import gui


@pytest.mark.parametrize("component", ("indicator_box", "indicator_door"))
def test_door_indicator_editor_delegates_to_engine_and_retains_feature_store(monkeypatch, component):
    seen = {}
    box_scene, door_scene = object(), object()
    box_guide, door_guide = object(), object()
    box_surface, door_surface = object(), object()
    box = SimpleNamespace(surface=box_surface, width=210.0, height=180.0,
                          reference_guide=box_guide, baseline_scene=box_scene,
                          baseline_status="盒子來源")
    door = SimpleNamespace(surface=door_surface, width=120.0, height=90.0,
                           reference_guide=door_guide, baseline_scene=door_scene,
                           baseline_status="小門來源")
    spec = object()
    monkeypatch.setattr(manufacturing_api, "resolve_indicator_editor_components",
                        lambda groups, *, thickness, door_spec:
                        seen.update({"groups": list(groups), "t": thickness, "spec": door_spec})
                        or {"indicator_box": box, "indicator_door": door})
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        pytest.fail("unexpected GUI error: " + str(args)))
    stored_box = ["box-feature"]
    stored_door = ["door-feature"]
    class Cache:
        def invalidate(self, key):
            seen["invalidate"] = key
    host = SimpleNamespace(
        door_layout_indicator_states={"0:0": {
            "mode": "indicator_box", "layers": 2, "groups": [2, 3, 4],
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        }},
        _door_layout_indicator_state_for_key=lambda key:
            pytest.fail("display accessor cannot repair physical manufacturing source"),
        get_float_values=lambda: {"t": 2.0},
        _indicator_door_part_spec=lambda vals, groups, *, features:
            seen.update({"spec_features": features}) or spec,
        door_layout_indicator_box_features={"0:0": stored_box},
        door_layout_indicator_door_features={"0:0": stored_door},
        _derived_cache_owner=Cache(),
        _request_phase6_update=lambda name: seen.update({"update": name}),
        _open_unified_hole_editor=lambda *args, **kwargs:
            seen.update({"args": args, "kwargs": kwargs}),
        draw_door_layout_overview=lambda: None,
    )
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(host, "0:0", component)
    part = {"indicator_box": box, "indicator_door": door}[component]
    assert seen["groups"] == [2, 3] and seen["t"] == 2.0
    assert seen["spec"] is spec and seen["spec_features"] is stored_door
    assert seen["args"][:5] == (
        component,
        ("指示燈盒子" if component == "indicator_box" else "指示燈小門") + " [0:0]",
        part.surface, part.width, part.height,
    )
    assert seen["kwargs"]["reference_guide"] is part.reference_guide
    assert seen["kwargs"]["baseline_scene"] is part.baseline_scene
    assert seen["kwargs"]["baseline_status_text"] == part.baseline_status
    expected_store = stored_box if component == "indicator_box" else stored_door
    # Editor edits are staged, never allowed to mutate persisted feature lists
    # until sync_callback actually commits them.
    assert seen["kwargs"]["feature_list_override"] == expected_store
    assert seen["kwargs"]["feature_list_override"] is not expected_store
    seen["kwargs"]["sync_callback"]()
    assert seen["invalidate"] == "geometry" and seen["update"] == "geometry"


def test_component_editor_refuses_inactive_mode_or_unknown_component():
    calls = []
    host = SimpleNamespace(
        _door_layout_indicator_state_for_key=lambda key: {"mode": "none"},
        get_float_values=lambda: calls.append("read"),
    )
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(host, "0:0", "indicator_box")
    assert not calls
    host._door_layout_indicator_state_for_key = lambda key: {"mode": "indicator_box"}
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(host, "0:0", "other")
    assert not calls


def test_global_indicator_box_model_name_is_not_an_additional_manufacturing_selector():
    from ae_engine import baseline_scene_adapters
    source = inspect.getsource(baseline_scene_adapters.get_stretched_indicator_box_data)
    assert "model_name" in source
    assert "ignored" in source
    assert 'indicator_shared_baseline_part_path("盒子.dxf")' in source


def test_gui_indicator_component_geometry_has_no_low_level_manufacturing_owner():
    source = inspect.getsource(gui.Phase6ApplicationHost.open_door_indicator_component_editor)
    assert "manufacturing_api.resolve_indicator_editor_components(" in source
    for token in (
        "ae.get_stretched_indicator_box_data(",
        "ae.get_stretched_door_data(",
        "build_indicator_box_result(",
        "build_door_result(",
        "build_finished_reference_guide(",
        "- 2.0 *",
    ):
        assert token not in source


@pytest.mark.parametrize("invalid", (
    {"layers": True},
    {"layers": 0},
    {"layers": 1.5},
    {"layers": 7},
    {"groups": [False, 2]},
    {"groups": [0, 2]},
    {"groups": [9, 2]},
    {"offset_x": float("nan")},
    {"offset_y": "not-a-number"},
))
def test_component_editor_rejects_unrepaired_physical_input_without_side_effects(
    monkeypatch, invalid,
):
    raw = {
        "mode": "indicator_box", "layers": 2,
        "groups": [3, 2, 2, 2, 2, 2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    raw.update(invalid)
    before = deepcopy(raw)
    calls = []
    def repairing_display(key):
        calls.append("display-repaired")
        raw.clear()
        raw.update({
            "mode": "indicator_box", "layers": 1, "groups": [2] * 6,
            "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
        })
        return raw
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, msg:
                        calls.append(("refused", title, msg)))
    host = SimpleNamespace(
        door_layout_indicator_states={"0:0": raw},
        _door_layout_indicator_state_for_key=repairing_display,
        get_float_values=lambda: calls.append("read-after-bad-source"),
        _indicator_door_part_spec=lambda *args, **kw: calls.append("part-built"),
        _open_unified_hole_editor=lambda *args, **kw: calls.append("editor-open"),
    )
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(
        host, "0:0", "indicator_box",
    )
    assert raw == before
    assert len(calls) == 1 and calls[0][0] == "refused"
    assert calls[0][1] == "開孔失敗"


def test_missing_saved_cell_does_not_fabricate_an_indicator_editor(monkeypatch):
    calls = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        calls.append(("error", args)))
    host = SimpleNamespace(
        door_layout_indicator_states={},
        _door_layout_indicator_state_for_key=lambda key:
            calls.append("fabricated-display-state"),
        get_float_values=lambda: calls.append("read"),
    )
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(
        host, "0:0", "indicator_box",
    )
    assert calls == []
    assert host.door_layout_indicator_states == {}


def test_component_editor_source_has_no_gui_physical_group_cast():
    source = inspect.getsource(
        gui.Phase6ApplicationHost.open_door_indicator_component_editor
    )
    assert "project_operator_door_cell_indicator_manufacturing_source(" in source
    assert "_door_layout_indicator_state_for_key(key)" in source  # legacy only
    assert "max(1, min(6, int(" not in source
    assert "groups = [int(v)" not in source
