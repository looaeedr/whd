# -*- coding: utf-8 -*-
"""Owned context-extension rendering for the Phase6 settings panel."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from whd_theme import WHD_SEMANTIC_COLORS
from phase6_settings_panel_primitives import (
    SettingsPanelExtensionResult,
    setting_number_text,
    build_choice_menubutton,
)


class Phase6SettingsPanelOwnedRenderMixin:
    def _owned_structure_entry(self, parent, row, label, value, active_type, field, *, suffix="mm"):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        var = tk.StringVar(master=parent, value=setting_number_text(value))
        entry = ttk.Entry(parent, textvariable=var, width=10, justify=tk.CENTER)
        entry.grid(row=row, column=1, sticky="w", pady=2)
        ttk.Label(parent, text=suffix).grid(row=row, column=2, sticky="w", padx=(5, 12), pady=2)
        if self._box_structure_numeric_changed is not None:
            entry.bind(
                "<Return>",
                lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
            )
            entry.bind(
                "<FocusOut>",
                lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
            )
        return var, entry

    def _render_owned_box_structure(self, parent, start_row, projection, state):
        frame = ttk.LabelFrame(parent, text="結構參數", padding=5)
        frame.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        piece_host = ttk.Frame(frame)
        piece_host.grid(row=0, column=0, columnspan=4, sticky="ew")
        piece_sections = {}
        piece_vars = {}
        piece_entries = {}
        active_type = projection.get("active_type")
        mode = str(projection.get("mode") or "integral")

        error = projection.get("projection_error")
        if error:
            ttk.Label(
                piece_host,
                text=f"逐片尺寸：無法解析（{error}）",
                foreground=WHD_SEMANTIC_COLORS["warning"],
            ).pack(fill=tk.X, pady=2)

        for item in tuple(projection.get("pieces") or ()):
            item = dict(item or {})
            part_key = str(item.get("part_key") or "")
            sub = ttk.LabelFrame(piece_host, text=str(item.get("label") or part_key), padding=4)
            sub._phase6_part_key = part_key
            sub.pack(fill=tk.X, pady=(2, 4))
            piece_sections[part_key] = sub
            piece_vars[part_key] = {}
            piece_entries[part_key] = {}

            input_spec = item.get("input")
            if input_spec:
                input_spec = dict(input_spec)
                field_key = str(input_spec.get("field_key") or "")
                ttk.Label(sub, text=str(input_spec.get("label") or "")).grid(
                    row=0, column=0, sticky="w", padx=(0, 6), pady=2
                )
                var = tk.StringVar(master=sub, value=setting_number_text(input_spec.get("value")))
                entry = ttk.Entry(sub, textvariable=var, width=10, justify=tk.CENTER)
                entry.grid(row=0, column=1, sticky="w", pady=2)
                ttk.Label(sub, text=str(input_spec.get("suffix") or "")).grid(
                    row=0, column=2, sticky="w", padx=(5, 12), pady=2
                )
                if self._box_structure_numeric_changed is not None:
                    field = str(input_spec.get("state_field") or "")
                    entry.bind(
                        "<Return>",
                        lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
                    )
                    entry.bind(
                        "<FocusOut>",
                        lambda _e, t=active_type, f=field, v=var: self._box_structure_numeric_changed(t, f, v),
                    )
                piece_vars[part_key][field_key] = var
                piece_entries[part_key][field_key] = entry

            next_row = 1 if input_spec else 0
            selector = item.get("back_panel_selector")
            if selector:
                selector = dict(selector)
                ttk.Label(sub, text=str(selector.get("label") or "後面板形式")).grid(
                    row=next_row, column=0, sticky="w", padx=(0, 6), pady=2
                )
                selector_var = tk.StringVar(
                    master=sub, value=str(selector.get("value") or "")
                )
                selector_widget = ttk.Combobox(
                    sub,
                    textvariable=selector_var,
                    values=tuple(selector.get("options") or ()),
                    state="readonly",
                    width=10,
                )
                selector_widget.grid(row=next_row, column=1, columnspan=2, sticky="w", pady=2)
                if self._box_back_panel_mode_changed is not None:
                    selector_widget.bind(
                        "<<ComboboxSelected>>",
                        lambda _e, v=selector_var: self._box_back_panel_mode_changed(v),
                    )
                piece_vars[part_key]["back_panel_mode"] = selector_var
                piece_entries[part_key]["back_panel_mode"] = selector_widget
                next_row += 1

            ttk.Label(
                sub,
                text=(
                    f"包外尺寸：{setting_number_text(item.get('formed_width'))} × "
                    f"{setting_number_text(item.get('formed_height'))} mm"
                ),
            ).grid(row=next_row, column=0, columnspan=4, sticky="w", pady=(2, 0))
            next_row += 1
            ttk.Label(
                sub,
                text=(
                    f"料尺寸：{setting_number_text(item.get('blank_width'))} × "
                    f"{setting_number_text(item.get('blank_height'))} mm"
                ),
            ).grid(row=next_row, column=0, columnspan=4, sticky="w", pady=(0, 2))
            next_row += 1
            detail = item.get("detail")
            if detail:
                ttk.Label(sub, text=str(detail)).grid(
                    row=next_row, column=0, columnspan=4, sticky="w", pady=(0, 2)
                )

        state["box_body_piece_input_host"] = piece_host
        state["box_body_piece_input_sections"] = piece_sections
        state["box_body_piece_input_vars"] = piece_vars
        state["box_body_piece_input_entries"] = piece_entries

        row = 1
        if mode in {"two_w", "three_w"}:
            self._owned_structure_entry(
                frame,
                row,
                "中央接合折邊",
                projection.get("seam_bend", 12),
                active_type,
                "seam_bend",
            )
            row += 1
            seam = float(projection.get("seam_bend", 12) or 0)
            if seam >= 50:
                ttk.Label(
                    frame,
                    text=f"⚠ 中央接合折邊 {seam:g} mm 已達 50 mm 以上，請確認尺寸是否合理。",
                    foreground=WHD_SEMANTIC_COLORS["warning"],
                ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(2, 4))
                row += 1
            advanced_open = bool(projection.get("advanced_open", False))
            button = ttk.Button(
                frame,
                text=("▼ 截角／避讓" if advanced_open else "▶ 截角／避讓"),
                command=(
                    (lambda t=active_type: self._box_structure_toggle_advanced(t))
                    if self._box_structure_toggle_advanced is not None else None
                ),
            )
            button.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))
            row += 1
            advanced = ttk.LabelFrame(frame, text="截角／避讓", padding=4)
            if advanced_open:
                advanced.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(3, 0))
            for index, field in enumerate(tuple(projection.get("advanced_fields") or ())):
                field = dict(field or {})
                self._owned_structure_entry(
                    advanced,
                    index,
                    str(field.get("label") or ""),
                    field.get("value"),
                    active_type,
                    str(field.get("field") or ""),
                    suffix=str(field.get("suffix") or "mm"),
                )
        return start_row + 1

    def _render_owned_endcap_fw(self, parent, context, start_row, projection, state):
        box = ttk.Frame(parent, padding=4)
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        ttk.Label(box, text="邊框寬度 FW", font=("Microsoft JhengHei", 9, "bold")).pack(anchor=tk.W)
        ttk.Separator(box, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 4))
        follow_var = tk.BooleanVar(master=box, value=bool(projection.get("follow", True)))
        value_var = tk.StringVar(master=box, value=setting_number_text(projection.get("effective")))
        check = ttk.Checkbutton(box, text="跟隨箱身 FW", variable=follow_var)
        check.pack(side=tk.LEFT, padx=(0, 8))
        entry = ttk.Entry(box, textvariable=value_var, width=9, justify=tk.CENTER)
        entry.pack(side=tk.LEFT, padx=(0, 6))
        entry.configure(state="normal")
        check.configure(state="disabled")
        if self._endcap_fw_value_selected is not None:
            entry.bind(
                "<Return>",
                lambda _e, p=context, v=value_var: self._endcap_fw_value_selected(p, v),
            )
            entry.bind(
                "<FocusOut>",
                lambda _e, p=context, v=value_var: self._endcap_fw_value_selected(p, v),
            )
        ttk.Label(box, text="直接修改：先改一端會帶另一端；再改另一端後各自獨立").pack(side=tk.LEFT)
        state["endcap_fw_follow_var"] = follow_var
        state["endcap_fw_value_var"] = value_var
        state["endcap_fw_widget"] = entry
        return start_row + 1

    def _render_owned_bottom_wrap(self, parent, context, start_row, projection, state):
        if not projection:
            return start_row
        box = ttk.LabelFrame(parent, text="下方包覆貼外預留", padding=4)
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
        reserve_u_var = tk.StringVar(master=box, value=setting_number_text(projection.get("reserve_u")))
        reserve_v_var = tk.StringVar(master=box, value=setting_number_text(projection.get("reserve_v")))
        ttk.Label(box, text="X 預留 (mm)").grid(row=0, column=0, sticky="e")
        u_entry = ttk.Entry(box, textvariable=reserve_u_var, width=8, justify=tk.CENTER)
        u_entry.grid(row=0, column=1, padx=(3, 10))
        ttk.Label(box, text="Y 預留 (mm)").grid(row=0, column=2, sticky="e")
        v_entry = ttk.Entry(box, textvariable=reserve_v_var, width=8, justify=tk.CENTER)
        v_entry.grid(row=0, column=3, padx=3)
        if self._bottom_wrap_commit is not None:
            for entry in (u_entry, v_entry):
                entry.bind(
                    "<Return>",
                    lambda _e, p=context, u=reserve_u_var, v=reserve_v_var: self._bottom_wrap_commit(p, u, v),
                )
                entry.bind(
                    "<FocusOut>",
                    lambda _e, p=context, u=reserve_u_var, v=reserve_v_var: self._bottom_wrap_commit(p, u, v),
                )
        ttk.Label(
            box,
            text="WRAP 關係由組合方式／Joint Graph 決定；此處只調整預留。封頭/封尾先連動，修改另一端後才獨立。",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 0))
        state["bottom_wrap_enabled_var"] = None
        state["bottom_wrap_reserve_u_var"] = reserve_u_var
        state["bottom_wrap_reserve_v_var"] = reserve_v_var
        state["bottom_wrap_widget"] = box
        return start_row + 1

    def _render_owned_corner(self, parent, context, start_row, projection, state):
        fixed_summary_var = state["fixed_corner_summary_var"]
        mode = str(projection.get("mode") or "none")
        if mode == "none":
            return start_row
        if mode == "fixed":
            summary = str(projection.get("summary") or "")
            if not summary:
                return start_row
            box = ttk.LabelFrame(parent, text="截角類型（固定 / 唯讀）", padding=4)
            box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
            fixed_summary_var.set(summary)
            ttk.Label(box, textvariable=fixed_summary_var, wraplength=900).pack(anchor=tk.W)
            return start_row + 1

        type_editable = bool(projection.get("type_editable", False))
        params_unlocked = bool(projection.get("params_unlocked", False))
        params_editable = bool(projection.get("params_editable", False))
        box = ttk.LabelFrame(
            parent,
            text="截角類型" if type_editable else "截角類型（基準預設）",
            padding=4,
        )
        box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))

        for pair in tuple(projection.get("pairs") or ()):
            pair = dict(pair or {})
            pair_key = str(pair.get("pair_key") or "")
            row = ttk.Frame(box)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=str(pair.get("label") or ""), width=6).pack(side=tk.LEFT)
            same_var = tk.BooleanVar(master=row, value=bool(pair.get("same", False)))
            state["corner_pair_vars"][pair_key] = same_var
            same_cb = ttk.Checkbutton(
                row,
                text="左右相同",
                variable=same_var,
                command=(
                    (lambda p=context, pair=pair_key, v=same_var: self._corner_pair_changed(p, pair, v))
                    if self._corner_pair_changed is not None else None
                ),
            )
            same_cb.configure(state=("normal" if params_editable else "disabled"))
            state["corner_pair_checkbuttons"][pair_key] = same_cb
            if params_unlocked:
                same_cb.pack(side=tk.LEFT, padx=(0, 6))

            targets = tuple(pair.get("targets") or ())
            for target_item in targets:
                target_item = dict(target_item or {})
                target_key = str(target_item.get("target_key") or "")
                target = ttk.Frame(row)
                target.pack(side=tk.LEFT, padx=(3, 8))
                side_label = str(target_item.get("side_label") or "")
                if side_label:
                    ttk.Label(target, text=side_label).grid(row=0, column=0, sticky="w")

                type_var = tk.StringVar(master=target, value=str(target_item.get("type_label") or ""))
                state["corner_type_vars"][target_key] = type_var
                type_cb = build_choice_menubutton(
                    target,
                    variable=type_var,
                    values=tuple(target_item.get("type_options") or ()),
                    state=("normal" if type_editable and not bool(target_item.get("top_assembly_owned")) else "disabled"),
                    width=12,
                    command=(
                        (lambda p=context, t=target_key: self._corner_type_selected(p, t))
                        if self._corner_type_selected is not None else None
                    ),
                )
                type_cb.grid(row=0, column=1, padx=2, sticky="w")

                subrow = ttk.Frame(target)
                state["corner_detail_frames"][target_key] = subrow
                amount_var = tk.StringVar(
                    master=subrow,
                    value=setting_number_text(target_item.get("amount_t", 1.0)),
                )
                state["corner_amount_vars"][target_key] = amount_var

                if params_unlocked:
                    subrow.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
                else:
                    ttk.Label(
                        target,
                        text=str(target_item.get("parameter_summary") or ""),
                    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

                kind = str(target_item.get("type_kind") or "")
                if kind == "CROSS":
                    mode_var = tk.StringVar(master=subrow, value=str(target_item.get("mode_label") or ""))
                    state["corner_mode_vars"][target_key] = mode_var
                    mode_cb = build_choice_menubutton(
                        subrow,
                        variable=mode_var,
                        values=("標準", "單邊留肉", "多切"),
                        state=("normal" if params_editable else "disabled"),
                        width=9,
                        command=(
                            (lambda p=context, t=target_key: self._corner_mode_selected(p, t))
                            if self._corner_mode_selected is not None else None
                        ),
                    )
                    mode_cb.pack(side=tk.LEFT, padx=(0, 3))
                    if str(target_item.get("mode_kind") or "") != "STANDARD":
                        direction_var = tk.StringVar(
                            master=subrow,
                            value=str(target_item.get("direction_label") or ""),
                        )
                        state["corner_direction_vars"][target_key] = direction_var
                        direction_cb = build_choice_menubutton(
                            subrow,
                            variable=direction_var,
                            values=tuple(target_item.get("direction_options") or ()),
                            state=("normal" if params_editable else "disabled"),
                            width=7,
                            command=(
                                (lambda p=context, t=target_key: self._corner_target_changed(p, t))
                                if self._corner_target_changed is not None else None
                            ),
                        )
                        direction_cb.pack(side=tk.LEFT, padx=3)
                        entry = ttk.Entry(subrow, textvariable=amount_var, width=6, justify=tk.CENTER)
                        entry.configure(state=("normal" if params_editable else "disabled"))
                        entry.pack(side=tk.LEFT, padx=(3, 1))
                        ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                        if self._corner_target_changed is not None:
                            entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                            entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                elif kind in {"OVERLAY", "INSERT"}:
                    action = "留肉（高）" if kind == "OVERLAY" else "多切（高）"
                    ttk.Label(subrow, text=action).pack(side=tk.LEFT, padx=(0, 3))
                    entry = ttk.Entry(subrow, textvariable=amount_var, width=6, justify=tk.CENTER)
                    entry.configure(state=("normal" if params_editable else "disabled"))
                    entry.pack(side=tk.LEFT, padx=(3, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    if self._corner_target_changed is not None:
                        entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                        entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                else:
                    ttk.Label(subrow, text="貼外留肉（高）").pack(side=tk.LEFT, padx=(0, 2))
                    primary = ttk.Entry(subrow, textvariable=amount_var, width=5, justify=tk.CENTER)
                    primary.configure(state=("normal" if params_editable else "disabled"))
                    primary.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    retain_var = tk.StringVar(
                        master=subrow,
                        value=setting_number_text(target_item.get("secondary_retain_t", 0)),
                    )
                    depth_var = tk.StringVar(
                        master=subrow,
                        value=setting_number_text(target_item.get("secondary_depth_t", 0)),
                    )
                    state["corner_secondary_retain_vars"][target_key] = retain_var
                    state["corner_secondary_depth_vars"][target_key] = depth_var
                    ttk.Label(subrow, text="  嵌入留肉").pack(side=tk.LEFT)
                    retain = ttk.Entry(subrow, textvariable=retain_var, width=5, justify=tk.CENTER)
                    retain.configure(state=("normal" if params_editable else "disabled"))
                    retain.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T  深度").pack(side=tk.LEFT)
                    depth = ttk.Entry(subrow, textvariable=depth_var, width=5, justify=tk.CENTER)
                    depth.configure(state=("normal" if params_editable else "disabled"))
                    depth.pack(side=tk.LEFT, padx=(1, 1))
                    ttk.Label(subrow, text="T").pack(side=tk.LEFT)
                    if self._corner_target_changed is not None:
                        for entry in (primary, retain, depth):
                            entry.bind("<Return>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
                            entry.bind("<FocusOut>", lambda _e, p=context, t=target_key: self._corner_target_changed(p, t))
        return start_row + 1

    def render_context_extensions(self, parent, context, start_row):
        """Dispatch Settings context extensions through the canonical panel owner."""
        if self._context_extension_projection is not None:
            return self.render_owned_context_extensions(parent, context, start_row)
        if self._render_context_extensions is not None:
            # Compatibility fallback for callers not yet migrated to the owned projection seam.
            return self._render_context_extensions(parent, context, start_row)
        return SettingsPanelExtensionResult(next_row=int(start_row), state=None)

    def render_owned_context_extensions(self, parent, context, start_row):
        """Render the live Settings extension cluster inside the canonical panel owner."""
        if self._context_extension_projection is None:
            return SettingsPanelExtensionResult(next_row=int(start_row), state={})
        projection = dict(self._context_extension_projection(str(context)) or {})
        state = {
            "corner_pair_vars": {},
            "corner_pair_checkbuttons": {},
            "corner_type_vars": {},
            "corner_mode_vars": {},
            "corner_direction_vars": {},
            "corner_amount_vars": {},
            "corner_secondary_retain_vars": {},
            "corner_secondary_depth_vars": {},
            "corner_detail_frames": {},
            "fixed_corner_summary_var": tk.StringVar(master=parent, value=""),
            "corner_param_lock_button": None,
            "endcap_fw_follow_var": None,
            "endcap_fw_value_var": None,
            "endcap_fw_widget": None,
            "bottom_wrap_enabled_var": None,
            "bottom_wrap_reserve_u_var": None,
            "bottom_wrap_reserve_v_var": None,
            "bottom_wrap_widget": None,
        }
        next_row = int(start_row)
        box_projection = projection.get("box_structure")
        if box_projection:
            next_row = self._render_owned_box_structure(
                parent, next_row, dict(box_projection), state
            )
        endcap_projection = projection.get("endcap_fw")
        if endcap_projection:
            next_row = self._render_owned_endcap_fw(
                parent, str(context), next_row, dict(endcap_projection), state
            )
        bottom_projection = projection.get("bottom_wrap")
        if bottom_projection:
            next_row = self._render_owned_bottom_wrap(
                parent, str(context), next_row, dict(bottom_projection), state
            )
        corner_projection = dict(projection.get("corner") or {"mode": "none"})
        next_row = self._render_owned_corner(
            parent, str(context), next_row, corner_projection, state
        )
        return SettingsPanelExtensionResult(next_row=next_row, state=state)


