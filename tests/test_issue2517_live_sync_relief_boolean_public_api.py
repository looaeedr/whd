"""#2517: live-sync and Relief source flags are interpreted only by public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_composition_state as gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _payload_host(source):
    events = []
    workspace = {
        "existing_parts": ["box_body"], "part_profiles": {},
        "box_body_profile": [], "part_features": {},
        "part_face_features": {}, "assembly_placements": {},
    }
    app = SimpleNamespace(
        _phase6_input_snapshot=source,
        _settings_values={"w": 800.0, "h": 1600.0, "d": 350.0},
        baseline_model_var=Var("金庫型"),
        _phase6_endcap_fw_state=api.normalize_endcap_fw_state({"fw": 25}),
        _phase6_corner_state={}, _phase6_corner_pair_same={},
    )
    owner = SimpleNamespace(
        app=app,
        _required=lambda _namespace, name: {
            "clone_profile": deepcopy,
            "normalize_endcap_fw_state": api.normalize_endcap_fw_state,
        }[name],
        collect_workspace_state=lambda _namespace: (
            events.append("collected"), deepcopy(workspace)
        )[1],
        serialize_assembly_relief_state=lambda _namespace: {"enabled": False},
    )
    return owner, events


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("door_raw,distance_raw,door_expected,distance_expected", (
    ("false", "false", False, False),
    ("TRUE", "0", True, False),
    (1, "on", True, True),
    ("no", 1, False, True),
    (False, True, False, True),
))
def test_live_sync_stable_flags_match_engine_and_survive_json_reload(
    family, door_raw, distance_raw, door_expected, distance_expected
):
    source = {
        "model": family, "multi_door_enabled": door_raw,
        "use_box_distance": distance_raw,
    }
    before = deepcopy(source)
    owner, events = _payload_host(source)
    payload = gui.corner_transaction_payload(owner, None)
    assert payload["multi_door_enabled"] is door_expected
    assert payload["use_box_distance"] is distance_expected
    assert payload["multi_door_enabled"] == api.normalize_operator_settings_boolean(door_raw)
    assert payload["use_box_distance"] == api.normalize_operator_settings_boolean(distance_raw)
    restored = json.loads(json.dumps(payload))
    assert restored["multi_door_enabled"] is door_expected
    assert restored["use_box_distance"] is distance_expected
    assert source == before
    assert events == ["collected"]


@pytest.mark.parametrize("field,bad", (
    ("multi_door_enabled", "maybe"),
    ("multi_door_enabled", 2),
    ("multi_door_enabled", None),
    ("multi_door_enabled", float("nan")),
    ("use_box_distance", "2"),
    ("use_box_distance", 1.25),
    ("use_box_distance", None),
    ("use_box_distance", []),
))
def test_corrupt_live_sync_flag_rejects_before_collecting_workspace(field, bad):
    source = {
        "model": "受電箱", "multi_door_enabled": "false",
        "use_box_distance": "false",
    }
    source[field] = bad
    before = deepcopy(source)
    owner, events = _payload_host(source)
    with pytest.raises(ValueError, match="布林值"):
        gui.corner_transaction_payload(owner, None)
    assert source == before
    assert events == []


@pytest.mark.parametrize("enabled_raw,expected", (
    ("false", False), ("true", True), (0, False), (1, True),
))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_relief_source_fallback_bool_uses_engine_on_save_and_reload(
    family, enabled_raw, expected
):
    source = {"model": family, "assembly_relief": {}}
    app = SimpleNamespace(
        assembly_ignore_fixed_corner_var=Var(enabled_raw),
        _phase6_last_relief_solutions={},
        designer_workspace=SimpleNamespace(available_parts=()),
        _phase6_input_snapshot=source,
    )
    owner = SimpleNamespace(
        app=app,
        _required=lambda _namespace, name: {
            "_phase6_current_relief_source_signature": lambda *_: {},
            "_phase6_assembly_relief_clearance": lambda *_: 0.25,
        }[name],
    )
    before = deepcopy(source)
    state = gui.serialize_assembly_relief_state(owner, None)
    direct = api.build_persisted_relief_state(
        required_parts=(), solutions={}, source_signature={},
        prior_state={}, fallback_enabled=expected, clearance=0.25,
    )
    assert state == direct and state["fallback_enabled"] is expected
    assert json.loads(json.dumps(state)) == direct
    assert source == before


@pytest.mark.parametrize("bad", ("maybe", "2", None, 2, 1.1, float("inf")))
def test_invalid_relief_fallback_flag_cannot_persist_as_enabled(bad):
    source = {"model": "金庫型", "assembly_relief": {"enabled": False}}
    app = SimpleNamespace(
        assembly_ignore_fixed_corner_var=Var(bad),
        _phase6_last_relief_solutions={},
        designer_workspace=SimpleNamespace(available_parts=()),
        _phase6_input_snapshot=source,
    )
    owner = SimpleNamespace(
        app=app,
        _required=lambda _namespace, name: (_ for _ in ()).throw(
            AssertionError("invalid flag should be rejected before signature")
        ),
    )
    before = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        gui.serialize_assembly_relief_state(owner, None)
    assert source == before


def test_missing_relief_widget_keeps_existing_default_compatibility():
    owner = SimpleNamespace(
        app=SimpleNamespace(
            _phase6_last_relief_solutions={},
            designer_workspace=SimpleNamespace(available_parts=()),
            _phase6_input_snapshot={},
        ),
        _required=lambda _namespace, name: {
            "_phase6_current_relief_source_signature": lambda *_: {},
            "_phase6_assembly_relief_clearance": lambda *_: 0.25,
        }[name],
    )
    assert gui.serialize_assembly_relief_state(owner, None)["fallback_enabled"] is True


def test_live_source_routes_have_no_gui_boolean_manufacturing_coercion():
    live = inspect.getsource(gui.corner_transaction_payload)
    relief = inspect.getsource(gui.serialize_assembly_relief_state)
    assert "manufacturing_api.normalize_operator_settings_boolean(" in live
    assert "manufacturing_api.normalize_operator_settings_boolean(" in relief
    assert 'bool(source.get("multi_door_enabled"' not in live
    assert 'bool(source.get("use_box_distance"' not in live
    assert "bool(enabled_var.get())" not in relief
