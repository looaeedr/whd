"""Static left control-panel presentation wiring."""

import tkinter as tk
from tkinter import ttk

from ae_engine.corner_type_ui import CUSTOM_MODEL_NAME


def build_left_panel(host, ctrl_pad_frame):
    # 區段 0：基準型號就是盤體類型；只有一個 Source of Truth。
    lbl_sec0 = ttk.Label(ctrl_pad_frame, text="0. 基準型號", style='Title.TLabel')
    lbl_sec0.pack(anchor=tk.W, pady=(0, 6))

    row_base = tk.Frame(ctrl_pad_frame, bg=host.COLOR_PANEL)
    row_base.pack(fill=tk.X, pady=2)

    lbl_base = ttk.Label(row_base, text="基準型號 :", width=12, anchor=tk.W)
    lbl_base.pack(side=tk.LEFT)

    base_models = host._baseline_model_choices()
    host.baseline_cb = ttk.Combobox(row_base, textvariable=host.baseline_var, 
                                    values=base_models, state="readonly", style='TCombobox')
    host.baseline_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if base_models:
        if "金庫型" in base_models:
            idx = base_models.index("金庫型")
            host.baseline_cb.current(idx)
        elif CUSTOM_MODEL_NAME in base_models:
            host.baseline_cb.current(base_models.index(CUSTOM_MODEL_NAME))
        else:
            host.baseline_cb.current(0)

    host._baseline_last_value = host.baseline_var.get().strip()
    host._enforce_known_model_corner_types(reset_all=True)
    # Capture the canonical Vault startup state before the user can edit it.
    # Returning to a known model must restore this preset, not the last
    # runtime values used before switching away.
    host._cabinet_family_defaults["金庫型"] = host._capture_cabinet_family_runtime()
    host.baseline_var.trace_add("write", lambda *args: host.on_baseline_changed())

    host.fold_designer_button = tk.Button(
        ctrl_pad_frame, text="開啟折彎 / 3D 設計", command=host.open_original_fold_designer,
        font=('Microsoft JhengHei', 10, 'bold'), bg=host.COLOR_ACCENT, fg="#ffffff",
        activebackground=host.COLOR_ACCENT, activeforeground="#ffffff", bd=0, cursor="hand2"
    )
    host.fold_designer_button.pack(fill=tk.X, pady=(8, 4), ipady=4)

    # 截角類型面板：自訂可編輯；固定板件／已知基準只顯示實際唯讀語意。
    host.create_corner_type_panel(ctrl_pad_frame)

    # 分隔線
    host.create_separator(ctrl_pad_frame)

    # 區段 1：基礎尺寸
    lbl_sec1 = ttk.Label(ctrl_pad_frame, text="1. 基礎尺寸設定 (mm)", style='Title.TLabel')
    lbl_sec1.pack(anchor=tk.W, pady=(0, 10))

    # 寬、高、深輸入框
    host.create_input_row(ctrl_pad_frame, "寬度 (W) :", host.w_var)
    host.create_input_row(ctrl_pad_frame, "高度 (H) :", host.h_var)
    host.create_input_row(ctrl_pad_frame, "深度 (D) :", host.d_var)

    # 折彎/板件專屬設定已集中到 3D 設定中心；主 GUI 僅保留全域尺寸。
    host.create_separator(ctrl_pad_frame)

    # 區段 3：計算結果與輸出
    lbl_sec3 = ttk.Label(ctrl_pad_frame, text="2. 展開尺寸計算結果", style='Title.TLabel')
    lbl_sec3.pack(anchor=tk.W, pady=(0, 10))

    # 結果顯示區域
    result_box = tk.Frame(ctrl_pad_frame, bg=host.COLOR_INPUT_BG, bd=1, relief=tk.SOLID, highlightthickness=0)
    result_box.pack(fill=tk.X, pady=5)

    host._phase6_result_part_rows = {
        "box_body": [
            host.create_result_row(result_box, "箱身 (z) 總長度:", host.result_z_var),
            host.create_result_row(result_box, "箱身 (z) 展開高:", host.result_z_h_var),
        ],
        # Head/Tail share the same unfolded-size result. Keep it while either
        # physical end cap exists; hide it only when both are deleted.
        "endcap": [
            host.create_result_row(result_box, "封頭/尾 展開寬:", host.result_y_w_var),
            host.create_result_row(result_box, "封頭/尾 展開深:", host.result_y_d_var),
        ],
        "door": [
            host.create_result_row(result_box, "門 (Door) 展開寬:", host.result_door_w_var),
            host.create_result_row(result_box, "門 (Door) 展開高:", host.result_door_h_var),
        ],
        "base_plate": [
            host.create_result_row(result_box, "底板 展開寬:", host.result_base_plate_w_var),
            host.create_result_row(result_box, "底板 展開高:", host.result_base_plate_h_var),
        ],
        "indicator_box": [
            host.create_result_row(result_box, "指示燈盒子 展開寬:", host.result_ib_w_var),
            host.create_result_row(result_box, "指示燈盒子 展開高:", host.result_ib_h_var),
        ],
        "indicator_door": [
            host.create_result_row(result_box, "指示燈小門 展開寬:", host.result_ib_door_w_var),
            host.create_result_row(result_box, "指示燈小門 展開高:", host.result_ib_door_h_var),
        ],
    }

    # 輸出選項區塊（固定顯示）
    host.create_separator(ctrl_pad_frame)

    lbl_output_opts = ttk.Label(ctrl_pad_frame, text="3. DXF 輸出選項", style='Title.TLabel')
    lbl_output_opts.pack(anchor=tk.W, pady=(0, 6))

    output_opts_box = tk.Frame(ctrl_pad_frame, bg=host.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
    output_opts_box.pack(fill=tk.X, pady=(0, 4))

    def make_chk(parent, text, var, cmd=None):
        return tk.Checkbutton(
            parent, text=text, variable=var,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_PANEL,
            activebackground=host.COLOR_INPUT_BG, activeforeground=host.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9), cursor="hand2",
            command=cmd
        )

    # DXF 選項（只剩 STOCK）
    make_chk(output_opts_box, "輸出 STOCK 母材外框 (青色虛線)",
             host.draw_stock_var, host.draw_preview).pack(anchor=tk.W, padx=10, pady=(6,6))

    # 輸出零件選擇
    host.create_separator(ctrl_pad_frame)
    lbl_parts = ttk.Label(ctrl_pad_frame, text="4. 選擇輸出零件", style='Title.TLabel')
    lbl_parts.pack(anchor=tk.W, pady=(0, 6))

    parts_box = tk.Frame(ctrl_pad_frame, bg=host.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
    parts_box.pack(fill=tk.X, pady=(0, 8))

    host._phase6_output_part_widgets = {
        "box_body": make_chk(parts_box, "箱身 (Z)  →  box_body_z.dxf", host.export_z_var),
        "head": make_chk(parts_box, "封頭 (Y)  →  end_cap_head.dxf", host.export_head_var),
        "tail": make_chk(parts_box, "封尾 (Y)  →  end_cap_tail.dxf", host.export_tail_var),
        "door": make_chk(parts_box, "門 (Door)  →  door_unfold.dxf / 多門 door_cN_rM.dxf", host.export_door_var),
        "base_plate": make_chk(parts_box, "底板  →  base_plate.dxf", host.export_base_plate_var),
        "indicator_box": make_chk(parts_box, "指示燈盒子  →  indicator_box.dxf", host.export_ib_var),
        "indicator_door": make_chk(parts_box, "指示燈小門  →  indicator_door.dxf", host.export_ib_door_var),
    }
    for index, key in enumerate(("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")):
        pady = (6, 1) if index == 0 else ((1, 6) if index == 6 else (1, 1))
        host._phase6_output_part_widgets[key].pack(anchor=tk.W, padx=10, pady=pady)

    # 輸出按鈕
    host.btn_export = tk.Button(
        ctrl_pad_frame,
        text="輸出選取的 DXF 檔案",
        font=('Microsoft JhengHei', 11, 'bold'),
        bg=host.COLOR_ACCENT, fg="#ffffff",
        activebackground=host.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
        bd=0, height=2, cursor="hand2",
        command=host.export_selected_dxf
    )
    host.btn_export.pack(fill=tk.X, pady=(8, 0))

    # ==========================================
