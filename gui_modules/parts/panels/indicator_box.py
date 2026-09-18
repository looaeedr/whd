"""Indicator-box/indicator-door input configuration boundary; drawing remains T6."""

import tkinter as tk
from tkinter import ttk

def collect_indicator_box_input(payload):
    """Copy existing indicator input values without deriving drawing or geometry."""
    return dict(payload or {})

def setup_tab_indicator_box_ui(host):
    # 頂部控制列
    top_ctrl = tk.Frame(host.tab_indicator_box, bg=host.COLOR_BG)
    top_ctrl.pack(fill=tk.X, padx=10, pady=5)

    host.chk_indicator_box_enabled = tk.Checkbutton(
        top_ctrl, text="門板預留指示燈盒開孔", variable=host.is_indicator_box_var,
        bg=host.COLOR_BG, fg=host.COLOR_TEXT, selectcolor=host.COLOR_PANEL,
        activebackground=host.COLOR_BG, activeforeground=host.COLOR_ACCENT,
        font=('Microsoft JhengHei', 9, 'bold'), cursor="hand2",
        command=host.on_indicator_box_toggle,
    )
    host.chk_indicator_box_enabled.pack(side=tk.LEFT, padx=(5, 14))

    # 層數選擇
    lbl_grid = tk.Label(top_ctrl, text="指示燈層數 (3個為一層) :", bg=host.COLOR_BG, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 10, 'bold'))
    lbl_grid.pack(side=tk.LEFT, padx=5)

    host.cb_ib_l = ttk.Combobox(top_ctrl, textvariable=host.indicator_l_var, values=["1", "2", "3", "4", "5", "6"], width=6, state="readonly", style='TCombobox')
    host.cb_ib_l.pack(side=tk.LEFT, padx=2)
    host.cb_ib_l.bind("<<ComboboxSelected>>", lambda e: host.on_layers_count_changed())

    # 說明標籤
    lbl_formula = ttk.Label(top_ctrl, text="公式：W=171+90*(g_max-1)+135 (單組W=326) / H=280*(L-1)+445 | 線槽跨距 100", style='TLabel')
    lbl_formula.pack(side=tk.RIGHT, padx=5)

    # 每層組數的配置區域 (動態 Frame)
    host.layers_config_frame = tk.Frame(host.tab_indicator_box, bg=host.COLOR_PANEL)
    host.layers_config_frame.pack(fill=tk.X, padx=10, pady=2)

    # 畫布 Frame
    canvas_frame = tk.Frame(host.tab_indicator_box, bg=host.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    # 畫布
    host.canvas_indicator_box = tk.Canvas(canvas_frame, bg=host.COLOR_CANVAS_BG, highlightthickness=0)
    host.canvas_indicator_box.pack(fill=tk.BOTH, expand=True)
    host.canvas_indicator_box.bind("<Configure>", host._route_indicator_canvas_configure)
    host._attach_part_hole_entrypoint(host.canvas_indicator_box, "indicator_box", allow_double=True)

    # 初始化動態組數選單
    host.rebuild_layers_config_ui()

def rebuild_layers_config_ui(host):
    # 清空先前的元件
    for widget in host.layers_config_frame.winfo_children():
        widget.destroy()

    try:
        layers = int(host.indicator_l_var.get())
    except ValueError:
        layers = 3

    # 逐層建立橫向的組數選擇選單
    for ly in range(layers):
        ly_frame = tk.Frame(host.layers_config_frame, bg=host.COLOR_PANEL)
        ly_frame.pack(side=tk.LEFT, padx=15, pady=4)

        label_text = f"第 {ly+1} 層組數:"
        if ly == 0:
            label_text = "第 1 層 (底) 組數:"
        elif ly == layers - 1 and layers > 1:
            label_text = f"第 {ly+1} 層 (頂) 組數:"

        tk.Label(ly_frame, text=label_text, bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')).pack(side=tk.LEFT, padx=2)

        cb = ttk.Combobox(ly_frame, textvariable=host.indicator_layer_g_vars[ly], values=["1", "2", "3", "4", "5", "6", "7", "8"], width=4, state="readonly", style='TCombobox')
        cb.pack(side=tk.LEFT, padx=2)
        cb.bind("<<ComboboxSelected>>", lambda e: host._request_phase6_update("geometry"))

def _indicator_small_door_size_chain_label(host):
    gap_text = host._indicator_small_door_gap_text()
    return (
        "指示燈小門展開圖預覽 | 尺寸連動：盒子內部淨開口 "
        f"→ 四邊各留 {gap_text} mm → 小門成品 → 小門展開"
    )

def setup_tab_indicator_door_ui(host):
    # 頂部控制列
    top_ctrl = tk.Frame(host.tab_indicator_door, bg=host.COLOR_BG)
    top_ctrl.pack(fill=tk.X, padx=10, pady=5)

    # 說明標籤
    lbl_formula = ttk.Label(
        top_ctrl,
        text=host._indicator_small_door_size_chain_label(),
        style='TLabel'
    )
    lbl_formula.pack(side=tk.LEFT, padx=5)

    # 畫布 Frame
    canvas_frame = tk.Frame(host.tab_indicator_door, bg=host.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    # 畫布
    host.canvas_indicator_door = tk.Canvas(canvas_frame, bg=host.COLOR_CANVAS_BG, highlightthickness=0)
    host.canvas_indicator_door.pack(fill=tk.BOTH, expand=True)
    host.canvas_indicator_door.bind("<Configure>", host._route_indicator_canvas_configure)
    host._attach_part_hole_entrypoint(host.canvas_indicator_door, "indicator_door", allow_double=True)
