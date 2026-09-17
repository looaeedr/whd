from pathlib import Path

VIEW = Path("gui_modules/editors/hole_editor_view.py")
GUI = Path("gui.py")

view = VIEW.read_text(encoding="utf-8")
old_tk_import = "from tkinter import messagebox\n"
new_tk_import = "from tkinter import messagebox, ttk\n"
if old_tk_import in view:
    view = view.replace(old_tk_import, new_tk_import, 1)
elif new_tk_import not in view:
    raise SystemExit("tkinter ttk import anchor missing")

builder = '''class HoleEditorWindowShellBuilder:
    """Build the transient editor window shell without owning editor state."""

    def __init__(self, host):
        self.host = host

    @staticmethod
    def window_geometry(screen_w, screen_h):
        win_w = max(720, min(1280, screen_w - 80))
        win_h = max(560, min(820, screen_h - 120))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        return win_w, win_h, pos_x, pos_y, f"{win_w}x{win_h}+{pos_x}+{pos_y}"

    def build(
        self, title, *, part_key, door_indicator_state,
        indicator_component_context_provider, baseline_status_text,
    ):
        host = self.host
        editor = tk.Toplevel(host.root)
        host.last_unified_hole_editor = editor
        editor.title(f"{title} — 統一開孔編輯器")
        editor.configure(bg=host.COLOR_BG)
        editor.transient(host.root)
        editor.grab_set()
        win_w, win_h, _pos_x, _pos_y, geometry = self.window_geometry(
            editor.winfo_screenwidth(), editor.winfo_screenheight()
        )
        fullscreen_state = [False]
        fullscreen_restore_geometry = [None]
        editor.geometry(geometry)
        editor.minsize(min(760, win_w), min(560, win_h))

        body = tk.Frame(editor, bg=host.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left = tk.Frame(
            body, bg=host.COLOR_PANEL, width=min(320, max(270, win_w // 4))
        )
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        left_insert_bar = tk.Frame(left, bg=host.COLOR_PANEL)
        left_insert_bar.pack(side=tk.BOTTOM, fill=tk.X)
        center = tk.Frame(body, bg=host.COLOR_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        editor_tabs = None
        main_page = None
        indicator_page = None
        component_tabs = None
        indicator_door_page = None
        indicator_page_visible = [False]
        if (
            part_key == "door"
            and door_indicator_state is not None
            and indicator_component_context_provider is not None
        ):
            editor_tabs = ttk.Notebook(center, height=32)
            main_page = tk.Frame(editor_tabs, bg=host.COLOR_BG)
            indicator_page = tk.Frame(editor_tabs, bg=host.COLOR_BG)
            editor_tabs.add(main_page, text="  門板  ")
            editor_tabs.pack(fill=tk.X, pady=(0, 4))
            component_tabs = ttk.Notebook(center, height=30)
            indicator_box_page = tk.Frame(component_tabs, bg=host.COLOR_BG)
            indicator_door_page = tk.Frame(component_tabs, bg=host.COLOR_BG)
            component_tabs.add(indicator_box_page, text="  盒體（基準檔＋指示燈）  ")
            component_tabs.add(indicator_door_page, text="  小門（基準檔）  ")

        big_font = ('Microsoft JhengHei', 15, 'bold')
        entry_font = ('Consolas', 12, 'bold')
        normal_font = ('Microsoft JhengHei', 11)
        baseline_status_var = tk.StringVar(value=str(baseline_status_text or ""))
        baseline_status_label = None
        if baseline_status_text or indicator_component_context_provider is not None:
            baseline_status_label = tk.Label(
                left, textvariable=baseline_status_var, bg=host.COLOR_PANEL,
                fg=("#64d2ff" if str(baseline_status_text or "").startswith("基準檔：") else "#ff9f0a"),
                font=('Microsoft JhengHei', 9, 'bold'), anchor=tk.W,
                justify=tk.LEFT, wraplength=285,
            )
            baseline_status_label.pack(fill=tk.X, padx=10, pady=(7, 2))

        return (
            editor, fullscreen_state, fullscreen_restore_geometry,
            left, left_insert_bar, center,
            editor_tabs, main_page, indicator_page, component_tabs,
            indicator_door_page, indicator_page_visible,
            big_font, entry_font, normal_font,
            baseline_status_var, baseline_status_label,
        )


'''
class_anchor = "class HoleEditorCanvasViewFactory:\n"
if "class HoleEditorWindowShellBuilder:" not in view:
    if view.count(class_anchor) != 1:
        raise SystemExit(f"window shell class anchor mismatch: {view.count(class_anchor)}")
    view = view.replace(class_anchor, builder + class_anchor, 1)
VIEW.write_text(view, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
import_anchor = "    HoleEditorCanvasViewFactory as _HoleEditorCanvasViewFactory,\n"
builder_import = "    HoleEditorWindowShellBuilder as _HoleEditorWindowShellBuilder,\n"
if builder_import not in gui:
    if gui.count(import_anchor) != 1:
        raise SystemExit(f"GUI window shell import anchor mismatch: {gui.count(import_anchor)}")
    gui = gui.replace(import_anchor, import_anchor + builder_import, 1)

method_start = gui.index("    def _open_unified_hole_editor(")
block_start = gui.index("        editor = tk.Toplevel(self.root)\n", method_start)
next_anchor = "        indicator_redraw = [None]\n"
block_end = gui.index(next_anchor, block_start)
replacement = '''        (
            editor, fullscreen_state, fullscreen_restore_geometry,
            left, left_insert_bar, center,
            editor_tabs, main_page, indicator_page, component_tabs,
            indicator_door_page, indicator_page_visible,
            big_font, entry_font, normal_font,
            baseline_status_var, baseline_status_label,
        ) = _HoleEditorWindowShellBuilder(self).build(
            title,
            part_key=part_key,
            door_indicator_state=door_indicator_state,
            indicator_component_context_provider=indicator_component_context_provider,
            baseline_status_text=baseline_status_text,
        )

'''
gui = gui[:block_start] + replacement + gui[block_end:]
GUI.write_text(gui, encoding="utf-8")
