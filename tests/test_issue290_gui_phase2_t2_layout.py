from pathlib import Path
import ast
import importlib

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
LAYOUT = ROOT / "gui_modules" / "layout"


def _imports_forbidden_dependency(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "gui" or a.name.startswith("compatibility") for a in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "gui" or (node.module or "").startswith("compatibility"):
                return True
    return False


def _host_method(name: str):
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        node for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_layout_is_focused_package_with_legacy_toolbar_export():
    assert LAYOUT.is_dir()
    for name in (
        "__init__.py",
        "styles.py",
        "toolbar.py",
        "main_window.py",
        "scrolling.py",
        "left_panel.py",
        "workspace.py",
    ):
        assert (LAYOUT / name).is_file(), name
    module = importlib.import_module("gui_modules.layout")
    assert callable(module._project_toolbar_presentation)


def test_layout_modules_do_not_import_root_or_legacy_compatibility():
    assert LAYOUT.is_dir()
    for path in LAYOUT.glob("*.py"):
        assert not _imports_forbidden_dependency(path), path


def test_root_layout_methods_are_thin_delegates_and_size_gate_holds():
    text = GUI.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 8650
    for name in ("setup_styles", "create_widgets"):
        node = _host_method(name)
        assert node.end_lineno - node.lineno + 1 <= 8, name
    create_widgets = _host_method("create_widgets")
    assert "tk.PanedWindow(self.root" not in ast.get_source_segment(text, create_widgets)


def test_no_layout_module_becomes_a_new_monolith():
    assert LAYOUT.is_dir()
    for path in LAYOUT.glob("*.py"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 1500, path
