from pathlib import Path
import ast


MOVED_ACTIONS = (
    "save_phase6_project_as",
    "save_phase6_project",
    "open_phase6_project",
    "load_phase6_project",
)


def _class_node(source: str, class_name: str):
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)


def test_project_action_module_owns_global_open_save_load_wrappers():
    module_path = Path("gui_modules/project_actions.py")
    assert module_path.is_file(), "T6 requires gui_modules/project_actions.py"
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    module_functions = {
        node.name
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(MOVED_ACTIONS) <= module_functions


def test_phase6_application_host_no_longer_defines_moved_action_bodies():
    gui_source = Path("gui.py").read_text(encoding="utf-8")
    host = _class_node(gui_source, "Phase6ApplicationHost")
    class_methods = {
        node.name
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(MOVED_ACTIONS).isdisjoint(class_methods)


def test_gui_imports_project_actions_without_reverse_gui_dependency():
    gui_source = Path("gui.py").read_text(encoding="utf-8")
    assert "from gui_modules.project_actions import" in gui_source
    module_source = Path("gui_modules/project_actions.py").read_text(encoding="utf-8")
    assert "import gui" not in module_source
    assert "from gui import" not in module_source
