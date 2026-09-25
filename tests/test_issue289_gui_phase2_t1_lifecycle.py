from __future__ import annotations

import ast
from pathlib import Path


# RED contract for #289/T1. Keep this structural gate independent from implementation details.
ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
APPLICATION = ROOT / "gui_modules" / "application"

MOVED_HOST_METHODS = {
    "__init__",
    "_current_cabinet_type_name",
    "_apply_manual_corner_snapshot",
    "_apply_fold_designer_live_settings",
    "_save_fold_designer_defaults",
    "_apply_fold_designer_live_corner_state",
    "_notify_fold_designer_corner_state",
    "_fold_designer_number_text",
    "_apply_existing_parts_from_fold_workspace",
    "_apply_phase6_project_snapshot",
    "_compose_phase6_project_snapshot_from_main_gui",
    "_capture_phase6_committed_snapshot",
    "_apply_original_fold_designer_snapshot",
    "_store_fold_designer_workspace",
    "_apply_fold_designer_live_snapshot",
    "_apply_fold_designer_corner_transaction",
    "_reload_current_baseline_features",
    "open_original_fold_designer",
    "_request_phase6_update",
    "_flush_phase6_authoritative_state",
    "bind_live_updates",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_t1_gui_monolith_gate_is_at_most_9000_lines():
    assert len(GUI.read_text(encoding="utf-8").splitlines()) <= 9000


def test_t1_application_modules_exist_and_never_import_gui():
    expected = {
        APPLICATION / "__init__.py",
        APPLICATION / "lifecycle.py",
        APPLICATION / "command_router.py",
    }
    assert all(path.is_file() for path in expected)

    for path in sorted(expected):
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "gui" for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "gui", path


def test_t1_host_delegates_lifecycle_cluster_instead_of_defining_it_inline():
    tree = _tree(GUI)
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    direct_methods = {
        node.name for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert MOVED_HOST_METHODS.isdisjoint(direct_methods)


def test_t1_scheduler_is_not_defined_inline_in_gui():
    tree = _tree(GUI)
    inline_classes = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    assert "_Phase6UpdateScheduler" not in inline_classes
