"""Composition root for the unified hole editor.

This module wires already-extracted editor controllers, presentation builders,
session authority, canvas authority, and manufacturing/geometry dependencies.
It owns no committed project or geometry state.
"""

from __future__ import annotations

from types import SimpleNamespace

from whd_theme import configure_tk_menu


class HoleEditorCompositionDependencies:
    """Explicit adapter for authorities currently imported by the GUI host module."""

    REQUIRED = (
        "RectGuide", "Vec2", "load_hole_catalog", "load_pipe_catalog",
        "_HoleEditorSessionFactory", "_HoleEditorWindowShellBuilder",
        "_HoleEditorIndicatorUiActions", "_HoleEditorIndicatorStateCollector",
        "_HoleEditorIndicatorPanelBuilder", "_HoleEditorCatalogSidebarBuilder",
        "_HoleEditorCenterWorkspaceBuilder", "_HoleEditorFullscreenActions",
        "_HoleEditorIndicatorFitValidation", "manufacturing_api", "messagebox", "tk",
        "_HoleEditorLiveContext", "_HoleEditorCanvasViewFactory",
        "render_secondary_scene", "render_resolved_features",
        "_HoleEditorSyncCoordinator", "_HoleEditorCreatedListPresentation",
        "_HoleEditorReferencePresentation", "feature_reference_anchor",
        "reference_distances", "door_enclosure_reference_guide", "DoorFrameEdges",
        "_HoleEditorCanvasRenderer", "door_enclosure_reference_offsets",
        "resolve_door_indicator_layout", "measure_door_indicator_position",
        "resolve_door_indicator_dimension_guides", "ResolvedRect", "HoleEditorCanvasFrame",
        "_HoleEditorFeatureFactory", "custom_circle_definition",
        "custom_rectangle_definition", "feature_from_definition",
        "feature_with_reference_anchor", "ReferenceAnchor", "_HoleEditorCatalogControls",
        "_HoleEditorTransientActions", "_HoleEditorCanvasPointerActions",
        "feature_is_within_surface", "move_feature_within_surface",
        "_HoleEditorCreatedListActions", "feature_with_process",
        "_HoleEditorReferenceActions", "move_feature_by_reference_distance",
        "_HoleEditorSelectedFeatureActions", "REFERENCE_ANCHOR_LABELS",
        "_HoleEditorRoundSettingsLauncher", "_open_round_hole_settings_impl",
        "_HoleEditorContextSwitcher", "_HoleEditorIndicatorContextRefresh",
        "_HoleEditorPageNavigation", "_HoleEditorModalLifecycle",
    )

    def __init__(self, namespace):
        self._namespace = namespace

    @classmethod
    def from_namespace(cls, namespace):
        missing = [name for name in cls.REQUIRED if name not in namespace]
        if missing:
            raise RuntimeError(f"hole-editor composition dependencies missing: {missing}")
        return cls(namespace)

    def __getattr__(self, name):
        try:
            return self._namespace[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _prepare_model(s):
    host, d = s.host, s.d
    s.feature_list = (
        host.surface_features[s.part_key]
        if s.feature_list_override is None else s.feature_list_override
    )
    s.hole_session = d._HoleEditorSessionFactory.create(
        "door", s.feature_list, max_undo_steps=50
    )
    if s.reference_guide is None:
        rminx, rminy, rmaxx, rmaxy = s.surface.polygon.bounds
        s.reference_guide = d.RectGuide(
            d.Vec2(rminx, rminy), d.Vec2(rmaxx, rmaxy), "finished_boundary"
        )
    hole_base_dir = d.manufacturing_api.operator_hole_catalog_root_path()
    s.general_catalog_defs = d.load_hole_catalog(hole_base_dir)
    s.pipe_catalog_defs = d.load_pipe_catalog(hole_base_dir)
    s.catalog_by_label = {}
    s.catalog_label_by_definition = {}
    for definition in s.general_catalog_defs + s.pipe_catalog_defs:
        if definition.shape == "circle":
            size_text = f"Ø{definition.diameter:g}"
        elif definition.shape == "rectangle":
            size_text = f"{definition.width:g}×{definition.height:g}"
        else:
            size_text = "DXF"
        process_text = (
            "盲孔" if definition.process == "BLIND_HOLE"
            else ("圖檔" if definition.process == "FROM_DXF" else "切穿")
        )
        label = f"{definition.name}  {size_text}  [{process_text}]"
        s.catalog_by_label[label] = definition
        s.catalog_label_by_definition[id(definition)] = label


def _build_shell_and_indicator(s):
    host, d = s.host, s.d
    (
        s.editor, s.fullscreen_state, s.fullscreen_restore_geometry,
        s.left, s.left_insert_bar, s.center,
        s.editor_tabs, s.main_page, s.indicator_page, s.component_tabs,
        s.indicator_door_page, s.indicator_page_visible,
        s.big_font, s.entry_font, s.normal_font,
        s.baseline_status_var, s.baseline_status_label,
    ) = d._HoleEditorWindowShellBuilder(host).build(
        s.title,
        part_key=s.part_key,
        door_indicator_state=s.door_indicator_state,
        indicator_component_context_provider=s.indicator_component_context_provider,
        baseline_status_text=s.baseline_status_text,
    )
    s.indicator_redraw = [None]
    s.indicator_context_refresh = [None]
    s.indicator_mode_var = None
    s.indicator_layers_var = None
    s.indicator_group_vars = []
    s.indicator_offset_x_var = None
    s.indicator_offset_y_var = None
    s.indicator_box_dist_var = None
    s.cabinet_locator_var = None
    if s.cabinet_reference_guide is not None:
        # Use the original release's "箱體定位距離" checkbox interaction,
        # not duplicate editable X/Y distance fields. This merely changes
        # the measurement guide, never the physical hole coordinates.
        s.cabinet_locator_var = d.tk.BooleanVar(master=s.editor, value=False)
        d.tk.Checkbutton(
            s.left, text="箱體定位距離", variable=s.cabinet_locator_var,
            bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
            selectcolor=host.COLOR_INPUT_BG,
            activebackground=host.COLOR_PANEL,
            command=lambda: (s.refresh_reference_fields(), s.redraw()),
        ).pack(fill=d.tk.X, padx=10, pady=(5, 4))
        s.editor._hole_cabinet_positioning = s.cabinet_locator_var
    indicator_ui_actions = d._HoleEditorIndicatorUiActions(
        editor_tabs=s.editor_tabs,
        indicator_page=s.indicator_page,
        main_page=s.main_page,
        indicator_page_visible=s.indicator_page_visible,
        mode_provider=lambda: (
            s.indicator_mode_var.get() if s.indicator_mode_var is not None else "none"
        ),
        context_refresh_provider=lambda: s.indicator_context_refresh[0],
        redraw_provider=lambda: s.indicator_redraw[0],
        schedule_idle=s.editor.after_idle,
        refresh_reference_fields=lambda: s.refresh_reference_fields(),
    )
    s.set_indicator_page_visible = indicator_ui_actions.set_indicator_page_visible
    s.request_indicator_redraw = indicator_ui_actions.request_indicator_redraw
    s.on_box_distance_toggle = indicator_ui_actions.on_box_distance_toggle
    indicator_state_collector = d._HoleEditorIndicatorStateCollector(
        mode_var_provider=lambda: s.indicator_mode_var,
        layers_var_provider=lambda: s.indicator_layers_var,
        group_vars_provider=lambda: s.indicator_group_vars,
        offset_x_var_provider=lambda: s.indicator_offset_x_var,
        offset_y_var_provider=lambda: s.indicator_offset_y_var,
        box_dist_var_provider=lambda: s.indicator_box_dist_var,
        normalize_state=lambda raw: host._normalize_door_indicator_state(
            d.manufacturing_api.normalize_operator_hole_editor_indicator_state(raw)
        ),
    )
    s.collect_indicator_state = indicator_state_collector.collect
    (
        s.indicator_mode_var, s.indicator_layers_var, s.indicator_group_vars,
        s.indicator_offset_x_var, s.indicator_offset_y_var, s.indicator_box_dist_var,
    ) = d._HoleEditorIndicatorPanelBuilder(host).build(
        left=s.left,
        part_key=s.part_key,
        door_indicator_state=s.door_indicator_state,
        request_redraw=s.request_indicator_redraw,
        on_box_distance_toggle=s.on_box_distance_toggle,
    )


def _build_sidebar_workspace_state(s):
    host, d = s.host, s.d
    s.ref_entries = {}
    (
        s.catalog_list, s.pipe_catalog_list, s.selected_catalog_text,
        s.var_d, s.var_w, s.var_h, s.var_blind, s.var_rotation,
        s.form_row_builders, s.insert_mode, s.insert_btn, s.created_list, s.delete_btn,
    ) = d._HoleEditorCatalogSidebarBuilder(host).build(
        left=s.left,
        left_insert_bar=s.left_insert_bar,
        big_font=s.big_font,
        normal_font=s.normal_font,
        entry_font=s.entry_font,
        catalog_label_by_definition=s.catalog_label_by_definition,
        general_catalog_defs=s.general_catalog_defs,
        pipe_catalog_defs=s.pipe_catalog_defs,
        ref_entries_provider=lambda: s.ref_entries,
    )
    (
        s.toolbar, s.rotation_buttons, s.fullscreen_btn, s.undo_btn,
        s.canvas, s.confirm_all_btn, s.cancel_all_btn,
    ) = d._HoleEditorCenterWorkspaceBuilder(host).build(center=s.center)
    fullscreen_actions = d._HoleEditorFullscreenActions(
        editor=s.editor,
        fullscreen_button=s.fullscreen_btn,
        fullscreen_state=s.fullscreen_state,
        restore_geometry=s.fullscreen_restore_geometry,
        redraw_provider=lambda: s.redraw,
    )
    s.toggle_fullscreen = fullscreen_actions.toggle_fullscreen
    s.fullscreen_btn.configure(command=s.toggle_fullscreen)
    header_fullscreen = getattr(s.editor, "_hole_header_fullscreen", None)
    if header_fullscreen is not None:
        header_fullscreen.configure(command=s.toggle_fullscreen)
    s.indicator_fit_error = [None]
    indicator_fit_validation = d._HoleEditorIndicatorFitValidation(
        door_indicator_state_provider=lambda: s.door_indicator_state,
        door_indicator_context_provider=lambda: s.door_indicator_context,
        door_thickness_provider=lambda: s.door_thickness,
        fit_error=s.indicator_fit_error,
        confirm_button=s.confirm_all_btn,
        collect_state=lambda: s.collect_indicator_state(),
        validate_fit=d.manufacturing_api.validate_door_indicator_fit,
        show_error=d.messagebox.showerror,
        normal_state=d.tk.NORMAL,
        disabled_state=d.tk.DISABLED,
    )
    s.validate_current_indicator_fit = indicator_fit_validation.validate
    s.manual_mark_mode = [False]
    s.manual_mark_length = None
    s.manual_mark_angle = None
    s.manual_mark_pattern = None
    s.manual_mark_dash = None
    s.manual_mark_gap = None
    s.manual_mark_status = None
    if getattr(s, "manual_marking_draft", None) is not None:
        mark_bar = d.tk.Frame(s.center, bg=host.COLOR_PANEL)
        mark_bar.pack(before=s.canvas, fill=d.tk.X, padx=4, pady=3)
        s.manual_mark_length = d.tk.StringVar(master=s.editor, value="60")
        s.manual_mark_angle = d.tk.StringVar(master=s.editor, value="0")
        s.manual_mark_pattern = d.tk.StringVar(master=s.editor, value="solid")
        s.manual_mark_dash = d.tk.StringVar(master=s.editor, value="10")
        s.manual_mark_gap = d.tk.StringVar(master=s.editor, value="5")
        mark_fields = (("長度 mm", s.manual_mark_length, 6), ("角度 °", s.manual_mark_angle, 5))
        if not s.solid_marking_only:
            mark_fields += (("實段 mm", s.manual_mark_dash, 5), ("留白 mm", s.manual_mark_gap, 5))
        for name, var, width in mark_fields:
            d.tk.Label(mark_bar, text=name, fg=host.COLOR_TEXT,
                       bg=host.COLOR_PANEL).pack(side=d.tk.LEFT, padx=(6, 1))
            d.tk.Entry(mark_bar, textvariable=var, width=width).pack(side=d.tk.LEFT)
        for label, value in (() if s.solid_marking_only else (("實線", "solid"), ("虛線", "dashed"))):
            d.tk.Radiobutton(
                mark_bar, text=label, value=value,
                variable=s.manual_mark_pattern, bg=host.COLOR_PANEL,
                fg=host.COLOR_TEXT, selectcolor=host.COLOR_INPUT_BG,
            ).pack(side=d.tk.LEFT, padx=2)
        s.manual_mark_draw_button = d.tk.Button(
            mark_bar, text="打標：中點放置", bg="#0a84ff", fg="white",
        )
        s.manual_mark_draw_button.pack(side=d.tk.LEFT, padx=5)
        s.manual_mark_select_button = d.tk.Button(
            mark_bar, text="選取", bg="#636366", fg="white",
        )
        s.manual_mark_select_button.pack(side=d.tk.LEFT, padx=2)
        if "circle" in s.manual_marking_draft.allowed_tools:
            s.manual_round_diameter = d.tk.StringVar(master=s.editor, value="")
            d.tk.Label(mark_bar, text="直徑 mm", fg=host.COLOR_TEXT,
                       bg=host.COLOR_PANEL).pack(side=d.tk.LEFT, padx=(6, 1))
            d.tk.Entry(mark_bar, textvariable=s.manual_round_diameter,
                       width=6).pack(side=d.tk.LEFT)
            s.manual_round_button = d.tk.Button(
                mark_bar, text="實線圓打標：選圓心", bg="#0a84ff", fg="white",
            )
            s.manual_round_button.pack(side=d.tk.LEFT, padx=3)
            s.editor._manual_round_marking_controls = (
                s.manual_round_button, s.manual_round_diameter,
            )
        s.manual_mark_status = d.tk.Label(
            s.center, text="", fg="#ff453a", bg=host.COLOR_PANEL,
            anchor="w",
        )
        s.manual_mark_status.pack(before=s.canvas, fill=d.tk.X, padx=10)
        s.editor._manual_marking_controls = (
            s.manual_mark_draw_button, s.manual_mark_select_button,
            s.manual_mark_status,
        )
        # Second-stage group tools. Only operator dimensions are gathered
        # here; all corner/arm geometry belongs to the Engine public API.
        s.manual_group_tool = ["select"]
        s.manual_group_arm_x = d.tk.StringVar(master=s.editor, value="20")
        s.manual_group_arm_y = d.tk.StringVar(master=s.editor, value="20")
        s.manual_group_spacing_x = d.tk.StringVar(master=s.editor, value="")
        s.manual_group_spacing_y = d.tk.StringVar(master=s.editor, value="")
        s.manual_group_angle = d.tk.StringVar(master=s.editor, value="0")
        s.manual_group_member = d.tk.StringVar(master=s.editor, value="")
        s.manual_group_offset_x = d.tk.StringVar(master=s.editor, value="0")
        s.manual_group_offset_y = d.tk.StringVar(master=s.editor, value="0")
        s.manual_group_tools = {}
        group_bar = d.tk.Frame(s.center, bg=host.COLOR_PANEL)
        if _has_group_mark_tools(s):
            group_bar.pack(before=s.canvas, fill=d.tk.X, padx=4, pady=(0, 2))
        for kind, label in (
            ("cross", "十字：交點"), ("l", "L：轉角"),
            ("pair_l", "一對L：群組中心"), ("quad_l", "四角L：群組中心"),
        ):
            if kind not in s.manual_marking_draft.allowed_tools:
                continue
            button = d.tk.Button(group_bar, text=label, bg="#3a3a44", fg="white")
            button.pack(side=d.tk.LEFT, padx=2)
            s.manual_group_tools[kind] = button
        for label, var in (
            ("水平臂 mm", s.manual_group_arm_x),
            ("垂直臂 mm", s.manual_group_arm_y),
            ("角間距 X", s.manual_group_spacing_x),
            ("角間距 Y", s.manual_group_spacing_y),
            ("角度 °", s.manual_group_angle),
        ):
            d.tk.Label(group_bar, text=label, bg=host.COLOR_PANEL,
                       fg=host.COLOR_TEXT).pack(side=d.tk.LEFT, padx=(5, 1))
            d.tk.Entry(group_bar, textvariable=var, width=5).pack(side=d.tk.LEFT)
        edit_bar = d.tk.Frame(s.center, bg=host.COLOR_PANEL)
        if _has_group_mark_tools(s):
            edit_bar.pack(before=s.canvas, fill=d.tk.X, padx=4, pady=(0, 2))
        d.tk.Label(edit_bar, text="雙擊角點選成員：", bg=host.COLOR_PANEL,
                   fg=host.COLOR_TEXT).pack(side=d.tk.LEFT)
        d.tk.Label(edit_bar, textvariable=s.manual_group_member,
                   bg=host.COLOR_PANEL, fg="#ff9f0a").pack(side=d.tk.LEFT, padx=3)
        for label, var in (("局部 ΔX mm", s.manual_group_offset_x),
                           ("局部 ΔY mm", s.manual_group_offset_y)):
            d.tk.Label(edit_bar, text=label, bg=host.COLOR_PANEL,
                       fg=host.COLOR_TEXT).pack(side=d.tk.LEFT, padx=(4, 1))
            d.tk.Entry(edit_bar, textvariable=var, width=6).pack(side=d.tk.LEFT)
        s.manual_group_apply_offset = d.tk.Button(
            edit_bar, text="套用單角偏移", bg="#0a84ff", fg="white",
        )
        s.manual_group_apply_offset.pack(side=d.tk.LEFT, padx=2)
        s.manual_group_apply_size = d.tk.Button(
            edit_bar, text="套用 X/Y・雙臂", bg="#3a3a44", fg="white",
        )
        s.manual_group_apply_size.pack(side=d.tk.LEFT, padx=2)
        s.manual_group_rotate = d.tk.Button(
            edit_bar, text="群組旋轉", bg="#3a3a44", fg="white",
        )
        s.manual_group_rotate.pack(side=d.tk.LEFT, padx=2)
        s.manual_group_mirror = d.tk.Button(
            edit_bar, text="鏡射（群組中心垂直軸）", bg="#3a3a44", fg="white",
        )
        s.manual_group_mirror.pack(side=d.tk.LEFT, padx=2)
        s.manual_mark_copy_button = d.tk.Button(
            edit_bar, text="從另存專案複製群組", bg="#3a3a44", fg="white",
        )
        s.manual_mark_copy_button.pack(side=d.tk.LEFT, padx=3)
        s.editor._manual_group_controls = (
            *s.manual_group_tools.values(), s.manual_group_apply_offset,
            s.manual_group_apply_size, s.manual_group_rotate,
            s.manual_group_mirror, s.manual_mark_copy_button,
        )
    s.dragging = [False]
    s.editor_closed = [False]
    s.suppress_entry_events = [False]
    s.pending_after = {}
    s.position_authority = [None]
    s.round_window = [None]
    s.active_part_key = [s.part_key]
    s.door_editor_context = {
        "part_key": s.part_key, "surface": s.surface,
        "width": s.width, "height": s.height,
        "reference_guide": s.reference_guide, "feature_list": s.feature_list,
        "baseline_scene": s.baseline_scene,
        "baseline_status_text": str(s.baseline_status_text or ""),
    }
    s.indicator_component_contexts = {}
    s.live_context = d._HoleEditorLiveContext(
        feature_list=s.feature_list,
        surface=s.surface,
        width=s.width,
        height=s.height,
        reference_guide=s.reference_guide,
        baseline_scene=s.baseline_scene,
        part_key=s.part_key,
    )


def _build_reference_stack(s):
    d = s.d
    s.var_x_edge = d.tk.StringVar()
    s.var_x_neighbor = d.tk.StringVar()
    s.var_y_edge = d.tk.StringVar()
    s.var_y_neighbor = d.tk.StringVar()
    s.lbl_x_edge = d.tk.StringVar(value="X 到邊框")
    s.lbl_x_neighbor = d.tk.StringVar(value="X 到鄰近孔")
    s.lbl_y_edge = d.tk.StringVar(value="Y 到邊框")
    s.lbl_y_neighbor = d.tk.StringVar(value="Y 到鄰近孔")
    s.overlay_widgets = []
    x_group = d.tk.Frame(s.canvas, bg="#24242c", bd=1, relief=d.tk.SOLID)
    d.tk.Label(
        x_group, text="X 定位", bg="#24242c", fg="#30d158",
        font=('Microsoft JhengHei', 10, 'bold'),
    ).pack(fill=d.tk.X, padx=5, pady=(3, 1))
    s.form_row_builders.add_group_entry(x_group, s.lbl_x_edge, s.var_x_edge, "x", "edge")
    s.form_row_builders.add_group_entry(x_group, s.lbl_x_neighbor, s.var_x_neighbor, "x", "neighbor")
    y_group = d.tk.Frame(s.canvas, bg="#24242c", bd=1, relief=d.tk.SOLID)
    d.tk.Label(
        y_group, text="Y 定位", bg="#24242c", fg="#64d2ff",
        font=('Microsoft JhengHei', 10, 'bold'),
    ).pack(fill=d.tk.X, padx=5, pady=(3, 1))
    s.form_row_builders.add_group_entry(y_group, s.lbl_y_edge, s.var_y_edge, "y", "edge")
    s.form_row_builders.add_group_entry(y_group, s.lbl_y_neighbor, s.var_y_neighbor, "y", "neighbor")
    s.overlay_widgets.extend([x_group, y_group])
    ref_panel = d.tk.Frame(s.canvas, bg="#1f1f27", bd=2, relief=d.tk.RIDGE)
    d.tk.Label(
        ref_panel, text="右鍵切換基準", bg="#1f1f27", fg="#ffd60a",
        font=('Microsoft JhengHei', 9, 'bold'),
    ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 2))
    s.confirm_ref_btn = d.tk.Button(
        ref_panel, text="確定", bg="#30d158", fg="white", bd=0,
        font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3,
    )
    s.confirm_ref_btn.grid(row=1, column=1, padx=(2, 4), pady=(2, 4))
    s.cancel_ref_btn = d.tk.Button(
        ref_panel, text="取消", bg="#ff9f0a", fg="white", bd=0,
        font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3,
    )
    s.cancel_ref_btn.grid(row=1, column=0, padx=(4, 2), pady=(2, 4))
    s.round_settings_btn = d.tk.Button(
        ref_panel, text="圓孔排列", bg="#5e5ce6", fg="white", bd=0,
        font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3, state=d.tk.DISABLED,
    )
    s.round_settings_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
    s.overlay_widgets.append(ref_panel)
    s.canvas_view = d._HoleEditorCanvasViewFactory.create(
        s.canvas,
        draw_grid=s.host.draw_grid,
        render_secondary_scene=d.render_secondary_scene,
        render_resolved_features=d.render_resolved_features,
        overlay_widgets={"x_group": x_group, "y_group": y_group, "panel": ref_panel},
    )
    sync_coordinator = d._HoleEditorSyncCoordinator(
        sync_callback=(None if getattr(s, "defer_workspace_sync", False)
                       else s.sync_callback),
        draw_preview=s.host.draw_preview,
    )
    s.sync_all = sync_coordinator.sync_all
    created_list_presentation = d._HoleEditorCreatedListPresentation(
        created_list=s.created_list,
        feature_list_provider=lambda: s.live_context.feature_list,
        selected_index_provider=lambda: s.hole_session.selected_index,
        end_token=d.tk.END,
    )
    s.refresh_created = created_list_presentation.refresh_created
    s.last_distances = [None]
    reference_presentation = d._HoleEditorReferencePresentation(
        selection_provider=lambda: (s.hole_session.selected_index, s.live_context.feature_list),
        context_provider=lambda: {
            "reference_guide": s.live_context.reference_guide,
            "cabinet_reference_guide": s.cabinet_reference_guide,
            "local_reference_guide": s.local_reference_guide,
            "cabinet_locator_enabled": bool(
                s.cabinet_locator_var is not None and s.cabinet_locator_var.get()
            ),
            "active_part_key": s.active_part_key[0],
            "indicator_box_dist_enabled": bool(
                s.indicator_box_dist_var is not None and s.indicator_box_dist_var.get()
            ),
            "door_frame_width": s.door_frame_width,
            "door_thickness": s.door_thickness,
            "door_gap_w": s.door_gap_w,
            "door_gap_h": s.door_gap_h,
            "door_frame_edges": s.door_frame_edges,
            "surface": s.live_context.surface,
            "width": s.live_context.width,
            "height": s.live_context.height,
        },
        feature_reference_anchor=d.feature_reference_anchor,
        reference_distances=d.reference_distances,
        door_enclosure_reference_guide=d.door_enclosure_reference_guide,
        door_frame_edges_factory=d.DoorFrameEdges,
        round_settings_btn=s.round_settings_btn,
        labels={
            "x_edge": s.lbl_x_edge, "x_neighbor": s.lbl_x_neighbor,
            "y_edge": s.lbl_y_edge, "y_neighbor": s.lbl_y_neighbor,
        },
        values={
            "x_edge": s.var_x_edge, "x_neighbor": s.var_x_neighbor,
            "y_edge": s.var_y_edge, "y_neighbor": s.var_y_neighbor,
        },
        ref_entries=s.ref_entries,
        side_labels={"left": "左", "right": "右", "top": "上", "bottom": "下"},
        last_distances=s.last_distances,
        suppress_entry_events=s.suppress_entry_events,
    )
    s.active_reference_guide = reference_presentation.active_reference_guide
    s.refresh_reference_fields = reference_presentation.refresh_reference_fields


