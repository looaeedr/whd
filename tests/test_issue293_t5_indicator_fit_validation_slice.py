from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACK = "validate_current_indicator_fit"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _validator_class():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorFitValidation"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorFitValidation is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, object] = {}
    exec(compile(module, str(EDITOR), "exec"), ns)
    return ns["HoleEditorIndicatorFitValidation"]


class _Button:
    def __init__(self): self.configure_calls = []
    def configure(self, **kwargs): self.configure_calls.append(kwargs)


class _Context:
    finished_width = 810.0
    finished_height = 510.0


def _build(*, state_marker=object(), context_marker=_Context(), collected=None):
    cls = _validator_class()
    fit_error = ["stale"]
    button = _Button()
    validate_calls = []
    error_calls = []

    def validate_fit(**kwargs):
        validate_calls.append(kwargs)

    validator = cls(
        door_indicator_state_provider=lambda: state_marker,
        door_indicator_context_provider=lambda: context_marker,
        door_thickness_provider=lambda: 2.0,
        fit_error=fit_error,
        confirm_button=button,
        collect_state=lambda: collected,
        validate_fit=validate_fit,
        show_error=lambda title, text: error_calls.append((title, text)),
        normal_state="normal",
        disabled_state="disabled",
    )
    return validator, fit_error, button, validate_calls, error_calls


def test_indicator_fit_callback_moves_out_of_unified_root():
    assert TARGET_CALLBACK not in _unified_nested_names(), "T5 RED: validate_current_indicator_fit remains rooted"
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorFitValidation"), None)
    assert cls is not None, "T5 RED: HoleEditorIndicatorFitValidation is missing"
    assert _span(cls) <= 85
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "validate" in methods
    assert _span(methods["validate"]) <= 45


def test_gui_wiring_keeps_collect_state_late_bound():
    composition = (ROOT / "gui_modules" / "editors" / "hole_editor_composition.py").read_text(encoding="utf-8")
    assert "collect_state=lambda: s.collect_indicator_state()" in composition, "T5 RED: indicator-state collection must stay late-bound"
    assert "collect_state=s.collect_indicator_state," not in composition

def test_validation_without_indicator_context_clears_error_and_enables_confirm():
    validator, fit_error, button, validate_calls, error_calls = _build(state_marker=None)
    assert validator.validate() is True
    assert fit_error == [None]
    assert button.configure_calls == [{"state": "normal"}]
    assert validate_calls == []
    assert error_calls == []


def test_validation_none_mode_short_circuits_without_manufacturing_call():
    validator, fit_error, button, validate_calls, error_calls = _build(collected={"mode": "none"})
    assert validator.validate() is True
    assert fit_error == [None]
    assert button.configure_calls == [{"state": "normal"}]
    assert validate_calls == []
    assert error_calls == []


def test_validation_delegates_exact_fit_inputs_and_reenables_confirm():
    collected = {
        "mode": "indicator_box",
        "layers": 2,
        "groups": [3, 4, 9],
        "offset_x": 12.5,
        "offset_y": -7.25,
    }
    validator, fit_error, button, validate_calls, error_calls = _build(collected=collected)
    assert validator.validate() is True
    assert validate_calls == [{
        "mode": "indicator_box",
        "groups": (3, 4),
        "finished_width": 810.0,
        "finished_height": 510.0,
        "thickness": 2.0,
        "offset": (12.5, -7.25),
    }]
    assert fit_error == [None]
    assert button.configure_calls == [{"state": "normal"}]
    assert error_calls == []


def test_validation_failure_disables_confirm_and_optional_message():
    cls = _validator_class()
    fit_error = [None]
    button = _Button()
    error_calls = []

    def validate_fit(**_kwargs):
        raise ValueError("outside finished door")

    validator = cls(
        door_indicator_state_provider=lambda: object(),
        door_indicator_context_provider=lambda: _Context(),
        door_thickness_provider=lambda: 2.0,
        fit_error=fit_error,
        confirm_button=button,
        collect_state=lambda: {
            "mode": "indicator", "layers": 1, "groups": [2],
            "offset_x": 0, "offset_y": 0,
        },
        validate_fit=validate_fit,
        show_error=lambda title, text: error_calls.append((title, text)),
        normal_state="normal",
        disabled_state="disabled",
    )
    assert validator.validate(show_error=True) is False
    assert fit_error == ["outside finished door"]
    assert button.configure_calls == [{"state": "disabled"}]
    assert error_calls == [("指示燈配置無法套用", "outside finished door")]
