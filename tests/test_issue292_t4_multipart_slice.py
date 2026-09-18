from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MULTIPART = ROOT / "gui_modules" / "parts" / "panels" / "multipart.py"
GUI = ROOT / "gui.py"


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_multipart_panel_owns_input_collection_not_geometry_authority():
    assert "collect_multipart_input" in _functions(MULTIPART)
    text = MULTIPART.read_text(encoding="utf-8").lower()
    for forbidden in ("manufacturing_api", "dxf", "mesh", "placement", "finished_dimension"):
        assert forbidden not in text


def test_multipart_input_collection_preserves_existing_identity_and_values():
    namespace = {}
    exec(compile(MULTIPART.read_text(encoding="utf-8"), str(MULTIPART), "exec"), namespace)
    collect = namespace["collect_multipart_input"]
    payload = {
        "stable_id": "box_body:part:2",
        "multipart_parts": ({"stable_id": "box_body:part:1", "width": 800},),
        "multipart_scope": "receiving-main",
        "model": "受電箱",
    }
    assert collect(payload) == payload


def test_multipart_input_collection_does_not_invent_missing_children():
    namespace = {}
    exec(compile(MULTIPART.read_text(encoding="utf-8"), str(MULTIPART), "exec"), namespace)
    result = namespace["collect_multipart_input"]({"model": "受電箱"})
    assert result == {"model": "受電箱"}


def test_gui_routes_multipart_payload_collection_through_panel_boundary():
    import inspect
    from gui_modules.application import fold_designer_adapter as owner
    owner_path = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
    text = owner_path.read_text(encoding="utf-8")
    assert "from gui_modules.parts.panels.multipart import collect_multipart_input" in text
    assert "collect_multipart_input(" in inspect.getsource(owner._query_fold_designer_render_data)
