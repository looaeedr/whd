from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _host_method(name: str):
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        (
            node for node in host.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ),
        None,
    )


def test_snapshot_projection_owner_is_split_and_root_is_thin():
    funcs = _functions(OWNER)
    required = (
        "_snapshot_base_state",
        "_snapshot_workspace_state",
        "_snapshot_part_dimensions",
        "_make_original_fold_designer_snapshot",
    )
    for name in required:
        assert name in funcs, f"4C owner helper missing: {name}"
        assert funcs[name].end_lineno - funcs[name].lineno + 1 <= 150

    assert (
        funcs["_make_original_fold_designer_snapshot"].end_lineno
        - funcs["_make_original_fold_designer_snapshot"].lineno
        + 1
        <= 30
    )

    root = _host_method("_make_original_fold_designer_snapshot")
    if root is not None:
        assert root.end_lineno - root.lineno + 1 <= 5
    else:
        assert "_make_original_fold_designer_snapshot = _phase6_fold_adapter._make_original_fold_designer_snapshot" in GUI.read_text(encoding="utf-8")


def test_snapshot_projection_keeps_authoritative_sources():
    text = OWNER.read_text(encoding="utf-8")
    for token in (
        "workspace_controller.part_profiles_snapshot()",
        "_phase6_current_existing_parts()",
        "door_layout_feature_map_to_part_features",
        "migrate_legacy_snapshot_joints",
        "manufacturing_api.indicator_box_unfolded_size",
        "manufacturing_api.indicator_small_door_unfolded_size",
    ):
        assert token in text, f"snapshot authority token missing: {token}"


def test_snapshot_projection_does_not_create_project_or_workspace_authority():
    text = OWNER.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "PROJECT_SCHEMA =" not in text
    assert "write_project(" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
