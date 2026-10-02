"""Assembly/corner presentation and routing helpers only."""

from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.corner_type_ui import CORNER_PAIR_CORNERS
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CrossCornerMode,
    normalize_corner_selection,
)


def sync_endcap_fw_controls(host):
    box_fw = float(host.fw_z_var.get())
    for part, var, follow_var, combo in (
        ("head", host.fw_head_var, host.fw_head_follow_var, getattr(host, "cb_fw_head", None)),
        ("tail", host.fw_tail_var, host.fw_tail_follow_var, getattr(host, "cb_fw_tail", None)),
    ):
        state = host.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
        follow = bool(state.get("follow_box", True))
        follow_var.set(follow)
        value = box_fw if follow else float(state.get("value", box_fw))
        text = host._fold_designer_number_text(value)
        if var.get() != text:
            var.set(text)
        if combo is not None:
            combo.configure(state="normal")


def sync_fold_designer_manual_corner_context(host, active_part):
    key = str(active_part or "")
    if key in {"indicator_box", "indicator_door"} and key in host.manual_corner_state:
        host._manual_corner_part_override = key
    else:
        host._manual_corner_part_override = None
    host.refresh_corner_type_panel()


def fixed_corner_summary(host, part_key, current_cabinet_type_name):
    if current_cabinet_type_name == "受電箱" and part_key in {"head", "tail"}:
        joint_state = dict(getattr(host, "assembly_joint_state", {}) or {})
        bottom_relation = edge_relation_for_part(joint_state, part_key, "BOTTOM")
        if bottom_relation is AssemblyJointRelation.WRAP:
            bottom_summary = "下方：包覆貼外（BOTTOM＝WRAP；FW 基準＝側板後折＋1T）"
        elif bottom_relation is AssemblyJointRelation.INSERT:
            bottom_summary = "下方：標準截角（BOTTOM＝嵌入；WRAP 關閉）"
        elif bottom_relation is None:
            bottom_summary = "下方：標準截角（BOTTOM Joint 未定義）"
        else:
            bottom_summary = f"下方：標準截角（BOTTOM＝{bottom_relation.value}）"
        return "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n" + bottom_summary
    return host._FIXED_CORNER_SUMMARIES.get(part_key, "目前板件使用固定截角規則")


def normalize_manual_corner_target(host, part_key):
    target = host.manual_active_corner_var.get()
    same = host.manual_corner_pair_same[part_key]
    pair = host._pair_for_corner_target(target)
    if pair is None:
        target = "top"
        pair = "top"
    if same[pair]:
        target = pair
    elif target == pair:
        target = CORNER_PAIR_CORNERS[pair][0]
    host.manual_active_corner_var.set(target)
    return target


def corner_parameter_summary(host_cls, selection):
    selection = normalize_corner_selection(selection)
    if selection.type_id is CornerTypeId.CROSS:
        mode = host_cls._CORNER_MODE_LABELS[selection.cross_mode]
        if selection.cross_mode is CrossCornerMode.STANDARD:
            return mode
        direction = host_cls._CORNER_DIRECTION_LABELS[selection.direction]
        return f"{mode}｜{direction}｜{host_cls._corner_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.OVERLAY:
        return f"留肉（高）｜{host_cls._corner_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.INSERT:
        return f"多切（高）｜{host_cls._corner_number_text(selection.amount_t)}T"
    return (
        f"貼外留肉 {host_cls._corner_number_text(selection.amount_t)}T｜"
        f"嵌入留肉 {host_cls._corner_number_text(selection.secondary_retain_t)}T｜"
        f"深度 {host_cls._corner_number_text(selection.secondary_depth_t)}T"
    )

import tkinter as tk

from ae_engine.corner_type_ui import CORNER_KEYS, build_corner_type_preview_geometry
from ae_engine.sheetmetal_geometry import CORNER_TYPE_LABELS, CornerDirection, CornerTypeSelection
from gui_modules.drawing import _corner_preview_canvas_point, _corner_preview_flip_y_for_target

