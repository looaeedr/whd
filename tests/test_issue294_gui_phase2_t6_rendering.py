from __future__ import annotations

import ast
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
RENDERING = ROOT / "gui_modules" / "rendering"
SCOPE = ROOT / "tests" / "process" / "test_issue294_t6_scope_reconciliation.py"
RECONCILED_GATE = 4_729

EXPECTED_MODULES = {
    "__init__.py",
    "canvas_2d.py",
    "overlays.py",
    "transforms.py",
    "door_view.py",
    "box_body_view.py",
    "interaction.py",
}

T7_HOLD_METHODS = {
    "_authoritative_render_data",
    "_manufacturing_context",
    "_box_body_part_spec_from_values",
    "_box_body_part_spec",
    "_end_cap_part_spec_from_values",
    "_end_cap_part_spec",
    "_door_part_spec_from_values",
    "_single_door_part_spec",
    "_door_layout_part_spec",
    "_base_plate_part_spec_from_values",
    "_base_plate_part_spec",
    "_indicator_box_part_spec_from_values",
    "_indicator_box_part_spec",
    "_indicator_door_part_spec_from_values",
    "_indicator_door_part_spec",
}


def _root_tree():
    source = GUI.read_text(encoding="utf-8")
    return source, ast.parse(source)


def _host(tree: ast.Module) -> ast.ClassDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )


def _span(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def _t6_symbols() -> set[str]:
    scope = runpy.run_path(str(SCOPE))
    return set(scope["PURE_T6_SYMBOLS"])


def _rendering_python_files() -> list[Path]:
    return sorted(RENDERING.glob("*.py")) if RENDERING.is_dir() else []


def test_issue294_rendering_package_has_explicit_responsibility_modules():
    assert RENDERING.is_dir(), "T6 RED: gui_modules/rendering package is not extracted yet"
    present = {path.name for path in _rendering_python_files()}
    missing = sorted(EXPECTED_MODULES - present)
    assert not missing, f"T6 RED: missing rendering responsibility modules: {missing}"


def test_issue294_root_t6_symbols_are_removed_or_thin_delegates_only():
    _source, tree = _root_tree()
    host = _host(tree)
    top = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    methods = {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    oversized = []
    for name in sorted(_t6_symbols()):
        node = methods.get(name) or top.get(name)
        if node is not None and _span(node) > 8:
            oversized.append((name, _span(node)))

    assert not oversized, (
        "T6 RED: root still owns non-thin rendering implementations: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_issue294_root_hits_reconciled_t6_gate():
    loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert loc <= RECONCILED_GATE, f"T6 RED: gui.py LOC={loc} > {RECONCILED_GATE}"


def test_issue294_rendering_package_import_direction_and_size_contract():
    files = _rendering_python_files()
    if not files:
        return

    violations = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        loc = len(source.splitlines())
        if loc > 1_500:
            violations.append(f"{path.name}: module LOC {loc} > 1500")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "gui" or alias.name.startswith("compatibility.legacy_exports"):
                        violations.append(f"{path.name}: forbidden import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "gui" or module.startswith("compatibility.legacy_exports"):
                    violations.append(f"{path.name}: forbidden import from {module}")
                if module.startswith("ae_engine.manufacturing_api"):
                    violations.append(f"{path.name}: manufacturing_api authority import")

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _span(node) > 150:
                violations.append(f"{path.name}:{node.name} method LOC {_span(node)} > 150")
            if isinstance(node, ast.ClassDef) and _span(node) > 800:
                violations.append(f"{path.name}:{node.name} class LOC {_span(node)} > 800")

        if "manufacturing_api." in source:
            violations.append(f"{path.name}: manufacturing_api call in renderer")
        for forbidden in (
            "def _authoritative_render_data",
            "def _manufacturing_context",
            "def _box_body_part_spec",
            "def _end_cap_part_spec",
            "def _door_layout_part_spec",
            "def _base_plate_part_spec",
        ):
            if forbidden in source:
                violations.append(f"{path.name}: forbidden authority definition {forbidden}")

    assert not violations, "\n".join(violations)


def test_issue294_t7_hold_authority_remains_outside_rendering_package():
    source, tree = _root_tree()
    host = _host(tree)
    methods = {node.name for node in host.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = sorted(T7_HOLD_METHODS - methods)
    if missing:
        t7_owner_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "gui_modules" / "application" / "fold_designer_adapter.py",
                ROOT / "gui_modules" / "application" / "manufacturing_adapter.py",
            )
        )
        unresolved = sorted(name for name in missing if f"def {name}" not in t7_owner_source)
        assert not unresolved, f"T7 HOLD authority has no current owner: {unresolved}"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _rendering_python_files())
    stolen = sorted(name for name in T7_HOLD_METHODS if f"def {name}" in combined)
    assert not stolen, f"T6 rendering package stole T7 authority: {stolen}"

def test_issue294_rendering_package_does_not_create_second_committed_state_owner():
    files = _rendering_python_files()
    if not files:
        return
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    forbidden_assignments = (
        "self.surface_features =",
        "self.assembly_joint_state =",
        "self.workspace_controller =",
        "self.project_controller =",
        "self.phase6_project =",
    )
    hits = [token for token in forbidden_assignments if token in combined]
    assert not hits, f"renderer created committed-state owner(s): {hits}"