def _build_renderer_and_catalog_actions(s):
    d = s.d
    canvas_renderer = d._HoleEditorCanvasRenderer(
        context_provider=lambda: {
            "surface": s.live_context.surface,
            "feature_list": s.live_context.feature_list,
            "width": s.live_context.width,
            "height": s.live_context.height,
            "reference_guide": s.live_context.reference_guide,
            "cabinet_reference_enabled": bool(
                s.cabinet_locator_var is not None and s.cabinet_locator_var.get()
            ),
            "baseline_scene": s.live_context.baseline_scene,
            "active_part_key": s.active_part_key[0],
            "indicator_box_dist_enabled": bool(
                s.indicator_box_dist_var is not None and s.indicator_box_dist_var.get()
            ),
            "indicator_mode_available": s.indicator_mode_var is not None,
            "door_indicator_context": s.door_indicator_context,
            "door_frame_width": s.door_frame_width,
            "door_thickness": s.door_thickness,
            "door_gap_w": s.door_gap_w,
            "door_gap_h": s.door_gap_h,
            "door_frame_edges": s.door_frame_edges,
        },
        canvas_view=s.canvas_view,
        selected_index_provider=lambda: s.hole_session.selected_index,
        reference_distances_provider=lambda: s.last_distances[0],
        measure_guide_provider=s.active_reference_guide,
        selected_catalog_text_provider=s.selected_catalog_text.get,
        insert_mode_provider=lambda: s.insert_mode[0],
        error_text_provider=lambda: s.indicator_fit_error[0],
        collect_indicator_state=s.collect_indicator_state,
        validate_current_indicator_fit=s.validate_current_indicator_fit,
        door_enclosure_reference_offsets=d.door_enclosure_reference_offsets,
        door_frame_edges_factory=d.DoorFrameEdges,
        vec2_factory=d.Vec2,
        resolve_door_indicator_layout=d.resolve_door_indicator_layout,
        render_resolved_features=d.render_resolved_features,
        measure_door_indicator_position=d.measure_door_indicator_position,
        resolve_door_indicator_dimension_guides=d.resolve_door_indicator_dimension_guides,
        indicator_box_opening_size=d.manufacturing_api.indicator_box_opening_size,
        resolved_rect_factory=d.ResolvedRect,
        canvas_frame_factory=d.HoleEditorCanvasFrame,
        arrow_both=d.tk.BOTH,
    )
    s.redraw = canvas_renderer.redraw
    s.indicator_redraw[0] = s.redraw
    feature_factory = d._HoleEditorFeatureFactory(
        selected_catalog_text=s.selected_catalog_text,
        rotation_var=s.var_rotation,
        diameter_var=s.var_d,
        width_var=s.var_w,
        height_var=s.var_h,
        blind_var=s.var_blind,
        context_provider=lambda: {
            "width": s.live_context.width, "height": s.live_context.height,
        },
        catalog_by_label=s.catalog_by_label,
        custom_circle_definition=d.custom_circle_definition,
        custom_rectangle_definition=d.custom_rectangle_definition,
        feature_from_definition=d.feature_from_definition,
        feature_with_reference_anchor=d.feature_with_reference_anchor,
        center_anchor=d.ReferenceAnchor.CENTER,
        show_error=d.messagebox.showerror,
    )
    s.make_feature = feature_factory.make_feature
    catalog_controls = d._HoleEditorCatalogControls(
        catalog_list=s.catalog_list,
        pipe_catalog_list=s.pipe_catalog_list,
        selected_catalog_text=s.selected_catalog_text,
        insert_mode=s.insert_mode,
        insert_btn=s.insert_btn,
        canvas=s.canvas,
        redraw=s.redraw,
    )
    s.on_catalog_select = catalog_controls.on_catalog_select
    s.set_insert_mode = catalog_controls.set_insert_mode
    s.on_catalog_double_click = catalog_controls.on_catalog_double_click
    s.insert_btn.configure(command=s.set_insert_mode)
    session_actions = d._HoleEditorTransientActions(
        hole_session=s.hole_session,
        feature_list_provider=lambda: s.live_context.feature_list,
        var_rotation=s.var_rotation,
        refresh_created=s.refresh_created,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
    )
    s.commit_active_edit = session_actions.commit_active_edit
    s.undo_last_action = session_actions.undo_last_action
    s.cancel_active_edit = session_actions.cancel_active_edit
    s.begin_edit = session_actions.begin_edit
    s.select_feature = session_actions.select_feature


