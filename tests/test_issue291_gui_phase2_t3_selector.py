from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
PARTS = ROOT / "gui_modules" / "parts"


def _host_method(name: str) -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        node for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _imports_forbidden_dependency(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "gui" or a.name.startswith("compatibility") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "gui" or module.startswith("compatibility"):
                return True
    return False


def test_t3_focused_selector_modules_exist():
    assert PARTS.is_dir()
    for name in ("__init__.py", "selector.py", "subtabs.py"):
        assert (PARTS / name).is_file(), name


def test_t3_parts_modules_do_not_import_root_or_legacy_compatibility():
    assert PARTS.is_dir()
    for path in PARTS.glob("*.py"):
        assert not _imports_forbidden_dependency(path), path


def test_root_selector_methods_are_thin_delegates_and_size_gate_holds():
    text = GUI.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 8520
    max_lines = {
        "_phase6_refresh_presence_ui": 3,
        "_box_body_piece_label": 4,
        "_box_body_piece_face_key": 4,
        "_refresh_box_body_piece_tabs_2d": 3,
        "_on_box_body_piece_2d_tab_changed": 3,
        "on_box_body_piece_double_click": 3,
    }
    for name, limit in max_lines.items():
        try:
            node = _host_method(name)
        except StopIteration:
            node = None
        if node is None:
            if name == "_phase6_refresh_presence_ui":
                assert "_phase6_refresh_presence_ui = _phase6_visibility.phase6_refresh_presence_ui" in text
                continue
            raise AssertionError(f"missing selector route: {name}")
        assert node.end_lineno - node.lineno + 1 <= limit, name

def test_box_body_physical_subtab_construction_is_not_inline_in_setup_tab_z():
    text = GUI.read_text(encoding="utf-8")
    node = _host_method("setup_tab_z_ui")
    source = ast.get_source_segment(text, node) or ""
    assert "build_box_body_piece_selector" in source
    assert "self.box_body_piece_tabs = ttk.Notebook" not in source


def test_t3_modules_do_not_create_second_authoritative_part_or_presence_store():
    if not PARTS.is_dir():
        raise AssertionError("focused parts package missing")
    forbidden_assignments = {
        "active_part",
        "current_part",
        "existing_parts",
        "part_presence",
    }
    for path in PARTS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assert target.id not in forbidden_assignments, (path, target.id)
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in {"self", "host"}:
                    assert target.attr not in forbidden_assignments, (path, target.attr)
