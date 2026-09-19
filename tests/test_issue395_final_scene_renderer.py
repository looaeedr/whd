from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path


VIEW = Path("phase6_final_scene_view.py")
RENDERER = Path("phase6_final_scene_renderer.py")
CONTRACTS = Path("phase6_final_scene_contracts.py")
BRIDGE = Path("fold_designer_bridge.py")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def _adapter_class() -> ast.ClassDef:
    tree = _tree(VIEW)
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneViewAdapter"
    )


def test_issue395_requires_renderer_owner_module():
    assert RENDERER.is_file(), (
        "RED: Phase 4 T6 requires phase6_final_scene_renderer.py"
    )
    source = RENDERER.read_text(encoding="utf-8")
    assert "class Phase6FinalSceneRenderer" in source


def test_issue395_renderer_has_no_bridge_gui_or_app_owner_dependency():
    assert RENDERER.is_file()
    source = RENDERER.read_text(encoding="utf-8")
    imports = _imports(RENDERER)
    forbidden = sorted(
        name for name in imports
        if name == "fold_designer_bridge" or name.startswith("gui")
    )
    assert forbidden == []
    assert "self.owner" not in source
    assert ".owner" not in source
    assert "Phase6FoldDesignerApp" not in source


def test_issue395_adapter_no_longer_owns_app_or_renderer_runtime_state():
    source = VIEW.read_text(encoding="utf-8")
    cls = _adapter_class()
    class_source = ast.unparse(cls)

    assert "self.owner" not in class_source
    assert "owner" not in [
        arg.arg for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        for arg in (node.args.args + node.args.kwonlyargs)
    ]

    runtime_attrs = {
        "last_cutting_mesh",
        "last_cutting_material",
        "cutting_mesh_error",
        "zoom_scale",
        "view_initialized",
        "base_renderer_render",
        "scroll_cid",
        "last_interference_diagnostic",
    }
    stored = []
    for node in ast.walk(cls):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr in runtime_attrs
        ):
            stored.append((node.attr, node.lineno))
    assert stored == [], (
        "RED: adapter still stores renderer/runtime state: "
        f"{stored}"
    )


def test_issue395_mirror_service_and_bridge_mirror_function_are_removed():
    bridge = BRIDGE.read_text(encoding="utf-8")
    contracts = CONTRACTS.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")

    assert "_phase6_sync_final_scene_view_compatibility_mirrors" not in bridge
    assert "mirror_view_state" not in contracts
    assert "mirror_view_state" not in view


def test_issue395_final_scene_view_hits_quantitative_facade_targets():
    source = VIEW.read_text(encoding="utf-8")
    attrs = re.findall(r"\bself\.([A-Za-z_][A-Za-z0-9_]*)", source)
    assert len(source.splitlines()) <= 750, (
        f"RED: final scene view lines={len(source.splitlines())} > 750"
    )
    assert len(attrs) <= 48, (
        f"RED: final scene view self refs={len(attrs)} > 48"
    )
    assert len(set(attrs)) <= 12, (
        f"RED: final scene view unique self attrs={len(set(attrs))} > 12"
    )


def test_issue395_renderer_owns_runtime_and_mutation_surface():
    assert RENDERER.is_file()
    source = RENDERER.read_text(encoding="utf-8")
    required_tokens = (
        "last_cutting_mesh",
        "last_cutting_material",
        "cutting_mesh_error",
        "zoom_scale",
        "view_initialized",
        "last_interference_diagnostic",
        "on_scroll",
        "adjust_zoom_scale",
        "render",
    )
    missing = [token for token in required_tokens if token not in source]
    assert missing == [], f"RED: renderer owner missing runtime/mutation surface: {missing}"
