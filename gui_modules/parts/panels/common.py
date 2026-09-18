"""Truly shared, stateless physical-part panel presentation helpers."""

import tkinter as tk
from tkinter import ttk


def logical_part_present(existing_parts, logical_key):
    """Project authoritative physical stable IDs into logical panel groups."""
    existing = set(str(key) for key in (existing_parts or ()))
    key = str(logical_key or "")
    if key == "door":
        return "door" in existing or any(item.startswith("door_c") for item in existing)
    if key == "base_plate":
        return "base_plate" in existing or any(item.startswith("base_plate_c") for item in existing)
    if key == "box_body":
        return "box_body" in existing or any(item.startswith("box_body:") for item in existing)
    return key in existing

def create_input_row(host, parent, label_text, var):
        row = tk.Frame(parent, bg=host.COLOR_PANEL)
        row.pack(fill=tk.X, pady=4)

        lbl = ttk.Label(row, text=label_text, width=12, anchor=tk.W)
        lbl.pack(side=tk.LEFT)

        entry = tk.Entry(row, textvariable=var, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
                         insertbackground=host.COLOR_TEXT, bd=1, relief=tk.SOLID,
                         font=('Microsoft JhengHei', 10), justify=tk.CENTER)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

def create_result_row(host, parent, label_text, var):
        row = tk.Frame(parent, bg=host.COLOR_INPUT_BG)
        row.pack(fill=tk.X, pady=6, padx=10)

        lbl = tk.Label(row, text=label_text, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT_MUTED,
                       font=('Microsoft JhengHei', 9), anchor=tk.W)
        lbl.pack(side=tk.LEFT)

        val = tk.Label(row, textvariable=var, bg=host.COLOR_INPUT_BG, fg="#30d158",
                       font=('Consolas', 11, 'bold'), anchor=tk.E)
        val.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        return row

def create_separator(host, parent):
        sep = tk.Frame(parent, height=1, bg="#2a2a30")
        sep.pack(fill=tk.X, pady=15)

def _make_grid_input(host, parent, row, col, label_text, var):
        f = tk.Frame(parent, bg=host.COLOR_PANEL)
        f.grid(row=row, column=col, padx=4, pady=2)
        lbl = tk.Label(f, text=label_text, bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 8))
        lbl.pack(side=tk.TOP)
        entry = tk.Entry(
            f, textvariable=var, width=5,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT, insertbackground=host.COLOR_TEXT,
            bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
        )
        entry.pack(side=tk.TOP)
        return entry