def draw_corner_type_icon(self, canvas, selection_or_type, *, large=False, flip_y=True):
    """Render a preview from the same semantic selection used by production geometry."""
    canvas.delete('all')
    w = max(10, int(float(canvas.cget('width'))))
    h = max(10, int(float(canvas.cget('height'))))
    margin = 5 if not large else 12
    if isinstance(selection_or_type, CornerTypeSelection):
        selection = normalize_corner_selection(selection_or_type)
    else:
        selection = CornerTypeSelection(CornerTypeId(selection_or_type))
    preview = build_corner_type_preview_geometry(selection)
    usable_w = max(1.0, w - 2 * margin)
    usable_h = max(1.0, h - 2 * margin)
    scale = min(usable_w / preview.span, usable_h / preview.span)
    ox = margin + (usable_w - preview.span * scale) / 2.0
    oy = h - margin - (usable_h - preview.span * scale) / 2.0

    def pt(point):
        return _corner_preview_canvas_point(
            point, ox=ox, oy=oy, scale=scale, span=preview.span, flip_y=flip_y
        )

    for path in preview.cut_paths:
        coords = []
        for point in path:
            coords.extend(pt(point))
        if len(coords) >= 4:
            canvas.create_line(*coords, fill='#30d158', width=3 if large else 2,
                               capstyle=tk.PROJECTING, joinstyle=tk.MITER)
    for path in preview.bend_paths:
        coords = []
        for point in path:
            coords.extend(pt(point))
        if len(coords) >= 4:
            canvas.create_line(*coords, fill='#0a84ff', dash=(3, 2), width=1,
                               capstyle=tk.PROJECTING, joinstyle=tk.MITER)
    if large:
        canvas.create_text(
            w / 2, 10, text=CORNER_TYPE_LABELS[selection.type_id],
            fill=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')
        )

def select_manual_corner(self, corner_key):
    part_key = self._current_manual_corner_part_key()
    if part_key is None or part_key not in self.manual_corner_state:
        return
    valid = set(CORNER_KEYS) | {'top', 'bottom'}
    if corner_key not in valid:
        return
    pair = self._pair_for_corner_target(corner_key)
    if corner_key in ('top', 'bottom') and not self.manual_corner_pair_same[part_key][pair]:
        corner_key = CORNER_PAIR_CORNERS[pair][0]
    elif corner_key in CORNER_KEYS and self.manual_corner_pair_same[part_key][pair]:
        corner_key = pair
    self.manual_active_corner_var.set(corner_key)
    self.refresh_corner_type_panel()

def selection_from_manual_corner_controls(self):
    try:
        type_id = CornerTypeId(self.manual_corner_type_var.get())
    except ValueError:
        return None
    try:
        amount = float(self.manual_corner_amount_var.get())
        secondary_retain = float(self.manual_corner_secondary_retain_var.get())
        secondary_depth = float(self.manual_corner_secondary_depth_var.get())
    except (TypeError, ValueError, tk.TclError):
        return None
    try:
        if type_id is CornerTypeId.CROSS:
            mode = self._CORNER_MODE_BY_LABEL.get(
                self.manual_corner_cross_mode_var.get(), CrossCornerMode.STANDARD
            )
            if mode is CrossCornerMode.STANDARD:
                return CornerTypeSelection(type_id, cross_mode=mode)
            direction = self._CORNER_DIRECTION_BY_LABEL.get(self.manual_corner_direction_var.get())
            if direction is None:
                direction = CornerDirection.WIDTH if mode is CrossCornerMode.RETAIN else CornerDirection.BOTH
            return CornerTypeSelection(
                type_id, cross_mode=mode, direction=direction, amount_t=amount
            )
        if type_id is CornerTypeId.OVERLAY:
            return CornerTypeSelection(type_id, amount_t=amount)
        if type_id is CornerTypeId.INSERT:
            return CornerTypeSelection(type_id, amount_t=amount)
        if type_id is CornerTypeId.INSERT_OVERLAY:
            return CornerTypeSelection(
                type_id, amount_t=amount,
                secondary_retain_t=secondary_retain,
                secondary_depth_t=secondary_depth,
            )
    except (TypeError, ValueError):
        return None
    return None

