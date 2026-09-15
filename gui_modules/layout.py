"""Stateless GUI layout and presentation contracts."""


def _project_toolbar_presentation():
    """Pure presentation contract for the compact engineering workbench header."""
    return {
        "actions": (
            ("open", "開啟專案", "secondary"),
            ("save", "儲存專案", "primary"),
            ("save_as", "另存新檔", "secondary"),
        ),
        "primary_action": "save",
        "toolbar_padx": 10,
        "toolbar_pady": 4,
        "button_padx": 8,
        "button_pady": 2,
        "title": "WHD｜箱體板金工程工作台",
        "subtitle": "專案・板件・圖面・製造輸出",
    }
