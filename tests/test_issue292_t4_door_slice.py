from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "gui_modules" / "parts" / "panels" / "door.py"
GUI = ROOT / "gui.py"


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_door_panel_owns_input_collection_not_geometry_authority():
    funcs = _functions(DOOR)
    assert "collect_door_input" in funcs
    text = DOOR.read_text(encoding="utf-8").lower()
    for forbidden in (
        "manufacturing_api", "dxf", "finished_dimension", "fold_geometry",
        "build_door_render_data", "derive_door", "mesh", "placement",
    ):
        assert forbidden not in text


def test_door_input_collection_preserves_authoritative_values():
    namespace = {}
    exec(compile(DOOR.read_text(encoding="utf-8"), str(DOOR), "exec"), namespace)
    collect = namespace["collect_door_input"]
    payload = {
        "door_layout_columns": ((800, (1100, 500)),),
        "door_layout_scope": "main",
        "door_handle_edges": {"door:c1:r1": "left"},
        "model": "受電箱",
    }
    result = collect(payload)
    assert result["door_layout_columns"] == payload["door_layout_columns"]
    assert result["door_layout_scope"] == "main"
    assert result["door_handle_edges"] == payload["door_handle_edges"]
    assert result["model"] == "受電箱"


def test_door_input_collection_does_not_invent_missing_topology():
    namespace = {}
    exec(compile(DOOR.read_text(encoding="utf-8"), str(DOOR), "exec"), namespace)
    collect = namespace["collect_door_input"]
    result = collect({"model": "受電箱"})
    assert "door_layout_columns" not in result
    assert result["model"] == "受電箱"


def test_gui_routes_door_payload_collection_through_panel_boundary():
    import inspect
    from gui_modules.application import fold_designer_adapter as owner
    owner_path = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
    text = owner_path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {(node.module, alias.name) for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert ("gui_modules.parts.panels.door", "collect_door_input") in imported
    assert "collect_door_input(" in inspect.getsource(owner._query_fold_designer_render_data)
