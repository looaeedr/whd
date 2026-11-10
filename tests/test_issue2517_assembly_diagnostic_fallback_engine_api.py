"""#2517 Assembly Relief diagnostic uses the same public Engine fallback source as save."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import (
    fold_designer_composition_assembly_corner as gui,
    fold_designer_composition_state as save_owner,
)
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController


class _Variable:
    def __init__(self, value):
        self.value = value
        self.writes = []
    def get(self):
        return self.value
    def set(self, text):
        self.writes.append(text)
        self.value = text


def _host(source, *, absent=False):
    calls = []
    status = _Variable("unchanged status")
    size = _Variable("unchanged size")

    class _Diagnostics:
        def diagnostic_status(self, **kwargs):
            calls.append(kwargs)
            return Phase6RegistryDiagnosticsController.diagnostic_status(**kwargs)

    app = SimpleNamespace(
        assembly_collision_status_var=status,
        assembly_relief_size_var=size,
        _phase6_last_relief_solutions={},
        _phase6_last_relief_errors={},
    )
    if not absent:
        app.assembly_ignore_fixed_corner_var = _Variable(source)
    host = SimpleNamespace(
        app=app,
        capabilities=SimpleNamespace(
            registry=SimpleNamespace(diagnostics=lambda: _Diagnostics()),
        ),
        _required=lambda _namespace, name:
            (lambda measurement: str(measurement))
            if name == "_phase6_relief_measurement_text" else None,
    )
    return host, calls, status, size


@pytest.mark.parametrize(("raw","expected"), [
    (False, False), ("false", False), ("FALSE", False),
    ("0", False), ("off", False), ("no", False), (0, False),
    (True, True), ("true", True), ("on", True), (1, True),
])
def test_real_gui_diagnostic_uses_canonical_engine_fallback_source(raw, expected):
    host, calls, status, size = _host(raw)
    result = gui.update_assembly_diagnostic_status(host, {})
    assert len(calls) == 1
    assert calls[0]["fallback_enabled"] is expected
    assert result == status.value
    assert len(status.writes) == len(size.writes) == 1
    if not expected:
        assert "立體備援已停用" in status.value
    # The original value is not rewritten by a read-only status request.
    assert host.app.assembly_ignore_fixed_corner_var.get() == raw


@pytest.mark.parametrize("invalid", [
    None, "maybe", "2", 2, -1, 1.5, [], {},
])
def test_invalid_fallback_source_cannot_publish_false_diagnostic(invalid):
    host, calls, status, size = _host(invalid)
    with pytest.raises(ValueError, match="布林值"):
        gui.update_assembly_diagnostic_status(host, {})
    assert calls == []
    assert status.value == "unchanged status"
    assert size.value == "unchanged size"
    assert status.writes == size.writes == []


def test_absent_legacy_control_preserves_original_default_without_creating_state():
    host, calls, status, size = _host(None, absent=True)
    gui.update_assembly_diagnostic_status(host, {})
    assert len(calls) == 1
    assert calls[0]["fallback_enabled"] is True
    assert not hasattr(host.app, "assembly_ignore_fixed_corner_var")


def test_same_public_engine_contract_used_in_diagnostic_and_save():
    diagnostic = inspect.getsource(gui.update_assembly_diagnostic_status)
    save = inspect.getsource(save_owner.serialize_assembly_relief_state)
    assert "manufacturing_api.normalize_operator_settings_boolean(enabled_var.get())" in diagnostic
    assert "manufacturing_api.normalize_operator_settings_boolean(enabled_var.get())" in save
    assert "bool(enabled_var.get())" not in diagnostic
    for raw in (False, "false", "0", "off", True, "true", "1"):
        assert manufacturing_api.normalize_operator_settings_boolean(raw) == (
            manufacturing_api.normalize_operator_settings_boolean(
                json.loads(json.dumps(raw))
            )
        )
