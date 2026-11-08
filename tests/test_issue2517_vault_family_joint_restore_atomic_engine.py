"""#2517 saved Vault AssemblyJoint must validate before any other GUI commit."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as gui
from phase6_endcap_semantics import assembly_intent_label, assembly_intent_value


class Var:
    def __init__(self, value, events):
        self.value = value
        self.events = events

    def get(self):
        return self.value

    def set(self, value):
        self.events.append(("var", value))
        self.value = value


def host():
    events = []
    multi = Var(False, events)
    assembly = Var("舊組合", events)
    workspace = SimpleNamespace(
        set_box_body_structure_state=lambda value: events.append(("structure", value)),
        set_box_body_profile=lambda value: events.append(("profile", value)),
    )
    app = SimpleNamespace(
        _current_cabinet_type_name=lambda: "金庫型",
        _apply_fold_designer_live_settings=lambda values, **kwargs:
            events.append(("settings", dict(values))),
        _apply_manual_corner_snapshot=lambda state, pairs:
            events.append(("corners", state, pairs)),
        workspace_controller=workspace,
        multi_door_enabled_var=multi,
        box_assembly_type_var=assembly,
        door_layout_columns=[],
        door_nameplate_center_datum_top=None,
        assembly_joint_state={"assembly_type": "OVERLAY"},
    )
    return app, events


def saved(joint=None, wrap=None):
    state = {
        "settings": {"w": "800.125", "draw_stock": "false"},
        "multi_door_enabled": "false",
        "door_nameplate_center_datum_top": "140.25",
        "door_layout_columns": [],
        "corner_state": {}, "corner_pair_same": {},
        "assembly_joint_state": joint if joint is not None else {
            "assembly_type": "INSERT_OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        },
    }
    if wrap is not None:
        state["endcap_bottom_wrap"] = wrap
    return state


@pytest.mark.parametrize("bad_joint", [
    {"assembly_joint_schema_version": 999, "assembly_type": "INSERT"},
    {"assembly_joint_schema_version": "invalid", "assembly_type": "INSERT"},
])
def test_future_or_corrupt_joint_schema_rejected_before_settings_or_corner_commit(bad_joint):
    app, events = host()
    before_joint = deepcopy(app.assembly_joint_state)
    raw = saved(joint=bad_joint)
    prior = deepcopy(raw)
    # Existing headless Engine is the only schema authority.
    with pytest.raises((ValueError, TypeError)):
        api.migrate_operator_assembly_joint_snapshot(deepcopy(bad_joint))
    with pytest.raises((ValueError, TypeError)):
        gui._restore_cabinet_family_runtime(app, raw)
    assert events == []
    assert app.assembly_joint_state == before_joint
    assert app.door_nameplate_center_datum_top is None
    assert raw == prior


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_valid_saved_joint_and_wrap_equal_original_engine_after_json_reload(model):
    app, events = host()
    app._current_cabinet_type_name = lambda: model
    wrap = {
        "mode": "INDEPENDENT",
        "head": {"enabled": True, "reserve_u": "3.5", "reserve_v": "1.0"},
        "tail": {"enabled": False, "reserve_u": "2.0", "reserve_v": "1.5"},
    }
    raw = json.loads(json.dumps(saved(wrap=wrap), ensure_ascii=False))
    prior = deepcopy(raw)
    joint = api.migrate_operator_assembly_joint_snapshot(raw["assembly_joint_state"])
    expected_wrap = api.normalize_endcap_bottom_wrap_state({
        "model": model, "endcap_bottom_wrap": wrap,
    })
    gui._restore_cabinet_family_runtime(app, raw)
    assert app.assembly_joint_state == joint
    assert app.endcap_bottom_wrap_state == expected_wrap
    assert app.box_assembly_type_var.get() == assembly_intent_label(
        assembly_intent_value(joint["assembly_type"])
    )
    assert events[0][0] == "settings"
    assert events[1][0] == "corners"
    assert raw == prior
    assert app.door_nameplate_center_datum_top == 140.25


def test_legacy_absent_joint_wrap_does_not_invent_or_override_gui_assembly():
    app, events = host()
    raw = saved()
    raw.pop("assembly_joint_state")
    gui._restore_cabinet_family_runtime(app, raw)
    assert app.assembly_joint_state == {"assembly_type": "OVERLAY"}
    assert not hasattr(app, "endcap_bottom_wrap_state")
    assert app.box_assembly_type_var.get() == "舊組合"
    assert [x[0] for x in events[:2]] == ["settings", "corners"]


def test_gui_stages_engine_joint_before_any_settings_commit():
    import inspect
    source = inspect.getsource(gui._restore_cabinet_family_runtime)
    assert source.index("manufacturing_api.migrate_operator_assembly_joint_snapshot(") < source.index(
        "self._apply_fold_designer_live_settings("
    )
    assert source.index("normalize_endcap_bottom_wrap_state(") < source.index(
        "self._apply_fold_designer_live_settings("
    )
    assert "next_joint_state = manufacturing_api.migrate_operator_assembly_joint_snapshot" in source
