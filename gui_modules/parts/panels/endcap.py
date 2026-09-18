"""Endcap input-panel presentation and thin routing only.

No baseline, manufacturing, geometry, DXF, or committed-state authority lives here.
"""

import tkinter as tk
from tkinter import ttk


def setup_tab_endcap_ui(self, tab_frame, key):
    """建立封頭或封尾分頁 UI，key='head' 或 'tail'"""
    label_map = {'head': '封頭', 'tail': '封尾'}
    # 頂部控制列
    top_ctrl = tk.Frame(tab_frame, bg=self.COLOR_BG)
    top_ctrl.pack(fill=tk.X, padx=10, pady=5)

    tk.Label(top_ctrl, text=f"{label_map[key]} — 邊框寬度 (FW) :",
             bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
             font=('Microsoft JhengHei', 9)).pack(side=tk.LEFT, padx=5)

    follow_var = self.fw_head_follow_var if key == 'head' else self.fw_tail_follow_var
    ttk.Checkbutton(
        top_ctrl, text="跟隨箱身 FW", variable=follow_var, state="disabled",
    ).pack(side=tk.LEFT, padx=(0, 5))
    cb_var = self.fw_head_var if key == 'head' else self.fw_tail_var
    cb = ttk.Combobox(top_ctrl, textvariable=cb_var,
                      values=["20", "25", "30", "35"],
                      width=8, state="normal", style='TCombobox')
    cb.pack(side=tk.LEFT, padx=5)
    cb.bind("<<ComboboxSelected>>", lambda e, k=key: self.on_fw_selected(k))
    cb.bind("<Return>", lambda e, k=key: self.on_fw_selected(k))
    cb.bind("<FocusOut>", lambda e, k=key: self.on_fw_selected(k))
    if key == 'head':
        self.cb_fw_head = cb
    else:
        self.cb_fw_tail = cb
    self._sync_endcap_fw_controls()

    # 板厚
    tk.Label(top_ctrl, text="板厚 (T) :",
             bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
             font=('Microsoft JhengHei', 9)).pack(side=tk.LEFT, padx=(15, 5))

    entry_t = ttk.Entry(top_ctrl, textvariable=self.t_var, width=6, justify=tk.CENTER)
    entry_t.pack(side=tk.LEFT, padx=5)

    # 畫布
    canvas_frame = tk.Frame(tab_frame, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    canvas = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.bind("<Configure>", lambda e: self.draw_preview())

    # 儲存畫布參照
    if key == 'head':
        self.canvas_head = canvas
    else:
        self.canvas_tail = canvas

    # 雙擊畫布開啟開孔編輯器
    canvas.bind("<Double-Button-1>", lambda e, k=key: self.open_hole_editor(k))

    # 雙擊提示標籤
    hint_lbl = tk.Label(canvas_frame,
        text="雙擊畫布開啟統一開孔編輯器",
        bg=self.COLOR_CANVAS_BG, fg="#3a3a48",
        font=('Microsoft JhengHei', 8))
    hint_lbl.place(relx=1.0, rely=1.0, anchor=tk.SE, x=-5, y=-5)
