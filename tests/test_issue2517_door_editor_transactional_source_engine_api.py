"""#2517: opening Door previews/editors must not commit physical Feature sources."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import door_render_host_adapter as view
from gui_modules.parts.panels.door import normalize_door_indicator_state
import gui


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _saved_indicator():
    return {
        "mode": "indicator_box", "layers": 1,
        "groups": [2, 2, 2, 2, 2, 2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }


@pytest.mark.parametrize("invalid", (
    {"layers": True}, {"groups": [False, 2]}, {"offset_x": "nan"},
))
def test_display_accessor_returns_detached_state_without_repairing_saved_source(invalid):
    raw = {**_saved_indicator(), **invalid}
    original = deepcopy(raw)
    host = SimpleNamespace(
        door_layout_indicator_states={"0:0": raw},
        _normalize_door_indicator_state=normalize_door_indicator_state,
    )
    shown = view._door_layout_indicator_state_for_key(host, "0:0")
    assert shown == normalize_door_indicator_state(original)
    assert shown is not raw
    assert host.door_layout_indicator_states == {"0:0": original}
    assert host.door_layout_indicator_states["0:0"] is raw
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_door_cell_indicator_manufacturing_source(raw)

    absent = view._door_layout_indicator_state_for_key(host, "1:0")
    assert absent["mode"] == "none"
    assert "1:0" not in host.door_layout_indicator_states


def test_2d_door_preview_does_not_create_missing_feature_row(monkeypatch):
    seen = []
    monkeypatch.setattr(
        manufacturing_api, "project_operator_door_cell_features",
        lambda result, features, indicator, **kwargs:
            seen.append((features, indicator)) or (),
    )
    host = SimpleNamespace(
        door_layout_indicator_states={},
        door_layout_features={},
        _normalize_door_indicator_state=normalize_door_indicator_state,
        _baseline_source_model=lambda: "受電箱",
        fw_z_var=_var("29"), t_var=_var("2"),
        door_gap_w_var=_var("3.5"), door_gap_h_var=_var("3.5"),
        door_fold_l_var=_var("15"), door_fold_b_var=_var("15"),
    )
    cell = SimpleNamespace(start_width=500.0, start_height=800.0, edges=object())
    assert view._door_layout_cell_resolved_features(host, cell, object(), "0:0") == ()
    assert seen[0][0] == [] and seen[0][1] is None
    assert host.door_layout_features == {}
    assert host.door_layout_indicator_states == {}


@pytest.mark.parametrize("existing", (False, True))
def test_door_cell_editor_stages_features_until_explicit_sync(monkeypatch, existing):
    monkeypatch.setattr(
        gui._door_layout_host_adapter, "_receiving_live_door_layout_source",
        lambda _host: None,
    )
    monkeypatch.setattr(
        manufacturing_api, "project_operator_hole_editor_door_cell",
        lambda result, spec, **kwargs: SimpleNamespace(
            surface="door-surface", width=result.width, height=result.height,
            reference_guide="guide",
            door_indicator_context=SimpleNamespace(
                finished_width=400.0, finished_height=650.0,
            ),
            door_frame_edges=object(),
            baseline_scene=kwargs.get("baseline_scene"),
            baseline_status=kwargs.get("baseline_status"),
        ),
    )
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        pytest.fail("unexpected GUI failure " + repr(args)))
    key = "0:0"
    features = {key: ["saved-feature"]} if existing else {}
    saved_state = _saved_indicator()
    states = {key: saved_state}
    captured, commits = {}, []
    controller = SimpleNamespace(
        part_features_snapshot=lambda: {},
        replace_part_features=lambda source: commits.append(deepcopy(source)),
    )
    cell = SimpleNamespace(
        column_index=0, row_index=0, start_width=500.0,
        start_height=800.0, edges=object(),
    )
    val = {
        "door_fold_l": 15.0, "door_fold_b": 15.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "t": 2.0, "fw": 29.0,
    }
    host = SimpleNamespace(
        last_unified_hole_editor=None,
        door_layout_selected_var=SimpleNamespace(set=lambda key: None),
        get_door_layout_cells=lambda: (cell,),
        _door_layout_cell_key=lambda cell: key,
        get_float_values=lambda: dict(val),
        _door_layout_cell_result=lambda cell, values:
            SimpleNamespace(width=510.0, height=810.0),
        _door_layout_part_spec=lambda cell, values: object(),
        door_layout_features=features,
        door_layout_indicator_states=states,
        door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        _normalize_door_indicator_state=normalize_door_indicator_state,
        _door_layout_indicator_state_for_key=lambda key:
            view._door_layout_indicator_state_for_key(
                SimpleNamespace(
                    door_layout_indicator_states=states,
                    _normalize_door_indicator_state=normalize_door_indicator_state,
                ), key,
            ),
        _door_layout_baseline_scene=lambda cell, values: (None, "source"),
        _open_unified_hole_editor=lambda *args, **kwargs:
            captured.update(kwargs),
        draw_door_layout_overview=lambda: None,
        _indicator_component_editor_contexts=lambda state, values, **kw: kw,
        workspace_controller=controller,
        surface_features={},
        fold_designer_app=None,
        _request_phase6_update=lambda mode: commits.append(mode),
    )
    before_features = deepcopy(features)
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, 0, 0)

    staged = captured["feature_list_override"]
    assert staged == (["saved-feature"] if existing else [])
    assert staged is not features.get(key)
    assert captured["door_indicator_state"] is not saved_state
    assert features == before_features and states[key] == saved_state
    # Reading optional component editor sources must be read-only too.
    captured["indicator_component_context_provider"](_saved_indicator())
    assert host.door_layout_indicator_box_features == {}
    assert host.door_layout_indicator_door_features == {}

    staged.append("operator-committed-feature")
    assert features == before_features and commits == []
    captured["sync_callback"]()
    assert features[key] == staged
    assert commits[0]["door_c1_r1"] == staged
    assert commits[-1] == "geometry"


@pytest.mark.parametrize("component", ("indicator_box", "indicator_door"))
def test_indicator_component_editor_stages_until_sync(monkeypatch, component):
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args:
                        pytest.fail("unexpected GUI failure " + repr(args)))
    geom = SimpleNamespace(
        surface=object(), width=200.0, height=180.0,
        reference_guide=object(), baseline_scene=object(),
        baseline_status="source",
    )
    monkeypatch.setattr(
        manufacturing_api, "resolve_indicator_editor_components",
        lambda *args, **kwargs: {"indicator_box": geom, "indicator_door": geom},
    )
    key = "0:0"
    box = {key: ["saved-box"]}
    door = {key: ["saved-door"]}
    before_box, before_door = deepcopy(box), deepcopy(door)
    captured, updates = {}, []
    host = SimpleNamespace(
        door_layout_indicator_states={key: _saved_indicator()},
        get_float_values=lambda: {"t": 2.0},
        _indicator_door_part_spec=lambda *args, **kwargs: object(),
        door_layout_indicator_box_features=box,
        door_layout_indicator_door_features=door,
        _open_unified_hole_editor=lambda *args, **kwargs: captured.update(kwargs),
        _request_phase6_update=lambda mode: updates.append(mode),
        draw_door_layout_overview=lambda: None,
    )
    gui.Phase6ApplicationHost.open_door_indicator_component_editor(
        host, key, component,
    )
    working = captured["feature_list_override"]
    target = box if component == "indicator_box" else door
    assert working == target[key] and working is not target[key]
    working.append("committed")
    assert box == before_box and door == before_door
    captured["sync_callback"]()
    assert target[key] == working
    assert updates == ["geometry"]
