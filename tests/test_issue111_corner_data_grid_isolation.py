import ast
import hashlib
from pathlib import Path

EXPECTED_DRAW_GRID_AST_SHA256 = '0e39d39d64190ff450bfd60659b7aff28cabdcdef0ac216f4865157adbc1cece'
EXPECTED_OTHER_GRID_CALLERS = ('draw_base_plate', 'draw_box_body', 'draw_door', 'draw_door_layout_overview', 'draw_end_cap', 'draw_indicator_box', 'draw_indicator_door')
TARGET = "_render_fold_designer_corner_data_view"

def _tree():
    return ast.parse(Path("gui.py").read_text(encoding="utf-8"))

def _functions():
    return [n for n in ast.walk(_tree()) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

def _function(name):
    matches = [n for n in _functions() if n.name == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]

def _calls_self_method(node, method):
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr == method and isinstance(f.value, ast.Name) and f.value.id == "self":
            return True
    return False

def test_corner_data_renderer_does_not_draw_background_grid():
    assert not _calls_self_method(_function(TARGET), "draw_grid")

def test_shared_draw_grid_implementation_ast_is_unchanged():
    node = _function("draw_grid")
    digest = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    assert digest == EXPECTED_DRAW_GRID_AST_SHA256

def test_all_unrelated_prechange_grid_callers_are_preserved():
    current = tuple(sorted(n.name for n in _functions() if n.name != TARGET and _calls_self_method(n, "draw_grid")))
    assert current == EXPECTED_OTHER_GRID_CALLERS

def test_corner_data_renderer_still_consumes_authoritative_drawing_scene():
    node = _function(TARGET)
    names = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "render_drawing_scene" in names
