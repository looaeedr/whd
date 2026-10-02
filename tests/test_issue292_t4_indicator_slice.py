from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "gui_modules" / "parts" / "panels" / "indicator_box.py"
GUI = ROOT / "gui.py"


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_indicator_panel_owns_input_collection_not_render_or_geometry():
    assert "collect_indicator_box_input" in _functions(PANEL)
    text = PANEL.read_text(encoding="utf-8").lower()
    for forbidden in ("manufacturing_api", "dxf", "mesh", "render", "placement", "finished_dimension"):
        assert forbidden not in text


def test_indicator_input_collection_preserves_only_present_values():
    namespace = {}
    exec(compile(PANEL.read_text(encoding="utf-8"), str(PANEL), "exec"), namespace)
    collect = namespace["collect_indicator_box_input"]
    payload = {
        "indicator_box_enabled": True,
        "indicator_box_width": "220",
        "indicator_box_height": "120",
        "indicator_door_enabled": False,
        "model": "受電箱",
    }
    assert collect(payload) == payload
    assert collect({"model": "受電箱"}) == {"model": "受電箱"}


def test_gui_imports_current_indicator_panel_collection_boundary():
    text = GUI.read_text(encoding="utf-8")
    assert "from gui_modules.parts.panels.indicator_box import collect_indicator_box_input" in text
    assert "collect_indicator_input" not in text
