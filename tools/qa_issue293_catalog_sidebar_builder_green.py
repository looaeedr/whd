from pathlib import Path

VIEW = Path("gui_modules/editors/hole_editor_view.py")
GUI = Path("gui.py")

view = VIEW.read_text(encoding="utf-8")
builder = '''class HoleEditorCatalogSidebarBuilder:
    """Build catalog/custom/created-list widgets without owning editor behavior."""

    def __init__(self, host):
        self.host = host

    def build(
        self, *, left, left_insert_bar, big_font, normal_font, entry_font,
        catalog_label_by_definition, general_catalog_defs, pipe_catalog_defs,
        ref_entries_provider,
    ):
        host = self.host
        tk.Label(
            left, text="一般開孔", bg=host.COLOR_PANEL, fg="#30d158",
            font=('Microsoft JhengHei', 13, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(10, 3))
        catalog_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#0a84ff", font=('Microsoft JhengHei', 11),
            height=6, exportselection=False,
        )
        catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        general_labels = [
            catalog_label_by_definition[id(definition)]
            for definition in general_catalog_defs
        ] + ["＋ 自訂圓孔", "＋ 自訂方孔"]
        for label in general_labels:
            catalog_list.insert(tk.END, label)

        tk.Label(
            left, text="管孔清單", bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 13, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(5, 3))
        pipe_catalog_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#bf5af2", font=('Microsoft JhengHei', 11),
            height=5, exportselection=False,
        )
        pipe_catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        pipe_labels = [
            catalog_label_by_definition[id(definition)]
            for definition in pipe_catalog_defs
        ]
        for label in pipe_labels:
            pipe_catalog_list.insert(tk.END, label)

        first_label = general_labels[0] if general_labels else (pipe_labels[0] if pipe_labels else "")
        if general_labels:
            catalog_list.selection_set(0)
        elif pipe_labels:
            pipe_catalog_list.selection_set(0)
        selected_catalog_text = tk.StringVar(value=first_label)
        tk.Label(
            left, textvariable=selected_catalog_text, bg="#2c2c34", fg="#ffd60a",
            anchor=tk.W, font=('Microsoft JhengHei', 10, 'bold'), wraplength=285,
            padx=8, pady=5,
        ).pack(fill=tk.X, padx=10, pady=(2, 5))

        custom_frame = tk.LabelFrame(
            left, text=" 自訂尺寸 ", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT_MUTED, font=normal_font,
        )
        custom_frame.pack(fill=tk.X, padx=10, pady=4)
        var_d = tk.StringVar(value="22.0")
        var_w = tk.StringVar(value="40.0")
        var_h = tk.StringVar(value="40.0")
        var_blind = tk.BooleanVar(value=False)
        var_rotation = tk.StringVar(value="360°")
        form_row_builders = HoleEditorFormRowBuilders(
            panel_bg=host.COLOR_PANEL,
            text_color=host.COLOR_TEXT,
            normal_font=normal_font,
            entry_font=entry_font,
            ref_entries_provider=ref_entries_provider,
        )
        form_row_builders.small_row(custom_frame, "直徑", var_d)
        form_row_builders.small_row(custom_frame, "寬 W", var_w)
        form_row_builders.small_row(custom_frame, "高 H", var_h)
        tk.Checkbutton(
            custom_frame, text="盲孔", variable=var_blind,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG, activebackground=host.COLOR_PANEL,
            font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(anchor=tk.W, padx=6, pady=3)

        insert_mode = [False]
        insert_btn = tk.Button(
            left_insert_bar, text="插入", bg="#30d158", fg="white",
            font=big_font, bd=0, pady=8,
        )
        insert_btn.pack(fill=tk.X, padx=10, pady=(7, 8))
        host.last_hole_editor_insert_button = insert_btn

        tk.Label(
            left, text="已開孔（雙擊：切穿 ⇄ 盲孔）", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT, font=('Microsoft JhengHei', 12, 'bold'),
        ).pack(fill=tk.X, padx=10, pady=(5, 3))
        created_list = tk.Listbox(
            left, bg=host.COLOR_INPUT_BG, fg=host.COLOR_TEXT,
            selectbackground="#5e5ce6", font=('Microsoft JhengHei', 12),
            height=9, exportselection=False,
        )
        created_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        delete_btn = tk.Button(
            left, text="刪除選中", bg="#ff453a", fg="white",
            font=('Microsoft JhengHei', 12, 'bold'), bd=0, pady=6,
        )
        delete_btn.pack(fill=tk.X, padx=10, pady=(3, 10))
        return (
            catalog_list, pipe_catalog_list, selected_catalog_text,
            var_d, var_w, var_h, var_blind, var_rotation,
            form_row_builders, insert_mode, insert_btn, created_list, delete_btn,
        )


'''
anchor = "class HoleEditorIndicatorPanelBuilder:\n"
if "class HoleEditorCatalogSidebarBuilder:" not in view:
    if view.count(anchor) != 1:
        raise SystemExit(f"catalog sidebar class anchor mismatch: {view.count(anchor)}")
    view = view.replace(anchor, builder + anchor, 1)
VIEW.write_text(view, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
import_anchor = "    HoleEditorCatalogControls as _HoleEditorCatalogControls,\n"
builder_import = "    HoleEditorCatalogSidebarBuilder as _HoleEditorCatalogSidebarBuilder,\n"
if builder_import not in gui:
    if gui.count(import_anchor) != 1:
        raise SystemExit(f"GUI catalog sidebar import anchor mismatch: {gui.count(import_anchor)}")
    gui = gui.replace(import_anchor, import_anchor + builder_import, 1)

method_start = gui.index("    def _open_unified_hole_editor(")
block_start = gui.index("        # ---- left: catalog ----\n", method_start)
next_anchor = "        # ---- center: always-visible rotation + canvas + whole-editor actions ----\n"
block_end = gui.index(next_anchor, block_start)
replacement = '''        (
            catalog_list, pipe_catalog_list, selected_catalog_text,
            var_d, var_w, var_h, var_blind, var_rotation,
            form_row_builders, insert_mode, insert_btn, created_list, delete_btn,
        ) = _HoleEditorCatalogSidebarBuilder(self).build(
            left=left,
            left_insert_bar=left_insert_bar,
            big_font=big_font,
            normal_font=normal_font,
            entry_font=entry_font,
            catalog_label_by_definition=catalog_label_by_definition,
            general_catalog_defs=general_catalog_defs,
            pipe_catalog_defs=pipe_catalog_defs,
            ref_entries_provider=lambda: ref_entries,
        )

'''
gui = gui[:block_start] + replacement + gui[block_end:]
GUI.write_text(gui, encoding="utf-8")
