from pathlib import Path

path = Path('gui.py')
text = path.read_text(encoding='utf-8')

old = '''def _project_toolbar_presentation():
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


'''

anchor = '''from gui_modules.drawing import (
    _corner_preview_canvas_point,
    _corner_preview_flip_y_for_target,
    render_drawing_scene,
)


'''

if text.count(old) != 1:
    raise SystemExit(f'expected exactly one toolbar body, got {text.count(old)}')
if text.count(anchor) != 1:
    raise SystemExit(f'expected exactly one drawing import anchor, got {text.count(anchor)}')

replacement = anchor + 'from gui_modules.layout import _project_toolbar_presentation\n\n\n'
path.write_text(text.replace(old, '', 1).replace(anchor, replacement, 1), encoding='utf-8')
