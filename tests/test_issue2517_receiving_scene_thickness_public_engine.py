"""#2517: Receiving Bay/Common FinalScene view T equals original Engine source."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api


_FILE = (
    Path(__file__).resolve().parents[1]
    / "gui_modules/application/fold_designer_composition_receiving.py"
)


def _thickness_call(owner):
    """Read the exact expression from the original GUI FinalScene Request."""
    tree = ast.parse(_FILE.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == owner]
    assert len(functions) == 1
    calls = [
        node for node in ast.walk(functions[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "FinalSceneViewRequest"
    ]
    assert len(calls) == 1
    args = [key.value for key in calls[0].keywords if key.arg == "thickness"]
    assert len(args) == 1
    # This is the actual GUI request argument, not a second parser/fixture.
    source = ast.unparse(args[0])
    assert "manufacturing_api.normalize_operator_source_dimension" in source
    assert "float(" not in source
    return compile(ast.Expression(body=args[0]), str(_FILE), "eval")


def _thickness(owner, snapshot):
    source = deepcopy(snapshot)
    host = SimpleNamespace(app=SimpleNamespace(_phase6_input_snapshot=source))
    expression = _thickness_call(owner)
    return eval(expression, {
        "manufacturing_api": api,
        "snapshot": source,
        "self": host,
    })


@pytest.mark.parametrize("owner", (
    "receiving_bay_preview_request", "_common_preview_request",
))
@pytest.mark.parametrize("raw", (2, "2", 2.125, "2.125", 0.875))
def test_gui_receiving_scene_request_uses_identical_public_engine_t(owner, raw):
    source = {"model": "受電箱", "t": raw}
    before = deepcopy(source)
    assert _thickness(owner, source) == api.normalize_operator_source_dimension(
        raw, field="t",
    )
    reloaded = json.loads(json.dumps(source, ensure_ascii=False))
    assert _thickness(owner, reloaded) == _thickness(owner, source)
    assert source == before


@pytest.mark.parametrize("owner", (
    "receiving_bay_preview_request", "_common_preview_request",
))
@pytest.mark.parametrize("bad", (
    True, False, 0, -1, None, "nan", "inf", "-inf", "not a number",
    [], {},
))
def test_invalid_saved_receiving_physical_thickness_never_enters_view_request(
    owner, bad,
):
    source = {"model": "受電箱", "t": bad}
    before = deepcopy(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        _thickness(owner, source)
    assert source == before


@pytest.mark.parametrize("owner", (
    "receiving_bay_preview_request", "_common_preview_request",
))
def test_legacy_absent_t_preserves_original_two_mm_view_fallback(owner):
    source = {"model": "受電箱"}
    assert _thickness(owner, source) == 2.0
    assert source == {"model": "受電箱"}


def test_only_engine_owns_receiving_scene_physical_thickness():
    source = _FILE.read_text(encoding="utf-8")
    for old in (
        'thickness=float(snapshot.get("t", 2))',
        'thickness=float(self.app._phase6_input_snapshot.get("t", 2))',
    ):
        assert old not in source
    for function in ("receiving_bay_preview_request", "_common_preview_request"):
        _thickness_call(function)
