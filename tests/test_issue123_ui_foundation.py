# -*- coding: utf-8 -*-
"""Issue #123 — engineering-workbench shell/toolbar presentation contract."""

import ast
from pathlib import Path


GUI_PATH = Path(__file__).resolve().parents[1] / "gui.py"


def _project_toolbar_spec_from_source():
    tree = ast.parse(GUI_PATH.read_text(encoding="utf-8"))
    func = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_project_toolbar_presentation"
        ),
        None,
    )
    assert func is not None, "_project_toolbar_presentation must exist"
    returns = [node for node in ast.walk(func) if isinstance(node, ast.Return)]
    assert len(returns) == 1
    return ast.literal_eval(returns[0].value)


def test_project_toolbar_uses_engineering_action_hierarchy():
    spec = _project_toolbar_spec_from_source()

    assert spec["actions"] == (
        ("open", "開啟專案", "secondary"),
        ("save", "儲存專案", "primary"),
        ("save_as", "另存新檔", "secondary"),
    )
    assert spec["primary_action"] == "save"


def test_project_toolbar_is_compact_and_not_marketing_copy():
    spec = _project_toolbar_spec_from_source()

    assert spec["toolbar_padx"] <= 12
    assert spec["toolbar_pady"] <= 6
    assert spec["button_padx"] <= 9
    assert spec["button_pady"] <= 3
    assert spec["title"] == "WHD｜箱體板金工程工作台"
    assert spec["subtitle"] == "專案・板件・圖面・製造輸出"
    assert "支援" not in spec["subtitle"]
    assert "實時" not in spec["subtitle"]