def refresh_manual_corner_parameter_rows(self, selection):
    for row in (
        self.manual_corner_mode_row, self.manual_corner_direction_row,
        self.manual_corner_amount_row, self.manual_corner_secondary_row,
    ):
        row.pack_forget()

    if selection.type_id is CornerTypeId.CROSS:
        self.manual_corner_mode_row.pack(fill=tk.X, pady=2)
        if selection.cross_mode is CrossCornerMode.STANDARD:
            return
        self.manual_corner_direction_row.pack(fill=tk.X, pady=2)
        self.manual_corner_amount_row.pack(fill=tk.X, pady=2)
        if selection.cross_mode is CrossCornerMode.RETAIN:
            self.manual_corner_direction_label.configure(text="留肉方向 :")
            self.manual_corner_direction_cb.configure(values=['寬', '高'], state='readonly')
            self.manual_corner_amount_label.configure(text="留肉 :")
        else:
            self.manual_corner_direction_label.configure(text="多切方向 :")
            self.manual_corner_direction_cb.configure(values=['寬＋高', '寬', '高'], state='readonly')
            self.manual_corner_amount_label.configure(text="多切 :")
        return

    self.manual_corner_amount_row.pack(fill=tk.X, pady=2)
    if selection.type_id is CornerTypeId.OVERLAY:
        self.manual_corner_amount_label.configure(text="留肉（高） :")
    elif selection.type_id is CornerTypeId.INSERT:
        self.manual_corner_amount_label.configure(text="多切（高） :")
    else:
        self.manual_corner_amount_label.configure(text="貼外留肉（高） :")
        self.manual_corner_secondary_row.pack(fill=tk.X, pady=2)

def toggle_manual_corner_parameter_lock(self):
    part_key = self._current_manual_corner_part_key()
    if not self._corner_part_parameters_unlockable(part_key):
        return
    state = getattr(self, "_manual_corner_param_unlocked", None)
    if not isinstance(state, dict):
        state = {}
        self._manual_corner_param_unlocked = state
    state[part_key] = not bool(state.get(part_key, False))
    self.refresh_corner_type_panel()

