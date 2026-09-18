import ast
from pathlib import Path

EXPECTED_ROOT_GRID_CALLERS = ('draw_base_plate', 'draw_box_body', 'draw_door', 'draw_end_cap', 'draw_indicator_box', 'draw_indicator_door')
TARGET = "_render_fold_designer_corner_data_view"
GUI_PATH = Path("gui.py")
RENDER_2D_PATH = Path("gui_modules/render_2d.py")
DOOR_VIEW_PATH = Path("gui_modules/rendering/door_view.py")


def _tree():
    return ast.parse(GUI_PATH.read_text(encoding="utf-8"))


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


def test_shared_draw_grid_implementation_contract_survives_owner_move():
    from gui_modules.render_2d import draw_grid

    class RecordingCanvas:
        def __init__(self):
            self.calls = []

        def create_line(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    canvas = RecordingCanvas()
    draw_grid(object(), canvas, 100, 90, tags=("grid",))

    assert [args for args, _ in canvas.calls] == [
        (0, 0, 0, 90),
        (40, 0, 40, 90),
        (80, 0, 80, 90),
        (0, 0, 100, 0),
        (0, 40, 100, 40),
        (0, 80, 100, 80),
    ]
    assert all(kwargs == {"fill": "#1c1c22", "width": 1, "tags": ("grid",)} for _, kwargs in canvas.calls)
    assert RENDER_2D_PATH.is_file()
    assert "draw_grid as _draw_grid_impl" in GUI_PATH.read_text(encoding="utf-8")


def test_all_unrelated_prechange_grid_callers_are_preserved():
    current = tuple(sorted(n.name for n in _functions() if n.name != TARGET and _calls_self_method(n, "draw_grid")))
    assert current == EXPECTED_ROOT_GRID_CALLERS

    door_tree = ast.parse(DOOR_VIEW_PATH.read_text(encoding="utf-8"))
    overview = [
        n for n in ast.walk(door_tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "draw_door_layout_overview_preview"
    ]
    assert len(overview) == 1
    assert any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "draw_grid"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "host"
        for call in ast.walk(overview[0])
        if isinstance(call, ast.Call)
    )


def test_corner_data_renderer_still_consumes_authoritative_drawing_scene():
    node = _function(TARGET)
    names = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "render_drawing_scene" in names
