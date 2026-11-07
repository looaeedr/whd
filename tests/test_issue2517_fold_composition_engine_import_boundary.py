"""#2517: extracted Fold Designer views cannot silently reintroduce Engine internals."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPOSITIONS = (
    "fold_designer_composition_assembly_corner.py",
    "fold_designer_composition_registry_edges.py",
    "fold_designer_composition_settings.py",
    "fold_designer_composition_state.py",
    "fold_designer_composition_shell_settings.py",
    "fold_designer_composition_receiving.py",
)


@pytest.mark.parametrize("name", COMPOSITIONS)
def test_extracted_fold_composition_only_imports_public_engine_or_corner_value_type(name):
    path = ROOT / "gui_modules" / "application" / name
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = []
    public_seen = False
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("ae_engine"):
                    forbidden.append(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "ae_engine":
                public_seen |= any(alias.name == "manufacturing_api" for alias in node.names)
                forbidden.extend(alias.name for alias in node.names if alias.name != "manufacturing_api")
            elif node.module == "ae_engine.sheetmetal_geometry":
                # A read-only CornerType enum remains a compatibility view type.
                forbidden.extend(alias.name for alias in node.names if alias.name != "CornerTypeId")
            elif node.module.startswith("ae_engine.") and node.module != "ae_engine.manufacturing_api":
                forbidden.append(node.module)
    assert public_seen, f"{name}: GUI operation must retain the public Engine API"
    assert not forbidden, f"{name}: private Engine import(s): {forbidden}"