def refresh_corner_type_panel(self):
    if self.corner_type_panel is None:
        return
    part_key = self._current_manual_corner_part_key()
    if part_key not in self.manual_corner_state:
        self.corner_type_panel.pack_forget()
        return
    if not self.corner_type_panel.winfo_ismapped():
        self.corner_type_panel.pack(fill=tk.X, pady=(6, 8), before=self.corner_type_panel_anchor)

    part_labels = {
        'head': '封頭', 'tail': '封尾', 'door': '門', 'base_plate': '底板',
        'indicator_box': '指示燈盒', 'indicator_door': '指示燈小門',
    }
    self.manual_corner_part_label.configure(text=f"板件：{part_labels.get(part_key, part_key)}")
    type_editable = self._corner_part_type_editable(part_key)
    unlockable = self._corner_part_parameters_unlockable(part_key)
    params_unlocked = self._manual_corner_parameters_unlocked(part_key)
    if not unlockable:
        self.manual_corner_title_label.configure(text="截角類型（固定 / 唯讀）")
        self.manual_corner_param_lock_button.pack_forget()
        self.manual_corner_editor_frame.pack_forget()
        summary = self._fixed_corner_summary(part_key)
        self.manual_corner_fixed_summary.configure(text=summary)
        self.manual_corner_fixed_summary.pack(fill=tk.X, padx=8, pady=(2, 8))
        return

    self.manual_corner_title_label.configure(text="截角類型" if type_editable else "截角類型（基準預設）")
    self.manual_corner_fixed_summary.pack_forget()
    if not self.manual_corner_param_lock_button.winfo_ismapped():
        self.manual_corner_param_lock_button.pack(side=tk.RIGHT, padx=(6, 0))
    self.manual_corner_param_lock_button.configure(text="🔓 參數解鎖" if params_unlocked else "🔒 參數鎖定")
    if not self.manual_corner_editor_frame.winfo_ismapped():
        self.manual_corner_editor_frame.pack(fill=tk.X)

    same = self.manual_corner_pair_same[part_key]
    self.manual_top_same_var.set(same['top'])
    self.manual_bottom_same_var.set(same['bottom'])
    target_key = self._normalize_manual_corner_target(part_key)
    selection = self._manual_selection_for_target(part_key, target_key)

    self._manual_corner_param_guard = True
    try:
        self.manual_corner_type_var.set(selection.type_id.value)
        if selection.cross_mode is not None:
            self.manual_corner_cross_mode_var.set(self._CORNER_MODE_LABELS[selection.cross_mode])
        if selection.direction is not None:
            self.manual_corner_direction_var.set(self._CORNER_DIRECTION_LABELS[selection.direction])
        self.manual_corner_amount_var.set(self._corner_number_text(selection.amount_t or 1.0))
        self.manual_corner_secondary_retain_var.set(
            self._corner_number_text(selection.secondary_retain_t if selection.secondary_retain_t is not None else 0.5)
        )
        self.manual_corner_secondary_depth_var.set(
            self._corner_number_text(selection.secondary_depth_t if selection.secondary_depth_t is not None else 2.0)
        )
    finally:
        self._manual_corner_param_guard = False

    for pair_key, controls in self.manual_corner_pair_buttons.items():
        for widget in (controls['pair'], controls['left'], controls['right']):
            widget.pack_forget()
        if same[pair_key]:
            controls['pair'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            controls['left'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
            controls['right'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        pair_targets = {pair_key} if same[pair_key] else set(CORNER_PAIR_CORNERS[pair_key])
        for name in ('pair', 'left', 'right'):
            widget = controls[name]
            widget_target = pair_key if name == 'pair' else CORNER_PAIR_CORNERS[pair_key][0 if name == 'left' else 1]
            active = widget_target == target_key and widget_target in pair_targets
            widget.configure(bg=self.COLOR_ACCENT if active else self.COLOR_PANEL,
                             fg='#ffffff' if active else self.COLOR_TEXT)

    params_editable = self._manual_corner_parameters_editable(part_key)
    for cb in self.manual_corner_pair_same_checkbuttons.values():
        if params_unlocked:
            if not cb.winfo_ismapped():
                cb.pack(side=tk.LEFT, padx=(2, 8), before=cb.master.winfo_children()[-1])
            cb.configure(state=(tk.NORMAL if params_editable else tk.DISABLED))
        else:
            cb.pack_forget()
    target_type_editable = type_editable and not (
        part_key in {"head", "tail"} and target_key in {"top", "top_left", "top_right"}
    )
    for rb in self.manual_corner_type_buttons.values():
        rb.configure(state=(tk.NORMAL if target_type_editable else tk.DISABLED))

    flip_y = _corner_preview_flip_y_for_target(target_key)
    for type_id, canvas in self.corner_type_small_canvases.items():
        self._draw_corner_type_icon(
            canvas, CornerTypeSelection(type_id), large=False, flip_y=flip_y
        )
        canvas.configure(highlightbackground=self.COLOR_ACCENT if type_id is selection.type_id else '#34343a')
    if params_unlocked:
        self.manual_corner_param_summary.pack_forget()
        if not self.manual_corner_param_frame.winfo_ismapped():
            self.manual_corner_param_frame.pack(fill=tk.X, padx=8, pady=(5, 2))
        self._refresh_manual_corner_parameter_rows(selection)
    else:
        self.manual_corner_param_frame.pack_forget()
        self.manual_corner_param_summary.configure(text=f"目前參數：{self._corner_parameter_summary(selection)}")
        if not self.manual_corner_param_summary.winfo_ismapped():
            self.manual_corner_param_summary.pack(fill=tk.X, padx=8, pady=(3, 5))
    if self.corner_type_preview_canvas is not None:
        self._draw_corner_type_icon(
            self.corner_type_preview_canvas, selection, large=True, flip_y=flip_y
        )

from tkinter import ttk
from ae_engine.corner_type_ui import CORNER_LABELS
from ae_engine.sheetmetal_geometry import EDITABLE_CORNER_TYPE_IDS

def _build_corner_pair_controls(host, editor):
    # 預設以上方／下方成對編輯；只有取消「左右相同」才拆成左右兩個角。
    host.manual_corner_pair_buttons = {}
    host.manual_corner_pair_same_checkbuttons = {}
    for pair_key, pair_label, same_var in (
        ('top', '上方截角', host.manual_top_same_var),
        ('bottom', '下方截角', host.manual_bottom_same_var),
    ):
        pair_row = tk.Frame(editor, bg=host.COLOR_INPUT_BG)
        pair_row.pack(fill=tk.X, padx=8, pady=3)
        tk.Label(
            pair_row, text=pair_label, width=8, anchor=tk.W,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            font=('Microsoft JhengHei', 9, 'bold'),
        ).pack(side=tk.LEFT)
        same_cb = tk.Checkbutton(
            pair_row, text='左右相同', variable=same_var,
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            activebackground=host.COLOR_INPUT_BG, activeforeground=host.COLOR_TEXT,
            selectcolor=host.COLOR_PANEL,
            command=lambda p=pair_key: host.on_manual_corner_pair_same_changed(p),
        )
        same_cb.pack(side=tk.LEFT, padx=(2, 8))
        host.manual_corner_pair_same_checkbuttons[pair_key] = same_cb
        button_frame = tk.Frame(pair_row, bg=host.COLOR_INPUT_BG)
        button_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        left_key, right_key = CORNER_PAIR_CORNERS[pair_key]
        pair_button = tk.Button(
            button_frame, text=('上方' if pair_key == 'top' else '下方'),
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, bd=0,
            activebackground=host.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
            command=lambda p=pair_key: host.select_manual_corner(p),
        )
        left_button = tk.Button(
            button_frame, text=CORNER_LABELS[left_key],
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, bd=0,
            activebackground=host.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
            command=lambda k=left_key: host.select_manual_corner(k),
        )
        right_button = tk.Button(
            button_frame, text=CORNER_LABELS[right_key],
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, bd=0,
            activebackground=host.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
            command=lambda k=right_key: host.select_manual_corner(k),
        )
        host.manual_corner_pair_buttons[pair_key] = {
            'frame': button_frame, 'pair': pair_button,
            'left': left_button, 'right': right_button,
        }

def _build_corner_type_selector(host, editor):
    type_frame = tk.Frame(editor, bg=host.COLOR_INPUT_BG)
    type_frame.pack(fill=tk.X, padx=8, pady=(5, 2))
    host.manual_corner_type_frame = type_frame
    host.corner_type_small_canvases = {}
    host.manual_corner_type_buttons = {}
    for type_id in EDITABLE_CORNER_TYPE_IDS:
        row = tk.Frame(type_frame, bg=host.COLOR_INPUT_BG)
        row.pack(fill=tk.X, pady=2)
        icon = tk.Canvas(
            row, width=54, height=40, bg=host.COLOR_CANVAS_BG,
            highlightthickness=1, highlightbackground='#34343a'
        )
        icon.pack(side=tk.LEFT, padx=(0, 6))
        icon.bind('<Button-1>', lambda e, tid=type_id: host.set_manual_corner_type(tid))
        host.corner_type_small_canvases[type_id] = icon
        rb = tk.Radiobutton(
            row,
            text=CORNER_TYPE_LABELS[type_id],
            variable=host.manual_corner_type_var,
            value=type_id.value,
            command=lambda tid=type_id: host.set_manual_corner_type(tid),
            bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            activebackground=host.COLOR_INPUT_BG, activeforeground=host.COLOR_TEXT,
            selectcolor=host.COLOR_PANEL, anchor=tk.W,
        )
        rb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        host.manual_corner_type_buttons[type_id] = rb

def _build_corner_parameter_controls(host, editor):
    host.manual_corner_param_summary = tk.Label(
        editor, text="", justify=tk.LEFT, anchor=tk.W,
        bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT_MUTED,
        font=('Microsoft JhengHei', 9), wraplength=520,
    )

    host.manual_corner_param_frame = tk.Frame(editor, bg=host.COLOR_INPUT_BG)

    host.manual_corner_mode_row = tk.Frame(host.manual_corner_param_frame, bg=host.COLOR_INPUT_BG)
    tk.Label(host.manual_corner_mode_row, text="方式 :", width=12, anchor=tk.W,
             bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT).pack(side=tk.LEFT)
    host.manual_corner_mode_cb = ttk.Combobox(
        host.manual_corner_mode_row, textvariable=host.manual_corner_cross_mode_var,
        values=['標準', '單邊留肉', '多切'], width=12, state='readonly', style='TCombobox'
    )
    host.manual_corner_mode_cb.pack(side=tk.LEFT, padx=4)
    host.manual_corner_mode_cb.bind('<<ComboboxSelected>>', host.on_manual_corner_mode_changed)

    host.manual_corner_direction_row = tk.Frame(host.manual_corner_param_frame, bg=host.COLOR_INPUT_BG)
    host.manual_corner_direction_label = tk.Label(
        host.manual_corner_direction_row, text="方向 :", width=12, anchor=tk.W,
        bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT
    )
    host.manual_corner_direction_label.pack(side=tk.LEFT)
    host.manual_corner_direction_cb = ttk.Combobox(
        host.manual_corner_direction_row, textvariable=host.manual_corner_direction_var,
        width=12, state='readonly', style='TCombobox'
    )
    host.manual_corner_direction_cb.pack(side=tk.LEFT, padx=4)
    host.manual_corner_direction_cb.bind('<<ComboboxSelected>>', host.on_manual_corner_parameter_changed)

    host.manual_corner_amount_row = tk.Frame(host.manual_corner_param_frame, bg=host.COLOR_INPUT_BG)
    host.manual_corner_amount_label = tk.Label(
        host.manual_corner_amount_row, text="數值 :", width=12, anchor=tk.W,
        bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT
    )
    host.manual_corner_amount_label.pack(side=tk.LEFT)
    host.manual_corner_amount_entry = ttk.Entry(
        host.manual_corner_amount_row, textvariable=host.manual_corner_amount_var,
        width=8, justify=tk.CENTER
    )
    host.manual_corner_amount_entry.pack(side=tk.LEFT, padx=4)
    tk.Label(host.manual_corner_amount_row, text="T", bg=host.COLOR_INPUT_BG,
             fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
    host.manual_corner_amount_entry.bind('<Return>', host.on_manual_corner_parameter_changed)
    host.manual_corner_amount_entry.bind('<FocusOut>', host.on_manual_corner_parameter_changed)

    host.manual_corner_secondary_row = tk.Frame(host.manual_corner_param_frame, bg=host.COLOR_INPUT_BG)
    tk.Label(host.manual_corner_secondary_row, text="嵌入留肉 :", width=12, anchor=tk.W,
             bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT).pack(side=tk.LEFT)
    host.manual_corner_secondary_retain_entry = ttk.Entry(
        host.manual_corner_secondary_row, textvariable=host.manual_corner_secondary_retain_var,
        width=7, justify=tk.CENTER
    )
    host.manual_corner_secondary_retain_entry.pack(side=tk.LEFT, padx=(4, 2))
    tk.Label(host.manual_corner_secondary_row, text="T   深度 :", bg=host.COLOR_INPUT_BG,
             fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
    host.manual_corner_secondary_depth_entry = ttk.Entry(
        host.manual_corner_secondary_row, textvariable=host.manual_corner_secondary_depth_var,
        width=7, justify=tk.CENTER
    )
    host.manual_corner_secondary_depth_entry.pack(side=tk.LEFT, padx=(4, 2))
    tk.Label(host.manual_corner_secondary_row, text="T", bg=host.COLOR_INPUT_BG,
             fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
    for entry in (host.manual_corner_secondary_retain_entry, host.manual_corner_secondary_depth_entry):
        entry.bind('<Return>', host.on_manual_corner_parameter_changed)
        entry.bind('<FocusOut>', host.on_manual_corner_parameter_changed)

    host.corner_type_preview_canvas = tk.Canvas(
        editor, width=150, height=105, bg=host.COLOR_CANVAS_BG,
        highlightthickness=1, highlightbackground='#34343a'
    )
    host.corner_type_preview_canvas.pack(padx=8, pady=(4, 8))

def create_corner_type_panel(host, parent):
    panel = tk.Frame(parent, bg=host.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
    host.corner_type_panel = panel

    title_row = tk.Frame(panel, bg=host.COLOR_INPUT_BG)
    title_row.pack(fill=tk.X, padx=8, pady=(8, 4))
    host.manual_corner_title_label = tk.Label(
        title_row, text="截角類型", bg=host.COLOR_INPUT_BG,
        fg=host.COLOR_ACCENT, font=('Microsoft JhengHei', 10, 'bold')
    )
    host.manual_corner_title_label.pack(side=tk.LEFT)
    host.manual_corner_param_lock_button = tk.Button(
        title_row, text="🔒 參數鎖定", command=host.toggle_manual_corner_parameter_lock,
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT, bd=0, cursor="hand2",
        activebackground=host.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
        font=('Microsoft JhengHei', 9, 'bold'), padx=6, pady=1,
    )
    host.manual_corner_part_label = tk.Label(
        title_row, text="", bg=host.COLOR_INPUT_BG,
        fg=host.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9)
    )
    host.manual_corner_part_label.pack(side=tk.RIGHT)

    host.manual_corner_fixed_summary = tk.Label(
        panel, text="", justify=tk.LEFT, anchor=tk.W,
        bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
        font=('Microsoft JhengHei', 9), wraplength=520,
    )

    host.manual_corner_editor_frame = tk.Frame(panel, bg=host.COLOR_INPUT_BG)
    editor = host.manual_corner_editor_frame
    _build_corner_pair_controls(host, editor)
    _build_corner_type_selector(host, editor)
    _build_corner_parameter_controls(host, editor)
    panel.pack_forget()
    host.corner_type_panel_anchor = tk.Frame(parent, bg=host.COLOR_PANEL, height=1)
    host.corner_type_panel_anchor.pack(fill=tk.X)
