from __future__ import annotations

import ast
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
VIEW = Path("phase6_final_scene_view.py")

ADAPTER_CLASS = "Phase6FinalSceneViewAdapter"

REQUIRED_METHODS = {
    "query_final_render_data",
    "make_assembly_scene_render_data",
    "query_assembly_render_data",
    "build_request",
    "render_cutting_mesh",
    "on_scroll",
    "install_renderer",
    "render_committed",
    "set_preview_enabled",
    "refresh_preview",
}

EXPECTED_DELEGATES = {
    "_phase6_query_final_render_data": "query_final_render_data",
    "_phase6_query_assembly_render_data": "query_assembly_render_data",
    "_phase6_final_scene_view_request": "build_request",
    "_phase6_on_3d_scroll": "on_scroll",
    "_phase6_install_renderer_view": "install_renderer",
    "_phase6_render_committed_view": "render_committed",
    "_phase6_set_3d_preview_enabled": "set_preview_enabled",
}

FORBIDDEN_ADAPTER_TOKENS = (
    "fold_designer_bridge",
    "phase6_manufacturing_service",
    "phase6_manufacturing_geometry",
    "build_part_render_data",
    "solve_world_backprojected_endcap_relief",
    "material_polygon_from_final_scene",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _adapter_class(tree: ast.Module):
    return next(
        (
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == ADAPTER_CLASS
        ),
        None,
    )


def test_issue370_requires_final_scene_view_adapter_without_solver_ownership():
    tree = _tree(VIEW)
    cls = _adapter_class(tree)
    assert cls is not None, "RED: missing T6 final-scene view adapter"

    methods = {
        node.name
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(REQUIRED_METHODS - methods)
    assert missing == [], f"RED: missing T6 final-scene adapter methods: {missing}"

    source = ast.unparse(cls)
    bad = [token for token in FORBIDDEN_ADAPTER_TOKENS if token in source]
    assert bad == [], f"T6 adapter crosses manufacturing authority boundary: {bad}"


def test_issue370_bridge_delegates_3d_render_orchestration():
    funcs = _functions(_tree(BRIDGE))
    missing = sorted(set(EXPECTED_DELEGATES) - set(funcs))
    assert missing == []
    assert "_phase6_render_true_cutting_mesh" not in funcs

    violations = []
    for name, delegate in EXPECTED_DELEGATES.items():
        source = ast.unparse(funcs[name])
        if ADAPTER_CLASS not in source and "_phase6_final_scene_adapter" not in source:
            if delegate not in source:
                violations.append((name, "MISSING_DELEGATE", delegate))

    assert violations == [], (
        "RED: bridge still owns T6 3D render orchestration: "
        f"{violations}"
    )


def test_issue370_adapter_boundary_has_no_direct_manufacturing_build_calls():
    tree = _tree(VIEW)
    cls = _adapter_class(tree)
    assert cls is not None, "RED: missing T6 final-scene view adapter"
    source = ast.unparse(cls)
    direct_build_tokens = (
        "build_part_render_data",
        "material_polygon_from_final_scene",
        "solve_world_backprojected_endcap_relief",
        "_phase6_resolve_manufacturing_geometry",
    )
    bad = [token for token in direct_build_tokens if token in source]
    assert bad == [], (
        "T6 adapter must consume injected authoritative providers, not build/solve: "
        f"{bad}"
    )
