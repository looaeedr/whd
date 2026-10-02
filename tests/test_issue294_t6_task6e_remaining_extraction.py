from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
INTERACTION = ROOT / "gui_modules" / "rendering" / "interaction.py"
BOX_VIEW = ROOT / "gui_modules" / "rendering" / "box_body_view.py"


def _span(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def _host_methods():
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _module_functions(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return source, {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_task6e_rendering_modules_export_remaining_routes():
    interaction_source, interaction_fns = _module_functions(INTERACTION)
    box_source, box_fns = _module_functions(BOX_VIEW)

    missing = []
    for name in ("draw_preview", "open_box_body_face_editor"):
        if name not in interaction_fns:
            missing.append(f"interaction:{name}")
    if "box_body_baseline_faces" not in box_fns:
        missing.append("box_body_view:box_body_baseline_faces")

    assert not missing, f"T6 TASK6E RED: remaining rendering routes missing: {missing}"


def test_task6e_root_remaining_t6_methods_are_thin_delegates():
    methods = _host_methods()
    oversized = []
    for name in (
        "draw_preview",
        "_box_body_baseline_faces",
        "open_box_body_face_editor",
    ):
        node = methods[name]
        if _span(node) > 4:
            oversized.append((name, _span(node)))

    assert not oversized, (
        "T6 TASK6E RED: root remaining T6 methods are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task6e_extracted_routes_do_not_steal_manufacturing_authority():
    interaction_source, interaction_fns = _module_functions(INTERACTION)
    box_source, box_fns = _module_functions(BOX_VIEW)

    selected = []
    for name in ("draw_preview", "open_box_body_face_editor"):
        node = interaction_fns.get(name)
        if node is not None:
            selected.append(ast.get_source_segment(interaction_source, node) or "")
    node = box_fns.get("box_body_baseline_faces")
    if node is not None:
        selected.append(ast.get_source_segment(box_source, node) or "")

    combined = "\n".join(selected)
    forbidden = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_box_body_part_spec",
        "_end_cap_part_spec",
        "build_box_body_result",
        "build_end_cap",
    )
    hits = [token for token in forbidden if token in combined]
    assert not hits, f"Task6E stole manufacturing authority: {hits}"


def test_task6e_rendering_package_import_direction_stays_clean():
    for path in (INTERACTION, BOX_VIEW):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "gui"
                    assert not alias.name.startswith("compatibility.legacy_exports")
                    assert not alias.name.startswith("ae_engine.manufacturing_api")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module != "gui"
                assert not module.startswith("compatibility.legacy_exports")
                assert not module.startswith("ae_engine.manufacturing_api")
