"""#2517 Receiving Set/Bay live Fold state keeps the Engine's exact W/H/D."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_composition_receiving as gui
from ae_engine.receiving_layout import new_receiving_layout


class Var:
    def __init__(self, text):
        self.text = text
    def get(self):
        return self.text
    def set(self, text):
        self.text = text


def _host(monkeypatch, projected, *, mode="set_bay", forbidden_geometry=False):
    events = []
    physical = dict(projected)
    physical["active_mode"] = mode
    physical["receiving_layout"] = {"sets": []}
    state = SimpleNamespace(w=800., h=1600., d=350.)
    initial_snapshot = {"model": "受電箱", "active_mode": mode, "w": 800., "h": 1600., "d": 350.}
    app = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(initial_snapshot),
        _phase6_box_whd={"w": 800., "h": 1600., "d": 350.},
        _phase6_receiving_set_bay_guard=False,
        designer_workspace=SimpleNamespace(
            available_parts=(),
            face_features_for=lambda key: {},
            stash_features=lambda key, rows: events.append("stash_feature"),
            stash_face_features=lambda key, rows: events.append("stash_face"),
        ),
        state=state,
        v_w=Var("800"), v_h=Var("1600"), v_d=Var("350"),
    )
    source_calls = []
    def project(snapshot, *, set_index, bay_index, validate_common):
        source_calls.append((set_index, bay_index, validate_common))
        return deepcopy(physical)
    def replace_mapping(app, name, value):
        events.append("replace_" + name)
        setattr(app, name, deepcopy(value))
    ports = {
        "project_receiving_bay_legacy_aliases": project,
        "_phase6_replace_mapping": replace_mapping,
        "_setting_number_text": lambda value: f"{value:g}",
        "original": SimpleNamespace(get_int=lambda value: pytest.fail(
            "legacy get_int must not round physical Bay W/H/D"
        )),
    }
    adapter = SimpleNamespace(
        layout={"sets": []},
        selection=SimpleNamespace(set_index=0, bay_index=0),
    )
    owner = SimpleNamespace(
        app=app,
        _required=lambda namespace, name: ports[name],
        receiving_adapter=lambda namespace: adapter,
        refresh_receiving_set_bay_control=lambda namespace: events.append("refresh"),
        refresh_back_panel_mode_control=lambda namespace: events.append("back"),
    )
    real = api.normalize_operator_live_box_dimensions
    def validated(source):
        events.append("engine_validate")
        return real(source)
    monkeypatch.setattr(api, "normalize_operator_live_box_dimensions", validated)
    if forbidden_geometry:
        def no_geometry(*args, **kwargs):
            pytest.fail("invalid Bay W/H/D must fail before Engine geometry")
        monkeypatch.setattr(api, "project_operator_receiving_live_bay_features", no_geometry)
    else:
        monkeypatch.setattr(
            api, "project_operator_receiving_live_bay_features",
            lambda *a, **k: SimpleNamespace(
                surface_updates=(), inner_panel_updates=(),
                box_body_joint_faces=(),
            ),
        )
    return owner, events, source_calls


@pytest.mark.parametrize("mode", ("set_bay", "quantity"))
def test_receiving_sync_uses_one_engine_validated_fractional_projection(monkeypatch, mode):
    physical = {"w": 820.25, "h": 1600.5, "d": 350.75}
    owner, events, calls = _host(monkeypatch, physical, mode=mode)
    assert gui.sync_receiving_current_bay(owner, {}, refresh_controls=False) is True
    assert calls == [(0, 0, True)]
    assert events[:3] == [
        "engine_validate", "replace__phase6_input_snapshot",
        "replace__phase6_box_whd",
    ]
    state = owner.app.state
    assert (state.w, state.h, state.d) == (820.25, 1600.5, 350.75)
    assert owner.app._phase6_box_whd == physical
    assert (owner.app.v_w.get(), owner.app.v_h.get(), owner.app.v_d.get()) == (
        "820.25", "1600.5", "350.75",
    )
    assert owner.app._phase6_receiving_set_bay_guard is False
    saved = json.loads(json.dumps(owner.app._phase6_input_snapshot))
    assert api.normalize_operator_live_box_dimensions(saved) == physical


@pytest.mark.parametrize("axis,bad", [
    ("w", True), ("w", False), ("w", "nan"), ("w", None),
    ("h", 0), ("h", -10), ("h", float("inf")),
    ("d", "not-a-number"), ("d", float("-inf")),
])
def test_invalid_projected_physical_dimension_cannot_update_any_gui_or_fold_state(monkeypatch, axis, bad):
    physical = {"w": 820.25, "h": 1600.5, "d": 350.75}
    physical[axis] = bad
    owner, events, _ = _host(
        monkeypatch, physical, forbidden_geometry=True,
    )
    before = deepcopy((
        owner.app._phase6_input_snapshot,
        owner.app._phase6_box_whd,
        vars(owner.app.state),
        (owner.app.v_w.get(), owner.app.v_h.get(), owner.app.v_d.get()),
    ))
    with pytest.raises(ValueError, match="包外尺寸"):
        gui.sync_receiving_current_bay(owner, {})
    assert events == ["engine_validate"]
    assert before == (
        owner.app._phase6_input_snapshot,
        owner.app._phase6_box_whd,
        vars(owner.app.state),
        (owner.app.v_w.get(), owner.app.v_h.get(), owner.app.v_d.get()),
    )


def test_real_receiving_layout_reprojects_exact_decimal_source_without_rounding():
    layout = new_receiving_layout(width=800., height=1600., depth=350.)
    layout = api.update_receiving_bay(
        layout, set_index=0, bay_index=0,
        width=820.25, height=1600.5, depth=350.75,
    )
    raw = {
        "model": "受電箱", "active_mode": "set_bay",
        "t": 2.0, "fw": 29.0, "receiving_layout": layout,
    }
    before = deepcopy(raw)
    projected = api.project_receiving_bay_legacy_aliases(
        raw, set_index=0, bay_index=0, validate_common=False,
    )
    assert api.normalize_operator_live_box_dimensions(projected) == {
        "w": 820.25, "h": 1600.5, "d": 350.75,
    }
    assert raw == before


def test_receiving_gui_does_not_round_authoritative_live_bay_dimensions():
    source = inspect.getsource(gui.sync_receiving_current_bay)
    assert "manufacturing_api.normalize_operator_live_box_dimensions(" in source
    assert "original.get_int" not in source
    assert "number = float if" not in source
    assert source.index("normalize_operator_live_box_dimensions(") < source.index(
        'required("_phase6_replace_mapping")('
    )
    assert 'app.state.w = physical["w"]' in source
    assert 'app.state.h = physical["h"]' in source
    assert 'app.state.d = physical["d"]' in source


def _legacy_fold_render_host(*, w="820.25", h="1600.5", d="350.75"):
    from types import SimpleNamespace

    state = SimpleNamespace(
        w=800., h=1600., d=350., symmetric=False, enable_y=False,
        alpha_bend=None, alpha_face=None,
    )
    rendered = []
    vars_ = (
        Var(w), Var(h), Var(d), Var(True), Var(False),
        Var("legacy bend"), Var("legacy face"),
    )
    app = SimpleNamespace(
        v_w=vars_[0], v_h=vars_[1], v_d=vars_[2],
        v_sy=vars_[3], v_ey=vars_[4],
        v_a_bend=vars_[5], v_a_face=vars_[6],
        state=state,
    )
    app.renderer = SimpleNamespace(
        render=lambda: rendered.append((
            state.w, state.h, state.d, state.symmetric, state.enable_y,
            state.alpha_bend, state.alpha_face,
        )),
    )
    return app, rendered


def test_real_fold_bridge_legacy_renderer_uses_engine_exact_fractional_dimensions():
    from fold_designer_bridge import _phase6_render_with_engine_live_dimensions

    app, rendered = _legacy_fold_render_host()
    assert _phase6_render_with_engine_live_dimensions(app) is None
    assert rendered == [(
        820.25, 1600.5, 350.75, True, False,
        "legacy bend", "legacy face",
    )]
    assert (app.state.w, app.state.h, app.state.d) == (
        820.25, 1600.5, 350.75,
    )


@pytest.mark.parametrize("axis,bad", [
    ("w", True), ("w", "nan"), ("h", 0), ("h", float("inf")),
    ("d", None), ("d", "invalid"),
])
def test_fold_redraw_refuses_invalid_physical_dimensions_before_state_or_render(axis, bad):
    from fold_designer_bridge import _phase6_render_with_engine_live_dimensions

    app, rendered = _legacy_fold_render_host()
    getattr(app, "v_" + axis).set(bad)
    old = deepcopy(vars(app.state))
    with pytest.raises(ValueError, match="包外尺寸"):
        _phase6_render_with_engine_live_dimensions(app)
    assert vars(app.state) == old
    assert rendered == []


def test_fold_bridge_all_redraw_routes_call_one_engine_validated_adapter():
    import inspect
    import fold_designer_bridge

    source = inspect.getsource(fold_designer_bridge)
    assert "def _phase6_render_with_engine_live_dimensions(" in source
    adapter = inspect.getsource(
        fold_designer_bridge._phase6_render_with_engine_live_dimensions
    )
    assert "manufacturing_api.normalize_operator_live_box_dimensions(" in adapter
    assert "get_int(self.v_" not in adapter
    assert "original.MainApp.do_update(self)" not in source
    assert source.count("_phase6_render_with_engine_live_dimensions(self)") >= 4
