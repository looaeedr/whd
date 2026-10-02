from __future__ import annotations

import ast
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
ADAPTER = Path("phase6_corner_data_view_adapter.py")
MAX_BRIDGE_LOC = 6380


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _method(path: Path, cls_name: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls_name)
    return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)


def test_issue1088_corner_data_widget_lifecycle_has_deep_owner():
    prepare = _method(ADAPTER, "Phase6CornerDataViewAdapter", "prepare_canvas")
    refresh = _method(ADAPTER, "Phase6CornerDataViewAdapter", "refresh_parts_panel")
    adapter_source = ADAPTER.read_text(encoding="utf-8")
    prepare_source = ast.get_source_segment(adapter_source, prepare) or ""
    refresh_source = ast.get_source_segment(adapter_source, refresh) or ""
    for token in ("tk.Canvas(", "ttk.Label("):
        assert token in prepare_source
    for token in ("ttk.Frame(", "ttk.Button("):
        assert token in refresh_source


def test_issue1088_bridge_keeps_only_thin_corner_data_presentation_wrappers():
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    prepare = _function(BRIDGE, "_phase6_prepare_corner_data_canvas")
    refresh = _function(BRIDGE, "_phase6_refresh_corner_data_parts_panel")
    prepare_source = ast.get_source_segment(bridge_source, prepare) or ""
    refresh_source = ast.get_source_segment(bridge_source, refresh) or ""
    assert "prepare_canvas(" in prepare_source
    assert "refresh_parts_panel(" in refresh_source
    for token in ("original.tk.Canvas(", "original.ttk.Label("):
        assert token not in prepare_source
    for token in ("original.ttk.Frame(", "original.ttk.Button("):
        assert token not in refresh_source
    assert prepare.end_lineno - prepare.lineno + 1 <= 16
    assert refresh.end_lineno - refresh.lineno + 1 <= 14


def test_issue1088_bridge_loc_ratchets_after_corner_data_owner_move():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= MAX_BRIDGE_LOC, f"bridge regrew to {loc} LOC; ratchet={MAX_BRIDGE_LOC}"
