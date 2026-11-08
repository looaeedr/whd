"""#2517: Fold Designer project load/export must retain exact Engine W/H/D."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

import fold_designer_bridge as bridge


class Var:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


def _host():
    actions = []
    state = SimpleNamespace(
        w=400, h=500, d=250, profiles_vault={}, struct_mode="vault",
    )
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 400, "h": 500, "d": 250},
        _phase6_last_w=400, _phase6_last_d=250,
        _phase6_sync_ready=False, state=state,
        v_w=Var(400), v_h=Var(500), v_d=Var(250),
        v_mode=Var("vault"),
        bend_ui=SimpleNamespace(
            rebuild_tabs=lambda: actions.append("tabs"),
            save=lambda: actions.append("save"),
        ),
        do_update=lambda: actions.append("update"),
    )
    return app, actions


def _patch_loading(monkeypatch):
    monkeypatch.setattr(bridge, "_phase6_receiving_layout_applicable",
                        lambda self: False)
    monkeypatch.setattr(bridge, "_phase6_apply_box_symmetry_policy",
                        lambda self: None)
    monkeypatch.setattr(bridge, "build_box_body_profile",
                        lambda snapshot: [{"len": 8, "core": "W"}])
    monkeypatch.setattr(bridge, "build_endcap_profile",
                        lambda snapshot: [{"len": 7}])


@pytest.mark.parametrize("family", ("金庫型", "受電箱", "RECEIVING", "receiving"))
def test_project_load_retains_fractional_operator_finished_box_dimensions(
        family, monkeypatch):
    _patch_loading(monkeypatch)
    app, actions = _host()
    snap = {"model": family, "w": "820.25", "h": 1600.5, "d": "360.75",
            "t": 2, "fw": 29}
    original = deepcopy(snap)
    bridge.Phase6FoldDesignerApp.load_phase6_snapshot(app, snap)
    assert (app.state.w, app.state.h, app.state.d) == (
        820.25, 1600.5, 360.75,
    )
    assert tuple(float(v.get()) for v in (app.v_w, app.v_h, app.v_d)) == (
        820.25, 1600.5, 360.75,
    )
    assert (app._phase6_last_w, app._phase6_last_d) == (820.25, 360.75)
    assert actions == ["tabs", "update"]
    assert snap == original
    assert app._phase6_input_snapshot["w"] == "820.25"
    assert "normalize_operator_live_box_dimensions(" in inspect.getsource(
        bridge.Phase6FoldDesignerApp.load_phase6_snapshot,
    )


def test_legacy_nested_settings_dimensions_are_only_missing_field_fallback(monkeypatch):
    _patch_loading(monkeypatch)
    app, _ = _host()
    snapshot = {
        "model": "金庫型", "h": 1700.125, "t": 2,
        "settings": {"w": "610.75", "h": 1600, "d": "300.25"},
    }
    bridge.Phase6FoldDesignerApp.load_phase6_snapshot(app, snapshot)
    assert (app.state.w, app.state.h, app.state.d) == (
        610.75, 1700.125, 300.25,
    )
    assert snapshot["settings"]["h"] == 1600
    assert app._phase6_input_snapshot["h"] == 1700.125


@pytest.mark.parametrize("field", ("w", "h", "d"))
@pytest.mark.parametrize("invalid", (True, None, -1, 0, "nan", "bad"))
def test_bad_project_physical_dimension_rejected_before_mutation(
        field, invalid, monkeypatch):
    _patch_loading(monkeypatch)
    app, actions = _host()
    saved = deepcopy((app._phase6_input_snapshot, app.state.profiles_vault))
    snapshot = {"model": "金庫型", "w": 820, "h": 1600, "d": 350}
    snapshot[field] = invalid
    with pytest.raises((TypeError, ValueError)):
        bridge.Phase6FoldDesignerApp.load_phase6_snapshot(app, snapshot)
    assert (app._phase6_input_snapshot, app.state.profiles_vault) == saved
    assert actions == []
    assert app._phase6_last_w == 400 and app._phase6_last_d == 250


def test_receiving_bay_projected_dimensions_rechecked_before_editor_tabs(
        monkeypatch):
    _patch_loading(monkeypatch)
    monkeypatch.setattr(bridge, "_phase6_receiving_layout_applicable",
                        lambda self: True)
    monkeypatch.setattr(bridge, "_phase6_receiving_adapter",
                        lambda self, **kwargs: None)
    def sync(self, **kwargs):
        self._phase6_input_snapshot.update(
            {"w": 820.25, "h": 1600.5, "d": 360.75},
        )
    monkeypatch.setattr(bridge, "_phase6_sync_receiving_current_bay", sync)
    app, _ = _host()
    snapshot = {"model": "受電箱", "w": 800, "h": 1600, "d": 350}
    bridge.Phase6FoldDesignerApp.load_phase6_snapshot(app, snapshot)
    assert (app.state.w, app.state.h, app.state.d) == (
        820.25, 1600.5, 360.75,
    )


def _patch_export(monkeypatch):
    monkeypatch.setattr(bridge, "read_box_body_profile",
                        lambda profile, snapshot: {
                            "w": 820, "d": 361, "fw": 29,
                        })
    monkeypatch.setattr(bridge, "read_endcap_profile",
                        lambda profile: {"ybottom1": 15})


def test_legacy_fold_export_keeps_real_live_whd_not_rounded_core(monkeypatch):
    _patch_export(monkeypatch)
    app, actions = _host()
    app._phase6_input_snapshot = {
        "model": "金庫型", "w": 800, "h": 1600, "d": 350,
    }
    app.state.profiles_vault = {
        "箱身": [], "封頭": [], "封尾": [],
    }
    for var, value in zip(
        (app.v_w, app.v_h, app.v_d),
        ("820.25", "1600.5", "360.75"),
    ):
        var.set(value)
    result = bridge.Phase6FoldDesignerApp.export_phase6_snapshot(app)
    assert (result["w"], result["h"], result["d"]) == (
        820.25, 1600.5, 360.75,
    )
    assert result["ybottom1"] == 15
    assert actions == ["save"]


@pytest.mark.parametrize("bad", (True, "nan", 0))
def test_legacy_export_bad_whd_rejects_before_bend_save(bad, monkeypatch):
    _patch_export(monkeypatch)
    app, actions = _host()
    app.v_h = SimpleNamespace(get=lambda: bad)
    with pytest.raises((TypeError, ValueError)):
        bridge.Phase6FoldDesignerApp.export_phase6_snapshot(app)
    assert actions == []