def _build_pointer_and_created_actions(s):
    d = s.d
    canvas_pointer_actions = d._HoleEditorCanvasPointerActions(
        hole_session=s.hole_session,
        canvas_view=s.canvas_view,
        dragging=s.dragging,
        insert_mode=s.insert_mode,
        context_provider=lambda: {
            "surface": s.live_context.surface,
            "width": s.live_context.width,
            "height": s.live_context.height,
            "feature_list": s.live_context.feature_list,
        },
        select_feature=s.select_feature,
        make_feature=s.make_feature,
        feature_is_within_surface=d.feature_is_within_surface,
        move_feature_within_surface=d.move_feature_within_surface,
        begin_edit=s.begin_edit,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
        warn_out_of_bounds=lambda: d.messagebox.showwarning(
            "超出開孔範圍", "孔的完整外形必須全部位於板面框內。"
        ),
    )
    s.on_canvas_down = canvas_pointer_actions.on_canvas_down
    s.on_canvas_drag = canvas_pointer_actions.on_canvas_drag
    s.on_canvas_up = canvas_pointer_actions.on_canvas_up
    created_list_actions = d._HoleEditorCreatedListActions(
        hole_session=s.hole_session,
        feature_list_provider=lambda: s.live_context.feature_list,
        created_list=s.created_list,
        select_feature=s.select_feature,
        feature_with_process=d.feature_with_process,
        refresh_created=s.refresh_created,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
    )
    s.on_created_select = created_list_actions.on_created_select
    s.toggle_created_process = created_list_actions.toggle_created_process
    s.delete_selected = created_list_actions.delete_selected
    s.delete_btn.configure(command=s.delete_selected)


def _build_reference_selection_actions(s):
    d = s.d
    reference_actions = d._HoleEditorReferenceActions(
        hole_session=s.hole_session,
        context_provider=lambda: {
            "feature_list": s.live_context.feature_list,
            "surface": s.live_context.surface,
            "width": s.live_context.width,
            "height": s.live_context.height,
        },
        suppress_entry_events=s.suppress_entry_events,
        reference_variables={
            ('x', 'edge'): s.var_x_edge, ('x', 'neighbor'): s.var_x_neighbor,
            ('y', 'edge'): s.var_y_edge, ('y', 'neighbor'): s.var_y_neighbor,
        },
        pending_after=s.pending_after,
        editor=s.editor,
        feature_with_reference_anchor=d.feature_with_reference_anchor,
        feature_reference_anchor=d.feature_reference_anchor,
        move_feature_by_reference_distance=d.move_feature_by_reference_distance,
        active_reference_guide=s.active_reference_guide,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
        show_format_error=lambda: d.messagebox.showerror("格式錯誤", "距離必須是數字"),
    )
    s.set_reference_anchor = reference_actions.set_reference_anchor
    s.apply_reference_value = reference_actions.apply_reference_value
    s.schedule_reference_value = reference_actions.schedule_reference_value
    for (axis, mode), entry in s.ref_entries.items():
        entry.bind(
            "<KeyRelease>",
            lambda event, a=axis, m=mode: s.schedule_reference_value(a, m),
        )
        entry.bind(
            "<Return>",
            lambda event, a=axis, m=mode: s.apply_reference_value(a, m, True),
        )
        entry.bind(
            "<FocusOut>",
            lambda event, a=axis, m=mode: s.apply_reference_value(a, m, False),
        )
    selected_feature_actions = d._HoleEditorSelectedFeatureActions(
        hole_session=s.hole_session,
        canvas_view=s.canvas_view,
        context_provider=lambda: {
            "feature_list": s.live_context.feature_list,
            "surface": s.live_context.surface,
            "width": s.live_context.width,
            "height": s.live_context.height,
        },
        select_feature=s.select_feature,
        menu_factory=lambda: configure_tk_menu(d.tk.Menu(s.editor, tearoff=0)),
        reference_anchor_labels=d.REFERENCE_ANCHOR_LABELS,
        feature_reference_anchor=d.feature_reference_anchor,
        set_reference_anchor=s.set_reference_anchor,
        var_rotation=s.var_rotation,
        rotate_feature=d.manufacturing_api.operator_hole_feature_with_rotation,
        feature_is_within_surface=d.feature_is_within_surface,
        warn_rotation_out_of_bounds=lambda: d.messagebox.showwarning(
            "旋轉失敗", "旋轉後孔的完整外形會超出板面框。"
        ),
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
    )
    s.on_canvas_right = selected_feature_actions.on_canvas_right
    s.rotate_selected = selected_feature_actions.rotate_selected
    for angle, button in s.rotation_buttons:
        button.configure(command=lambda a=angle: s.rotate_selected(a))
    round_settings_launcher = d._HoleEditorRoundSettingsLauncher(
        editor=s.editor,
        theme={
            "bg": s.host.COLOR_BG,
            "panel": s.host.COLOR_PANEL,
            "text": s.host.COLOR_TEXT,
            "input_bg": s.host.COLOR_INPUT_BG,
            "muted": s.host.COLOR_TEXT_MUTED,
        },
        hole_session=s.hole_session,
        context_provider=lambda: {
            "feature_list": s.live_context.feature_list,
            "surface": s.live_context.surface,
            "width": s.live_context.width,
            "height": s.live_context.height,
        },
        round_window=s.round_window,
        position_authority=s.position_authority,
        refresh_created=s.refresh_created,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
        sync_all=s.sync_all,
        open_round_hole_settings=d._open_round_hole_settings_impl,
    )
    s.round_settings_btn.configure(command=round_settings_launcher.open)


