import ast
import dataclasses
import json
from pathlib import Path

import pytest


def _contains_mutable(value):
    from collections.abc import Mapping
    if isinstance(value, (dict, list, set)):
        return True
    if isinstance(value, Mapping):
        return any(_contains_mutable(k) or _contains_mutable(v) for k, v in value.items())
    if isinstance(value, tuple):
        return any(_contains_mutable(v) for v in value)
    if dataclasses.is_dataclass(value):
        return any(_contains_mutable(getattr(value, f.name)) for f in dataclasses.fields(value))
    return False


def test_issue390_settings_state_is_deeply_immutable():
    from phase6_settings_contracts import SettingsStateSnapshot

    settings = {"t": 2.0, "nested": {"rows": [1, 2]}}
    corners = {"head": {"top_left": {"type": "A"}}}
    state = SettingsStateSnapshot(
        settings_values=settings,
        input_snapshot={"w": 800, "h": 1800, "d": 400},
        box_whd={"w": 800, "h": 1800, "d": 400},
        pending_settings={"fw": 29},
        endcap_fw_state={"head": 29},
        endcap_bottom_wrap_state={"head": {"enabled": True}},
        corner_state=corners,
        corner_pair_same={"head": True},
        assembly_type="INSERT_OVERLAY",
        last_external_revision=4,
        last_external_transaction_id="tx-3",
        active_transaction_id="tx-4",
        debounce_pending=True,
        workspace_dirty=False,
    )
    settings["nested"]["rows"][0] = 999
    corners["head"]["top_left"]["type"] = "B"

    assert state.settings_values["nested"]["rows"][0] == 1.0
    assert state.corner_state["head"]["top_left"]["type"] == "A"
    assert not _contains_mutable(state)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.assembly_type = "OVERLAY"


def test_issue390_requests_results_and_effects_are_typed_and_frozen():
    from phase6_settings_contracts import (
        ExternalModelTransitionRequest,
        ExternalSettingsSyncRequest,
        SettingsCommitRequest,
        SettingsEffect,
        SettingsMutationResult,
        SettingsStageRequest,
        SettingsStateSnapshot,
    )

    stage = SettingsStageRequest(key="fw", value={"mm": 29}, transaction_id="tx-1")
    commit = SettingsCommitRequest(updates={"fw": 29, "t": 2}, transaction_id="tx-1", source="operator")
    sync = ExternalSettingsSyncRequest(revision=7, transaction_id="tx-ext", settings_delta={"fw": 30})
    model = ExternalModelTransitionRequest(model="受電箱", revision=8, transaction_id="tx-model", snapshot={"w": 800})
    effect = SettingsEffect(kind="mark_workspace_dirty", payload={"dirty": True})
    result = SettingsMutationResult(
        state=SettingsStateSnapshot(),
        updates={"fw": 29},
        effects=(effect,),
    )

    assert stage.value["mm"] == 29.0
    assert commit.updates["t"] == 2.0
    assert sync.revision == 7
    assert model.model == "受電箱"
    assert result.effects == (effect,)
    assert not _contains_mutable(result)


def test_issue390_canonical_serialization_and_fingerprint_are_order_stable():
    from phase6_settings_contracts import (
        SettingsCommitRequest,
        canonical_settings_json,
        settings_fingerprint,
    )

    a = SettingsCommitRequest(updates={"b": [2, 1], "a": {"y": 2, "x": 1}}, transaction_id="tx", source="operator")
    b = SettingsCommitRequest(updates={"a": {"x": 1, "y": 2}, "b": [2, 1]}, transaction_id="tx", source="operator")
    assert canonical_settings_json(a) == canonical_settings_json(b)
    assert settings_fingerprint(a) == settings_fingerprint(b)
    assert json.loads(canonical_settings_json(a))["updates"]["a"] == {"x": 1.0, "y": 2.0}


def test_issue390_contracts_reject_callbacks_tk_and_app_objects():
    from phase6_settings_contracts import freeze_settings_value

    with pytest.raises(TypeError):
        freeze_settings_value(lambda: None)

    class FakeTk:
        __module__ = "tkinter"
    with pytest.raises(TypeError):
        freeze_settings_value(FakeTk())

    class FakeApp:
        __module__ = "fold_designer_bridge"
    with pytest.raises(TypeError):
        freeze_settings_value(FakeApp())


def test_issue390_contract_module_has_no_tk_gui_or_bridge_imports():
    path = Path("phase6_settings_contracts.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(name == "tkinter" or name.startswith("tkinter.") for name in imports)
    assert not any(name == "fold_designer_bridge" or name.startswith("gui") for name in imports)
