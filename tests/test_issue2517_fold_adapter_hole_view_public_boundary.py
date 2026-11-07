"""#2517: presenter modules cannot reacquire private Engine manufacturing APIs."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FOLD_ADAPTER = ROOT / "gui_modules/application/fold_designer_adapter.py"
HOLE_VIEW = ROOT / "gui_modules/editors/hole_editor_view.py"


def _engine_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(("import", alias.name) for alias in node.names
                           if alias.name == "ae_engine" or alias.name.startswith("ae_engine."))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "ae_engine" or node.module.startswith("ae_engine."):
                imports.extend(("from", node.module, alias.name) for alias in node.names)
    return tuple(imports)


def test_fold_adapter_retains_only_public_engine_and_read_only_corner_enum():
    imports = _engine_imports(FOLD_ADAPTER)
    assert ("from", "ae_engine", "manufacturing_api") in imports
    assert ("from", "ae_engine.sheetmetal_geometry", "CornerTypeId") in imports
    assert not (set(imports) - {
        ("from", "ae_engine", "manufacturing_api"),
        ("from", "ae_engine.sheetmetal_geometry", "CornerTypeId"),
    })


def test_hole_editor_presentation_does_not_import_engine_geometry_functions():
    # Input mutations and physical dimensions are handled by the existing
    # editor session/public Engine API; this Tk view is render-only.
    assert _engine_imports(HOLE_VIEW) == ()


def test_corner_type_compatibility_alias_is_original_engine_value_type():
    from ae_engine.sheetmetal_geometry import CornerTypeId
    from gui_modules.application.fold_designer_adapter import CornerTypeId as adapter_corner

    assert adapter_corner is CornerTypeId
