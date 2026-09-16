#!/usr/bin/env python3
"""Temporary deterministic #290 T2 layout extractor.

This work-branch-only tool moves exact presentation regions out of gui.py.
It is intentionally removed before #290 acceptance.
"""
from __future__ import annotations

import ast
import io
import textwrap
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OLD_LAYOUT = ROOT / "gui_modules" / "layout.py"
LAYOUT_DIR = ROOT / "gui_modules" / "layout"


def _method_map(text: str):
    tree = ast.parse(text, filename=str(GUI))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, ast.FunctionDef)
    }


def _method_body(text: str, node: ast.FunctionDef) -> str:
    lines = text.splitlines(keepends=True)
    return textwrap.dedent("".join(lines[node.lineno:node.end_lineno]))


def _function_source(text: str, name: str) -> str:
    tree = ast.parse(text)
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    lines = text.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1:node.end_lineno]).rstrip() + "\n"


def _rename_self(code: str) -> str:
    out = []
    reader = io.StringIO(code).readline
    for tok in tokenize.generate_tokens(reader):
        if tok.type == tokenize.NAME and tok.string == "self":
            tok = tokenize.TokenInfo(tok.type, "host", tok.start, tok.end, tok.line)
        out.append(tok)
    return tokenize.untokenize(out)


def _find_line(lines: list[str], marker: str) -> int:
    matches = [i for i, line in enumerate(lines) if marker in line]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one marker {marker!r}, got {len(matches)}")
    return matches[0]


def _wrap(name: str, args: str, body: str, *, tail: str = "") -> str:
    renamed = _rename_self(body).rstrip() + "\n"
    result = f"def {name}({args}):\n" + textwrap.indent(renamed, "    ")
    if tail:
        result += textwrap.indent(tail.rstrip() + "\n", "    ")
    return result


def _replace_methods(text: str, methods: dict[str, ast.FunctionDef]) -> str:
    lines = text.splitlines(keepends=True)
    replacements = {
        "setup_styles": "    def setup_styles(self):\n        _configure_layout_styles(self)\n",
        "create_widgets": "    def create_widgets(self):\n        _build_main_layout(self)\n",
    }
    for name in sorted(replacements, key=lambda n: methods[n].lineno, reverse=True):
        node = methods[name]
        lines[node.lineno - 1:node.end_lineno] = [replacements[name]]
    text = "".join(lines)
    old = "from gui_modules.layout import _project_toolbar_presentation\n"
    new = (
        "from gui_modules.layout import (\n"
        "    _project_toolbar_presentation,\n"
        "    configure_styles as _configure_layout_styles,\n"
        "    build_main_layout as _build_main_layout,\n"
        ")\n"
    )
    if old not in text:
        raise RuntimeError("expected legacy gui_modules.layout import not found")
    return text.replace(old, new, 1)