def _build_navigation_and_lifecycle(s):
    d = s.d
    context_switcher = d._HoleEditorContextSwitcher(
        live_context=s.live_context,
        hole_session=s.hole_session,
        door_context=s.door_editor_context,
        indicator_contexts=s.indicator_component_contexts,
        cancel_active_edit=s.cancel_active_edit,
        insert_mode=s.insert_mode,
        insert_button=s.insert_btn,
        active_part_key=s.active_part_key,
        position_authority=s.position_authority,
        baseline_status_var=s.baseline_status_var,
        baseline_status_label=s.baseline_status_label,
        baseline_status_color=d._HoleEditorIndicatorContextRefresh.baseline_status_color,
        refresh_created=s.refresh_created,
        refresh_reference_fields=s.refresh_reference_fields,
        redraw=s.redraw,
    )
    s.switch_editor_context = context_switcher.switch
    indicator_context_refresh_controller = d._HoleEditorIndicatorContextRefresh(
        component_context_provider=s.indicator_component_context_provider,
        indicator_mode_available=(s.indicator_mode_var is not None),
        collect_indicator_state=s.collect_indicator_state,
        component_contexts=s.indicator_component_contexts,
        baseline_status_var=s.baseline_status_var,
        baseline_status_label=s.baseline_status_label,
        set_indicator_page_visible=s.set_indicator_page_visible,
        active_context_key_provider=lambda: s.hole_session.active_context_key,
        switch_editor_context=s.switch_editor_context,
        redraw=s.redraw,
        editor_tabs=s.editor_tabs,
        indicator_page=s.indicator_page,
        component_tabs=s.component_tabs,
        toolbar=s.toolbar,
        selected_component_key_provider=lambda: s.page_navigation.selected_indicator_component_key(),
    )
    s.refresh_indicator_component_contexts = indicator_context_refresh_controller.refresh
    s.page_navigation = d._HoleEditorPageNavigation(
        editor_tabs=s.editor_tabs,
        main_page=s.main_page,
        indicator_page=s.indicator_page,
        component_tabs=s.component_tabs,
        indicator_door_page=s.indicator_door_page,
        toolbar=s.toolbar,
        refresh_indicator_component_contexts=s.refresh_indicator_component_contexts,
        switch_editor_context=s.switch_editor_context,
    )
    if s.editor_tabs is not None:
        s.editor_tabs.bind(
            "<<NotebookTabChanged>>", s.page_navigation.on_editor_page_changed
        )
        if s.component_tabs is not None:
            s.component_tabs.bind(
                "<<NotebookTabChanged>>",
                s.page_navigation.on_indicator_component_page_changed,
            )
        s.indicator_context_refresh[0] = s.refresh_indicator_component_contexts
        s.set_indicator_page_visible(
            s.indicator_mode_var is not None
            and s.indicator_mode_var.get() == "indicator_box"
        )
        s.refresh_indicator_component_contexts()
    modal_lifecycle = d._HoleEditorModalLifecycle(
        hole_session=s.hole_session,
        has_selected_feature=lambda: (
            0 <= s.hole_session.selected_index < len(s.live_context.feature_list)
        ),
        position_authority=s.position_authority,
        commit_active_edit=s.commit_active_edit,
        sync_all=s.sync_all,
        validate_current_indicator_fit=s.validate_current_indicator_fit,
        door_indicator_state=s.door_indicator_state,
        collect_indicator_state=s.collect_indicator_state,
        door_indicator_commit=s.door_indicator_commit,
        editor_closed=s.editor_closed,
        editor=s.editor,
        on_close=s.on_close,
        before_commit=(lambda: s.on_confirm_features(
            list(s.live_context.feature_list),
        )) if s.on_confirm_features is not None else None,
        on_confirm=(s.on_confirm if s.on_confirm_features is None else None),
        insert_mode=s.insert_mode,
        set_insert_mode=s.set_insert_mode,
        cancel_active_edit=s.cancel_active_edit,
        sync_on_cancel=not getattr(s, "skip_cancel_sync", False),
    )
    if str(s.part_key).startswith("inner_door:"):
        def accept_verified_openings(verified):
            from phase6_hole_editor_session import HoleEditorAction

            projected = d.manufacturing_api.plan_operator_inner_door_nfb_hole_stage(
                part_key=s.part_key,
                surface=s.live_context.surface,
                width=s.live_context.width,
                height=s.live_context.height,
                current_features=s.live_context.feature_list,
                incoming_features=verified,
                mode="verified_append",
            )
            s.hole_session.execute(HoleEditorAction.preview_all(projected))
            s.refresh_created()
            s.sync_all()
            # External sync redraws assembly preview, not native Editor.
            s.redraw()
        s.editor._receiving_accept_verified_openings = accept_verified_openings

        def stage_selected_nfb_openings(openings):
            # The Engine plans exact CSV draft replacement; only the original
            # Hole Editor Session owns transient edits and undo/confirm.
            from phase6_hole_editor_session import HoleEditorAction

            projected = d.manufacturing_api.plan_operator_inner_door_nfb_hole_stage(
                part_key=s.part_key,
                surface=s.live_context.surface,
                width=s.live_context.width,
                height=s.live_context.height,
                current_features=s.live_context.feature_list,
                incoming_features=openings,
                mode="csv_replace",
            )
            s.hole_session.execute(HoleEditorAction.preview_all(projected))
            s.refresh_created()
            s.sync_all()
            s.redraw()
        s.editor._receiving_stage_selected_nfb_openings = stage_selected_nfb_openings
        # The Receiving tab switches back after stage; paint again once its
        # main Canvas is mapped, not only while the settings tab is visible.
        s.editor._receiving_redraw_main_holes = s.redraw
        s.editor._receiving_pending_features = lambda: tuple(s.live_context.feature_list)

    s.confirm_reference_edit = modal_lifecycle.confirm_reference_edit
    s.confirm_all = modal_lifecycle.confirm_all
    s.cancel_all = modal_lifecycle.cancel_all
    s.on_escape = modal_lifecycle.on_escape
    s.confirm_ref_btn.configure(command=s.confirm_reference_edit)
    s.cancel_ref_btn.configure(command=s.cancel_active_edit)
    s.undo_btn.configure(command=s.undo_last_action)
    s.confirm_all_btn.configure(command=s.confirm_all)
    s.cancel_all_btn.configure(command=s.cancel_all)



def _has_group_mark_tools(s):
    return bool({"cross", "l", "pair_l", "quad_l"}.intersection(
        s.manual_marking_draft.allowed_tools,
    ))


def _guard_manual_marking_sync(s):
    """Keep stale mark and conflicting new hole in the editor for correction.

    The physical Engine still REJECTS publication.  Only the explicitly
    detected mark/material collision is presented as a live red warning; all
    unrelated legacy hole sync failures preserve their original exception.
    Called before pointer actions capture the session sync callback.
    """
    if getattr(s, "manual_marking_draft", None) is None:
        return
    authoritative_sync = s.sync_all

    def sync_with_mark_warning():
        try:
            return authoritative_sync()
        except (ValueError, TypeError, RuntimeError):
            current = tuple(s.live_context.feature_list)
            if not any(s.d.manufacturing_api.is_manual_mark(row) for row in current):
                raise
            try:
                s.d.manufacturing_api.validate_physical_sheet_marking_draft(
                    s.manual_marking_draft, current,
                )
            except (ValueError, TypeError, RuntimeError) as mark_error:
                s.manual_mark_status.configure(
                    text="打標／孔位無法確認：" + str(mark_error),
                    fg="#ff453a",
                )
                s.confirm_all_btn.configure(state=s.d.tk.DISABLED)
                # The original complete features remain in the editing session.
                # No invalid data is copied into the physical Workspace.
                return
            raise  # Not a mark collision: preserve existing hole failure.

    s.sync_all = sync_with_mark_warning


