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
        "RectGuide", "Vec2", "ae", "load_hole_catalog", "load_pipe_catalog",
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
        "_HoleEditorSelectedFeatureActions", "REFERENCE_ANCHOR_LABELS", "replace",
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
    hole_base_dir = d.ae.baseline_hole_catalog_root_path()
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
        normalize_state=host._normalize_door_indicator_state,
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
        sync_callback=s.sync_callback, draw_preview=s.host.draw_preview,
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
        rotate_feature=lambda feature, rotation: d.replace(feature, rotation_deg=rotation),
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
        insert_mode=s.insert_mode,
        set_insert_mode=s.set_insert_mode,
        cancel_active_edit=s.cancel_active_edit,
    )
    s.confirm_reference_edit = modal_lifecycle.confirm_reference_edit
    s.confirm_all = modal_lifecycle.confirm_all
    s.cancel_all = modal_lifecycle.cancel_all
    s.on_escape = modal_lifecycle.on_escape
    s.confirm_ref_btn.configure(command=s.confirm_reference_edit)
    s.cancel_ref_btn.configure(command=s.cancel_active_edit)
    s.undo_btn.configure(command=s.undo_last_action)
    s.confirm_all_btn.configure(command=s.confirm_all)
    s.cancel_all_btn.configure(command=s.cancel_all)


def _bind_editor_events(s):
    s.editor.bind("<F11>", s.toggle_fullscreen)
    s.editor.bind("<Control-z>", s.undo_last_action)
    s.editor.bind("<Control-Z>", s.undo_last_action)
    s.editor.bind("<Escape>", s.on_escape)
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
    on_close=None, baseline_scene=None, baseline_status_text=None,
    indicator_component_context_provider=None, *, dependencies,
):
    s = SimpleNamespace(
        host=host, d=dependencies, part_key=part_key, title=title, surface=surface,
        width=width, height=height, sync_callback=sync_callback,
        reference_guide=reference_guide, feature_list_override=feature_list_override,
        door_indicator_state=door_indicator_state,
        door_indicator_context=door_indicator_context,
        door_indicator_commit=door_indicator_commit, door_frame_edges=door_frame_edges,
        door_gap_w=door_gap_w, door_gap_h=door_gap_h,
        door_frame_width=door_frame_width, door_thickness=door_thickness,
        on_close=on_close, baseline_scene=baseline_scene,
        baseline_status_text=baseline_status_text,
        indicator_component_context_provider=indicator_component_context_provider,
    )
    _prepare_model(s)
    _build_shell_and_indicator(s)
    _build_sidebar_workspace_state(s)
    _build_reference_stack(s)
    _build_renderer_and_catalog_actions(s)
    _build_pointer_and_created_actions(s)
    _build_reference_selection_actions(s)
    _build_navigation_and_lifecycle(s)
    _bind_editor_events(s)
