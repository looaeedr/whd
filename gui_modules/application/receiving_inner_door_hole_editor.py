# -*- coding: utf-8 -*-
"""Use the existing Vault Door hole editor for one Receiving inner-door sheet.

Only the GUI adapter lives here. Manufacturing topology, features, and the
inner-door dimensions remain with their established authority owners.
"""
from __future__ import annotations


def is_inner_door_sheet(part_key: object) -> bool:
    key = str(part_key or "")
    return key.startswith("inner_door:") and key.endswith(":panel")



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


def open_inner_door_hole_editor(app, part_key: str, *, from_corner_data=False, from_part_preview=False):
    """Open the existing Vault Door hole editor; preserve view-only Corner Data selection."""
    if not is_inner_door_sheet(part_key):
        raise ValueError("不是可開孔編輯的內門門板")
    workspace = app.designer_workspace
    if part_key not in workspace.available_parts:
        raise ValueError("內門門板目前不在有效板件清單")
    host = getattr(getattr(app, "_scene_query_callback", None), "__self__", None)
    if str(workspace.active_part) != part_key:
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
        build_door_result, DoorFrameEdges,
    )
    from ae_engine.sheetmetal_features import feature_surface_from_structural_result
    from ae_engine import manufacturing_api

    snapshot = dict(app._phase6_input_snapshot)
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
    guide = inner_door_work_area_guide(snapshot, panel, structural)
    # The inner-door hole UI must show the same physical CUTTING/BEND as
    # its produced DXF. Reuse Vault certified folding/corner rules without
    # importing the OUTER Vault Door's fixed handle/nameplate holes into a
    # Receiving inner-door/NFB physical hole owner.
    render = manufacturing_api.build_inner_door_panel_render_data(panel)
    features = workspace.features_for(part_key)

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

    title = "內門門板：" + str(panel.inner_door_id)
    window = host._open_unified_hole_editor(
        part_key, title, surface, structural.width, structural.height,
        reference_guide=guide,
        feature_list_override=features,
        sync_callback=commit,
        door_frame_edges=DoorFrameEdges(
            left=False, right=False, top=False, bottom=False,
        ),
        door_thickness=float(panel.thickness),
        baseline_scene=render.scene,
        baseline_status_text="金庫型門板共用折彎／截角；內門孔位獨立",
    )
    editor = window or getattr(host, "last_unified_hole_editor", None)
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
