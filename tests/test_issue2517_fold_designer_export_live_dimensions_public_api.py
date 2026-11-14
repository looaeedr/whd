"""#2517: live physical W/H/D must survive Fold Designer Save/Export."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

import fold_designer_bridge as bridge


class Var:
    def __init__(self, value):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


def _host(*, model="受電箱", part="box_body", dimensions=None, settings=None,
          quantity=None, endcap_profiles=None):
    dims = dict(dimensions or {"w": 820.25, "h": 1600.5, "d": 360.75})
    saved = {"model": model, "t": 2.0, "fw": 29.0, **dims}
    if quantity is not None:
        saved["active_mode"] = "quantity"
        saved["receiving_quantity_box"] = deepcopy(quantity)
    workspace = SimpleNamespace(
        active_part=part,
        profiles_for=lambda key: deepcopy(endcap_profiles or {}),
        snapshot=lambda: {
            "part_profiles": {}, "part_features": {},
            "part_face_features": {}, "existing_parts": [],
        },
    )
    calls = []
    app = SimpleNamespace(
        _phase6_box_whd=dims, _phase6_input_snapshot=saved,
        _settings_values=dict(settings or {"w": 800, "h": 1600, "d": 350}),
        _phase6_corner_state={}, _phase6_corner_pair_same={},
        _phase6_endcap_fw_state={}, _phase6_endcap_bottom_wrap_state={},
        designer_workspace=workspace,
        state=SimpleNamespace(active_bend="箱身", struct_mode="vault"),
        v_mode=Var("vault"),
        v_w=Var(str(dims.get("w"))), v_h=Var(str(dims.get("h"))),
        v_d=Var(str(dims.get("d"))),
        bend_ui=SimpleNamespace(rebuild_tabs=lambda: None),
        _save_current_part=lambda **kwargs: calls.append(kwargs),
    )
    return app, calls


def _patch_legacy(monkeypatch, *, readback=None):
    monkeypatch.setattr(bridge, "_phase6_workspace_navigation",
                        lambda self: SimpleNamespace(set_switching=lambda *_: None))
    monkeypatch.setattr(bridge, "_FIX10_EXPORT",
                        lambda self: {"w": 800, "h": 1600, "d": 350, "fw": 29})
    monkeypatch.setattr(bridge, "normalize_endcap_fw_state", lambda source: {})
    monkeypatch.setattr(bridge, "normalize_endcap_bottom_wrap_state", lambda source: {})
    if readback is not None:
        monkeypatch.setattr(bridge, "read_endcap_xy_profiles",
                            lambda *args: deepcopy(readback))


@pytest.mark.parametrize("model", ("金庫型", "受電箱", "RECEIVING", "receiving"))
@pytest.mark.parametrize("part", ("box_body", "door"))
def test_export_live_physical_dimensions_override_stale_settings(
        model, part, monkeypatch):
    _patch_legacy(monkeypatch)
    app, calls = _host(model=model, part=part)
    raw = deepcopy(app._phase6_box_whd)
    result = bridge._fix11_export(app)
    assert calls == [{"notify": False}]
    assert {axis: result[axis] for axis in raw} == raw
    assert app._phase6_box_whd == raw
    assert app._settings_values == {"w": 800, "h": 1600, "d": 350}
    source = inspect.getsource(bridge._fix11_export)
    assert "normalize_operator_live_box_dimensions(" in source
    assert "dimension_number = " not in source


@pytest.mark.parametrize("bad", (True, None, 0, -1, "nan", float("inf"), "invalid"))
def test_export_invalid_physical_source_rejected_before_any_save(bad, monkeypatch):
    _patch_legacy(monkeypatch)
    app, calls = _host(dimensions={"w": bad, "h": 1600, "d": 350})
    before = deepcopy((app._phase6_box_whd, app._phase6_input_snapshot))
    with pytest.raises((TypeError, ValueError)):
        bridge._fix11_export(app)
    assert calls == []
    assert (app._phase6_box_whd, app._phase6_input_snapshot) == before


def test_head_export_keeps_live_whd_not_integer_fold_readback(monkeypatch):
    _patch_legacy(monkeypatch, readback={
        "w": 820, "d": 361, "fw": 29, "yl1": 15, "ybottom1": 15,
    })
    app, _ = _host(part="head", endcap_profiles={"X": [{"len": 1.0}]})
    output = bridge._fix11_export(app)
    assert (output["w"], output["h"], output["d"]) == (820.25, 1600.5, 360.75)
    assert (app._phase6_box_whd["w"], app._phase6_box_whd["d"]) == (820.25, 360.75)
    assert (app._phase6_input_snapshot["w"], app._phase6_input_snapshot["d"]) == (820.25, 360.75)
    assert output["yl1"] == 15


def test_receiving_quantity_uses_saved_common_box_and_engine_validation(monkeypatch):
    _patch_legacy(monkeypatch, readback={"w": 820, "d": 360, "fw": 29})
    app, _ = _host(part="tail", quantity={"w": "830.125", "d": "370.625"},
                    endcap_profiles={"Y": [{"len": 15.0}]})
    output = bridge._fix11_export(app)
    assert (output["w"], output["h"], output["d"]) == (830.125, 1600.5, 370.625)
    assert app._phase6_box_whd == {"w": 830.125, "h": 1600.5, "d": 370.625}


def test_rejected_quantity_dimensions_do_not_mutate_live_box(monkeypatch):
    _patch_legacy(monkeypatch, readback={"w": 820, "d": 360})
    app, _ = _host(part="head", quantity={"w": True, "d": 370.625},
                    endcap_profiles={"X": [{"len": 1.0}]})
    before = deepcopy(app._phase6_box_whd)
    with pytest.raises((TypeError, ValueError)):
        bridge._fix11_export(app)
    assert app._phase6_box_whd == before
