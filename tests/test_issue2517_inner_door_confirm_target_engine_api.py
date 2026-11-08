"""#2517: Receiving inner-door physical-vs-candidate persistence is Engine-owned."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine import operator_receiving_inner_door_source as owner
from gui_modules.application import receiving_inner_door_hole_editor as gui
from gui_modules.application import fold_designer_composition_receiving as composition


@pytest.mark.parametrize(
    ("source", "expected"),
    [(None, "physical"), ("single", "physical"), ("candidate", "candidate")],
)
def test_public_engine_inner_door_commit_target_preserves_operator_entry_contract(source, expected):
    serialized = json.loads(json.dumps(source))
    assert manufacturing_api.operator_receiving_inner_door_commit_target(source) == expected
    assert manufacturing_api.operator_receiving_inner_door_commit_target(serialized) == expected
    assert gui.inner_door_commit_target(source) == expected
    assert ae_engine.operator_receiving_inner_door_commit_target is (
        manufacturing_api.operator_receiving_inner_door_commit_target
    )
    assert manufacturing_api.operator_receiving_inner_door_commit_target is (
        owner.operator_receiving_inner_door_commit_target
    )


@pytest.mark.parametrize(
    "invalid",
    ("", "quantity", "set_bay", "Candidate", " candidate ", True, False,
     0, 1, 1.0, [], {}, ("single",)),
)
def test_invalid_inner_door_commit_mode_fails_closed_before_gui_or_source_mutation(invalid):
    with pytest.raises(ValueError, match="未知的內門編輯來源"):
        manufacturing_api.operator_receiving_inner_door_commit_target(invalid)
    with pytest.raises(ValueError, match="未知的內門編輯來源"):
        gui.inner_door_commit_target(invalid)

    workspace = SimpleNamespace(available_parts=(), active_part="other")
    app = SimpleNamespace(designer_workspace=workspace, _scene_query_callback=None)
    with pytest.raises(ValueError, match="未知的內門編輯來源"):
        gui.open_inner_door_hole_editor(
            app, "inner_door:upper:panel", settings_mode=invalid,
        )
    assert workspace.available_parts == ()
    assert workspace.active_part == "other"


def test_gui_entry_and_both_composition_paths_delegate_target_to_engine_public_api(monkeypatch):
    calls = []
    def engine_target(source):
        calls.append(source)
        return "candidate"
    monkeypatch.setattr(manufacturing_api, "operator_receiving_inner_door_commit_target", engine_target)
    assert gui.inner_door_commit_target("single") == "candidate"
    assert calls == ["single"]
    assert "manufacturing_api.operator_receiving_inner_door_commit_target(" in inspect.getsource(
        gui.inner_door_commit_target
    )
    composition_source = inspect.getsource(composition)
    assert composition_source.count(
        "manufacturing_api.operator_receiving_inner_door_commit_target("
    ) >= 3
    assert "from .receiving_inner_door_hole_editor import inner_door_commit_target" not in composition_source
    assert 'if mode != "candidate":' not in composition_source
