from __future__ import annotations

from gui_modules.layout import _project_toolbar_presentation


def test_project_toolbar_preserves_operator_action_semantics():
    presentation = _project_toolbar_presentation()

    assert presentation["actions"] == (
        ("open", "開啟專案", "secondary"),
        ("save", "儲存專案", "primary"),
        ("save_as", "另存新檔", "secondary"),
    )
    assert presentation["primary_action"] == "save"


def test_project_toolbar_preserves_operator_workbench_copy():
    presentation = _project_toolbar_presentation()

    assert presentation["title"] == "WHD｜箱體板金工程工作台"
    assert presentation["subtitle"] == "專案・板件・圖面・製造輸出"
