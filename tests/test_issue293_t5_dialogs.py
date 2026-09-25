from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
DIALOGS = ROOT / "gui_modules" / "editors" / "dialogs.py"


def test_issue293_xy_parser_preserves_current_numeric_contract():
    from gui_modules.editors.dialogs import parse_xy_values

    assert parse_xy_values("12.5", "-3") == (12.5, -3.0)
    with pytest.raises(ValueError):
        parse_xy_values("bad", "1")
    with pytest.raises(ValueError):
        parse_xy_values("1", "bad")


def test_issue293_xy_dialog_preserves_modal_confirm_cancel_bindings():
    assert DIALOGS.is_file(), "T5 dialog RED: dialogs.py has not been extracted"
    source = DIALOGS.read_text(encoding="utf-8")
    for marker in (
        "tk.Toplevel",
        "grab_set",
        "<Return>",
        "<Escape>",
        "wait_window",
        "messagebox.showerror",
        "請輸入正確的數字格式",
    ):
        assert marker in source


def test_issue293_root_ask_xy_dialog_is_only_a_thin_delegate():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    method = next(
        node
        for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == "ask_xy_dialog"
    )
    span = int(method.end_lineno) - int(method.lineno) + 1
    assert span <= 12, f"ask_xy_dialog remains rooted ({span} LOC)"
    segment = ast.get_source_segment(GUI.read_text(encoding="utf-8"), method) or ""
    assert "_ask_xy_dialog_impl" in segment
