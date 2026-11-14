"""#2517: Fold Designer Settings BooleanVar projection respects Engine saved-source truth."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_composition_shell_settings as gui


class BoolControl:
    def __init__(self):
        self.writes = []
    def set(self, value):
        self.writes.append(value)


class TextControl:
    def __init__(self):
        self.writes = []
    def set(self, value):
        self.writes.append(value)


def _projection_host():
    left = BoolControl()
    right = BoolControl()
    info = TextControl()
    app = SimpleNamespace(
        left_global_vars={"draw_stock": left},
        setting_vars={"use_box_distance": right, "yl1": info},
        _phase6_settings_guard=False,
        _phase6_input_snapshot={"model": "金庫型"},
    )
    names = {
        "original": SimpleNamespace(tk=SimpleNamespace(BooleanVar=BoolControl)),
        "_setting_number_text": lambda value: str(value),
    }
    owner = SimpleNamespace(app=app, _required=lambda _ns, key: names[key])
    return owner, app, left, right, info


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("left_raw,right_raw", (
    ("false", "true"), ("FALSE", "off"), ("0", "1"),
    ("no", "yes"), (False, True), (0, 1), ("on", "false"),
))
def test_saved_boolean_projection_equals_public_engine_and_json_reload(
    family, left_raw, right_raw,
):
    owner, app, left, right, info = _projection_host()
    app._phase6_input_snapshot["model"] = family
    source = {"draw_stock": left_raw, "use_box_distance": right_raw, "yl1": "15.625"}
    before = deepcopy(source)
    saved = json.loads(json.dumps(source, ensure_ascii=False))
    gui.settings_application_project_ui_values(owner, "ui", saved)
    assert left.writes == [api.normalize_operator_settings_boolean(left_raw)]
    assert right.writes == [api.normalize_operator_settings_boolean(right_raw)]
    assert info.writes == ["15.625"]
    assert app._phase6_settings_guard is False
    assert saved == before
    assert app._phase6_input_snapshot == {"model": family}


@pytest.mark.parametrize("field", ("draw_stock", "use_box_distance"))
@pytest.mark.parametrize("bad", (
    None, "invalid", "2", 2, -1, 1.5, [], {}, float("inf"),
))
def test_invalid_saved_bool_rejects_before_any_snapshot_or_gui_mutation(field, bad):
    owner, app, left, right, info = _projection_host()
    source = {"draw_stock": "false", "use_box_distance": "true", "yl1": "16"}
    source[field] = bad
    before = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        gui.settings_application_project_ui_values(
            owner, "ui", source, editor_commit=True,
            editor_snapshot={"model": "受電箱"},
        )
    assert source == before
    assert app._phase6_input_snapshot == {"model": "金庫型"}
    assert not left.writes and not right.writes and not info.writes
    assert app._phase6_settings_guard is False


def test_legacy_non_boolean_settings_and_missing_switch_are_unchanged():
    owner, app, left, right, info = _projection_host()
    gui.settings_application_project_ui_values(owner, "ui", {"yl1": "-2.25"})
    assert info.writes == ["-2.25"]
    assert left.writes == [] and right.writes == []
    assert app._phase6_settings_guard is False


def test_rollback_does_not_require_projection_of_unused_corrupt_switch():
    owner, app, left, right, _ = _projection_host()
    model = TextControl()
    model.get = lambda: "金庫型"
    app.baseline_model_var = model
    gui.settings_application_project_ui_values(
        owner, "ui", {"draw_stock": "invalid"},
        baseline_stage="rollback", new_model="金庫型",
    )
    assert model.writes == [] and left.writes == [] and right.writes == []


def test_gui_settings_boolean_does_not_use_python_truthiness():
    source = inspect.getsource(gui.settings_application_project_ui_values)
    assert "manufacturing_api.normalize_operator_settings_boolean(" in source
    assert source.index("normalize_operator_settings_boolean(") < source.index(
        "if bool(editor_commit)"
    )
    assert "var.set(bool(values[key]))" not in source
