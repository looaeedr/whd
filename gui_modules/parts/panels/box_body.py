"""Box-body panel presentation and thin routing only.

Physical-piece identity/navigation remains owned by the accepted T3 subtabs and
workspace controller state. Manufacturing/state authority remains outside this module.
"""

import tkinter as tk
from tkinter import ttk

from phase6_endcap_semantics import ASSEMBLY_TYPE_LABELS
from gui_modules.parts.subtabs import build_box_body_piece_selector


def setup_tab_z_ui(self):
    # 頂部控制列
    top_ctrl = tk.Frame(self.tab_z, bg=self.COLOR_BG)
    top_ctrl.pack(fill=tk.X, padx=10, pady=5)

    lbl_fw = ttk.Label(top_ctrl, text="邊框寬度 (FW) :", style='TLabel')
    lbl_fw.pack(side=tk.LEFT, padx=5)

    # 箱身 FW 選擇框
    self.cb_fw_z = ttk.Combobox(top_ctrl, textvariable=self.fw_z_var, values=["20", "25", "30", "35"],
                                width=8, state="readonly", style='TCombobox')
    self.cb_fw_z.pack(side=tk.LEFT, padx=5)
    self.cb_fw_z.bind("<<ComboboxSelected>>", lambda e: self.on_fw_selected("z"))

    ttk.Label(top_ctrl, text="組合方式 :", style='TLabel').pack(side=tk.LEFT, padx=(15, 5))
    self.cb_box_assembly = ttk.Combobox(
        top_ctrl, textvariable=self.box_assembly_type_var,
        values=tuple(ASSEMBLY_TYPE_LABELS.values()), width=10, state="readonly", style='TCombobox'
    )
    self.cb_box_assembly.pack(side=tk.LEFT, padx=5)
    self.cb_box_assembly.bind("<<ComboboxSelected>>", self.on_box_assembly_changed)

    # 板厚
    lbl_t = ttk.Label(top_ctrl, text="板厚 (T) :", style='TLabel')
    lbl_t.pack(side=tk.LEFT, padx=(15, 5))

    entry_t_z = ttk.Entry(top_ctrl, textvariable=self.t_var, width=6, justify=tk.CENTER)
    entry_t_z.pack(side=tk.LEFT, padx=5)

    info_lbl = tk.Label(top_ctrl, text="(與封頭尾連動)", bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9))
    info_lbl.pack(side=tk.LEFT, padx=5)

    # 多件式箱身只占一個頂層「箱身」，物理子板件用第二層標籤切換。
    self.box_body_piece_tabs = build_box_body_piece_selector(self, self.tab_z)

    # 畫布 Frame
    canvas_frame = tk.Frame(self.tab_z, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    self.box_body_canvas_frame = canvas_frame
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    # 箱身畫布
    self.canvas_z = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
    self.canvas_z.pack(fill=tk.BOTH, expand=True)
    self.canvas_z.bind("<Configure>", lambda e: self.draw_preview())
    self.canvas_z.bind("<Button-1>", self.on_box_body_canvas_press)
    self.canvas_z.bind("<Double-Button-1>", self.on_box_body_piece_double_click)
