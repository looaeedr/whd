from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "gui_modules" / "parts" / "panels" / "indicator_box.py"
GUI = ROOT / "gui.py"


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_indicator_panel_owns_input_collection_not_drawing_or_geometry():
    assert "collect_indicator_box_input" in _functions(PANEL)
    text = PANEL.read_text(encoding="utf-8").lower()
    for forbidden in ("manufacturing_api", "dxf", "mesh", "placement", "render_data", "draw_"):
        assert forbidden not in text


def test_indicator_input_collection_preserves_authoritative_values():
    namespace = {}
    exec(compile(PANEL.read_text(encoding="utf-8"), str(PANEL), "exec"), namespace)
    payload = {"stable_id": "indicator_box:1", "width": 300, "height": 180, "model": "受電箱"}
    assert namespace["collect_indicator_box_input"](payload) == payload


def test_indicator_input_collection_does_not_invent_values():
    namespace = {}
    exec(compile(PANEL.read_text(encoding="utf-8"), str(PANEL), "exec"), namespace)
    assert namespace["collect_indicator_box_input"]({"model": "受電箱"}) == {"model": "受電箱"}


def test_gui_routes_indicator_payload_through_panel_boundary():
    import inspect
    from gui_modules.application import fold_designer_adapter as owner
    owner_path = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
    text = owner_path.read_text(encoding="utf-8")
    assert "from gui_modules.parts.panels.indicator_box import collect_indicator_box_input" in text
    assert "collect_indicator_box_input(" in inspect.getsource(owner._query_fold_designer_render_data)
