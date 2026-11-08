"""#2517 Receiving NFB Y editor has a single public Engine source contract."""
from copy import deepcopy
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_shared_settings import (
    normalize_receiving_operator_nfb_layer_heights as canonical,
    validate_setting,
)


_GUI = (
    Path(__file__).resolve().parents[1]
    / "gui_modules/application/fold_designer_composition_receiving.py"
)


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _gui_read_heights(first, second, *, count=2, area=1100.0):
    """Execute the actual GUI nested callback without running a Tk window."""
    tree = ast.parse(_GUI.read_text(encoding="utf-8"))
    funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "read_layer_heights"
    ]
    assert len(funcs) == 1
    scope = {
        "manufacturing_api": api,
        "layer_height_vars": (_Var(first), _Var(second)),
        "layers": _Var(count),
        "namespace": None,
        "self": SimpleNamespace(),
        "_current_mode_snapshot": lambda _self, _namespace: {"h": area},
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(_GUI), "exec"), scope)
    return scope["read_layer_heights"]()


@pytest.mark.parametrize("raw,expected", (
    (["550", "830"], [550.0, 830.0]),
    (("330.125", "830.375"), [330.125, 830.375]),
    ([550, 830], [550.0, 830.0]),
    ([550.0, 830.0], [550.0, 830.0]),
    (["3.30125e2", "8.30375e2"], [330.125, 830.375]),
))
def test_real_public_api_is_original_engine_shared_setting_owner(raw, expected):
    before = deepcopy(raw)
    assert api.normalize_receiving_operator_nfb_layer_heights is canonical
    assert ae_engine.normalize_receiving_operator_nfb_layer_heights is canonical
    assert "normalize_receiving_operator_nfb_layer_heights" in ae_engine.__all__
    assert canonical(raw) == validate_setting("inner_door_layer_heights_mm", expected)
    assert canonical(raw) == expected
    assert raw == before
    assert canonical(json.loads(json.dumps(expected))) == expected


@pytest.mark.parametrize("raw", (
    [True, 830], [False, 830], ["true", "830"],
    [None, 830], [[], 830], [{}, 830],
    ["nan", "830"], ["inf", "830"], ["330", "-inf"],
    ["0", "830"], ["-0.125", "830"], ["830", "550"],
    ["330", "330"], ["bad", "830"], [330], [],
    "330,830", {"first": 330, "second": 830},
))
def test_invalid_nfb_height_sources_fail_closed_without_modifying_saved_data(raw):
    before = deepcopy(raw)
    with pytest.raises(ValueError, match="第一層／第二層高度"):
        api.normalize_receiving_operator_nfb_layer_heights(raw)
    assert raw == before


@pytest.mark.parametrize("count,source", (
    (1, ("550", "830")), (2, ("330.125", "830.375")),
))
def test_real_gui_callback_is_identical_to_public_engine_and_work_area(count, source):
    result = _gui_read_heights(*source, count=count)
    assert result == api.validate_receiving_nfb_layer_heights_for_work_area(
        {"h": 1100}, api.normalize_receiving_operator_nfb_layer_heights(source),
        layer_count=count,
    )
    restored = json.loads(json.dumps({"layer_heights_mm": result, "layers": count}))
    assert _gui_read_heights(
        *restored["layer_heights_mm"], count=restored["layers"],
    ) == result


@pytest.mark.parametrize("bad_first,bad_second", (
    ("nan", "830"), ("330", "inf"),
    (True, "830"), ("830", "550"), ("0", "830"),
))
def test_invalid_gui_readback_cannot_create_an_nfb_height_source(bad_first, bad_second):
    with pytest.raises(ValueError):
        _gui_read_heights(bad_first, bad_second)


def test_work_area_remains_engine_owned_and_custom_height_is_not_replaced():
    raw = ("410.125", "830.375")
    checked = api.normalize_receiving_operator_nfb_layer_heights(raw)
    assert api.transition_receiving_nfb_layer_heights(
        checked, old_count=1, new_count=2,
    ) == checked
    assert api.transition_receiving_nfb_layer_heights(
        [550.0, 830.0], old_count=1, new_count=2,
    ) == [330.0, 830.0]
    with pytest.raises(ValueError, match="作業區"):
        _gui_read_heights("330", "830", area=700.0)


def test_gui_initial_and_both_edit_paths_never_coerce_physical_y_before_engine():
    text = _GUI.read_text(encoding="utf-8")
    assert text.count("manufacturing_api.normalize_receiving_operator_nfb_layer_heights(") == 3
    assert 'value=f"{float(v):g}"' not in text
    assert "heights = [float(field.get().strip()) for field in layer_height_vars]" not in text
    assert "heights = [float(field.get().strip())" not in text