def create_advanced_inputs(host, parent):
        # 箱身參數
        lbl_z = tk.Label(parent, text="箱身折彎與補償:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_z.pack(anchor=tk.W, pady=(8, 2))

        row_z1 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_z1.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_z1, "zl1", host.zl1_var)
        host.create_sub_input(row_z1, "zl2", host.zl2_var)
        # 佔位用以維持排版對齊
        tk.Frame(row_z1, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        row_z2 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_z2.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_z2, "zr1", host.zr1_var)
        host.create_sub_input(row_z2, "zr2", host.zr2_var)
        # 佔位用以維持排版對齊
        tk.Frame(row_z2, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        # 封頭尾參數
        lbl_y = tk.Label(parent, text="封頭尾折彎:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_y.pack(anchor=tk.W, pady=(8, 2))

        row_y1 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_y1.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_y1, "yl1", host.yl1_var)
        host.create_sub_input(row_y1, "yr1", host.yr1_var)
        # 佔位用
        tk.Frame(row_y1, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        row_y2 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_y2.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_y2, "y上1", host.ytop1_var)
        host.create_sub_input(row_y2, "y下1", host.ybottom1_var)
        # 佔位用
        tk.Frame(row_y2, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        # 門參數
        lbl_door = tk.Label(parent, text="門間隙與折邊:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_door.pack(anchor=tk.W, pady=(8, 2))

        row_door1 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_door1.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_door1, "間隙W", host.door_gap_w_var)
        host.create_sub_input(row_door1, "間隙H", host.door_gap_h_var)
        # 佔位用
        tk.Frame(row_door1, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        row_door2 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_door2.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_door2, "左折", host.door_fold_l_var)
        host.create_sub_input(row_door2, "右折", host.door_fold_r_var)
        # 佔位用
        tk.Frame(row_door2, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        row_door3 = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_door3.pack(fill=tk.X, pady=2)
        host.create_sub_input(row_door3, "上折", host.door_fold_t_var)
        host.create_sub_input(row_door3, "下折", host.door_fold_b_var)
        # 佔位用
        tk.Frame(row_door3, bg=host.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)

        # 底板參數
        lbl_base = tk.Label(parent, text="底板收縮與折邊:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_base.pack(anchor=tk.W, pady=(8, 2))

        # 1. 四面同與折邊
        row_same = tk.Frame(parent, bg=host.COLOR_PANEL)
        row_same.pack(fill=tk.X, pady=2)

        # 四面同核取方塊
        host.chk_same = tk.Checkbutton(
            row_same, text="四面同", variable=host.base_plate_all_same_var,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, selectcolor=host.COLOR_INPUT_BG,
            activebackground=host.COLOR_PANEL, activeforeground=host.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9), cursor="hand2",
            command=host.on_base_plate_same_toggle
        )
        host.chk_same.pack(side=tk.LEFT, padx=2)

        # 四面同的值輸入框
        host.entry_shrink_same = tk.Entry(
            row_same, textvariable=host.base_plate_shrink_same_var, width=5,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT, insertbackground=host.COLOR_TEXT,
            bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
        )
        host.entry_shrink_same.pack(side=tk.LEFT, padx=2)

        # 折邊輸入框
        lbl_bend = tk.Label(row_same, text="  折邊:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 9))
        lbl_bend.pack(side=tk.LEFT, padx=2)
        host.entry_bend = tk.Entry(
            row_same, textvariable=host.base_plate_bend_var, width=5,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT, insertbackground=host.COLOR_TEXT,
            bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
        )
        host.entry_bend.pack(side=tk.LEFT, padx=2)

        # 2. 上下左右十字形收縮輸入框
        grid_frame = tk.Frame(parent, bg=host.COLOR_PANEL)
        grid_frame.pack(pady=4)

        # Row 0: 上
        e_top = _make_grid_input(host, grid_frame, 0, 1, "上縮", host.base_plate_shrink_top_var)
        # Row 1: 左, 右
        e_left = _make_grid_input(host, grid_frame, 1, 0, "左縮", host.base_plate_shrink_left_var)

        lbl_center = tk.Label(grid_frame, text="底板", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_center.grid(row=1, column=1, padx=6)

        e_right = _make_grid_input(host, grid_frame, 1, 2, "右縮", host.base_plate_shrink_right_var)
        # Row 2: 下
        e_bottom = _make_grid_input(host, grid_frame, 2, 1, "下縮", host.base_plate_shrink_bottom_var)

        host.base_plate_entries.extend([e_top, e_bottom, e_left, e_right])

        # 輸出選項區塊
        sep = tk.Frame(parent, height=1, bg="#2a2a30")
        sep.pack(fill=tk.X, pady=(12, 6))

        lbl_out = tk.Label(parent, text="輸出選項:", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
                           font=('Microsoft JhengHei', 9, 'bold'))
        lbl_out.pack(anchor=tk.W, pady=(0, 4))

        stock_row = tk.Frame(parent, bg=host.COLOR_PANEL)
        stock_row.pack(fill=tk.X, pady=2)

        # STOCK 勾選框
        host.chk_stock = tk.Checkbutton(
            stock_row,
            text="輸出 STOCK 母材外框 (青色)",
            variable=host.draw_stock_var,
            bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG,
            activebackground=host.COLOR_PANEL,
            activeforeground=host.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9),
            cursor="hand2",
            command=host.draw_preview
        )
        host.chk_stock.pack(side=tk.LEFT, padx=2)

def create_sub_input(host, parent, label_text, var):
        frame = tk.Frame(parent, bg=host.COLOR_PANEL)
        frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        lbl = tk.Label(frame, text=label_text, bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 8))
        lbl.pack(side=tk.TOP, anchor=tk.W)

        entry = tk.Entry(frame, textvariable=var, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
                         insertbackground=host.COLOR_TEXT, bd=1, relief=tk.SOLID,
                         font=('Consolas', 9), justify=tk.CENTER, width=6)
        entry.pack(side=tk.BOTTOM, fill=tk.X, ipady=1)

def toggle_advanced_panel(host):
        if host.adv_frame.winfo_manager():
            # 已展開，進行收合
            host.adv_frame.pack_forget()
            host.adv_btn.configure(text="▶ 進階參數設定 (板厚/折彎)")
        else:
            # 已收合，進行展開
            host.adv_frame.pack(fill=tk.X, before=host.adv_btn.master.children[list(host.adv_btn.master.children.keys())[-3]]) # 插在計算結果前
            host.adv_frame.pack(fill=tk.X, pady=(5, 10))
            host.adv_btn.configure(text="▼ 收起進階參數設定")

def _attach_part_hole_entrypoint(host, canvas, part_key, *, allow_double=True):
    """All supported panels use one memorable entry point: double-click opens holes."""
    canvas.unbind("<Button-3>")
    if allow_double:
        canvas.bind("<Double-Button-1>", lambda e, k=part_key: host.open_part_hole_editor(k))
