from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, got {count}")
    return text.replace(old, new, 1)


path = Path("phase6_settings_panel.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    kwargs = {"textvariable": variable, "state": state}\n',
    '    kwargs = {"textvariable": variable, "state": state, "takefocus": True}\n',
    "dropdown takefocus",
)
text = replace_once(
    text,
    '    menu = tk.Menu(button, tearoff=False)\n',
    '    menu = tk.Menu(\n        button, tearoff=False, relief=tk.RAISED, borderwidth=1, activeborderwidth=1\n    )\n',
    "dropdown floating border",
)
text = replace_once(
    text,
    '    button.configure(menu=menu)\n    button._phase6_menu = menu\n    return button\n',
    '    button.configure(menu=menu)\n    button._phase6_menu = menu\n    button._phase6_foreground_role = "dropdown"\n    menu._phase6_foreground_role = "floating_menu"\n    return button\n',
    "dropdown roles",
)
keyboard_lines = [
    '    def _scroll_settings_keyboard(self, event):',
    '        """Keyboard reachability for the existing settings scroll owner."""',
    '        canvas = self.settings_scroll_canvas',
    '        if canvas is None:',
    '            return "break"',
    '        key = str(getattr(event, "keysym", "") or "")',
    '        try:',
    '            if key == "Home":',
    '                canvas.yview_moveto(0.0)',
    '            elif key == "End":',
    '                canvas.yview_moveto(1.0)',
    '            elif key in {"Prior", "Page_Up"}:',
    '                canvas.yview_scroll(-1, "pages")',
    '            elif key in {"Next", "Page_Down"}:',
    '                canvas.yview_scroll(1, "pages")',
    '            else:',
    '                return None',
    '        except tk.TclError:',
    '            pass',
    '        return "break"',
    '',
    '',
]
keyboard_method = "\n".join(keyboard_lines)
text = replace_once(
    text,
    '    def _bind_settings_scroll_tree(self, widget):\n',
    keyboard_method + '    def _bind_settings_scroll_tree(self, widget):\n',
    "keyboard method",
)
text = replace_once(
    text,
    '            widget.bind("<Button-5>", self._scroll_settings_fields, add="+")\n',
    '            widget.bind("<Button-5>", self._scroll_settings_fields, add="+")\n            widget.bind("<Home>", self._scroll_settings_keyboard, add="+")\n            widget.bind("<End>", self._scroll_settings_keyboard, add="+")\n            widget.bind("<Prior>", self._scroll_settings_keyboard, add="+")\n            widget.bind("<Next>", self._scroll_settings_keyboard, add="+")\n',
    "keyboard bindings",
)
path.write_text(text, encoding="utf-8")


path = Path("fold_designer_bridge.py")
text = path.read_text(encoding="utf-8")
helper_lines = [
    'def _phase6_configure_floating_surface(window, owner, *, modal=False):',
    '    """Apply the shared foreground/focus contract without owning domain state."""',
    '    try:',
    '        window.transient(owner)',
    '    except Exception:',
    '        pass',
    '    try:',
    '        window.configure(takefocus=True)',
    '    except Exception:',
    '        pass',
    '    window._phase6_foreground_role = "floating_surface"',
    '    try:',
    '        window.bind("<Escape>", lambda _event: window.destroy(), add="+")',
    '        window.lift()',
    '        window.after_idle(window.focus_set)',
    '    except Exception:',
    '        pass',
    '    if modal:',
    '        try:',
    '            window.grab_set()',
    '        except Exception:',
    '            pass',
    '    return window',
    '',
    '',
    'def _phase6_status_projection(self):',
    '    """Project existing cabinet/part/view owners into one low-noise status line."""',
    '    family = _phase6_current_cabinet_family(self) or "-"',
    '    mode = str(getattr(self, "_phase6_3d_display_mode", "single") or "single")',
    '    if mode == "assembly":',
    '        part_text = "-"',
    '        view_text = "組合體"',
    '    elif mode == "corner_data":',
    '        part_key = (',
    '            getattr(self, "_phase6_corner_data_selected_part_key", None)',
    '            or getattr(self, "active_part_key", None)',
    '        )',
    '        part_text = _phase6_part_label(part_key) if part_key else "-"',
    '        view_text = "截角資料"',
    '    else:',
    '        part_key = getattr(self, "active_part_key", None)',
    '        part_text = _phase6_part_label(part_key) if part_key else "-"',
    '        view_text = "單件 3D"',
    '    return f"箱型：{family}  ｜  板件：{part_text}  ｜  視圖：{view_text}"',
    '',
    '',
    'def _phase6_refresh_status_bar(self):',
    '    """Refresh the projection sink only; never write selection/domain state."""',
    '    text = _phase6_status_projection(self)',
    '    var = getattr(self, "status_projection_var", None)',
    '    if var is not None and hasattr(var, "set"):',
    '        var.set(text)',
    '    return text',
    '',
    '',
]
helpers = "\n".join(helper_lines)
text = replace_once(
    text,
    'def _phase6_open_relief_registry_form(self):\n',
    helpers + 'def _phase6_open_relief_registry_form(self):\n',
    "UI helpers",
)
text = replace_once(
    text,
    '    win = original.tk.Toplevel(self.root)\n    win.title("PHASE6 截角資料庫 / 組合接合")\n    win.geometry("1120x720")\n',
    '    win = original.tk.Toplevel(self.root)\n    win.title("PHASE6 截角資料庫 / 組合接合")\n    win.geometry("1120x720")\n    _phase6_configure_floating_surface(win, self.root, modal=False)\n',
    "registry floating surface",
)
status_lines = [
    '    previous_status = getattr(self, "status_bar", None)',
    '    if previous_status is not None:',
    '        try:',
    '            previous_status.destroy()',
    '        except Exception:',
    '            pass',
    '    self.status_bar = original.ttk.Frame(self.root, padding=(8, 2))',
    '    original.ttk.Separator(',
    '        self.status_bar, orient=original.tk.HORIZONTAL',
    '    ).pack(fill=original.tk.X, pady=(0, 2))',
    '    self.status_projection_var = original.tk.StringVar(',
    '        master=self.status_bar, value=_phase6_status_projection(self)',
    '    )',
    '    self.status_projection_label = original.ttk.Label(',
    '        self.status_bar, textvariable=self.status_projection_var, anchor=original.tk.W',
    '    )',
    '    self.status_projection_label.pack(fill=original.tk.X)',
    '    self.status_bar.pack(side=original.tk.BOTTOM, fill=original.tk.X)',
    '',
    '',
]
status_block = "\n".join(status_lines)
text = replace_once(
    text,
    'def _phase6_build_persistent_top_area(self):\n    """固定版面：最上列命令；其下兩行全域設定；左右工作區。"""\n',
    'def _phase6_build_persistent_top_area(self):\n    """固定版面：最上列命令；其下兩行全域設定；左右工作區。"""\n' + status_block,
    "status bar build",
)
text = replace_once(
    text,
    '    _phase6_refresh_structure_tree(self)\n\n\ndef _fix11_refresh_part_button_states(self):\n',
    '    _phase6_refresh_structure_tree(self)\n    _phase6_refresh_status_bar(self)\n\n\ndef _fix11_refresh_part_button_states(self):\n',
    "status refresh from selector projection",
)
text = replace_once(
    text,
    '        _phase6_refresh_corner_data_unfold_view(self)\n    return resolved\n',
    '        _phase6_refresh_corner_data_unfold_view(self)\n    _phase6_refresh_status_bar(self)\n    return resolved\n',
    "corner-data status refresh",
)
path.write_text(text, encoding="utf-8")
