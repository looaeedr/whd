from __future__ import annotations

import ast
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
ADAPTER = Path("phase6_corner_data_view_adapter.py")

REQUIRED_METHODS = {
    "part_keys",
    "navigation_rows",
    "resolve_selection",
    "info_request",
    "unfold_projection",
    "unfold_projections",
    "selected_projection",
    "view_payload",
    "zoom_from_event",
    "edge_host_placement",
    "formed_size_text",
    "unfolded_blank_text",
    "current_unfolded_size",
    "registry_preview_geometry",
    "canvas_visibility_plan",
}

EXPECTED_DELEGATES = {
    "_phase6_corner_data_part_keys": "part_keys",
    "_phase6_corner_data_navigation_rows": "navigation_rows",
    "_phase6_select_corner_data_part": "resolve_selection",
    "_phase6_corner_data_info_request_for_key": "info_request",
    "_phase6_corner_data_unfold_projection_for_key": "unfold_projection",
    "_phase6_corner_data_unfold_projections": "unfold_projections",
    "_phase6_corner_data_unfold_projection": "selected_projection",
    "_phase6_refresh_corner_data_unfold_view": "view_payload",
    "_phase6_on_corner_data_mousewheel": "zoom_from_event",
    "_phase6_place_drawing_edge_host": "edge_host_placement",
    "_phase6_format_formed_size_text": "formed_size_text",
    "_phase6_format_unfolded_blank_text": "unfolded_blank_text",
    "_phase6_current_unfolded_size": "current_unfolded_size",
    "_phase6_prepare_corner_data_canvas": "canvas_visibility_plan",
    "_phase6_hide_corner_data_canvas": "canvas_visibility_plan",
}

FORBIDDEN_ADAPTER_TOKENS = (
    "phase6_manufacturing_service",
    "phase6_manufacturing_geometry",
    "solve_world_backprojected_endcap_relief",
    "_phase6_folded_mesh_from_polygon",
    "_phase6_folded_outside_envelope",
    "build_part_render_data",
    "material_polygon_from_final_scene",
)

VIEW_RECONSTRUCTION_TOKENS = (
    "_phase6_folded_mesh_from_polygon",
    "_phase6_folded_outside_envelope",
    "_phase6_profile_geometry",
    "_phase6_fold_ownership_exemptions",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue369_requires_corner_data_view_adapter_without_solver_ownership():
    assert ADAPTER.is_file(), "RED: missing T5 corner-data view adapter"
    tree = _tree(ADAPTER)
    methods = {
        n.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6CornerDataViewAdapter"
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(REQUIRED_METHODS - methods)
    assert missing == [], f"RED: missing T5 view-adapter methods: {missing}"

    source = ADAPTER.read_text(encoding="utf-8")
    bad = [token for token in FORBIDDEN_ADAPTER_TOKENS if token in source]
    assert bad == [], f"T5 adapter crosses manufacturing authority boundary: {bad}"


def test_issue369_bridge_delegates_authoritative_2d_projection_and_view_state():
    funcs = _functions(_tree(BRIDGE))
    moved_to_adapter = {"_phase6_current_unfolded_size", "_phase6_format_formed_size_text"}
    missing = sorted(set(EXPECTED_DELEGATES) - set(funcs))
    assert set(missing) <= moved_to_adapter

    adapter_methods = {
        n.name
        for cls in _tree(ADAPTER).body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6CornerDataViewAdapter"
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {"current_unfolded_size", "formed_size_text"} <= adapter_methods

    violations = []
    for name, delegate in EXPECTED_DELEGATES.items():
        if name not in funcs:
            continue
        source = ast.unparse(funcs[name])
        if delegate not in source:
            violations.append((name, "MISSING_DELEGATE", delegate))

    bridge_source = BRIDGE.read_text(encoding="utf-8")
    assert (
        "_phase6_registry_preview_2d = lambda self: "
        "_phase6_registry_panel(self).draw_registry_preview()"
    ) in bridge_source
    preview_payload = ast.unparse(funcs["_phase6_registry_preview_payload"])
    assert "_phase6_registry_validate_formula_form" in preview_payload
    assert "registry_preview_geometry" in preview_payload

    select = funcs["_phase6_select_corner_data_part"]
    for node in ast.walk(select):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == "_phase6_corner_data_selected_part_key"
        ):
            violations.append((
                "_phase6_select_corner_data_part",
                "DIRECT_VIEW_STATE_WRITE",
                node.attr,
                node.lineno,
            ))

    assert violations == [], (
        "RED: bridge still owns T5 authoritative 2D projection/view state: "
        f"{violations}"
    )


def test_issue369_view_layer_does_not_reconstruct_formed_geometry():
    funcs = _functions(_tree(BRIDGE))
    if "_phase6_format_formed_size_text" in funcs:
        source = ast.unparse(funcs["_phase6_format_formed_size_text"])
    else:
        source = ADAPTER.read_text(encoding="utf-8")
    bad = [token for token in VIEW_RECONSTRUCTION_TOKENS if token in source]
    assert bad == [], (
        "RED: view layer still reconstructs formed geometry instead of consuming "
        f"authoritative dimensions: {bad}"
    )
