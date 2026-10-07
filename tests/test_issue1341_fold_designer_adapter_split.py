from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "gui_modules" / "application"
ADAPTER = APP / "fold_designer_adapter.py"
IMPLEMENTATIONS = tuple(
    APP / f"fold_designer_composition_{name}.py"
    for name in (
        "state",
        "settings",
        "receiving",
        "registry_edges",
        "assembly_corner",
        "shell_settings",
    )
)
PROJECTIONS = (
    APP / "fold_designer_manufacturing_projection.py",
    APP / "fold_designer_snapshot_projection.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_issue1341_adapter_and_composition_are_bounded():
    source = ADAPTER.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 1_000
    cls = next(
        node for node in _tree(ADAPTER).body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6FoldDesignerComposition"
    )
    assert cls.end_lineno - cls.lineno + 1 <= 800


def test_issue1341_extracted_owners_are_small_and_one_way():
    for path in (*IMPLEMENTATIONS, *PROJECTIONS):
        assert path.is_file(), path
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 1_000, f"{path.name} regrew: {len(source.splitlines())}"
        assert "from fold_designer_bridge import" not in source
        assert "import fold_designer_bridge" not in source


def test_issue1341_root_composition_methods_are_thin_routes():
    source = ADAPTER.read_text(encoding="utf-8")
    cls = next(
        node for node in _tree(ADAPTER).body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6FoldDesignerComposition"
    )
    implementation_modules = {
        "_composition_state",
        "_composition_settings",
        "_composition_receiving",
        "_composition_registry_edges",
        "_composition_assembly_corner",
        "_composition_shell_settings",
    }
    routed = 0
    for node in cls.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        block = ast.get_source_segment(source, node) or ""
        if any(name in block for name in implementation_modules):
            routed += 1
            assert node.end_lineno - node.lineno + 1 <= 5, node.name
    assert routed >= 100
