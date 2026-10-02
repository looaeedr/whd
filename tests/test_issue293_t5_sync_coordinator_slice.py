from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACK = "sync_all"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _coordinator_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorSyncCoordinator"), None)
    assert node is not None, "T5 RED: HoleEditorSyncCoordinator is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, object] = {}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorSyncCoordinator"]


def test_sync_all_moves_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert TARGET_CALLBACK not in nested, "T5 RED: sync_all remains rooted in _open_unified_hole_editor"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorSyncCoordinator"), None)
    assert cls is not None, "T5 RED: HoleEditorSyncCoordinator is missing"
    assert _span(cls) <= 25
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "sync_all" in methods
    assert _span(methods["sync_all"]) <= 8


def test_sync_all_preserves_external_sync_then_preview_order():
    cls = _coordinator_class()
    calls: list[str] = []
    coordinator = cls(
        sync_callback=lambda: calls.append("sync"),
        draw_preview=lambda: calls.append("preview"),
    )
    assert coordinator.sync_all() is None
    assert calls == ["sync", "preview"]


def test_sync_all_without_external_callback_still_draws_preview():
    cls = _coordinator_class()
    calls: list[str] = []
    coordinator = cls(sync_callback=None, draw_preview=lambda: calls.append("preview"))
    assert coordinator.sync_all() is None
    assert calls == ["preview"]