def apply() -> None:
    if LAYOUT_DIR.is_dir() and not OLD_LAYOUT.exists():
        print("ISSUE290_T2_ALREADY_EXTRACTED")
        return
    if not OLD_LAYOUT.exists():
        raise RuntimeError("expected gui_modules/layout.py before first extraction")

    gui_text = GUI.read_text(encoding="utf-8")
    methods = _method_map(gui_text)
    setup_body = _method_body(gui_text, methods["setup_styles"])
    create_body = _method_body(gui_text, methods["create_widgets"])
    body_lines = create_body.splitlines(keepends=True)

    i_main = _find_line(body_lines, "# 主內容區域 (左右分欄)")
    i_ctrl = _find_line(body_lines, "# 控制面板卡片")
    i_sec0 = _find_line(body_lines, "# 區段 0：基準型號")
    i_right = _find_line(body_lines, "# 右側：舊 2D 入口已收斂")
    if not (0 < i_main < i_ctrl < i_sec0 < i_right < len(body_lines)):
        raise RuntimeError("unexpected #290 create_widgets region ordering")

    toolbar_body = "".join(body_lines[:i_main])
    main_body = "".join(body_lines[i_main:i_ctrl])
    scrolling_body = "".join(body_lines[i_ctrl:i_sec0])
    left_body = "".join(body_lines[i_sec0:i_right])
    workspace_body = "".join(body_lines[i_right:])

    old_layout_text = OLD_LAYOUT.read_text(encoding="utf-8")
    toolbar_contract = _function_source(old_layout_text, "_project_toolbar_presentation")

    LAYOUT_DIR.mkdir(parents=True, exist_ok=False)

    (LAYOUT_DIR / "styles.py").write_text(
        '"""T2-owned ttk/theme presentation setup."""\n\n'
        "from tkinter import ttk\n\n"
        "from whd_theme import apply_ttk_dark_theme\n\n\n"
        + _wrap("configure_styles", "host", setup_body),
        encoding="utf-8",
    )

    (LAYOUT_DIR / "toolbar.py").write_text(
        '"""Project toolbar presentation and widget construction."""\n\n'
        "import tkinter as tk\n"
        "from tkinter import ttk\n\n"
        "from phase6_settings_center import UI_TEXT_SIZE_LABELS\n\n\n"
        + toolbar_contract
        + "\n"
        + _wrap("build_project_toolbar", "host", toolbar_body),
        encoding="utf-8",
    )

    (LAYOUT_DIR / "scrolling.py").write_text(
        '"""Scrollable left-panel presentation shell."""\n\n'
        "import tkinter as tk\n\n\n"
        + _wrap(
            "build_scroll_shell",
            "host, left_container",
            scrolling_body,
            tail="return ctrl_pad_frame",
        ),
        encoding="utf-8",
    )

    (LAYOUT_DIR / "left_panel.py").write_text(
        '"""Static left control-panel presentation wiring."""\n\n'
        "import tkinter as tk\n"
        "from tkinter import ttk\n\n"
        "from ae_engine.corner_type_ui import CUSTOM_MODEL_NAME\n\n\n"
        + _wrap("build_left_panel", "host, ctrl_pad_frame", left_body),
        encoding="utf-8",
    )

    (LAYOUT_DIR / "workspace.py").write_text(
        '"""Right workspace notice and compatibility-only presentation hosts."""\n\n'
        "import tkinter as tk\n\n\n"
        + _wrap("build_workspace", "host, main_paned", workspace_body),
        encoding="utf-8",
    )

    main_shell = _wrap(
        "build_main_shell",
        "host",
        main_body,
        tail="return main_paned, left_container",
    )
    (LAYOUT_DIR / "main_window.py").write_text(
        '"""Root layout composition for the WHD engineering workbench."""\n\n'
        "import tkinter as tk\n\n"
        "from .left_panel import build_left_panel\n"
        "from .scrolling import build_scroll_shell\n"
        "from .toolbar import build_project_toolbar\n"
        "from .workspace import build_workspace\n\n\n"
        + main_shell
        + "\n\n"
        + "def build_main_layout(host):\n"
        + "    build_project_toolbar(host)\n"
        + "    main_paned, left_container = build_main_shell(host)\n"
        + "    ctrl_pad_frame = build_scroll_shell(host, left_container)\n"
        + "    build_left_panel(host, ctrl_pad_frame)\n"
        + "    build_workspace(host, main_paned)\n",
        encoding="utf-8",
    )

    (LAYOUT_DIR / "__init__.py").write_text(
        '"""Focused T2 layout package; no committed domain-state ownership."""\n\n'
        "from .main_window import build_main_layout\n"
        "from .styles import configure_styles\n"
        "from .toolbar import _project_toolbar_presentation\n\n"
        "__all__ = [\n"
        "    \"_project_toolbar_presentation\",\n"
        "    \"build_main_layout\",\n"
        "    \"configure_styles\",\n"
        "]\n",
        encoding="utf-8",
    )

    GUI.write_text(_replace_methods(gui_text, methods), encoding="utf-8")
    OLD_LAYOUT.unlink()

    # Fail closed on syntax/import-direction or structural drift before commit.
    generated = sorted(LAYOUT_DIR.glob("*.py"))
    for path in [GUI, *generated]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    gui_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    if gui_loc > 8650:
        raise RuntimeError(f"T2 structural gate failed after extraction: gui.py={gui_loc}")
    for path in generated:
        loc = len(path.read_text(encoding="utf-8").splitlines())
        if loc > 1500:
            raise RuntimeError(f"layout module too large: {path}={loc}")
    print(f"ISSUE290_T2_EXTRACTED gui_loc={gui_loc}")


if __name__ == "__main__":
    apply()
