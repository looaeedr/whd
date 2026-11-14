"""#2517: legacy settings physical policy is only computed in public Engine API."""
import configparser
import inspect
from dataclasses import is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import ReliefConfig, Vec2
from ae_engine.sheetmetal_features import VaultEndCapFeaturePolicy
from phase6_settings_center import apply_settings_to_ae, save_defaults_to_ini


def _policy():
    return VaultEndCapFeaturePolicy(
        hanging_hole_radius=3.2, hanging_hole_y_from_top_bend=6.0,
        square_hole_origin=Vec2(3.0, 18.0), square_hole_size=Vec2(4.0, 4.0),
        tail_bottom_hole_radius=2.5, tail_bottom_hole_y=5.0,
    )


def _host(tmp_path):
    return SimpleNamespace(
        INI_PATH=tmp_path / "config.ini",
        config=configparser.ConfigParser(),
        RELIEF_CONFIG=ReliefConfig(),
        VAULT_ENDCAP_FEATURE_POLICY=_policy(),
        hang_hole_r=3.2, hang_hole_y_up=6.0, sq_x_left=3.0,
        sq_width=4.0, sq_y_bottom=18.0, sq_height=4.0,
        bottom_hole_r=2.5, bottom_hole_y=5.0,
        base_plate_shrink_def=55.0,
    )


def test_real_gui_settings_commit_updates_engine_fixed_cutting_policy(tmp_path):
    host = _host(tmp_path)
    old = host.VAULT_ENDCAP_FEATURE_POLICY
    assert is_dataclass(old)
    input_rows = {
        "hang_hole_r": 5.125, "hang_hole_y_up": 7.25,
        "sq_x_left": 8.75, "sq_y_bottom": 12.5,
        "sq_width": 9.0, "sq_height": 6.0,
        "bottom_hole_r": 3.75, "bottom_hole_y": 11.0,
    }
    apply_settings_to_ae(host, input_rows)
    effective = host.VAULT_ENDCAP_FEATURE_POLICY
    assert effective != old
    assert old.hanging_hole_radius == 3.2
    assert effective.hanging_hole_radius == 5.125
    assert effective.hanging_hole_y_from_top_bend == 7.25
    assert effective.square_hole_origin == Vec2(8.75, 12.5)
    assert effective.square_hole_size == Vec2(9.0, 6.0)
    assert effective.tail_bottom_hole_radius == 3.75
    assert effective.tail_bottom_hole_y == 11.0


def test_engine_and_gui_settings_use_same_relief_physical_policy(tmp_path):
    host = _host(tmp_path)
    before = host.RELIEF_CONFIG
    apply_settings_to_ae(host, {"relief_bottom_y_factor": 0.75})
    assert host.RELIEF_CONFIG.bottom_y_factor == 0.75
    assert before.bottom_y_factor == 0.5
    assert api.apply_operator_legacy_runtime_manufacturing_policies is not None


@pytest.mark.parametrize("edges,shared", [
    ((55, 55, 55, 55), 55.0),
    ((55.5, 55.5, 55.5, 55.5), 55.5),
    ((55, 55.00001, 55, 55), None),
    ((55, 54, 55, 55), None),
    ((0, 0, 0, 0), 0.0),
])
def test_legacy_base_shrink_requires_all_equal_real_edges(tmp_path, edges, shared):
    values = dict(zip((
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
    ), edges))
    assert api.operator_legacy_shared_base_plate_shrink(values) == shared
    host = _host(tmp_path)
    apply_settings_to_ae(host, values)
    assert host.base_plate_shrink_def == (shared if shared is not None else 55.0)
    save_defaults_to_ini(host, values, context="base_plate", apply_runtime=False)
    ini = configparser.ConfigParser()
    ini.read(host.INI_PATH, encoding="utf-8")
    assert (ini.getfloat("BASE_PLATE", "shrink") if ini.has_option("BASE_PLATE", "shrink") else None) == shared


def test_partial_edge_settings_never_overwrite_legacy_shared_value(tmp_path):
    host = _host(tmp_path)
    apply_settings_to_ae(host, {"base_plate_shrink_top": 50.0})
    assert host.base_plate_shrink_def == 55.0
    assert api.operator_legacy_shared_base_plate_shrink({
        "base_plate_shrink_top": 55, "base_plate_shrink_bottom": 55,
        "base_plate_shrink_left": 55,
    }) is None


def test_gui_is_only_transport_and_engine_cannot_import_gui(monkeypatch, tmp_path):
    import ae_engine.operator_settings_transactions as owner
    import phase6_settings_center as gui
    called = []
    def fake(ae_module, values, *, relief_changes=None):
        called.append((ae_module, dict(values), dict(relief_changes or {})))
    monkeypatch.setattr(owner, "apply_operator_legacy_runtime_manufacturing_policies", fake)
    host = _host(tmp_path)
    gui.apply_settings_to_ae(host, {"hang_hole_r": 7.25, "relief_bottom_y_factor": 0.9})
    assert called == [(host, {"hang_hole_r": 7.25, "relief_bottom_y_factor": 0.9},
                       {"bottom_y_factor": 0.9})]
    raw = inspect.getsource(gui.apply_settings_to_ae)
    assert "manufacturing_api.apply_operator_runtime_settings_to_ae(" in raw
    assert "setattr(" not in raw
    assert "VAULT_ENDCAP_FEATURE_POLICY" not in raw
    assert "base_plate_shrink_def" not in raw
    assert "RELIEF_CONFIG" not in raw
    for source in (inspect.getsource(owner), inspect.getsource(api.operator_legacy_shared_base_plate_shrink)):
        assert "from phase6_" not in source and "from gui_modules" not in source
