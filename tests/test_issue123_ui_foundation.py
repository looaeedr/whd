# -*- coding: utf-8 -*-
"""Issue #123 — engineering-workbench shell/toolbar presentation contract."""

from gui import _project_toolbar_presentation


def test_project_toolbar_uses_engineering_action_hierarchy():
    spec = _project_toolbar_presentation()

    assert spec["actions"] == (
        ("open", "開啟專案", "secondary"),
        ("save", "儲存專案", "primary"),
        ("save_as", "另存新檔", "secondary"),
    )
    assert spec["primary_action"] == "save"


def test_project_toolbar_is_compact_and_not_marketing_copy():
    spec = _project_toolbar_presentation()

    assert spec["toolbar_padx"] <= 12
    assert spec["toolbar_pady"] <= 6
    assert spec["button_padx"] <= 9
    assert spec["button_pady"] <= 3
    assert spec["title"] == "WHD｜箱體板金工程工作台"
    assert spec["subtitle"] == "專案・板件・圖面・製造輸出"
    assert "支援" not in spec["subtitle"]
    assert "實時" not in spec["subtitle"]
