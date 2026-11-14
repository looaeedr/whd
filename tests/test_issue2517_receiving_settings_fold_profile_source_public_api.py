"""#2517: Receiving Settings-to-Fold projection consumes canonical Engine Family/Bay source.

This is a GUI-to-Engine parity test, not a new GUI manufacturing algorithm.
"""
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import fold_designer_composition_shell_settings as shell
from phase6_settings_profile_projection import SettingsProfileProjectionRequest


LIVE = {"w": 820.25, "h": 1600.5, "d": 360.75}
SAVED_DEFAULTS = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _request_controller(model, *, live=None, settings=None):
    snapshot = {"model": model, "w": 810, "h": 1650, "d": 355}
    defaults = deepcopy(SAVED_DEFAULTS if settings is None else settings)
    working = deepcopy(LIVE if live is None else live)
    seen = []
    workspace = SimpleNamespace(
        available_parts=("box_body",),
        active_part="box_body",
        part_profiles_snapshot=lambda: {},
    )
    app = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _settings_values=defaults,
        _phase6_box_whd=working,
        designer_workspace=workspace,
        state=SimpleNamespace(profiles_vault={"箱身": []}),
    )
    def required(_namespace, name):
        return {
            "SettingsProfileProjectionRequest": SettingsProfileProjectionRequest,
            "build_settings_profile_projection": lambda request: (
                seen.append(request) or request
            ),
        }[name]
    controller = SimpleNamespace(
        app=app,
        _required=required,
        apply_settings_profile_projection=lambda _ns, plan, *, render=True: plan,
    )
    return controller, app, seen


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_receiving_settings_fold_projection_uses_exact_engine_bay_source(model, monkeypatch):
    controller, app, seen = _request_controller(model)
    before = deepcopy((
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    ))
    actual = manufacturing_api.project_receiving_manufacturing_request_settings(
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    )
    called = []
    real = manufacturing_api.project_receiving_manufacturing_request_settings
    def monitored(snapshot, settings, box):
        called.append((deepcopy(snapshot), deepcopy(settings), deepcopy(box)))
        return real(snapshot, settings, box)
    monkeypatch.setattr(
        shell.manufacturing_api,
        "project_receiving_manufacturing_request_settings", monitored,
    )
    plan = shell.refresh_profiles_from_settings(controller, object(), render=False)
    assert plan is seen[0]
    assert dict(plan.settings_values) == actual
    assert {axis: plan.settings_values[axis] for axis in LIVE} == LIVE
    assert plan.settings_values["t"] == 2.0
    assert len(called) == 1
    assert (
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    ) == before
    source = inspect.getsource(shell.refresh_profiles_from_settings)
    assert "project_receiving_manufacturing_request_settings(" in source
    assert 'in {"受電箱", "RECEIVING"}' not in source


@pytest.mark.parametrize("model", ("金庫型", "VAULT", "自訂", "UNKNOWN", ""))
def test_other_family_fold_settings_keep_existing_default_priority(model):
    controller, app, seen = _request_controller(model)
    plan = shell.refresh_profiles_from_settings(controller, object(), render=False)
    assert plan is seen[0]
    assert dict(plan.settings_values) == SAVED_DEFAULTS
    assert app._phase6_box_whd == LIVE


@pytest.mark.parametrize("raw", (True, False, None, 0, -4, "nan", "inf", "bad"))
def test_invalid_receiving_live_dimension_rejected_before_fold_projection(raw):
    working = {**LIVE, "w": raw}
    controller, app, seen = _request_controller("receiving", live=working)
    before = deepcopy((
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    ))
    with pytest.raises((ValueError, TypeError)):
        shell.refresh_profiles_from_settings(controller, object(), render=False)
    assert not seen
    assert (
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    ) == before


@dataclass(frozen=True)
class TypedFeature:
    feature_id: str


def test_receiving_alias_settings_materialization_keeps_typed_confirmed_features():
    typed = TypedFeature("door_c1_r1/h1")
    live = {
        "model": "receiving",
        "receiving_layout": {"set": (typed,)},
        "part_features": {"door_c1_r1": [typed]},
    }
    app = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(live),
        state=SimpleNamespace(profiles_vault={"箱身": []}),
        designer_workspace=SimpleNamespace(
            active_part="box_body",
            available_parts=("box_body",),
        ),
    )
    saved = []
    controller = SimpleNamespace(
        app=app,
        _required=lambda _ns, name: {
            "materialize_settings_profile_value": deepcopy,
            "clone_profile": deepcopy,
        }[name],
        capabilities=SimpleNamespace(
            workspace=SimpleNamespace(
                navigation=lambda: SimpleNamespace(stash_profiles=lambda *_: None)
            )
        ),
        refresh_assembly_parts_panel_if_topology_changed=lambda *_: saved.append(1),
    )
    plan = SimpleNamespace(
        snapshot={
            "model": "receiving",
            "receiving_layout": {"set": ({"flattened": True},)},
            "part_features": {"door_c1_r1": [{"flattened": True}]},
        },
        box_body_profile=(), derived_sync_required=False, part_profiles={},
        active_part="box_body", active_profiles={},
    )
    shell.apply_settings_profile_projection(controller, object(), plan, render=False)
    assert saved == [1]
    assert app._phase6_input_snapshot["receiving_layout"] == live["receiving_layout"]
    assert app._phase6_input_snapshot["part_features"] == live["part_features"]
    assert isinstance(
        app._phase6_input_snapshot["part_features"]["door_c1_r1"][0],
        TypedFeature,
    )
