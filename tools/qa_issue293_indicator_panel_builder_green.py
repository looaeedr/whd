from pathlib import Path

VIEW = Path("gui_modules/editors/hole_editor_view.py")
GUI = Path("gui.py")

view = VIEW.read_text(encoding="utf-8")
builder = '''class HoleEditorIndicatorPanelBuilder:
    """Build Door indicator controls while leaving state/validation elsewhere."""

    def __init__(self, host):
        self.host = host

    def build(
        self, *, left, part_key, door_indicator_state,
        request_redraw, on_box_distance_toggle,
    ):
        if part_key != "door" or door_indicator_state is None:
            return None, None, [], None, None, None

        host = self.host
        seed_state = host._normalize_door_indicator_state(door_indicator_state)
        mode_var = tk.StringVar(value=seed_state["mode"])
        layers_var = tk.StringVar(value=str(seed_state["layers"]))
        group_vars = [
            tk.StringVar(value=str(int(seed_state["groups"][i])))
            for i in range(6)
        ]
        offset_x_var = tk.StringVar(
            value=host._door_layout_number_text(seed_state["offset_x"])
        )
        offset_y_var = tk.StringVar(
            value=host._door_layout_number_text(seed_state["offset_y"])
        )
        box_dist_var = tk.BooleanVar(value=seed_state["is_box_dist"])

        frame = tk.LabelFrame(
            left, text=" 門指示燈 / 指示燈盒子 ",
            bg=host.COLOR_PANEL, fg="#ffd60a",
            font=('Microsoft JhengHei', 11, 'bold'),
        )
        frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        mode_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        mode_row.pack(fill=tk.X, padx=5, pady=(3, 2))
        for text, value in (
            ("不使用", "none"),
            ("直接指示燈", "indicator"),
            ("指示燈盒子", "indicator_box"),
        ):
            tk.Radiobutton(
                mode_row, text=text, value=value, variable=mode_var,
                bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
                selectcolor=host.COLOR_INPUT_BG,
                activebackground=host.COLOR_PANEL, activeforeground=host.COLOR_TEXT,
                font=('Microsoft JhengHei', 9, 'bold'), command=request_redraw,
            ).pack(side=tk.LEFT, padx=(0, 5))

        layer_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        layer_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(
            layer_row, text="層數", bg=host.COLOR_PANEL,
            fg=host.COLOR_TEXT, width=5, anchor=tk.W,
        ).pack(side=tk.LEFT)
        layer_combo = ttk.Combobox(
            layer_row, textvariable=layers_var,
            values=["1", "2", "3", "4", "5", "6"], width=4, state="readonly",
        )
        layer_combo.pack(side=tk.LEFT)

        groups_frame = tk.Frame(frame, bg=host.COLOR_PANEL)
        groups_frame.pack(fill=tk.X, padx=6, pady=2)
        group_controls = HoleEditorIndicatorGroupControls(
            groups_frame=groups_frame, layers_var=layers_var,
            group_vars=group_vars, request_redraw=request_redraw,
            panel_bg=host.COLOR_PANEL, muted_color=host.COLOR_TEXT_MUTED,
        )
        layer_combo.bind("<<ComboboxSelected>>", group_controls.rebuild)
        group_controls.rebuild()

        pos_row = tk.Frame(frame, bg=host.COLOR_PANEL)
        pos_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(pos_row, text="X", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        x_entry = tk.Entry(pos_row, textvariable=offset_x_var, width=6, justify=tk.CENTER)
        x_entry.pack(side=tk.LEFT, padx=(2, 6))
        tk.Label(pos_row, text="Y", bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        y_entry = tk.Entry(pos_row, textvariable=offset_y_var, width=6, justify=tk.CENTER)
        y_entry.pack(side=tk.LEFT, padx=(2, 6))
        tk.Button(
            pos_row, text="置中",
            command=lambda: (offset_x_var.set("0"), offset_y_var.set("0"), request_redraw()),
            bg="#3a3a44", fg="white", bd=0,
        ).pack(side=tk.LEFT)
        x_entry.bind("<KeyRelease>", request_redraw)
        y_entry.bind("<KeyRelease>", request_redraw)
        tk.Checkbutton(
            frame, text="箱體定位距離", variable=box_dist_var,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG, activebackground=host.COLOR_PANEL,
            command=on_box_distance_toggle, font=('Microsoft JhengHei', 9),
        ).pack(anchor=tk.W, padx=6, pady=(1, 4))
        return mode_var, layers_var, group_vars, offset_x_var, offset_y_var, box_dist_var


'''
anchor = "class HoleEditorWindowShellBuilder:\n"
if "class HoleEditorIndicatorPanelBuilder:" not in view:
    if view.count(anchor) != 1:
        raise SystemExit(f"indicator panel class anchor mismatch: {view.count(anchor)}")
    view = view.replace(anchor, builder + anchor, 1)
VIEW.write_text(view, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
import_anchor = "    HoleEditorIndicatorGroupControls as _HoleEditorIndicatorGroupControls,\n"
builder_import = "    HoleEditorIndicatorPanelBuilder as _HoleEditorIndicatorPanelBuilder,\n"
if builder_import not in gui:
    if gui.count(import_anchor) != 1:
        raise SystemExit(f"GUI indicator panel import anchor mismatch: {gui.count(import_anchor)}")
    gui = gui.replace(import_anchor, import_anchor + builder_import, 1)

method_start = gui.index("    def _open_unified_hole_editor(")
block_start = gui.index('        if part_key == "door" and door_indicator_state is not None:\n', method_start)
next_anchor = "        # ---- left: catalog ----\n"
block_end = gui.index(next_anchor, block_start)
replacement = '''        (
            indicator_mode_var, indicator_layers_var, indicator_group_vars,
            indicator_offset_x_var, indicator_offset_y_var, indicator_box_dist_var,
        ) = _HoleEditorIndicatorPanelBuilder(self).build(
            left=left,
            part_key=part_key,
            door_indicator_state=door_indicator_state,
            request_redraw=request_indicator_redraw,
            on_box_distance_toggle=on_box_distance_toggle,
        )

'''
gui = gui[:block_start] + replacement + gui[block_end:]
GUI.write_text(gui, encoding="utf-8")
