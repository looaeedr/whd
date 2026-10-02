"""Door layout/input panel presentation and routing boundary.

Door-layout committed structures remain owned by the existing authoritative
host/controller seam during T4.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from whd_theme import configure_tk_menu

def collect_door_input(payload):
    """Copy door presentation/input values without deriving topology or geometry."""
    data = dict(payload or {})
    result = {}
    for key in (
        "door_layout_columns",
        "door_layout_scope",
        "door_handle_edges",
        "model",
    ):
        if key in data:
            result[key] = data[key]
    return result

def _parse_layout_value(var, label):
    try:
        value = float(var.get())
    except ValueError as exc:
        raise ValueError(f"{label}不是有效數字") from exc
    if value <= 0:
        raise ValueError(f"{label}必須大於 0")
    return value

def _reject_door_layout_dimension(host, var, previous_value, message):
    var.set(host._door_layout_number_text(previous_value))
    messagebox.showwarning("多門尺寸錯誤", message)
    host.refresh_door_layout_status()
    try:
        host.draw_preview()
    except Exception:
        pass
    return False

def refresh_door_layout_status(host):
    if not hasattr(host, "door_layout_status_label"):
        return
    if not host.multi_door_enabled_var.get():
        host.door_layout_status_label.config(text="單門模式：沿用左側 W / H", fg=host.COLOR_TEXT_MUTED)
        return
    try:
        width_completion = getattr(host, "_door_layout_width_completion", None)
        if width_completion is not None and not width_completion.valid:
            host.door_layout_status_label.config(
                text=f"配置待修正：寬度超出 {width_completion.excess:g} mm", fg="#ff9f0a"
            )
            return
        for index, column in enumerate(host.door_layout_columns, start=1):
            completion = column.get("height_completion")
            if completion is not None and not completion.valid:
                host.door_layout_status_label.config(
                    text=f"配置待修正：欄 {index} 高度超出 {completion.excess:g} mm", fg="#ff9f0a"
                )
                return
        cells = host.get_door_layout_cells()
        host.door_layout_status_label.config(
            text=f"配置有效：{len(cells)} 片門｜點選格子可選擇門片", fg="#30d158"
        )
    except Exception as exc:
        host.door_layout_status_label.config(text=f"配置待修正：{exc}", fg="#ff9f0a")

def rebuild_door_layout_ui(host):
    if not hasattr(host, "door_layout_columns_frame"):
        return
    for widget in host.door_layout_columns_frame.winfo_children():
        widget.destroy()
    host.door_layout_inner_door_vars = {}
    host.door_layout_inner_door_offset_vars = {}
    host.door_layout_inner_door_offset_entries = {}
    host._ensure_door_layout_default()

    for column_index, column in enumerate(host.door_layout_columns):
        col_frame = tk.Frame(host.door_layout_columns_frame, bg=host.COLOR_PANEL, bd=1, relief=tk.SOLID)
        col_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=3, pady=3)

        width_row = tk.Frame(col_frame, bg=host.COLOR_PANEL)
        width_row.pack(fill=tk.X, padx=4, pady=(4, 2))
        width_caption = f"欄 {column_index+1} 寬" + (" (自動)" if column.get("width_auto") else "")
        tk.Label(
            width_row, text=width_caption, bg=host.COLOR_PANEL,
            fg="#30d158" if column.get("width_auto") else host.COLOR_TEXT,
            font=('Microsoft JhengHei', 8, 'bold')
        ).pack(anchor=tk.CENTER)
        width_entry = tk.Entry(
            width_row, textvariable=column["width_var"], width=8,
            bg=host.COLOR_INPUT_BG, fg="#30d158" if column.get("width_auto") else host.COLOR_TEXT,
            insertbackground=host.COLOR_TEXT, font=('Consolas', 10, 'bold'), justify=tk.CENTER
        )
        width_entry.pack(anchor=tk.CENTER, pady=2)
        width_entry.bind("<FocusOut>", lambda e, c=column_index: host.commit_door_layout_width(c))
        width_entry.bind("<Return>", lambda e, c=column_index: host.commit_door_layout_width(c))

        tk.Label(
            col_frame, text="高度 ↓", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 8)
        ).pack(anchor=tk.CENTER, pady=(2, 0))

        for row_index, (height_var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"])):
            height_row = tk.Frame(col_frame, bg=host.COLOR_PANEL)
            height_row.pack(fill=tk.X, padx=4, pady=1)
            tk.Label(
                height_row, text=f"{row_index+1}", width=2, bg=host.COLOR_PANEL,
                fg="#30d158" if is_auto else host.COLOR_TEXT_MUTED, font=('Consolas', 8, 'bold')
            ).pack(side=tk.LEFT)
            height_entry = tk.Entry(
                height_row, textvariable=height_var, width=7,
                bg=host.COLOR_INPUT_BG, fg="#30d158" if is_auto else host.COLOR_TEXT,
                insertbackground=host.COLOR_TEXT, font=('Consolas', 10), justify=tk.CENTER
            )
            height_entry.pack(side=tk.LEFT, padx=2)
            height_entry.bind(
                "<FocusOut>", lambda e, c=column_index, r=row_index: host.commit_door_layout_height(c, r)
            )
            height_entry.bind(
                "<Return>", lambda e, c=column_index, r=row_index: host.commit_door_layout_height(c, r)
            )
            if is_auto:
                tk.Label(
                    height_row, text="自動", bg=host.COLOR_PANEL, fg="#30d158",
                    font=('Microsoft JhengHei', 7, 'bold')
                ).pack(side=tk.LEFT, padx=(1, 0))
            else:
                tk.Button(
                    height_row, text="−", width=2,
                    command=lambda c=column_index, r=row_index: host.remove_door_layout_height(c, r),
                    bg=host.COLOR_BG, fg="#ff6b6b", bd=1, relief=tk.SOLID,
                    activebackground=host.COLOR_PANEL, activeforeground="#ff6b6b"
                ).pack(side=tk.LEFT, padx=(1, 0))

            if str(host.baseline_var.get() or "").strip() == "受電箱":
                cell_key = f"{column_index}:{row_index}"
                inner_var = tk.BooleanVar(
                    master=host.root,
                    value=host._receiving_inner_door_enabled(cell_key),
                )
                host.door_layout_inner_door_vars[cell_key] = inner_var
                tk.Checkbutton(
                    height_row, text="內門", variable=inner_var,
                    bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, selectcolor=host.COLOR_INPUT_BG,
                    activebackground=host.COLOR_PANEL, activeforeground=host.COLOR_ACCENT,
                    font=('Microsoft JhengHei', 8, 'bold'), cursor="hand2",
                    command=lambda key=cell_key: host._commit_receiving_inner_door_checkbox(key),
                ).pack(side=tk.LEFT, padx=(5, 0))
                offset_var = tk.StringVar(
                    master=host.root,
                    value=host._fold_designer_number_text(host._receiving_inner_door_inward_offset(cell_key)),
                )
                host.door_layout_inner_door_offset_vars[cell_key] = offset_var
                tk.Label(
                    height_row, text="內退", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
                    font=('Microsoft JhengHei', 7, 'bold')
                ).pack(side=tk.LEFT, padx=(3, 1))
                offset_entry = tk.Entry(
                    height_row, textvariable=offset_var, width=5,
                    state=tk.NORMAL if inner_var.get() else tk.DISABLED,
                    bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT, disabledforeground=host.COLOR_TEXT_MUTED,
                    insertbackground=host.COLOR_TEXT, font=('Consolas', 9), justify=tk.CENTER
                )
                offset_entry.pack(side=tk.LEFT, padx=(0, 1))
                offset_entry.bind(
                    "<FocusOut>", lambda e, key=cell_key: host._commit_receiving_inner_door_inward_offset(key)
                )
                offset_entry.bind(
                    "<Return>", lambda e, key=cell_key: host._commit_receiving_inner_door_inward_offset(key)
                )
                host.door_layout_inner_door_offset_entries[cell_key] = offset_entry
                tk.Label(
                    height_row, text="mm", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
                    font=('Consolas', 7)
                ).pack(side=tk.LEFT)

        if not column.get("width_auto"):
            tk.Button(
                col_frame, text="刪除此欄", command=lambda c=column_index: host.remove_door_layout_column(c),
                bg=host.COLOR_BG, fg="#ff6b6b", bd=1, relief=tk.SOLID,
                activebackground=host.COLOR_PANEL, activeforeground="#ff6b6b",
                font=('Microsoft JhengHei', 8, 'bold')
            ).pack(anchor=tk.CENTER, pady=(3, 4))

    host.refresh_door_layout_status()

def setup_tab_door_ui(host):
    # Door 第一頁只保留「啟用多門配置」；其餘編輯都直接在 Canvas / 開孔 editor。
    top_ctrl = tk.Frame(host.tab_door, bg=host.COLOR_BG)
    top_ctrl.pack(fill=tk.X, padx=10, pady=5)
    tk.Checkbutton(
        top_ctrl, text="啟用多門配置", variable=host.multi_door_enabled_var,
        bg=host.COLOR_BG, fg=host.COLOR_TEXT, selectcolor=host.COLOR_PANEL,
        activebackground=host.COLOR_BG, activeforeground=host.COLOR_ACCENT,
        font=('Microsoft JhengHei', 9, 'bold'), cursor="hand2",
        command=host.toggle_multi_door_layout,
    ).pack(side=tk.LEFT, padx=5)
    host.door_layout_status_label = tk.Label(
        top_ctrl, text="", bg=host.COLOR_BG, fg=host.COLOR_TEXT_MUTED,
        font=('Microsoft JhengHei', 8, 'bold')
    )
    # 狀態 label 只留作既有邏輯相容，不 pack、不佔畫面。

    host.door_layout_body = tk.Frame(host.tab_door, bg=host.COLOR_PANEL, bd=1, relief=tk.SOLID)
    host.door_layout_columns_frame = tk.Frame(host.door_layout_body, bg=host.COLOR_PANEL)
    host.door_layout_columns_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
    layout_actions = tk.Frame(host.door_layout_body, bg=host.COLOR_PANEL)
    layout_actions.pack(fill=tk.X, padx=4, pady=(0, 4))
    tk.Label(
        layout_actions,
        text="寬度由左→右；高度由上→下。綠色『自動』格是剩餘尺寸，直接修改它就會固定並自動補下一格。",
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 8)
    ).pack(side=tk.LEFT, padx=8)
    host._ensure_door_layout_default()
    host.rebuild_door_layout_ui()
    # 預設單門模式，不顯示多門明細。
    host.door_layout_body.pack_forget()

    # 門指示燈選項面板 (預設隱藏)
    host.door_indicator_opts_frame = tk.Frame(host.tab_door, bg=host.COLOR_BG)

    door_ind_ctrl = tk.Frame(host.door_indicator_opts_frame, bg=host.COLOR_BG)
    door_ind_ctrl.pack(fill=tk.X, pady=2)

    lbl_door_grid = tk.Label(door_ind_ctrl, text="指示燈層數 (3個為一層) :", bg=host.COLOR_BG, fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 10, 'bold'))
    lbl_door_grid.pack(side=tk.LEFT, padx=5)

    host.cb_door_ind_l = ttk.Combobox(door_ind_ctrl, textvariable=host.door_indicator_l_var, values=["1", "2", "3", "4", "5", "6"], width=6, state="readonly", style='TCombobox')
    host.cb_door_ind_l.pack(side=tk.LEFT, padx=2)
    host.cb_door_ind_l.bind("<<ComboboxSelected>>", lambda e: host.on_door_layers_count_changed())

    btn_reset_pos_x = tk.Button(
        door_ind_ctrl,
        text="左右置中",
        font=('Microsoft JhengHei', 9, 'bold'),
        bg=host.COLOR_PANEL, fg=host.COLOR_ACCENT, bd=1, relief=tk.SOLID,
        activebackground=host.COLOR_BG, activeforeground=host.COLOR_ACCENT,
        cursor="hand2", padx=10,
        command=host.reset_door_indicator_offset_x
    )
    btn_reset_pos_x.pack(side=tk.LEFT, padx=10)

    btn_reset_pos_y = tk.Button(
        door_ind_ctrl,
        text="上下置中",
        font=('Microsoft JhengHei', 9, 'bold'),
        bg=host.COLOR_PANEL, fg=host.COLOR_ACCENT, bd=1, relief=tk.SOLID,
        activebackground=host.COLOR_BG, activeforeground=host.COLOR_ACCENT,
        cursor="hand2", padx=10,
        command=host.reset_door_indicator_offset_y
    )
    btn_reset_pos_y.pack(side=tk.LEFT, padx=10)

    host.chk_box_dist = tk.Checkbutton(
        door_ind_ctrl,
        text="箱體定位距離",
        variable=host.is_box_dist_var,
        bg=host.COLOR_BG,
        fg=host.COLOR_TEXT,
        selectcolor=host.COLOR_PANEL,
        activebackground=host.COLOR_BG,
        activeforeground=host.COLOR_ACCENT,
        font=('Microsoft JhengHei', 9, 'bold'),
        cursor="hand2",
        command=host.update_calculations
    )
    host.chk_box_dist.pack(side=tk.LEFT, padx=15)

    # 每層組數配置
    host.door_layers_config_frame = tk.Frame(host.door_indicator_opts_frame, bg=host.COLOR_PANEL)
    host.door_layers_config_frame.pack(fill=tk.X, padx=10, pady=2)

    host.rebuild_door_layers_config_ui()

    # 畫布 Frame
    canvas_frame = tk.Frame(host.tab_door, bg=host.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    host.door_canvas_frame = canvas_frame
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    # 門畫布
    host.canvas_door = tk.Canvas(canvas_frame, bg=host.COLOR_CANVAS_BG, highlightthickness=0)
    host.canvas_door.pack(fill=tk.BOTH, expand=True)
    host.canvas_door.bind("<Configure>", lambda e: host.draw_preview())
    host.canvas_door.bind("<Button-1>", host.on_door_canvas_press)
    host.canvas_door.bind("<B1-Motion>", host.on_door_canvas_drag)
    host.canvas_door.bind("<ButtonRelease-1>", host.on_door_canvas_release)
    host._attach_part_hole_entrypoint(host.canvas_door, "door", allow_double=True)
    # 覆寫通用雙擊：單門開 Door editor；多門由格子 tag 精準處理並阻止重複開窗。
    host.canvas_door.bind("<Double-Button-1>", host.on_door_canvas_double_click)



def normalize_door_indicator_state(state):
    raw = dict(state or {})
    mode = raw.get("mode")
    if mode not in {"none", "indicator", "indicator_box"}:
        if raw.get("box_enabled"):
            mode = "indicator_box"
        elif raw.get("enabled"):
            mode = "indicator"
        else:
            mode = "none"
    try:
        layers = max(1, min(6, int(raw.get("layers", 1))))
    except (TypeError, ValueError):
        layers = 1
    groups = list(raw.get("groups", [2] * 6))
    while len(groups) < 6:
        groups.append(2)
    normalized_groups = []
    for value in groups[:6]:
        try:
            normalized_groups.append(max(1, int(value)))
        except (TypeError, ValueError):
            normalized_groups.append(2)
    return {
        "mode": mode,
        "enabled": mode == "indicator",
        "box_enabled": mode == "indicator_box",
        "layers": layers,
        "groups": normalized_groups,
        "offset_x": float(raw.get("offset_x", 0.0) or 0.0),
        "offset_y": float(raw.get("offset_y", 0.0) or 0.0),
        "is_box_dist": bool(raw.get("is_box_dist", False)),
    }


def destroy_door_layout_entry_widgets(host):
    for widget in list(host.door_layout_width_entries.values()) + list(host.door_layout_height_entries.values()):
        try:
            widget.destroy()
        except tk.TclError:
            pass
    host.door_layout_width_entries = {}
    host.door_layout_height_entries = {}
    host.door_layout_entry_windows = []


def door_layout_entry_menu(host, entry, *, column_index, row_index=None):
    menu = configure_tk_menu(tk.Menu(entry, tearoff=False))
    if row_index is None:
        column = host.door_layout_columns[column_index]
        if not column.get("width_auto", False):
            menu.add_command(
                label="刪除此欄",
                command=lambda: host.remove_door_layout_column(column_index),
            )
    else:
        column = host.door_layout_columns[column_index]
        if not column["height_auto"][row_index]:
            menu.add_command(
                label="刪除此層",
                command=lambda: host.remove_door_layout_height(column_index, row_index),
            )
    if menu.index("end") is not None:
        entry.bind(
            "<Button-3>",
            lambda e, m=menu: (m.tk_popup(e.x_root, e.y_root), "break")[1],
        )


def rebuild_door_layers_config_ui(host):
    for widget in host.door_layers_config_frame.winfo_children():
        widget.destroy()

    try:
        layers = int(host.door_indicator_l_var.get())
    except ValueError:
        layers = 1

    for ly in range(layers):
        ly_frame = tk.Frame(host.door_layers_config_frame, bg=host.COLOR_PANEL)
        ly_frame.pack(side=tk.LEFT, padx=15, pady=4)

        label_text = f"第 {ly+1} 層組數:"
        if ly == 0:
            label_text = "第 1 層 (底) 組數:"
        elif ly == layers - 1 and layers > 1:
            label_text = f"第 {ly+1} 層 (頂) 組數:"

        tk.Label(
            ly_frame,
            text=label_text,
            bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT,
            font=("Microsoft JhengHei", 9, "bold"),
        ).pack(side=tk.LEFT, padx=2)

        cb = ttk.Combobox(
            ly_frame,
            textvariable=host.door_indicator_layer_g_vars[ly],
            values=["1", "2", "3", "4", "5", "6", "7", "8"],
            width=4,
            state="readonly",
            style="TCombobox",
        )
        cb.pack(side=tk.LEFT, padx=2)
        cb.bind(
            "<<ComboboxSelected>>",
            lambda e: host._request_phase6_update("geometry"),
        )
