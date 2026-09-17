from pathlib import Path

VIEW = Path("gui_modules/editors/hole_editor_view.py")
GUI = Path("gui.py")

view = VIEW.read_text(encoding="utf-8")
builder = '''class HoleEditorCenterWorkspaceBuilder:
    """Build center workspace widgets without owning editor actions."""

    def __init__(self, host):
        self.host = host

    def build(self, *, center):
        host = self.host
        toolbar = tk.Frame(center, bg=host.COLOR_PANEL)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            toolbar, text="旋轉", bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(side=tk.LEFT, padx=(10, 6), pady=6)
        rotation_buttons = []
        for angle in (90, 180, 270, 360):
            btn = tk.Button(
                toolbar, text=f"{angle}°", bg="#3a3a44", fg="white", bd=0,
                font=('Microsoft JhengHei', 11, 'bold'), padx=10, pady=4,
            )
            btn.pack(side=tk.LEFT, padx=3, pady=4)
            rotation_buttons.append((angle, btn))
        fullscreen_btn = tk.Button(
            toolbar, text="全螢幕", bg="#0a84ff", fg="white", bd=0,
            font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4,
        )
        fullscreen_btn.pack(side=tk.LEFT, padx=(12, 3), pady=4)
        undo_btn = tk.Button(
            toolbar, text="↶ 回上一步", bg="#636366", fg="white", bd=0,
            font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4,
        )
        undo_btn.pack(side=tk.LEFT, padx=(8, 3), pady=4)
        tk.Label(
            toolbar, text="雙擊已開孔：切穿 ⇄ 盲孔　右鍵孔：選十字基準",
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 10),
        ).pack(side=tk.RIGHT, padx=10)

        canvas = tk.Canvas(center, bg=host.COLOR_CANVAS_BG, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        host.last_hole_editor_canvas = canvas

        footer = tk.Frame(center, bg=host.COLOR_PANEL)
        footer.pack(fill=tk.X, pady=(6, 0))
        confirm_all_btn = tk.Button(
            footer, text="確定全部", bg="#30d158", fg="white", bd=0,
            font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7,
        )
        confirm_all_btn.pack(side=tk.RIGHT, padx=(6, 10), pady=6)
        cancel_all_btn = tk.Button(
            footer, text="取消全部", bg="#ff453a", fg="white", bd=0,
            font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7,
        )
        cancel_all_btn.pack(side=tk.RIGHT, padx=6, pady=6)
        tk.Label(
            footer, text="Esc：取消目前插入／定位；沒有進行中的操作時則取消全部",
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 10),
        ).pack(side=tk.LEFT, padx=10)
        return (
            toolbar, rotation_buttons, fullscreen_btn, undo_btn,
            canvas, confirm_all_btn, cancel_all_btn,
        )


'''
anchor = "class HoleEditorCatalogSidebarBuilder:\n"
if "class HoleEditorCenterWorkspaceBuilder:" not in view:
    if view.count(anchor) != 1:
        raise SystemExit(f"center workspace class anchor mismatch: {view.count(anchor)}")
    view = view.replace(anchor, builder + anchor, 1)
VIEW.write_text(view, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
import_anchor = "    HoleEditorCatalogSidebarBuilder as _HoleEditorCatalogSidebarBuilder,\n"
builder_import = "    HoleEditorCenterWorkspaceBuilder as _HoleEditorCenterWorkspaceBuilder,\n"
if builder_import not in gui:
    if gui.count(import_anchor) != 1:
        raise SystemExit(f"GUI center workspace import anchor mismatch: {gui.count(import_anchor)}")
    gui = gui.replace(import_anchor, import_anchor + builder_import, 1)

method_start = gui.index("    def _open_unified_hole_editor(")
block_start = gui.index("        # ---- center: always-visible rotation + canvas + whole-editor actions ----\n", method_start)
next_anchor = "        indicator_fit_error = [None]\n"
block_end = gui.index(next_anchor, block_start)
replacement = '''        (
            toolbar, rotation_buttons, fullscreen_btn, undo_btn,
            canvas, confirm_all_btn, cancel_all_btn,
        ) = _HoleEditorCenterWorkspaceBuilder(self).build(center=center)

        fullscreen_actions = _HoleEditorFullscreenActions(
            editor=editor,
            fullscreen_button=fullscreen_btn,
            fullscreen_state=fullscreen_state,
            restore_geometry=fullscreen_restore_geometry,
            redraw_provider=lambda: redraw,
        )
        toggle_fullscreen = fullscreen_actions.toggle_fullscreen
        fullscreen_btn.configure(command=toggle_fullscreen)

'''
gui = gui[:block_start] + replacement + gui[block_end:]
GUI.write_text(gui, encoding="utf-8")
