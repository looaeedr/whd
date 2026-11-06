"""#2517: physical Door/BasePlate Hole Editor family gate uses public Engine."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.corner_type_ui import is_unknown_model as engine_owner
from gui_modules.editors import hole_editor


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _host(model):
    policies = []
    token = object()

    def policy(part, fw):
        policies.append((part, fw))
        return token

    host = SimpleNamespace(
        baseline_var=_Var(model),
        _manual_corner_policy=policy,
        _door_material_frame_width=lambda fw, thickness: fw - thickness,
        _baseline_source_model=lambda: None if engine_owner(model) else model,
        _single_door_indicator_state_snapshot=lambda: {"source": "saved"},
        _apply_single_door_indicator_state=lambda state: None,
        _indicator_component_editor_contexts=lambda *a, **k: {},
        surface_features={"indicator_box": [], "indicator_door": []},
    )
    return host, policies, token


def _values():
    return {"fw": 30.0, "t": 2.0, "door_gap_w": 2.0, "door_gap_h": 3.0}


@pytest.mark.parametrize("model", ["自訂", "未知類型", "金庫型", "受電箱"])
def test_door_hole_editor_uses_public_family_for_real_projection(monkeypatch, model):
    host, policies, token = _host(model)
    values = _values()
    before = deepcopy(values)
    calls = []
    classification = []
    original_gate = manufacturing_api.is_unknown_operator_model

    def gate(name):
        classification.append(name)
        return original_gate(name)

    def project(source, **kwargs):
        calls.append((source, kwargs))
        return SimpleNamespace(
            surface="door_surface", width=100, height=200,
            reference_guide=None, door_indicator_context=None,
            door_frame_edges=None, baseline_scene=None,
            baseline_status="canonical",
        )

    monkeypatch.setattr(manufacturing_api, "is_unknown_operator_model", gate)
    monkeypatch.setattr(manufacturing_api, "project_operator_hole_editor_door", project)
    response = hole_editor._door_context(host, values)
    custom = engine_owner(model)
    assert classification == [model]
    assert calls == [(values, {
        "material_frame_width": 28.0, "is_custom": custom,
        "corner_policy": token if custom else None,
        "baseline_model": None if custom else model,
    })]
    assert policies == ([("door", 28.0)] if custom else [])
    assert response["surface"] == "door_surface"
    assert response["door_indicator_state"] == {"source": "saved"}
    assert values == before


@pytest.mark.parametrize("model", ["自訂", "未知類型", "金庫型", "受電箱"])
def test_base_plate_hole_editor_uses_public_family_for_real_projection(monkeypatch, model):
    host, policies, token = _host(model)
    values = _values()
    before = deepcopy(values)
    calls = []
    classification = []
    original_gate = manufacturing_api.is_unknown_operator_model

    def gate(name):
        classification.append(name)
        return original_gate(name)

    def project(source, **kwargs):
        calls.append((source, kwargs))
        return SimpleNamespace(surface="base_surface", width=180,
                               height=270, reference_guide=None,
                               baseline_status="canonical")

    monkeypatch.setattr(manufacturing_api, "is_unknown_operator_model", gate)
    monkeypatch.setattr(manufacturing_api, "project_operator_hole_editor_base_plate", project)
    response = hole_editor._base_plate_context(host, values)
    custom = engine_owner(model)
    assert classification == [model]
    assert calls == [(values, {
        "is_custom": custom, "corner_policy": token if custom else None,
    })]
    assert policies == ([("base_plate", 30.0)] if custom else [])
    assert response["surface"] == "base_surface"
    assert values == before


def test_bad_family_source_fails_before_door_or_base_projection(monkeypatch):
    host, _, _ = _host("corrupt-source")
    values = _values()
    before = deepcopy(values)
    projected = []
    def fail(_value):
        raise ValueError("MODEL_SOURCE_INVALID")
    monkeypatch.setattr(manufacturing_api, "is_unknown_operator_model", fail)
    monkeypatch.setattr(manufacturing_api, "project_operator_hole_editor_door",
                        lambda *a, **k: projected.append("door"))
    monkeypatch.setattr(manufacturing_api, "project_operator_hole_editor_base_plate",
                        lambda *a, **k: projected.append("base"))
    for caller in (hole_editor._door_context, hole_editor._base_plate_context):
        with pytest.raises(ValueError, match="MODEL_SOURCE_INVALID"):
            caller(host, values)
    assert projected == []
    assert values == before


def test_hole_editor_physical_family_gate_no_private_engine_import():
    text = Path("gui_modules/editors/hole_editor.py").read_text(encoding="utf-8")
    assert "from ae_engine.corner_type_ui import is_unknown_model" not in text
    assert text.count("custom = manufacturing_api.is_unknown_operator_model(host.baseline_var.get())") == 2
