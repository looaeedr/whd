# -*- coding: utf-8 -*-
"""Use the existing Vault Door hole editor for one Receiving inner-door sheet.

Only the GUI adapter lives here. Manufacturing topology, features, and the
inner-door dimensions remain with their established authority owners.
"""
from __future__ import annotations


def is_inner_door_sheet(part_key: object) -> bool:
    key = str(part_key or "")
    return key.startswith("inner_door:") and key.endswith(":panel")



def inner_door_commit_target(settings_mode):
    """Binding is the actual launch entry, NEVER global set_bay/quantity data.

    Only the explicit 多連設定 inner-door editor receives candidate ownership.
    Ordinary board/corner/part-preview and 單只 settings write physical parts
    on the parent editor Confirm All. NFB tab Confirm never writes either.
    """
    if settings_mode == "candidate":
        return "candidate"
    if settings_mode in (None, "single"):
        return "physical"
    raise ValueError("未知的內門編輯來源")


def inner_door_work_area_guide(snapshot, panel, structural):
    """Project the source door-layout cell into the local inner-door editor.

    The outer 800×1100 (or selected cell W/H) is a measurement/display guide,
    NOT a new CUTTING surface or feature-local coordinate system. Door feature
    coordinates and manufacturing remain in the real 19-mm folded sheet.
    """
    from ae_engine.cabinet_types.receiving import (
        DOOR_DEFAULTS, inner_door_panel_vertical_contract,
    )
    from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
    from ae_engine.sheetmetal_features import RectGuide, Vec2

    columns = tuple(snapshot.get("door_layout_columns") or ())
    cells = derive_door_layout_cells(columns)
    cell_key = str(panel.cell_key)
    cell = next((item for item in cells
                 if f"{item.column_index}:{item.row_index}" == cell_key), None)
    if cell is None:
        raise ValueError(f"內門 {panel.inner_door_id} 找不到所屬作業區 {cell_key}")

    vertical = inner_door_panel_vertical_contract(
        cell_height=cell.start_height,
        thickness=panel.thickness,
        gap_h=float(snapshot.get("door_gap_h", DOOR_DEFAULTS["door_gap_h"])),
    )
    # Panel is vertically lower inside its work-area cell by half the top-frame
    # occupation. In local unfolded-door coordinates the CELL center is higher
    # than the panel center; X stays symmetrically centered between side frames.
    cx = float(structural.width) / 2.0
    cy = float(structural.height) / 2.0 - vertical["center_offset_y"]
    half_w = float(cell.start_width) / 2.0
    half_h = float(cell.start_height) / 2.0
    return RectGuide(
        Vec2(cx - half_w, cy - half_h),
        Vec2(cx + half_w, cy + half_h),
        "receiving_inner_door_work_area",
    )


