from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ADAPTER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
PROJECT_CONTROLLER = ROOT / "phase6_project_controller.py"

RETIRED_NO_CALLER_WRAPPERS = {
    "_phase6_final_scene_set_preview_enabled",
    "_phase6_commit_output_draw_stock",
    "_phase6_export_selected_dxf_from_3d",
}

# #1084 ratchets the post-#624 bridge surface downward. 6500 remains only the
# legacy absolute ceiling; it is not a target size or permission to regrow.
MAX_BRIDGE_LOC = 6455


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {child.name for child in node.body if isinstance(child, ast.FunctionDef)}
    raise AssertionError(f"class not found: {class_name}")


def test_issue1084_retired_no_caller_wrappers_do_not_regrow():
    funcs = _top_level_functions(BRIDGE)
    assert RETIRED_NO_CALLER_WRAPPERS.isdisjoint(funcs)


def test_issue1084_deep_owners_exist_without_bridge_wrappers():
    adapter_methods = _class_methods(ADAPTER, "Phase6FoldDesignerComposition")
    project_methods = _class_methods(PROJECT_CONTROLLER, "Phase6ProjectController")
    assert "final_scene_set_preview_enabled" in adapter_methods
    assert "commit_output_stock" in project_methods
    assert "route_selected_dxf_export" in project_methods


def test_issue1084_bridge_loc_ratchets_below_legacy_6500_ceiling():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= MAX_BRIDGE_LOC, f"bridge regrew to {loc} LOC; ratchet={MAX_BRIDGE_LOC}"
