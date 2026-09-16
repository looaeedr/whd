"""Root layout composition for the WHD engineering workbench."""

import tkinter as tk

from .left_panel import build_left_panel
from .scrolling import build_scroll_shell
from .toolbar import build_project_toolbar
from .workspace import build_workspace


def build_main_shell(host):
    # 主內容區域 (左右分欄)
    main_paned = tk.PanedWindow(host.root, orient=tk.HORIZONTAL, bg=host.COLOR_BG, bd=0, sashwidth=4)
    main_paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
    host.main_paned = main_paned

    # ==========================================
    # 左側：控制面板
    # ==========================================
    left_container = tk.Frame(main_paned, bg=host.COLOR_BG)
    main_paned.add(left_container, width=320)
    host.left_container = left_container
    return main_paned, left_container


def build_main_layout(host):
    build_project_toolbar(host)
    main_paned, left_container = build_main_shell(host)
    ctrl_pad_frame = build_scroll_shell(host, left_container)
    build_left_panel(host, ctrl_pad_frame)
    build_workspace(host, main_paned)