def open_inner_door_hole_editor(
    app, part_key: str, *, from_corner_data=False, from_part_preview=False,
    settings_mode=None, initial_features=None, on_settings_confirm=None,
    selected_candidate_version=None, physical_snapshot=None,
):
    """Open the existing Vault Door hole editor; preserve view-only Corner Data selection."""
    if not is_inner_door_sheet(part_key):
        raise ValueError("不是可開孔編輯的內門門板")
    workspace = app.designer_workspace
    if settings_mode is None and part_key not in workspace.available_parts:
        raise ValueError("內門門板目前不在有效板件清單")
    host = getattr(getattr(app, "_scene_query_callback", None), "__self__", None)
    # Use the entry identity captured at window creation, not the project's
    # stored Set/Bay data or another settings window's existence.
    inner_door_commit_target(settings_mode)
    # An explicit settings-button entry already identifies this physical panel;
    # the old panel-double-click path still requires active-part selection.
    if settings_mode is None and str(workspace.active_part) != part_key:
        corner_selected = (
            from_corner_data
            and str(getattr(app, "_phase6_3d_display_mode", "") or "") == "corner_data"
            and str(getattr(app, "_phase6_corner_data_selected_part_key", "") or "") == part_key
        )
        preview_selected = (
            from_part_preview
            and getattr(getattr(host, "workspace_controller", None), "active_part", None) == part_key
        )
        if not corner_selected and not preview_selected:
            raise ValueError("請先選取要開孔的內門門板")

    if host is None or not callable(getattr(host, "_open_unified_hole_editor", None)):
        raise ValueError("未連接既有金庫型門板開孔編輯器")

    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_part_adapters import (
        build_door_result, build_finished_reference_guide, DoorFrameEdges,
    )
    from ae_engine.sheetmetal_features import feature_surface_from_structural_result
    from ae_engine import manufacturing_api

    snapshot = dict(app._phase6_input_snapshot if physical_snapshot is None
                    else physical_snapshot)
    panel = next((
        item for item in cabinet_family_policy.derive_inner_door_panels(snapshot)
        if item.stable_id == part_key
    ), None)
    if panel is None:
        raise ValueError("目前專案沒有這片內門門板")

    # Both editing and manufacturing use the Vault Door finished-face anchor,
    # independent of the outer door's FW, gaps, and bending settings.
    structural = build_door_result(
        w=panel.width, h=panel.height, t=panel.thickness,
        fw=25.0, gap_w=0.0, gap_h=0.0,
        fold_left=19.0, fold_right=19.0,
        fold_top=19.0, fold_bottom=19.0,
        frame_edges=DoorFrameEdges(
            left=False, right=False, top=False, bottom=False,
        ),
    )
    surface = feature_surface_from_structural_result("door", structural)
    # Original checkbox: OFF measures from the real inner-door finished face;
    # ON measures from its authoritative full work-area (e.g. 800 x 1100).
    door_guide = build_finished_reference_guide(
        "door", structural, finished_width=panel.width,
        finished_height=panel.height,
    )
    work_area_guide = inner_door_work_area_guide(snapshot, panel, structural)
    # The inner-door hole UI must show the same physical CUTTING/BEND as
    # its produced DXF. Reuse Vault certified folding/corner rules without
    # importing the OUTER Vault Door's fixed handle/nameplate holes into a
    # Receiving inner-door/NFB physical hole owner.
    render = manufacturing_api.build_inner_door_panel_render_data(panel)
    from copy import deepcopy
    features = (workspace.features_for(part_key) if initial_features is None
                else deepcopy(list(initial_features)))

    def commit():
        # Workspace is authoritative; original outer Door holes remain separate.
        workspace.stash_features(part_key, features)
        # A Corner Data editor must not overwrite another active part's hole preview.
        if str(workspace.active_part) == part_key:
            app._load_part_holes(part_key)
        app.submit_update_intent("geometry", commit=True)
        if (
            from_corner_data
            and str(getattr(app, "_phase6_3d_display_mode", "") or "") == "corner_data"
        ):
            refresh = getattr(app, "_phase6_refresh_corner_data_unfold_view", None)
            if callable(refresh):
                refresh()

    def confirm_settings(final_features):
        # Hole Editor calls this ONLY on 確定全部.  No candidate / Bay writes
        # occur on its live sync or on 取消全部.
        editor = getattr(host, "last_unified_hole_editor", None)
        staged = getattr(editor, "_receiving_staged_config", None)
        if on_settings_confirm is not None:
            on_settings_confirm(part_key, deepcopy(list(final_features)), staged)
        elif staged is not None and any(
                getattr(feature, "source_type", None) == "NFB_CSV_SOURCE"
                for feature in final_features):
            # 3D double-click is a DIRECT physical-door entry. The original
            # handler used to save native Features only; the staged NFB
            # selection was silently discarded by the next canonical
            # Set/Bay projection. Commit its complete CSV source AND holes
            # through the same physical Bay adapter as Single settings.
            from ae_engine.receiving_inner_door_candidates import validate_door_config
            import fold_designer_bridge as bridge
            owner = bridge._phase6_composition(app)
            config = validate_door_config(staged)
            config = deepcopy(config)
            config.setdefault("features", {})[part_key] = deepcopy(list(final_features))
            mode = workspace.active_mode
            if mode == "set_bay":
                adapter = owner.receiving_adapter(vars(bridge))
                selected = adapter.selection
                adapter.apply_inner_door_candidate_to_bays(
                    config, selected.set_index, (selected.bay_index,),
                    version_id="",
                )
                owner.mark_receiving_switch_layout_dirty(vars(bridge), adapter)
                owner.sync_receiving_current_bay(
                    vars(bridge), refresh_controls=False,
                )
                app.submit_update_intent("geometry", commit=True)
            elif mode == "quantity":
                from ae_engine.receiving_quantity_box import update_common_box
                from ae_engine.receiving_nfb_csv_committed_config import (
                    committed_csv_nfb_config, preview_quantity_nfb_submission,
                )
                from ae_engine.receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
                current = app._phase6_input_snapshot
                projected = update_common_box(current, {
                    "inner_door_layers": config["layers"],
                    "inner_door_models": deepcopy(config["models"]),
                    "inner_door_layer_heights_mm": deepcopy(
                        config.get("layer_heights_mm")
                    ),
                })
                typed = committed_csv_nfb_config(
                    part_key, final_features, config,
                )
                quantity = workspace.quantity_model
                projected = preview_quantity_nfb_submission(
                    projected, quantity, typed,
                )
                quantity.set_version_nfb_config(
                    quantity.selected_version_id, submitted=True,
                    config=typed,
                )
                current.pop(RECEIVING_RUNTIME_SELECTION_KEY, None)
                current.update(projected)
                workspace.set_receiving_common_box(
                    projected["receiving_quantity_box"]
                )
                owner.receiving_adapter(vars(bridge), reset=True)
                owner.sync_receiving_current_bay(
                    vars(bridge), refresh_controls=False,
                )
                workspace.stash_features(part_key, deepcopy(list(final_features)))
                if workspace.active_part == part_key:
                    app._load_part_holes(part_key)
                bridge._phase6_sync_authoritative_derived_parts(app)
                app.submit_update_intent("geometry", commit=True)
            else:
                raise ValueError("受電箱實體 NFB 編輯需要有效的連／數量模式")
        else:
            workspace.stash_features(part_key, deepcopy(list(final_features)))
            if str(workspace.active_part) == part_key:
                app._load_part_holes(part_key)
            app.submit_update_intent("geometry", commit=True)
            if (from_corner_data and str(getattr(
                    app, "_phase6_3d_display_mode", "") or "") == "corner_data"):
                refresh = getattr(app, "_phase6_refresh_corner_data_unfold_view", None)
                if callable(refresh):
                    refresh()

    # Nested settings dialogs may own a grab. The original editor, not the
    # settings dialog, owns interaction until 確定全部／取消全部.
    root = getattr(app, "root", None)
    parent_modal = (getattr(root, "_receiving_multi_settings_window", None)
                    if settings_mode is not None and root is not None else None)
    if settings_mode is not None and parent_modal is not None and parent_modal.winfo_exists():
        if parent_modal.grab_current() is parent_modal:
            parent_modal.grab_release()

    def restore_settings_dialog():
        if (parent_modal is not None and parent_modal.winfo_exists()
                and parent_modal.grab_current() is None):
            parent_modal.grab_set()
            parent_modal.lift()

    title = "內門門板：" + str(panel.inner_door_id)
    window = host._open_unified_hole_editor(
        part_key, title, surface, structural.width, structural.height,
        # The operator editor always DISPLAYS the full work area (800x1100).
        # The checkbox changes measurement authority, not the shown size.
        reference_guide=work_area_guide,
        local_reference_guide=door_guide,
        cabinet_reference_guide=work_area_guide,
        feature_list_override=features,
        # Every entry stays transient until native Confirm All, including
        # direct Corner Data / board-preview routes. Cancel All must never
        # leave a Receiving-tab NFB in the physical workspace.
        sync_callback=lambda: None,
        **({"on_close": restore_settings_dialog} if settings_mode is not None else {}),
        on_confirm_features=confirm_settings,
        door_frame_edges=DoorFrameEdges(
            left=False, right=False, top=False, bottom=False,
        ),
        door_thickness=float(panel.thickness),
        baseline_scene=render.scene,
        baseline_status_text="金庫型門板共用折彎／截角；內門孔位獨立",
    )
    editor = window or getattr(host, "last_unified_hole_editor", None)
    if settings_mode is not None:
        editor._receiving_staged_config = None
        editor._receiving_settings_mode = settings_mode
        editor._receiving_candidate_version = selected_candidate_version
    receiving_page = getattr(editor, "_receiving_config_frame", None)
    if receiving_page is not None:
        # Reuse the existing Receiving Set/Bay candidate/NFB data authority,
        # placing its widgets inside the original Hole Editor's 受電箱 tab.
        # The receiving tab's composition owner is the Fold Designer `app`.
        # `host` is the primary GUI owning the generic hole editor, and
        # must never be used for Receiving-specific navigation ports.
        build_receiving_tab = getattr(
            app, "_phase6_open_embedded_receiving_inner_editor", None,
        )
        if callable(build_receiving_tab):
            build_receiving_tab(receiving_page)
        else:
            # Legacy preview/test hosts do not always mount the Assembly
            # coordinator. They must still open the original Hole Editor.
            # Production Bridge installs this port before any navigation.
            from tkinter import ttk
            ttk.Label(
                receiving_page, text="目前未提供受電箱設定入口",
            ).pack(anchor="w", padx=12, pady=12)
    return editor


def sync_inner_door_hole_editor_button(app, part_key: str) -> None:
    """Mount a visible editing entry only while the inner-door sheet is active."""
    previous = getattr(app, "_phase6_inner_door_hole_button", None)
    if previous is not None:
        try:
            previous.destroy()
        except Exception:
            pass
        app._phase6_inner_door_hole_button = None

    if not is_inner_door_sheet(part_key):
        return
    import tkinter as tk
    from tkinter import ttk

    parent = getattr(app, "input_content_host", None)
    if parent is None:
        return
    button = ttk.Button(
        parent, text="內門開孔編輯",
        command=lambda key=part_key: open_inner_door_hole_editor(app, key),
    )
    children = tuple(child for child in parent.pack_slaves() if child is not button)
    pack = {"fill": tk.X, "padx": 4, "pady": (3, 6)}
    if children:
        pack["before"] = children[0]
    button.pack(**pack)
    app._phase6_inner_door_hole_button = button
