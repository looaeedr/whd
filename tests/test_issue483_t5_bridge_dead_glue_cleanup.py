from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"

REMOVED = {
    "_phase6_on_setting_var_changed",
    "_phase6_corner_targets",
    "_phase6_on_endcap_fw_follow_selected",
    "_phase6_bind_translated_var",
    "_phase6_scene_from_structural_result",
    "_phase6_profile_material_total",
}

PROTECTED_KEEP = {
    "_phase6_rebuild_linked_endcaps",
    "_phase6_settings_box_structure_projection",
    "_phase6_settings_endcap_fw_projection",
    "_phase6_settings_bottom_wrap_projection",
    "_phase6_settings_corner_projection",
    "_phase6_settings_context_extension_projection",
    "_phase6_sync_settings_panel_extension",
    "_fix11_init",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_functions() -> set[str]:
    return {
        node.name
        for node in _tree(BRIDGE).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _facade_binding_count() -> int:
    tree = _tree(BRIDGE)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "install_fold_designer_bridge_facade"
    ]
    assert len(calls) == 1
    mapping = next(arg for arg in calls[0].args if isinstance(arg, ast.Dict))
    return len(mapping.keys)


def test_issue483_removes_only_census_proven_dead_glue():
    funcs = _top_functions()
    assert REMOVED.isdisjoint(funcs)
    assert PROTECTED_KEEP <= funcs



def test_issue483_protected_bridge_boundaries_remain_intact():
    assert (ROOT / "phase6_workspace_shell.py").is_file()
    assert not (ROOT / "phase6_part_editor_session.py").exists()
    assert _facade_binding_count() <= 69

def test_issue483_no_second_composition_root_or_reverse_import():
    assert not (ROOT / "gui_modules" / "application" / "fold_designer_composition.py").exists()
    for rel in (
        "gui_modules/application/fold_designer_adapter.py",
        "phase6_final_scene_view.py",
        "phase6_settings_panel.py",
        "phase6_workspace_navigation_controller.py",
        "phase6_designer_workspace.py",
        "phase6_fold_profiles.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "from fold_designer_bridge import" not in source
        assert "import fold_designer_bridge" not in source
