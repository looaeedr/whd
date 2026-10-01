from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "phase6_assembly_panel.py"


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(name: str) -> ast.FunctionDef:
    return next(
        node
        for node in _module(BRIDGE).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _owner_methods() -> dict[str, ast.FunctionDef]:
    tree = _module(OWNER)
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6AssemblyPanel"
    )
    return {
        node.name: node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
    }


def test_assembly_panel_owner_exposes_compatibility_and_render_entrypoints():
    methods = _owner_methods()
    for name in (
        "install_legacy_aliases",
        "sync_dynamic_legacy_aliases",
        "render_available_parts",
        "represented_part_keys",
        "refresh_if_topology_changed",
    ):
        assert name in methods


def test_bridge_assembly_panel_functions_are_thin_owner_wrappers():
    limits = {
        "_phase6_install_assembly_panel_aliases": 4,
        "_phase6_current_assembly_panel_part_keys": 5,
        "_phase6_refresh_assembly_parts_panel_if_topology_changed": 14,
        "_phase6_refresh_assembly_parts_panel": 13,
    }
    for name, limit in limits.items():
        fn = _function(name)
        assert fn.end_lineno - fn.lineno + 1 <= limit


def test_assembly_panel_owner_does_not_reverse_import_bridge_or_manufacturing():
    tree = _module(OWNER)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "fold_designer_bridge" not in imports
    assert not [name for name in imports if "manufacturing" in name]


def test_bridge_loc_ratchets_below_5930_after_assembly_panel_owner_deepening():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 5930, f"Bridge regrew past #1108 ratchet: {loc}"
