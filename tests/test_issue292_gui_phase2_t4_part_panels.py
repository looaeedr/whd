from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
PANELS = ROOT / "gui_modules" / "parts" / "panels"
LEGACY = ROOT / "gui_modules" / "part_panels.py"
RECONCILED_GUI_GATE = 7_464

EXPECTED_PANEL_FILES = {
    "__init__.py",
    "common.py",
    "assembly_corner.py",
    "box_body.py",
    "endcap.py",
    "base_plate.py",
    "door.py",
    "divider.py",
    "multipart.py",
    "indicator_box.py",
}

# Whole-method responsibilities that Task 1 proved are unambiguous T4
# presentation/input-normalization scope. After cutover, root may retain only a
# tiny compatibility/delegation seam for an established caller.
MOVED_ROOT_METHODS = {
    "_sync_endcap_fw_controls",
    "_sync_fold_designer_manual_corner_context",
    "_fixed_corner_summary",
    "_reset_manual_corner_parameter_locks",
    "toggle_manual_corner_parameter_lock",
    "_corner_parameter_summary",
    "create_corner_type_panel",
    "_draw_corner_type_icon",
    "_normalize_manual_corner_target",
    "select_manual_corner",
    "_corner_number_text",
    "_selection_from_manual_corner_controls",
    "_refresh_manual_corner_parameter_rows",
    "refresh_corner_type_panel",
    "sync_base_plate_shrink",
    "create_input_row",
    "create_result_row",
    "create_separator",
    "create_advanced_inputs",
    "create_sub_input",
    "toggle_advanced_panel",
    "setup_tab_z_ui",
    "_attach_part_hole_entrypoint",
    "setup_tab_endcap_ui",
    "setup_tab_base_plate_ui",
    "_door_layout_number_text",
    "_parse_layout_value",
    "_reject_door_layout_dimension",
    "refresh_door_layout_status",
    "rebuild_door_layout_ui",
    "setup_tab_door_ui",
    "setup_tab_indicator_box_ui",
    "rebuild_layers_config_ui",
    "_indicator_small_door_size_chain_label",
    "setup_tab_indicator_door_ui",
}

FORBIDDEN_SHADOW_ASSIGNMENTS = {
    "active_part",
    "existing_parts",
    "settings",
    "door_layout_columns",
    "receiving_inner_doors",
    "project_path",
    "geometry",
}


def _host_method_spans() -> dict[str, int]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: (node.end_lineno or node.lineno) - node.lineno + 1
        for node in host.body
        if isinstance(node, ast.FunctionDef)
    }


def _panel_python_files() -> list[Path]:
    if not PANELS.is_dir():
        return []
    return sorted(path for path in PANELS.glob("*.py") if path.is_file())


def test_physical_part_panel_package_is_split_by_responsibility():
    assert PANELS.is_dir(), "missing gui_modules/parts/panels package"
    actual = {path.name for path in PANELS.iterdir() if path.is_file()}
    assert EXPECTED_PANEL_FILES <= actual, (
        f"missing focused panel modules: {sorted(EXPECTED_PANEL_FILES - actual)}"
    )


def test_panel_modules_do_not_import_root_gui_or_legacy_compatibility():
    files = _panel_python_files()
    assert files, "panel package must exist before import-direction checks can pass"
    offenders: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "gui" or alias.name.startswith("compatibility"):
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "gui" or module.startswith("compatibility"):
                    offenders.append(f"{path.name}: from {module} import ...")
    assert not offenders, f"forbidden panel dependencies: {offenders}"


def test_panels_do_not_create_known_committed_shadow_stores():
    files = _panel_python_files()
    assert files, "panel package must exist before shadow-state checks can pass"
    offenders: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in {"self", "host"}
                    and target.attr in FORBIDDEN_SHADOW_ASSIGNMENTS
                ):
                    offenders.append(f"{path.name}:{target.attr}")
    assert not offenders, f"panel shadow-state candidates: {offenders}"


def test_moved_root_methods_are_absent_or_thin_delegates():
    spans = _host_method_spans()
    fat = {name: spans[name] for name in MOVED_ROOT_METHODS if spans.get(name, 0) > 4}
    assert not fat, f"T4 presentation implementations still rooted in gui.py: {fat}"


def test_gui_meets_reconciled_t4_root_gate():
    loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert loc <= RECONCILED_GUI_GATE, f"gui.py LOC {loc} exceeds T4 gate {RECONCILED_GUI_GATE}"


def test_legacy_part_panels_is_removed_or_thin_deprecated_shim():
    if not LEGACY.exists():
        return
    text = LEGACY.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "DEPRECATED" in text and "_phase6_logical_part_present" not in functions, (
        "legacy gui_modules/part_panels.py still owns implementation instead of a thin deprecated shim"
    )
