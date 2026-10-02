from __future__ import annotations

import ast
from pathlib import Path


PROJECTION = Path("phase6_final_scene_projection.py")
VIEW = Path("phase6_final_scene_view.py")

REQUIRED_PROJECTION_FUNCTIONS = {
    "_phase6_profile_base_index",
    "_phase6_profile_geometry",
    "_phase6_fold_mask_for_cross_coordinate",
    "_phase6_profile_map_with_guides",
    "_phase6_profile_map",
    "_phase6_profile_flat_map",
    "_phase6_folded_mesh_from_polygon",
    "_phase6_mesh_feature_segments",
    "_phase6_fitted_limits_from_vertices",
    "_phase6_scene_fold_boundaries",
    "_phase6_profile_to_scene_boundaries",
    "_phase6_fold_ownership_exemptions",
    "_default_number_text",
    "_phase6_folded_outside_envelope",
    "_phase6_profile_operator_fold_values",
    "_phase6_contract_profile_rows",
    "_phase6_box_body_piece_world_mapper",
    "_phase6_box_body_piece_dimension_lines",
    "_phase6_box_body_structure_meshes",
    "format_operator_info_text",
    "_phase6_triangle_bounds",
    "_phase6_place_assembly_triangles",
    "make_assembly_scene_render_data",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_defs(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue394_requires_pure_projection_module():
    assert PROJECTION.is_file(), (
        "RED: Phase 4 T5 requires phase6_final_scene_projection.py"
    )
    tree = _tree(PROJECTION)
    missing = sorted(REQUIRED_PROJECTION_FUNCTIONS - _top_defs(tree))
    assert not missing, f"RED: missing projection functions: {missing}"


def test_issue394_projection_module_has_no_renderer_ui_or_bridge_dependency():
    assert PROJECTION.is_file()
    source = PROJECTION.read_text(encoding="utf-8")
    tree = _tree(PROJECTION)

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden_imports = sorted(
        name for name in imports
        if name == "tkinter"
        or name.startswith("tkinter.")
        or name == "fold_designer_bridge"
        or name.startswith("gui")
        or name.startswith("matplotlib")
        or name == "whd_theme"
    )
    assert forbidden_imports == []
    assert "self." not in source
    assert ".ax3d" not in source
    assert "add_collection3d" not in source
    assert ".plot(" not in source
    assert ".draw(" not in source
    assert ".draw_idle(" not in source


def test_issue394_view_imports_projection_instead_of_duplicating_formulas():
    source = VIEW.read_text(encoding="utf-8")
    tree = _tree(VIEW)
    definitions = _top_defs(tree)
    duplicated = sorted(REQUIRED_PROJECTION_FUNCTIONS & definitions)
    assert duplicated == [], (
        "RED: projection formulas still duplicated in Final Scene view: "
        f"{duplicated}"
    )
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "phase6_final_scene_projection"
    ]
    assert imports, "RED: Final Scene view does not import projection owner"


def test_issue394_projection_smoke_keeps_profile_mapping_contract():
    from phase6_final_scene_projection import (
        _phase6_profile_geometry,
        _phase6_profile_map,
        _phase6_profile_flat_map,
    )

    profile = (
        {"len": 20.0, "angle": -90.0},
        {"len": 60.0, "core": "W"},
        {"len": 20.0, "angle": 90.0},
    )
    boundaries, folded = _phase6_profile_geometry(profile)
    assert boundaries == (0.0, 20.0, 80.0, 100.0)
    assert len(folded) == 4
    assert len(_phase6_profile_map(50.0, boundaries, folded)) == 2
    flat, z = _phase6_profile_flat_map(
        50.0,
        boundaries,
        profile=profile,
    )
    assert isinstance(flat, float)
    assert z == 0.0


def test_issue394_adapter_owns_assembly_dto_projection_without_bridge_wrapper():
    bridge = Path("fold_designer_bridge.py")
    view_tree = _tree(VIEW)
    bridge_tree = _tree(bridge)

    cls = next(
        node for node in view_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneViewAdapter"
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "make_assembly_scene_render_data"
    )
    assert "_project_assembly_scene_render_data" in ast.unparse(method)

    bridge_funcs = {
        node.name: node
        for node in bridge_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_phase6_make_assembly_scene_render_data" not in bridge_funcs

