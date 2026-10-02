"""Project toolbar presentation and widget construction."""

import tkinter as tk
from tkinter import ttk

from phase6_settings_center import UI_TEXT_SIZE_LABELS


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

def build_project_toolbar(host):
    # Compact CAD-style workbench header. Project callbacks and text-scale
    # authority stay unchanged; only presentation hierarchy/density changes.
    toolbar_spec = _project_toolbar_presentation()
    host.project_toolbar_shell = tk.Frame(
        host.root, bg=host.COLOR_PANEL, bd=1, relief=tk.SOLID
    )
    host.project_toolbar_shell.pack(
        fill=tk.X,
        padx=toolbar_spec["toolbar_padx"],
        pady=(toolbar_spec["toolbar_pady"], 2),
    )

    host.project_toolbar = tk.Frame(host.project_toolbar_shell, bg=host.COLOR_PANEL)
    host.project_toolbar.pack(side=tk.LEFT, padx=(6, 10), pady=3)

    secondary_button_opts = dict(
        font=('Microsoft JhengHei', 9),
        bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
        activebackground=host.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
        bd=1, relief=tk.SOLID, cursor="hand2",
        padx=toolbar_spec["button_padx"], pady=toolbar_spec["button_pady"],
    )
    primary_button_opts = dict(
        font=('Microsoft JhengHei', 9, 'bold'),
        bg=host.COLOR_ACCENT, fg="#ffffff",
        activebackground=host.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
        bd=1, relief=tk.SOLID, cursor="hand2",
        padx=toolbar_spec["button_padx"], pady=toolbar_spec["button_pady"],
    )

    host.project_open_button = tk.Button(
        host.project_toolbar, text="開啟專案", command=host.open_phase6_project,
        **secondary_button_opts
    )
    host.project_open_button.pack(side=tk.LEFT, padx=(0, 4))
    host.project_save_button = tk.Button(
        host.project_toolbar, text="儲存專案", command=host.save_phase6_project,
        **primary_button_opts
    )
    host.project_save_button.pack(side=tk.LEFT, padx=(0, 4))
    host.project_save_as_button = tk.Button(
        host.project_toolbar, text="另存新檔", command=host.save_phase6_project_as,
        **secondary_button_opts
    )
    host.project_save_as_button.pack(side=tk.LEFT)

    identity_frame = tk.Frame(host.project_toolbar_shell, bg=host.COLOR_PANEL)
    identity_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 8), pady=3)
    tk.Label(
        identity_frame, text=toolbar_spec["title"],
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
        font=('Microsoft JhengHei', 10, 'bold'), anchor=tk.W,
    ).pack(anchor=tk.W)
    tk.Label(
        identity_frame, text=toolbar_spec["subtitle"],
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
        font=('Microsoft JhengHei', 8), anchor=tk.W,
    ).pack(anchor=tk.W)

    text_size_frame = tk.Frame(host.project_toolbar_shell, bg=host.COLOR_PANEL)
    text_size_frame.pack(side=tk.RIGHT, padx=(8, 8), pady=3)
    tk.Label(
        text_size_frame, text="文字大小", bg=host.COLOR_PANEL,
        fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9)
    ).pack(side=tk.LEFT, padx=(0, 4))
    host.ui_text_size_combo = ttk.Combobox(
        text_size_frame, textvariable=host.ui_text_size_var,
        values=tuple(UI_TEXT_SIZE_LABELS.values()), state="readonly", width=4,
    )
    host.ui_text_size_combo.pack(side=tk.LEFT)
    host.ui_text_size_combo.bind("<<ComboboxSelected>>", host.on_ui_text_size_changed)