def _install_manual_marking_actions(s):
    """Engine-owned physical MARKING; one ProfileFeature per group.

    Single click selects the whole group, double click chooses a stable
    member for its local offset, and dragging moves the group center only.
    No member-level deletion or GUI-owned geometry.
    """
    if getattr(s, "manual_marking_draft", None) is None:
        return
    from phase6_hole_editor_session import HoleEditorAction
    from math import hypot
    d = s.d
    api = d.manufacturing_api
    real_redraw = s.redraw
    # Rejected round placement never enters Features, so replaying the
    # valid current draft on a passive redraw cannot dismiss its warning.
    round_rejection = None
    # A source selection is not a Feature or an Undo record. The pending
    # receipt lives only in this editor until the operator clicks a target.
    pending_copy = None
    copy_rejection = None
    placed_copy_receipts = {}

    def checked_redraw():
        try:
            api.validate_physical_sheet_marking_draft(
                s.manual_marking_draft,
                tuple(s.live_context.feature_list),
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            s.manual_mark_status.configure(
                text="打標／孔位無法確認：" + str(exc), fg="#ff453a",
            )
            s.confirm_all_btn.configure(state=d.tk.DISABLED)
        else:
            s.manual_mark_status.configure(text=round_rejection or "", fg="#ff453a")
            s.confirm_all_btn.configure(state=d.tk.NORMAL)
        result = real_redraw()
        if copy_rejection is not None:
            s.manual_mark_status.configure(text=copy_rejection, fg="#ff453a")
        elif pending_copy is not None:
            s.manual_mark_status.configure(text=pending_copy["prompt"], fg="#007aff")
        if pending_copy is not None:
            s.confirm_all_btn.configure(state=d.tk.DISABLED)
        if round_rejection:
            # The canvas renderer updates generic confirmation controls.
            # This rejected tool attempt still owns its own disabled state.
            s.confirm_all_btn.configure(state=d.tk.DISABLED)
        return result

    def dismiss_round_rejection():
        nonlocal round_rejection
        if round_rejection is not None:
            round_rejection = None
            checked_redraw()

    s.redraw = checked_redraw
    s.indicator_redraw[0] = checked_redraw

    # The editable corner belongs to the exact group *and* editor context
    # hit by the latest valid double-click, never to a reused member name.
    s.manual_group_edit_identity = [None]  # (stable group_id, member_id)
    s.manual_group_edit_context = [None]   # (Session context, list identity)
    # The grab is scoped to the exact editor context, feature list and source.
    drag_origin = [None]
    corner_arm = [None]   # (group_id, member_id, Session context, list)

    def clear_member_edit():
        s.manual_group_edit_identity[0] = None
        s.manual_group_edit_context[0] = None
        s.manual_group_member.set("")
        s.manual_group_offset_x.set("")
        s.manual_group_offset_y.set("")

    def select_mode():
        nonlocal pending_copy, copy_rejection
        was_pending = pending_copy is not None or copy_rejection is not None
        pending_copy = None
        copy_rejection = None
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        s.manual_mark_mode[0] = False
        s.manual_group_tool[0] = "select"
        s.manual_mark_draw_button.configure(relief=d.tk.RAISED)
        s.manual_mark_select_button.configure(relief=d.tk.SUNKEN)
        if hasattr(s, "manual_round_button"):
            s.manual_round_button.configure(relief=d.tk.RAISED)
        for button in s.manual_group_tools.values():
            button.configure(relief=d.tk.RAISED)
        dismiss_round_rejection()
        if was_pending:
            checked_redraw()

    def draw_mode(kind="line"):
        nonlocal pending_copy
        if kind not in s.manual_marking_draft.allowed_tools:
            return
        if pending_copy is not None or copy_rejection is not None:
            select_mode()
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        s.set_insert_mode(False)
        s.manual_mark_mode[0] = True
        s.manual_group_tool[0] = kind
        s.manual_mark_draw_button.configure(
            relief=d.tk.SUNKEN if kind == "line" else d.tk.RAISED)
        s.manual_mark_select_button.configure(relief=d.tk.RAISED)
        if hasattr(s, "manual_round_button"):
            s.manual_round_button.configure(relief=d.tk.SUNKEN if kind == "circle" else d.tk.RAISED)
        for key, button in s.manual_group_tools.items():
            button.configure(relief=d.tk.SUNKEN if kind == key else d.tk.RAISED)
        if kind != "circle":
            dismiss_round_rejection()

    def selected_group():
        idx = s.hole_session.selected_index
        items = s.live_context.feature_list
        if 0 <= idx < len(items) and api.is_manual_group(items[idx]):
            return items[idx]
        return None

    def publish_group_change(**values):
        if "member_id" not in values:
            clear_member_edit()  # geometry/pose edits invalidate the corner hot spot
        old = selected_group()
        if old is None:
            return False
        try:
            changed = api.edit_physical_manual_group(
                old, part_key=s.part_key, context=s.manual_marking_draft.context,
                marking_draft=s.manual_marking_draft,
                existing_features=tuple(s.live_context.feature_list), **values,
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            s.manual_mark_status.configure(
                text="群組編輯被拒絕：" + str(exc), fg="#ff453a")
            return False
        s.hole_session.execute(HoleEditorAction.replace_selected_committed(changed))
        s.refresh_created()
        s.sync_all()
        s.redraw()
        return True

    def edit_selected_member():
        group = selected_group()
        member_id = s.manual_group_member.get()
        binding = s.manual_group_edit_identity[0]
        scope = s.manual_group_edit_context[0]
        if (group is None or binding is None or not member_id
                or binding != (api.group_parameters(group)["group_id"], member_id)
                or scope != (s.hole_session.active_context_key,
                             id(s.live_context.feature_list))):
            clear_member_edit()
            s.manual_mark_status.configure(
                text="請重新雙擊要修改的群組角點", fg="#ff453a",
            )
            return False
        return publish_group_change(
            member_id=member_id,
            offset_x=s.manual_group_offset_x.get(),
            offset_y=s.manual_group_offset_y.get(),
        )

    def edit_group_size():
        group = selected_group()
        if group is None:
            return False
        p = api.group_parameters(group)
        values = {
            "arm_x": s.manual_group_arm_x.get(),
            "arm_y": s.manual_group_arm_y.get(),
        }
        if p["kind"] in ("pair_l", "quad_l"):
            values["spacing_x"] = s.manual_group_spacing_x.get()
        if p["kind"] == "quad_l":
            values["spacing_y"] = s.manual_group_spacing_y.get()
        return publish_group_change(**values)

    def rotate_group():
        group = selected_group()
        if group is None:
            return False
        return publish_group_change(angle=s.manual_group_angle.get())

    def mirror_group():
        group = selected_group()
        if group is None:
            return False
        return publish_group_change(
            mirror_vertical=not api.group_parameters(group)["mirror_vertical"])

    def mark_down(event):
        nonlocal round_rejection
        # Also clear when the legacy pointer handler leaves its old selection
        # active on empty canvas; a subsequent double must hit a real corner.
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        point = s.canvas_view.canvas_to_world(event.x, event.y)
        if point is None:
            return
        # The ordinary hole insertion route always wins when armed,
        # including shortcuts that reach the original catalog controller.
        if s.insert_mode[0]:
            if s.manual_mark_mode[0] or pending_copy is not None or copy_rejection is not None:
                select_mode()
            return original_down(event)
        if pending_copy is not None:
            return place_pending_copy(point)
        if not s.manual_mark_mode[0]:
            # Whole group selection also works at its nominal center or a
            # member corner, not only on an ink stroke. No single L identity.
            for idx, item in enumerate(s.live_context.feature_list):
                if not api.is_manual_group(item):
                    continue
                corners = api.group_member_world_points(item)
                if (hypot(point.x-item.offset.x, point.y-item.offset.y) <= 5
                    or any(hypot(point.x-p.x, point.y-p.y) <= 5 for _, p in corners)):
                    group_id = api.group_parameters(item)["group_id"]
                    drag_origin[0] = (
                        id(s.live_context.feature_list),
                        s.hole_session.active_context_key,
                        group_id, point, item.offset,
                    )
                    nearest = min(
                        ((hypot(point.x-corner.x, point.y-corner.y), member_id)
                         for member_id, corner in corners),
                        default=None,
                    )
                    if nearest is not None and nearest[0] <= 5.0:
                        corner_arm[0] = (
                            group_id, nearest[1],
                            s.hole_session.active_context_key,
                            id(s.live_context.feature_list),
                        )
                    s.hole_session.execute(HoleEditorAction.select(idx))
                    s.dragging[0] = True
                    s.refresh_created()
                    s.redraw()
                    return "break"
            hit = s.canvas_view.hit_test(event.x, event.y)
            result = original_down(event)
            idx = s.hole_session.selected_index
            rows = s.live_context.feature_list
            if (s.dragging[0] and hit == idx and 0 <= idx < len(rows)
                    and api.is_manual_round_mark(rows[idx])):
                drag_origin[0] = (
                    id(rows), s.hole_session.active_context_key,
                    ("round", idx), point, rows[idx].offset, rows[idx],
                )
            return result
        try:
            if s.manual_group_tool[0] == "circle":
                mark = api.create_physical_sheet_mark(
                    s.manual_marking_draft, tuple(s.live_context.feature_list), tool="circle",
                    centre=point, diameter=s.manual_round_diameter.get(),
                )
            elif s.manual_group_tool[0] == "line":
                mark = api.create_physical_sheet_mark(
                    s.manual_marking_draft, tuple(s.live_context.feature_list), tool="line",
                    midpoint=point, length=s.manual_mark_length.get(),
                    angle_deg=s.manual_mark_angle.get(),
                    pattern=s.manual_mark_pattern.get(),
                    dash=s.manual_mark_dash.get(), gap=s.manual_mark_gap.get(),
                )
            else:
                kind = s.manual_group_tool[0]
                # Group X/Y have NO default: an operator explicitly enters
                # their corner spacing before pair/four-corner placement.
                sx = s.manual_group_spacing_x.get() if kind in ("pair_l", "quad_l") else 0
                sy = s.manual_group_spacing_y.get() if kind == "quad_l" else 0
                mark = api.create_physical_sheet_mark(
                    s.manual_marking_draft, tuple(s.live_context.feature_list),
                    tool=kind, center=point,
                    arm_x=s.manual_group_arm_x.get(), arm_y=s.manual_group_arm_y.get(),
                    spacing_x=sx, spacing_y=sy,
                    angle=s.manual_group_angle.get(),
                    pattern=s.manual_mark_pattern.get(),
                    dash=s.manual_mark_dash.get(), gap=s.manual_mark_gap.get(),
                )
        except (ValueError, TypeError, RuntimeError) as exc:
            warning = "打標位置不合法：" + str(exc)
            if s.manual_group_tool[0] == "circle":
                round_rejection = warning
            s.manual_mark_status.configure(text=warning, fg="#ff453a")
            s.confirm_all_btn.configure(state=d.tk.DISABLED)
            return "break"
        round_rejection = None
        s.hole_session.execute(HoleEditorAction.insert(mark))
        s.hole_session.execute(HoleEditorAction.commit_active())
        s.refresh_created()
        try:
            s.sync_all()
        except (ValueError, TypeError, RuntimeError) as exc:
            s.manual_mark_status.configure(
                text="打標提交被拒絕：" + str(exc), fg="#ff453a",
            )
            s.confirm_all_btn.configure(state=d.tk.DISABLED)
        s.redraw()
        return "break"

    original_down = s.on_canvas_down
    original_drag = s.on_canvas_drag
    original_up = s.on_canvas_up

    def safe_up(event):
        grab = drag_origin[0]
        try:
            if grab is not None and len(grab) == 6:
                # The release position is authoritative even if Tk
                # coalesces away a final motion event.
                safe_drag(event)
                # One round drag is one Undo transaction. Releasing over an
                # invalid circumference restores the original round mark.
                action = (HoleEditorAction.cancel_active() if round_rejection else
                          HoleEditorAction.commit_active(keep_selected=True))
                s.hole_session.execute(action)
                s.refresh_created()
            return original_up(event)
        finally:
            drag_origin[0] = None

    def safe_drag(event):
        nonlocal round_rejection
        idx = s.hole_session.selected_index
        items = s.live_context.feature_list
        if (0 <= idx < len(items)
                and getattr(items[idx], "layer", None) == "MARKING"):
            if not s.dragging[0]:
                return "break"
            point = s.canvas_view.canvas_to_world(event.x, event.y)
            grab = drag_origin[0]
            if grab is None:
                return "break"
            if point is None:
                if len(grab) == 6:
                    round_rejection = "圓打標移動被拒絕：請在圖面內放置"
                    s.redraw()
                return "break"
            if len(grab) == 6:
                list_id, context_key, selection, cursor_down, center_down, previous = grab
                if (id(items) != list_id or s.hole_session.active_context_key != context_key
                        or selection != ("round", idx) or items[idx] is not previous):
                    return "break"
                # Tk forwards cursor intent; the Engine owns the exact circle
                # circumference and checks every original physical cutout.
                center = type(center_down)(
                    center_down.x + (point.x - cursor_down.x),
                    center_down.y + (point.y - cursor_down.y),
                )
                try:
                    moved = api.move_physical_sheet_round_mark(
                        s.manual_marking_draft, items, selected_index=idx, centre=center,
                    )
                except (ValueError, TypeError, RuntimeError) as exc:
                    round_rejection = "圓打標移動被拒絕：" + str(exc)
                    s.redraw()
                    return "break"
                round_rejection = None
                s.hole_session.execute(HoleEditorAction.replace_selected(moved))
                drag_origin[0] = (*grab[:-1], moved)
                s.redraw()
                return "break"
            if not api.is_manual_group(items[idx]):
                return "break"
            list_id, context_key, group_id, cursor_down, center_down = grab
            if (list_id != id(items)
                    or context_key != s.hole_session.active_context_key
                    or group_id != api.group_parameters(items[idx])["group_id"]):
                return "break"
            # GUI only preserves the operator's grab delta: canonical
            # full-arm and local-mm geometry stays in the Engine API.
            center = type(center_down)(
                center_down.x + point.x - cursor_down.x,
                center_down.y + point.y - cursor_down.y,
            )
            try:
                moved = api.edit_physical_manual_group(
                    items[idx], center=center, part_key=s.part_key,
                    context=s.manual_marking_draft.context,
                    marking_draft=s.manual_marking_draft,
                    existing_features=tuple(items),
                )
            except (ValueError, TypeError, RuntimeError):
                return "break"
            clear_member_edit()
            corner_arm[0] = None
            s.hole_session.execute(HoleEditorAction.replace_selected(moved))
            s.redraw()
            return "break"
        return original_drag(event)

    def mark_double(event):
        # A native multi-click must obey the active insertion/copy tool.
        # Selecting group members is meaningful only in selection mode.
        if pending_copy is not None or s.manual_mark_mode[0] or s.insert_mode[0]:
            return mark_down(event)
        clear_member_edit()
        drag_origin[0] = None
        point = s.canvas_view.canvas_to_world(event.x, event.y)
        if point is None:
            return "break"

        # Resolve the *current* pointer hot spot, not the old Session
        # selection. A and B can both have a "top_right" member.
        hits = []
        for idx, item in enumerate(s.live_context.feature_list):
            if not api.is_manual_group(item):
                continue
            for member_id, corner in api.group_member_world_points(item):
                distance = hypot(point.x-corner.x, point.y-corner.y)
                if distance <= 5.0:
                    hits.append((distance, idx, member_id))
        if not hits:
            corner_arm[0] = None
            return "break"
        hits.sort()
        distance, target_idx, member = hits[0]
        if (any(idx != target_idx for _, idx, _ in hits)
                or (len(hits) > 1 and abs(hits[1][0]-distance) < 1e-9)):
            # Two coincident group corners are not an implicit selection.
            corner_arm[0] = None
            return "break"
        if s.hole_session.selected_index != target_idx:
            s.hole_session.execute(HoleEditorAction.select(target_idx))
            s.refresh_created()
        group = selected_group()
        if group is None:
            return "break"
        p = api.group_parameters(group)
        target = (
            p["group_id"], member, s.hole_session.active_context_key,
            id(s.live_context.feature_list),
        )
        if corner_arm[0] != target:
            # A first click just after Undo/delete may be classified by Tk
            # as Double/Triple from an earlier click sequence. It may arm
            # the *new* real corner, never authorize Apply on its own.
            corner_arm[0] = target
            return "break"
        dx, dy = next((x, y) for mid, x, y in p["members"] if mid == member)
        s.manual_group_edit_identity[0] = (p["group_id"], member)
        s.manual_group_edit_context[0] = (
            s.hole_session.active_context_key, id(s.live_context.feature_list),
        )
        s.manual_group_member.set(member)
        s.manual_group_offset_x.set(str(dx))
        s.manual_group_offset_y.set(str(dy))
        s.manual_group_arm_x.set(str(p["arm_x"]))
        s.manual_group_arm_y.set(str(p["arm_y"]))
        s.manual_group_spacing_x.set(str(p["spacing_x"]))
        s.manual_group_spacing_y.set(str(p["spacing_y"]))
        s.manual_group_angle.set(str(p["angle"]))
        return "break"

    def mark_escape(event=None):
        if pending_copy is not None or s.manual_mark_mode[0]:
            select_mode()
            return "break"
        if original_escape is not None:
            return original_escape(event)

    original_escape = s.on_escape if hasattr(s, "on_escape") else None
    original_toggle = s.toggle_created_process
    original_right = s.on_canvas_right
    original_rotate = s.rotate_selected

    def safe_toggle(event=None):
        clear_member_edit()
        # Both automatic MARKING and manual group features are non-process
        # contours; double-click must not turn them into CUTTING/BLIND_HOLE.
        chosen_index = s.created_list.curselection()
        idx = chosen_index[0] if chosen_index else s.hole_session.selected_index
        features = s.live_context.feature_list
        if (0 <= idx < len(features)
                and getattr(features[idx], "layer", None) == "MARKING"):
            return "break"
        return original_toggle(event)

    def selected_feature():
        idx = s.hole_session.selected_index
        rows = s.live_context.feature_list
        return rows[idx] if 0 <= idx < len(rows) else None

    def safe_right(event):
        clear_member_edit()
        chosen = selected_feature()
        if chosen is not None and getattr(chosen, "layer", None) == "MARKING":
            return "break"  # legacy rotation may corrupt authored MARKING
        return original_right(event)

    original_delete = s.delete_selected

    def safe_delete():
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        chosen = selected_feature()
        if (chosen is not None and getattr(chosen, "layer", None) == "MARKING"
                and not api.is_manual_mark(chosen)):
            return "break"  # source-owned automatic marking is readonly
        return original_delete()

    def rotate_selected(angle):
        clear_member_edit()
        group = selected_group()
        if group is not None:
            return publish_group_change(
                angle=api.group_parameters(group)["angle"] + angle)
        chosen = selected_feature()
        if chosen is not None and getattr(chosen, "layer", None) == "MARKING":
            return "break"
        return original_rotate(angle)

    # Other existing Tk routes may mutate selection without a Canvas press.
    # Keep the original Session and insertion handlers, only invalidate the
    # pending group-member edit at their public GUI boundaries.
    original_created_select = s.on_created_select
    original_undo = s.undo_last_action
    original_activate_context = s.hole_session.activate_context

    def safe_created_select(event=None):
        # A ListboxSelect event may be generated by refresh_created() for
        # the *same* group after its valid Canvas double-click. Do not
        # invalidate that authorization unless the selected identity changes.
        chosen = s.created_list.curselection()
        binding = s.manual_group_edit_identity[0]
        if binding is not None or corner_arm[0] is not None:
            idx = chosen[0] if chosen else -1
            rows = s.live_context.feature_list
            expected_group_id = (binding[0] if binding is not None
                                 else corner_arm[0][0])
            if (not 0 <= idx < len(rows) or not api.is_manual_group(rows[idx])
                    or api.group_parameters(rows[idx])["group_id"] != expected_group_id):
                clear_member_edit()
                corner_arm[0] = None
        return original_created_select(event)

    def safe_undo(event=None):
        if pending_copy is not None:
            select_mode()
            return "break"
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        return original_undo(event)

    def safe_activate_context(*args, **kwargs):
        if pending_copy is not None:
            select_mode()
        clear_member_edit()
        drag_origin[0] = None
        corner_arm[0] = None
        return original_activate_context(*args, **kwargs)

    s.on_created_select = safe_created_select
    s.undo_last_action = safe_undo
    s.undo_btn.configure(command=safe_undo)
    s.hole_session.activate_context = safe_activate_context
    s.toggle_created_process = safe_toggle
    s.on_canvas_right = safe_right
    s.delete_selected = safe_delete
    s.delete_btn.configure(command=safe_delete)
    s.rotate_selected = rotate_selected
    s.manual_mark_select_button.configure(command=select_mode)
    s.manual_mark_draw_button.configure(command=lambda: draw_mode("line"))
    if hasattr(s, "manual_round_button"):
        s.manual_round_button.configure(command=lambda: draw_mode("circle"))
    for kind, button in s.manual_group_tools.items():
        button.configure(command=lambda key=kind: draw_mode(key))
    s.manual_group_apply_offset.configure(command=edit_selected_member)
    s.manual_group_apply_size.configure(command=edit_group_size)
    s.manual_group_rotate.configure(command=rotate_group)
    s.manual_group_mirror.configure(command=mirror_group)

    # Capture the actual target session at editor creation, not after a
    # file selector returns (which may run another Tk event loop).
    copy_host = s.host
    copy_app = getattr(copy_host, "fold_designer_app", None)
    copy_workspace = getattr(copy_app, "designer_workspace", None)
    copy_controller = getattr(copy_host, "project_controller", None)
    copy_epoch = getattr(copy_controller, "project_load_epoch", None)
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
    try:
        copy_target_state = api.project_live_manual_marking_copy_target_state(
            current_workspace_marking_source(copy_app), s.part_key,
            editor_features=tuple(s.feature_list),
        )
    except (ValueError, TypeError):
        copy_target_state = None  # Independent/scoped editors do not gain Copy authority.

    def live_copy_target(path):
        from pathlib import Path
        from phase6_manufacturing_adapter import build_scene_payload_for_app

        current_path = getattr(copy_controller, "project_path", None)
        if (copy_app is None or copy_workspace is None or copy_epoch is None
                or getattr(copy_host, "fold_designer_app", None) is not copy_app
                or copy_app.designer_workspace is not copy_workspace
                or getattr(copy_host, "project_controller", None) is not copy_controller
                or copy_controller.project_load_epoch != copy_epoch
                or not current_path or Path(current_path).resolve(strict=True) != path
                or s.part_key != "base_plate"
                or s.part_key not in copy_workspace.available_parts
                or copy_target_state is None):
            raise ValueError("MANUAL_COPY_TARGET_EDITOR_SESSION_STALE")
        live = current_workspace_marking_source(copy_app)
        if api.project_live_manual_marking_copy_target_state(live, s.part_key) != copy_target_state:
            raise ValueError("MANUAL_COPY_TARGET_EDITOR_SESSION_STALE")
        # Same original physical editor pipeline, including its ordinary
        # baseline hole handling. No second coordinate or material builder.
        payload = build_scene_payload_for_app(copy_app, s.part_key)
        payload["features"] = ()
        render = copy_host._query_fold_designer_render_data(s.part_key, payload)
        context = api.resolve_physical_sheet_editor_context(s.part_key, render)
        return context, live

    def verified_copy_args(receipt):
        context, live_snapshot = live_copy_target(receipt["target_project_path"])
        return {**receipt, "target_context": context, "target_live_snapshot": live_snapshot}

    def place_pending_copy(point):
        nonlocal pending_copy, copy_rejection
        if pending_copy is None:
            return "break"
        pending = pending_copy
        try:
            if (pending["context"] != s.hole_session.active_context_key
                    or pending["list_id"] != id(s.live_context.feature_list)
                    or pending["features"] != tuple(s.live_context.feature_list)
                    or s.insert_mode[0]):
                raise ValueError("MANUAL_COPY_TARGET_EDITOR_SESSION_STALE")
            args = verified_copy_args(pending["receipt"])
            # Recheck both the opened and current physical target before
            # any retryable placement error can retain the source receipt.
            api.verify_saved_manual_marking_copy_sources(
                **{**args, "target_context": s.manual_marking_draft.context},
            )
            clone = api.copy_saved_manual_marking_group_to_selected_sheet(
                **args, target_features=tuple(s.live_context.feature_list),
                target_position=point,
            )
        except api.ManualCopyPlacementRejected as exc:
            copy_rejection = "跨板定位被拒絕：" + str(exc) + "；請重新選點（Esc 取消）"
            s.redraw()
            return "break"
        except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
            select_mode()
            copy_rejection = "跨板定位被拒絕：" + str(exc)
            s.redraw()
            return "break"
        select_mode()
        s.hole_session.execute(HoleEditorAction.commit_active())
        s.hole_session.execute(HoleEditorAction.insert(clone))
        s.hole_session.execute(HoleEditorAction.commit_active())
        try:
            s.refresh_created()
            s.sync_all()
            s.redraw()
        except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
            s.hole_session.execute(HoleEditorAction.undo())
            s.refresh_created()
            s.redraw()
            copy_rejection = "跨板定位被拒絕：" + str(exc)
            s.redraw()
            return "break"
        placed_copy_receipts[api.group_parameters(clone)["group_id"]] = pending["receipt"]
        return "break"

    original_confirm_features = s.on_confirm_features

    def confirm_with_copy_sources(features):
        if pending_copy is not None:
            raise ValueError("MANUAL_COPY_TARGET_POSITION_REQUIRED")
        for feature in features:
            if not api.is_manual_group(feature):
                continue
            receipt = placed_copy_receipts.get(api.group_parameters(feature)["group_id"])
            if receipt is not None:
                args = verified_copy_args(receipt)
                api.verify_saved_manual_marking_copy_sources(**args)
                api.propose_operator_physical_sheet_hole_features(
                    s.part_key, args["target_context"], tuple(features),
                )
        return original_confirm_features(features)

    if original_confirm_features is not None:
        s.on_confirm_features = confirm_with_copy_sources

    def copy_from_other_saved_project():
        """Select one saved group; wait for the operator's target anchor."""
        nonlocal pending_copy, copy_rejection
        from hashlib import sha256
        from pathlib import Path
        from tkinter import filedialog, simpledialog
        from phase6_project_file import read_project

        select_mode()
        target_project = getattr(
            getattr(s.host, "project_controller", None), "project_path", None,
        )
        if not target_project:
            copy_rejection = "跨板複製：請先儲存目標專案，再選擇其他已存來源"
            checked_redraw()
            return False
        try:
            source_project = filedialog.askopenfilename(
                parent=s.editor, title="選擇有手動打標的來源專案 .p6fold",
                filetypes=(("WHD 專案", "*.p6fold"),),
            )
            if not source_project:
                return False
            source_path = Path(source_project).resolve(strict=True)
            target_path = Path(target_project).resolve(strict=True)
            source_sha = sha256(source_path.read_bytes()).hexdigest()
            target_sha = sha256(target_path.read_bytes()).hexdigest()
            source_data = read_project(source_path)["snapshot"]
            target_data = read_project(target_path)["snapshot"]
            candidates = api.list_saved_manual_marking_copy_groups(
                source_snapshot=source_data,
                source_project_path=source_path,
                source_project_sha256=source_sha,
            )
            if not candidates:
                raise ValueError("MANUAL_COPY_SOURCE_GROUP_MISSING")
            if len(candidates) == 1:
                selected_id = candidates[0]
            else:
                selected_id = simpledialog.askstring(
                    "選擇打標群組", "來源有多個群組，請輸入要複製的群組 ID：\n"
                    + "\n".join(candidates), parent=s.editor,
                )
                if selected_id is None:
                    return False
            if original_confirm_features is None:
                raise ValueError("MANUAL_COPY_TARGET_EDITOR_CONFIRM_REQUIRED")
            receipt = dict(
                source_snapshot=source_data, source_project_path=source_path,
                source_project_sha256=source_sha,
                target_snapshot=target_data, target_project_path=target_path,
                target_project_sha256=target_sha, source_group_id=selected_id,
            )
            args = verified_copy_args(receipt)
            group = api.verify_saved_manual_marking_copy_sources(**args)
            api.verify_saved_manual_marking_copy_sources(
                **{**args, "target_context": s.manual_marking_draft.context},
            )
            kind = api.group_parameters(group)["kind"]
            prompt = ("跨板複製：點選目標轉角" if kind == "l" else
                      "跨板複製：點選目標交點" if kind == "cross" else
                      "跨板複製：點選目標群組中心") + "（Esc 取消）"
        except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
            # No copy is pending yet. Preserve the warning on passive
            # redraw without disabling Confirm for unrelated valid edits.
            copy_rejection = "跨板複製被拒絕：" + str(exc)
            checked_redraw()
            return False
        draw_mode("copy")
        pending_copy = {
            "receipt": receipt, "prompt": prompt,
            "context": s.hole_session.active_context_key,
            "list_id": id(s.live_context.feature_list),
            "features": tuple(s.live_context.feature_list),
        }
        s.redraw()
        return True

    original_insert_mode = s.set_insert_mode
    original_catalog_double = s.on_catalog_double_click

    def hole_insert_mode(force=None):
        entering = not s.insert_mode[0] if force is None else bool(force)
        if entering and (s.manual_mark_mode[0] or pending_copy is not None or copy_rejection is not None):
            select_mode()
        return original_insert_mode(force)

    def hole_catalog_double(event=None, source_list=None):
        result = original_catalog_double(event, source_list)
        if s.insert_mode[0] and (s.manual_mark_mode[0] or pending_copy is not None or copy_rejection is not None):
            select_mode()
        return result

    s.set_insert_mode = hole_insert_mode
    s.insert_btn.configure(command=hole_insert_mode)
    s.on_catalog_double_click = hole_catalog_double

    if _has_group_mark_tools(s):
        s.manual_mark_copy_button.configure(command=copy_from_other_saved_project)
        s.editor._manual_group_copy_from_saved = copy_from_other_saved_project
    select_mode()
    s.on_canvas_down = mark_down
    s.on_canvas_drag = safe_drag
    s.on_canvas_up = safe_up
    s.manual_mark_escape = mark_escape
    s.editor._manual_marking_place = mark_down
    s.editor._manual_marking_select = select_mode
    if _has_group_mark_tools(s):
        s.editor._manual_group_double = mark_double
        s.canvas.bind("<Double-Button-1>", mark_double)
        s.canvas.bind("<Triple-Button-1>", mark_double)
        s.canvas.bind("<Quadruple-Button-1>", mark_double)

def _bind_editor_events(s):
    # CADCraft is an opt-in external inspection only. Re-resolve the active
    # editor context on click (including inner-door context switches); never
    # import CADCraft edits or mutate this editor's pending feature session.
    cadcraft_button = getattr(s.editor, "_hole_header_cadcraft", None)
    if cadcraft_button is not None:
        def preview_in_cadcraft():
            from .cadcraft_preview_bridge import open_hole_editor_cadcraft_preview
            try:
                saved = open_hole_editor_cadcraft_preview(
                    surface=s.live_context.surface,
                    features=s.live_context.feature_list,
                    width=s.live_context.width,
                    height=s.live_context.height,
                    baseline_scene=s.live_context.baseline_scene,
                )
            except (OSError, ValueError, TypeError) as exc:
                s.d.messagebox.showerror("CADCraft 試看", str(exc), parent=s.editor)
            else:
                s.d.messagebox.showinfo(
                    "CADCraft 試看",
                    "已在 CADCraft 開啟暫存檢視圖：\n"
                    + str(saved)
                    + "\nCADCraft 內修改不會回寫 WHD；請繼續使用原 2D 開孔編輯器儲存孔位。",
                    parent=s.editor,
                )
        cadcraft_button.configure(command=preview_in_cadcraft)

    return_button = getattr(s.editor, "_hole_header_cadcraft_return", None)
    status_label = getattr(s.editor, "_hole_header_cadcraft_status", None)
    s.editor._hole_cadcraft_return_ticket = None
    s.editor._hole_cadcraft_gui_process = None
    s.editor._hole_cadcraft_control_port = None
    trial_button = getattr(s.editor, "_hole_header_cadcraft_draw", None)
    if trial_button is not None:
        def draw_new_cadcraft_picture():
            """Opt-in new CADCraft drawing from WHD coordinates, never a save."""
            from queue import Empty, Queue
            from threading import Thread
            from .cadcraft_command_preview_bridge import (
                find_cadcraft_cli, prepare_whd_cadcraft_commands,
                draw_whd_commands_with_cadcraft,
            )
            try:
                context = s.live_context
                old_snapshot = s.hole_session.snapshot()
                instructions = prepare_whd_cadcraft_commands(
                    surface=context.surface,
                    features=tuple(context.feature_list),
                    width=context.width, height=context.height,
                )
                executable = find_cadcraft_cli()
            except (OSError, ValueError, TypeError) as exc:
                s.d.messagebox.showerror("CADCraft 指令繪圖試作", str(exc), parent=s.editor)
                return

            # Any new drawing invalidates a previous manual-return provenance.
            s.editor._hole_cadcraft_return_ticket = None
            s.editor._hole_cadcraft_control_port = None
            if return_button is not None:
                return_button.configure(state="disabled")
            if status_label is not None:
                status_label.configure(text="正在產生 CADCraft 開孔交換圖…")
            trial_button.configure(state="disabled")
            result_queue = Queue(maxsize=1)

            def worker():
                try:
                    result = draw_whd_commands_with_cadcraft(
                        instructions=instructions, executable=executable)
                    result_queue.put(("ok", result))
                except Exception as exc:
                    result_queue.put(("error", str(exc)))

            def poll_for_result():
                try:
                    if not s.editor.winfo_exists():
                        return
                    status, outcome = result_queue.get_nowait()
                except Empty:
                    s.editor.after(100, poll_for_result)
                    return
                trial_button.configure(state="normal")
                if status != "ok":
                    s.d.messagebox.showerror(
                        "CADCraft 指令繪圖試作", str(outcome), parent=s.editor)
                elif s.hole_session.snapshot() != old_snapshot:
                    s.d.messagebox.showwarning(
                        "CADCraft 指令繪圖試作",
                        "WHD 開孔已變更，本次 CADCraft 出圖僅供舊版對照：\n"
                        + str(outcome.preview_png),
                        parent=s.editor,
                    )
                else:
                    # Establish a live ticket from the *exact* verified DXF.
                    # Synthetic GUI tests may intentionally supply only an
                    # isolated test path, not a physical proof output.
                    return_denied = "隔離 DXF 檔案不存在"
                    if outcome.output_dxf.is_file():
                        from .cadcraft_manual_hole_return_bridge import (
                            create_manual_return_ticket,
                        )
                        try:
                            ticket = create_manual_return_ticket(
                                output=outcome.output_dxf,
                                features=old_snapshot.features,
                                session=s.hole_session,
                                surface=context.surface,
                                width=context.width, height=context.height,
                            )
                        except (OSError, ValueError, TypeError) as exc:
                            return_denied = str(exc)
                        else:
                            return_denied = ""
                            s.editor._hole_cadcraft_return_ticket = ticket
                            if return_button is not None:
                                return_button.configure(state="normal")
                    # Issue the GUI launch only AFTER the original WHD
                    # provenance ticket is validated; no blocking modal dialog
                    # that would keep the CADCraft window behind WHD.
                    if return_denied:
                        if status_label is not None:
                            status_label.configure(text="CADCraft 交換圖不可回傳")
                        s.d.messagebox.showerror(
                            "CADCraft 開孔編輯", "交換圖建立但無法回傳：" + return_denied,
                            parent=s.editor,
                        )
                    else:
                        from .cadcraft_command_preview_bridge import (
                            open_cadcraft_hole_editor,
                        )
                        try:
                            from .cadcraft_live_return_bridge import (
                                reserve_cadcraft_control_port,
                            )
                            control_port = reserve_cadcraft_control_port()
                            process = open_cadcraft_hole_editor(
                                ticket.output, control_port=control_port
                            )
                        except (OSError, ValueError, TypeError) as exc:
                            if status_label is not None:
                                status_label.configure(text="CADCraft 啟動失敗")
                            s.d.messagebox.showerror(
                                "CADCraft 開孔編輯",
                                "無法開啟 CADCraft 編輯視窗：" + str(exc)
                                + "\n交換圖仍保留：" + str(ticket.output),
                                parent=s.editor,
                            )
                        else:
                            s.editor._hole_cadcraft_gui_process = process
                            # Synthetic GUI tests may use a no-process launch
                            # stub; only a real pollable process owns live TCP.
                            s.editor._hole_cadcraft_control_port = (
                                control_port if callable(getattr(process, "poll", None))
                                else None
                            )
                            if status_label is not None:
                                status_label.configure(
                                    text="CADCraft 已啟動；修改後直接按『改孔回傳』"
                                )
                            # Windows starts a visible process asynchronously;
                            # the program window may initially sit behind this
                            # modal WHD editor. Hand foreground over only while
                            # WHD still owns foreground (never steal focus from
                            # another app the user switched to meanwhile).
                            from .cadcraft_command_preview_bridge import (
                                focus_started_cadcraft_window,
                            )
                            pid = getattr(process, "pid", None)
                            if isinstance(pid, int) and pid > 0:
                                def focus_new_cadcraft(attempt=0):
                                    if not s.editor.winfo_exists():
                                        return
                                    if focus_started_cadcraft_window(pid):
                                        return
                                    if attempt < 12 and process.poll() is None:
                                        s.editor.after(
                                            150, lambda: focus_new_cadcraft(attempt + 1)
                                        )
                                    elif status_label is not None:
                                        status_label.configure(
                                            text="CADCraft 已啟動；若視窗在後方請 Alt+Tab"
                                        )
                                s.editor.after(180, focus_new_cadcraft)

            Thread(target=worker, name="whd-cadcraft-command-draw", daemon=True).start()
            s.editor.after(100, poll_for_result)

        trial_button.configure(command=draw_new_cadcraft_picture)

    if return_button is not None:
        def stage_return_ticket(ticket):
            """Reuse the original WHD preview/confirm/cancel path unchanged."""
            from .cadcraft_manual_hole_return_bridge import stage_manual_cadcraft_return
            try:
                pending = stage_manual_cadcraft_return(ticket)
            except (OSError, ValueError, TypeError) as exc:
                s.d.messagebox.showerror("CADCraft 改孔回傳", str(exc), parent=s.editor)
                return
            s.refresh_created()
            s.redraw()
            move_details = [
                f"原孔 {index + 1}: X {dx:+.3f} mm、Y {dy:+.3f} mm"
                for index, dx, dy in pending.moves
            ]
            added_details = [
                f"新孔 {index + 1}: {type(feature).__name__}"
                for index, feature in enumerate(pending.additions)
            ]
            details = "\n".join(move_details + added_details)
            confirmed = False
            try:
                confirmed = s.d.messagebox.askyesno(
                    "CADCraft 改孔回傳 — WHD 預覽",
                    f"已驗證 {len(pending.moves)} 個原孔平移、"
                    f"{len(pending.additions)} 個新孔（原孔尺寸、孔型不變）：\n"
                    + details
                    + "\n\n確認：提交至 WHD 原開孔 Session；"
                      "取消：復原預覽、不更改原孔。\n"
                      "製造圖仍由 WHD 原本的主編輯器『確定／儲存』流程產生。",
                    parent=s.editor,
                )
                if confirmed:
                    pending.confirm()
                else:
                    pending.cancel()
                    if status_label is not None:
                        status_label.configure(text="已取消 CADCraft 回傳，原孔不變")
            except Exception as exc:
                if pending.stage.active:
                    pending.cancel()
                s.d.messagebox.showerror("CADCraft 改孔回傳", str(exc), parent=s.editor)
                return
            finally:
                s.refresh_created()
                s.redraw()
            if confirmed:
                s.editor._hole_cadcraft_return_ticket = None
                return_button.configure(state="disabled")
                if status_label is not None:
                    status_label.configure(text="CADCraft 孔位已送回 WHD")
                s.d.messagebox.showinfo(
                    "CADCraft 改孔回傳",
                    "新增／平移孔位已確認至 WHD Session。請在原開孔編輯器按『確定』，"
                    "由 WHD 原流程儲存並重新產生製造圖。",
                    parent=s.editor,
                )

        def return_manually_moved_holes():
            """Read unsaved native CADCraft via TCP, with legacy saved-DXF fallback."""
            from queue import Empty, Queue
            from threading import Thread
            ticket = getattr(s.editor, "_hole_cadcraft_return_ticket", None)
            if ticket is None:
                s.d.messagebox.showerror(
                    "CADCraft 改孔回傳", "尚無有效的 WHD→CADCraft 交換圖，請先指令出圖。",
                    parent=s.editor,
                )
                return
            port = getattr(s.editor, "_hole_cadcraft_control_port", None)
            process = getattr(s.editor, "_hole_cadcraft_gui_process", None)
            if port is None or not callable(getattr(process, "poll", None)):
                # Legacy user-saved disposable DXF remains independently valid.
                stage_return_ticket(ticket)
                return
            from .cadcraft_live_return_bridge import capture_unsaved_cadcraft_return
            return_button.configure(state="disabled")
            if status_label is not None:
                status_label.configure(text="正在讀取 CADCraft 即時圖元…")
            queue = Queue(maxsize=1)

            def worker():
                try:
                    captured = capture_unsaved_cadcraft_return(
                        ticket, port=port, process=process,
                    )
                    queue.put(("ok", captured))
                except Exception as exc:
                    queue.put(("error", str(exc)))

            def poll():
                if not s.editor.winfo_exists():
                    return
                try:
                    status, result = queue.get_nowait()
                except Empty:
                    s.editor.after(100, poll)
                    return
                return_button.configure(state="normal")
                if status != "ok":
                    # Preserve old disk-based exchange as a manual fallback.
                    s.editor._hole_cadcraft_control_port = None
                    if status_label is not None:
                        status_label.configure(text="CADCraft TCP 回傳失敗；可先存檔再回傳")
                    s.d.messagebox.showerror(
                        "CADCraft 即時回傳",
                        str(result) + "\n若已在 CADCraft 存檔，可再按『改孔回傳』使用舊流程。",
                        parent=s.editor,
                    )
                    return
                stage_return_ticket(result)

            Thread(target=worker, name="whd-cadcraft-live-capture", daemon=True).start()
            s.editor.after(100, poll)

        return_button.configure(command=return_manually_moved_holes)
    s.editor.bind("<F11>", s.toggle_fullscreen)
    s.editor.bind("<Control-z>", s.undo_last_action)
    s.editor.bind("<Control-Z>", s.undo_last_action)
    s.editor.bind("<Escape>", (
        s.manual_mark_escape if getattr(s, "manual_marking_draft", None) is not None else s.on_escape
    ))
    s.editor.protocol("WM_DELETE_WINDOW", s.cancel_all)
    s.catalog_list.bind(
        "<<ListboxSelect>>", lambda event: s.on_catalog_select(event, s.catalog_list)
    )
    s.catalog_list.bind(
        "<Double-Button-1>",
        lambda event: s.on_catalog_double_click(event, s.catalog_list),
    )
    s.pipe_catalog_list.bind(
        "<<ListboxSelect>>",
        lambda event: s.on_catalog_select(event, s.pipe_catalog_list),
    )
    s.pipe_catalog_list.bind(
        "<Double-Button-1>",
        lambda event: s.on_catalog_double_click(event, s.pipe_catalog_list),
    )
    s.created_list.bind("<<ListboxSelect>>", s.on_created_select)
    s.created_list.bind("<Double-Button-1>", s.toggle_created_process)
    s.canvas.bind("<Button-1>", s.on_canvas_down)
    s.canvas.bind("<B1-Motion>", s.on_canvas_drag)
    s.canvas.bind("<ButtonRelease-1>", s.on_canvas_up)
    s.canvas.bind("<Button-3>", s.on_canvas_right)
    s.canvas.bind("<Configure>", lambda event: s.redraw())
    s.refresh_created()
    s.editor.after(50, s.redraw)


def open_unified_hole_editor(
    host, part_key, title, surface, width, height, sync_callback=None,
    reference_guide=None, feature_list_override=None, door_indicator_state=None,
    door_indicator_context=None, door_indicator_commit=None, door_frame_edges=None,
    door_gap_w=None, door_gap_h=None, door_frame_width=None, door_thickness=None,
    on_close=None, on_confirm=None, on_confirm_features=None,
    baseline_scene=None, baseline_status_text=None,
    indicator_component_context_provider=None, cabinet_reference_guide=None,
    local_reference_guide=None, manual_marking_draft=None,
    defer_workspace_sync=False, skip_cancel_sync=False, solid_marking_only=False, *, dependencies,
):
    s = SimpleNamespace(
        host=host, d=dependencies, part_key=part_key, title=title, surface=surface,
        width=width, height=height, sync_callback=sync_callback,
        reference_guide=reference_guide, cabinet_reference_guide=cabinet_reference_guide,
        local_reference_guide=local_reference_guide,
        feature_list_override=feature_list_override,
        door_indicator_state=door_indicator_state,
        door_indicator_context=door_indicator_context,
        door_indicator_commit=door_indicator_commit, door_frame_edges=door_frame_edges,
        door_gap_w=door_gap_w, door_gap_h=door_gap_h,
        door_frame_width=door_frame_width, door_thickness=door_thickness,
        on_close=on_close, on_confirm=on_confirm,
        on_confirm_features=on_confirm_features, baseline_scene=baseline_scene,
        baseline_status_text=baseline_status_text,
        indicator_component_context_provider=indicator_component_context_provider,
        manual_marking_draft=manual_marking_draft, solid_marking_only=solid_marking_only,
        defer_workspace_sync=defer_workspace_sync,
        skip_cancel_sync=skip_cancel_sync,
    )
    _prepare_model(s)
    _build_shell_and_indicator(s)
    _build_sidebar_workspace_state(s)
    _build_reference_stack(s)
    _build_renderer_and_catalog_actions(s)
    _guard_manual_marking_sync(s)
    _build_pointer_and_created_actions(s)
    _build_reference_selection_actions(s)
    _build_navigation_and_lifecycle(s)
    _install_manual_marking_actions(s)
    _bind_editor_events(s)
