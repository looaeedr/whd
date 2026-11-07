"""#2517: main GUI model and CornerType readbacks must use public Engine."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import gui
from ae_engine import manufacturing_api
from ae_engine.corner_type_ui import (
    is_unknown_model as internal_is_unknown_model,
    assembly_type_from_corner_state as internal_assembly_from_corner_state,
)
from ae_engine.sheetmetal_corner_policy import normalize_corner_selection
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


@pytest.mark.parametrize("model", ["自訂", "未知類型", "受電箱", "金庫型", "", None, "nonstandard"])
def test_gui_model_mode_equals_original_engine_and_public_api(model):
    assert gui.is_unknown_model is manufacturing_api.is_unknown_operator_model
    assert manufacturing_api.is_unknown_operator_model(model) == internal_is_unknown_model(model)
    fake = SimpleNamespace(baseline_var=_Var(model), manual_corner_state={"head": {}})
    assert gui.Phase6ApplicationHost._corner_part_type_editable(fake, "head") == internal_is_unknown_model(model)
    expected = None if not model or internal_is_unknown_model(model) else str(model).strip()
    assert gui.Phase6ApplicationHost._baseline_source_model(fake) == expected


def test_main_gui_legacy_assembly_fallback_calls_exact_public_engine(monkeypatch):
    calls = []
    marker = CornerTypeId.OVERLAY
    def public(source):
        calls.append(source)
        return marker
    monkeypatch.setattr(manufacturing_api, "operator_assembly_type_from_corner_state", public)
    source = {"head": {"top_left": CornerTypeSelection(CornerTypeId.OVERLAY)}}
    saved = deepcopy(source)
    fake = SimpleNamespace(
        box_assembly_type_var=None,
        assembly_joint_state=None,
        manual_corner_state=source,
    )
    assert gui.Phase6ApplicationHost._current_box_assembly_type(fake) is marker
    assert calls == [source]
    assert source == saved


def test_main_gui_legacy_assembly_has_original_engine_parity():
    assert gui.assembly_type_from_corner_state is manufacturing_api.operator_assembly_type_from_corner_state
    assert manufacturing_api.operator_assembly_type_from_corner_state is internal_assembly_from_corner_state
    for part in ("head", "tail"):
        payload = {part: {"top_left": CornerTypeSelection(CornerTypeId.C04)}}
        before = deepcopy(payload)
        assert manufacturing_api.operator_assembly_type_from_corner_state(payload) == internal_assembly_from_corner_state(payload)
        assert payload == before


def test_manual_corner_readback_is_engine_owned_and_does_not_mutate(monkeypatch):
    actual = CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=1)
    source = {"head": {"top_left": actual}}
    before = deepcopy(source)
    fake = SimpleNamespace(manual_corner_state=source)
    canonical = normalize_corner_selection(actual)
    assert gui.normalize_corner_selection is manufacturing_api.operator_normalize_corner_selection
    assert gui.Phase6ApplicationHost._manual_selection_for_target(fake, "head", "top") == canonical
    assert source == before
    calls = []
    def public(item):
        calls.append(item)
        return canonical
    monkeypatch.setattr(manufacturing_api, "operator_normalize_corner_selection", public)
    assert gui.Phase6ApplicationHost._manual_selection_for_target(fake, "head", "top") == canonical
    assert calls == [actual]
    assert source == before


def test_no_internal_corner_or_model_semantics_called_by_main_gui():
    text = Path("gui.py").read_text(encoding="utf-8")
    assert "return manufacturing_api.operator_assembly_type_from_corner_state(corner_state)" in text
    assert "physical_key = manufacturing_api.project_operator_corner_selection_target(" in text
    assert "self.manual_corner_state[part_key][physical_key]" in text
    assert "return manufacturing_api.operator_normalize_corner_selection(" in text
    assert "manufacturing_api.is_unknown_operator_model(self.baseline_var.get())" in text
    assert "from ae_engine.corner_type_ui import (" in text  # typed display metadata may remain
    for code in (
        "if not is_unknown_model(self.baseline_var.get()):",
        "or is_unknown_model(value):",
        "return assembly_type_from_corner_state(corner_state)",
        "return normalize_corner_selection(self.manual_corner_state[part_key][target_key])",
    ):
        assert code not in text
