"""#2517 Vault Family restore preflights Corner using the real public Engine owner."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import (
    new_manual_corner_pair_same_state, new_manual_corner_state,
)
from gui_modules.application import cabinet_controller as cabinet
from gui_modules.application import lifecycle


PARTS = ("head", "tail", "door", "base_plate")


class TrackedVar:
    def __init__(self, value, events=None):
        self.value = value
        self.events = events

    def get(self):
        return self.value

    def set(self, value):
        if self.events is not None:
            self.events.append(("variable", value))
        self.value = value


def host(model="自訂"):
    events = []
    state = new_manual_corner_state(PARTS)
    pairs = new_manual_corner_pair_same_state(PARTS)
    workspace = SimpleNamespace(
        set_box_body_structure_state=lambda value: events.append(("structure", value)),
        set_box_body_profile=lambda value: events.append(("profile", value)),
    )
    app = SimpleNamespace(
        baseline_var=TrackedVar(model),
        _current_cabinet_type_name=lambda: "金庫型" if model == "自訂" else model,
        manual_corner_state=state,
        manual_corner_pair_same=pairs,
        refresh_corner_type_panel=lambda: events.append(("corner_ui",)),
        _apply_fold_designer_live_settings=lambda values, **kw:
            events.append(("settings", dict(values), kw)),
        workspace_controller=workspace,
        multi_door_enabled_var=TrackedVar(False, events),
        door_layout_columns=[],
        door_nameplate_center_datum_top=None,
    )
    # Execute the *real* saved Corner apply, not a stub that silently accepts
    # invalid serialized manufacturing sources.
    app._apply_manual_corner_snapshot = lambda *args: lifecycle._apply_manual_corner_snapshot(
        app, *args
    )
    return app, events


def saved(corners=None, pairs=None):
    return {
        "settings": {"w": "800.125", "draw_stock": "false"},
        "multi_door_enabled": "false",
        "corner_state": {"head": {"top_left": "OVERLAY"}} if corners is None else corners,
        "corner_pair_same": {"head": {"top": False}} if pairs is None else pairs,
        "door_layout_columns": [],
    }


@pytest.mark.parametrize(("model", "broken"), (
    ("金庫型", "bad_saved_pair"), ("自訂", "bad_saved_pair"),
    ("金庫型", "bad_saved_corner"), ("自訂", "bad_saved_corner"),
    ("金庫型", "bad_live_family"), ("受電箱", "bad_live_family"),
))
def test_invalid_late_corner_rejects_entire_family_restore_before_settings(model, broken):
    app, events = host(model)
    if broken == "bad_live_family":
        app.manual_corner_state["tail"].pop("bottom_right")
        payload = saved()
    elif broken == "bad_saved_pair":
        payload = saved(pairs={"head": {"top": False}, "tail": ["not-an-object"]})
    else:
        payload = saved(corners={"head": {"top_left": "OVERLAY"}, "tail": ["invalid"]})
    original_source = deepcopy(payload)
    initial_corners = deepcopy(app.manual_corner_state)
    initial_pairs = deepcopy(app.manual_corner_pair_same)
    with pytest.raises((ValueError, TypeError, AttributeError, KeyError)):
        api.propose_operator_saved_manual_corner_snapshot(
            app.manual_corner_state, app.manual_corner_pair_same,
            saved_corner_state=payload["corner_state"],
            saved_corner_pair_same=payload["corner_pair_same"],
            baseline_model=model, cabinet_family=app._current_cabinet_type_name(),
        )
    with pytest.raises((ValueError, TypeError, AttributeError, KeyError)):
        cabinet._restore_cabinet_family_runtime(app, payload)
    assert events == []
    assert app.manual_corner_state == initial_corners
    assert app.manual_corner_pair_same == initial_pairs
    assert payload == original_source


@pytest.mark.parametrize("model", ("金庫型", "受電箱", "自訂"))
def test_saved_corner_uses_same_engine_candidate_with_json_and_keeps_live_aliases(model):
    app, events = host(model)
    payload = json.loads(json.dumps(saved(
        corners={
            "head": {"top_left": {"type_id": "C02", "rotation_quadrants": 1},
                     "bottom_left": {"type_id": "BAD_CORNER"}},
            "tail": {"top_left": "OVERLAY"},
        },
        pairs={"head": {"top": False}, "tail": {"bottom": True}},
    ), ensure_ascii=False))
    original_source = deepcopy(payload)
    state_aliases = {key: app.manual_corner_state[key] for key in PARTS}
    pair_aliases = {key: app.manual_corner_pair_same[key] for key in PARTS}
    expected = api.propose_operator_saved_manual_corner_snapshot(
        app.manual_corner_state, app.manual_corner_pair_same,
        saved_corner_state=payload["corner_state"],
        saved_corner_pair_same=payload["corner_pair_same"],
        baseline_model=model, cabinet_family=app._current_cabinet_type_name(),
    )
    cabinet._restore_cabinet_family_runtime(app, payload)
    assert (app.manual_corner_state, app.manual_corner_pair_same) == expected
    for part in PARTS:
        assert app.manual_corner_state[part] is state_aliases[part]
        assert app.manual_corner_pair_same[part] is pair_aliases[part]
    assert events[0][0] == "settings"
    assert events[1][0] == "corner_ui"
    assert payload == original_source


def test_family_controller_preflights_public_corner_engine_before_settings_commit():
    source = inspect.getsource(cabinet._restore_cabinet_family_runtime)
    assert "manufacturing_api.propose_operator_saved_manual_corner_snapshot(" in source
    assert source.index("manufacturing_api.propose_operator_saved_manual_corner_snapshot(") < (
        source.index("self._apply_fold_designer_live_settings(")
    )
    assert "from ae_engine.corner_type_ui import" not in source


def test_empty_saved_corner_still_detects_corrupt_certified_live_tail_before_settings():
    app, events = host("金庫型")
    app.manual_corner_state["tail"].pop("bottom_right")
    before = deepcopy(app.manual_corner_state)
    payload = saved(corners={}, pairs={})
    original = deepcopy(payload)
    with pytest.raises((KeyError, ValueError)):
        cabinet._restore_cabinet_family_runtime(app, payload)
    assert events == []
    assert app.manual_corner_state == before
    assert payload == original
