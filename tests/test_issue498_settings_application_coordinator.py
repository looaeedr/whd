from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest


COORDINATOR = Path("gui_modules/application/fold_designer_settings_coordinator.py")
CONTRACTS = Path("phase6_settings_contracts.py")
COMPOSITION = Path("gui_modules/application/fold_designer_adapter.py")

EXPECTED_PORT_FIELDS = (
    "read_settings_snapshot",
    "read_profile_snapshot",
    "save_current_part",
    "apply_profile_plan",
    "sync_derived_parts",
    "project_ui_values",
    "render_bending",
    "refresh_settings_panel",
    "refresh_topology",
    "refresh_persistent_controls",
    "submit_update_intent",
    "publish_live_state",
    "project_status",
)


def _ports():
    from gui_modules.application.fold_designer_settings_coordinator import (
        Phase6SettingsApplicationPorts,
    )
    from phase6_settings_contracts import SettingsStateSnapshot

    def noop(*args, **kwargs):
        return None

    return Phase6SettingsApplicationPorts(
        read_settings_snapshot=lambda: SettingsStateSnapshot(),
        read_profile_snapshot=lambda: {},
        save_current_part=noop,
        apply_profile_plan=noop,
        sync_derived_parts=noop,
        project_ui_values=noop,
        render_bending=noop,
        refresh_settings_panel=noop,
        refresh_topology=noop,
        refresh_persistent_controls=noop,
        submit_update_intent=noop,
        publish_live_state=noop,
        project_status=noop,
    )


def test_issue498_requires_explicit_typed_settings_application_boundary():
    assert COORDINATOR.is_file(), (
        "RED: missing Phase 5 Settings application coordinator"
    )

    from gui_modules.application.fold_designer_settings_coordinator import (
        Phase6FoldDesignerSettingsCoordinator,
        Phase6SettingsApplicationPorts,
    )

    ports = _ports()
    assert dataclasses.is_dataclass(ports)
    assert tuple(field.name for field in dataclasses.fields(ports)) == EXPECTED_PORT_FIELDS

    with pytest.raises(dataclasses.FrozenInstanceError):
        ports.project_status = lambda value: None

    tx = object()
    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=tx,
        ports=ports,
    )
    assert coordinator.transactions is tx
    assert coordinator.ports is ports


def test_issue498_ports_fail_closed_on_non_callable_runtime_surface():
    assert COORDINATOR.is_file(), (
        "RED: missing Phase 5 Settings application coordinator"
    )

    from gui_modules.application.fold_designer_settings_coordinator import (
        Phase6SettingsApplicationPorts,
    )

    values = {name: (lambda *args, **kwargs: None) for name in EXPECTED_PORT_FIELDS}
    values["read_settings_snapshot"] = object()
    with pytest.raises(TypeError):
        Phase6SettingsApplicationPorts(**values)


def test_issue498_application_effect_contract_is_bounded_and_frozen():
    source = CONTRACTS.read_text(encoding="utf-8")
    assert "class SettingsApplicationEffectKind" in source, (
        "RED: missing bounded Settings application effect kind"
    )
    assert "class SettingsApplicationEffect" in source, (
        "RED: missing typed Settings application effect contract"
    )

    from phase6_settings_contracts import (
        SettingsApplicationEffect,
        SettingsApplicationEffectKind,
    )

    effect = SettingsApplicationEffect(
        kind=SettingsApplicationEffectKind.SUBMIT_UPDATE_INTENT,
        payload={"reason": "settings_changed"},
    )
    assert effect.kind is SettingsApplicationEffectKind.SUBMIT_UPDATE_INTENT
    assert effect.payload["reason"] == "settings_changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        effect.kind = SettingsApplicationEffectKind.PROJECT_STATUS
    with pytest.raises(ValueError):
        SettingsApplicationEffect(kind="arbitrary_runtime_command")


def test_issue498_coordinator_has_no_reverse_bridge_tk_or_manufacturing_ownership():
    assert COORDINATOR.is_file(), (
        "RED: missing Phase 5 Settings application coordinator"
    )
    tree = ast.parse(COORDINATOR.read_text(encoding="utf-8"), filename=str(COORDINATOR))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {
        name
        for name in imports
        if name == "fold_designer_bridge"
        or name == "tkinter"
        or name.startswith("tkinter.")
        or "manufacturing" in name
    }
    assert forbidden == set()


def test_issue498_existing_composition_owns_single_settings_coordinator_factory():
    source = COMPOSITION.read_text(encoding="utf-8")
    assert "Phase6FoldDesignerSettingsCoordinator" in source, (
        "RED: existing composition does not own Phase 5 Settings coordinator"
    )
    assert "def settings_coordinator(" in source, (
        "RED: existing composition lacks Settings coordinator factory"
    )

    from gui_modules.application.fold_designer_adapter import Phase6FoldDesignerComposition

    composition = Phase6FoldDesignerComposition(SimpleNamespace())
    tx = object()
    composition._settings_transactions = tx
    ports = _ports()

    first = composition.settings_coordinator(ports)
    second = composition.settings_coordinator(_ports())

    assert first is second
    assert first.transactions is tx
    assert first.ports is ports


def test_issue498_port_specs_classify_role_owner_direction_and_bootstrap():
    from gui_modules.application.fold_designer_settings_coordinator import (
        SETTINGS_APPLICATION_PORT_SPECS,
        Phase6SettingsApplicationPortRole,
    )

    assert tuple(SETTINGS_APPLICATION_PORT_SPECS) == EXPECTED_PORT_FIELDS
    assert {
        name: spec.role for name, spec in SETTINGS_APPLICATION_PORT_SPECS.items()
    } == {
        "read_settings_snapshot": Phase6SettingsApplicationPortRole.READ,
        "read_profile_snapshot": Phase6SettingsApplicationPortRole.READ,
        "save_current_part": Phase6SettingsApplicationPortRole.EFFECT,
        "apply_profile_plan": Phase6SettingsApplicationPortRole.MUTATION,
        "sync_derived_parts": Phase6SettingsApplicationPortRole.MUTATION,
        "project_ui_values": Phase6SettingsApplicationPortRole.EFFECT,
        "render_bending": Phase6SettingsApplicationPortRole.EFFECT,
        "refresh_settings_panel": Phase6SettingsApplicationPortRole.EFFECT,
        "refresh_topology": Phase6SettingsApplicationPortRole.EFFECT,
        "refresh_persistent_controls": Phase6SettingsApplicationPortRole.EFFECT,
        "submit_update_intent": Phase6SettingsApplicationPortRole.EFFECT,
        "publish_live_state": Phase6SettingsApplicationPortRole.EFFECT,
        "project_status": Phase6SettingsApplicationPortRole.EFFECT,
    }

    for name, spec in SETTINGS_APPLICATION_PORT_SPECS.items():
        assert spec.canonical_owner.strip(), name
        assert spec.callback_direction in {
            "owner_to_coordinator",
            "coordinator_to_owner",
        }
        assert isinstance(spec.bootstrap_required, bool)
        assert isinstance(spec.compatibility_only, bool)

    assert SETTINGS_APPLICATION_PORT_SPECS["save_current_part"].compatibility_only
    assert not any(
        spec.compatibility_only
        for name, spec in SETTINGS_APPLICATION_PORT_SPECS.items()
        if name != "save_current_part"
    )
