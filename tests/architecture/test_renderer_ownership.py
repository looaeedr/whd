from pathlib import Path
import ast


SAFE_HELPERS = (
    "_draw_layout_resolved_features",
    "_draw_layout_baseline_secondary",
    "draw_grid",
)


def test_structure_safe_helpers_move_to_render_2d_without_reverse_gui_dependency():
    module_path = Path("gui_modules/render_2d.py")
    assert module_path.is_file(), "T7 first cut requires gui_modules/render_2d.py"
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    module_functions = {
        node.name
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(SAFE_HELPERS) <= module_functions
    assert "import gui" not in module_source
    assert "from gui import" not in module_source


def test_structure_phase6_host_no_longer_defines_safe_helper_bodies():
    gui_source = Path("gui.py").read_text(encoding="utf-8")
    tree = ast.parse(gui_source)
    host = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost")
    methods = {
        node.name
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(SAFE_HELPERS).isdisjoint(methods)
    assert "from gui_modules.render_2d import" in gui_source


def test_structure_existing_3d_deep_module_remains_the_only_new_3d_owner():
    view_source = Path("phase6_final_scene_view.py").read_text(encoding="utf-8")
    renderer_source = Path("phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    view_tree = ast.parse(view_source)
    renderer_tree = ast.parse(renderer_source)
    assert any(
        isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneViewAdapter"
        for node in view_tree.body
    )
    assert any(
        isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneRenderer"
        for node in renderer_tree.body
    )
    assert "must not build PartSpec" in view_source or "不得建立 PartSpec" in view_source
    assert not Path("gui_modules/render_3d.py").exists()
