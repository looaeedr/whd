# -*- coding: utf-8 -*-
"""Use the existing Vault Door hole editor for one Receiving inner-door sheet.

Only the GUI adapter lives here. Manufacturing topology, features, and the
inner-door dimensions remain with their established authority owners.
"""
from __future__ import annotations


def is_inner_door_sheet(part_key: object) -> bool:
    key = str(part_key or "")
    return key.startswith("inner_door:") and key.endswith(":panel")


def open_inner_door_hole_editor(app, part_key: str):
    """Edit only the selected physical inner-door panel and persist its features."""
    if not is_inner_door_sheet(part_key):
        raise ValueError("不是可開孔編輯的內門門板")
    workspace = app.designer_workspace
    if part_key not in workspace.available_parts:
        raise ValueError("內門門板目前不在有效板件清單")
    if str(workspace.active_part) != part_key:
        raise ValueError("請先選取要開孔的內門門板")

    host = getattr(getattr(app, "_scene_query_callback", None), "__self__", None)
    if host is None or not callable(getattr(host, "_open_unified_hole_editor", None)):
        raise ValueError("未連接既有金庫型門板開孔編輯器")

    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_part_adapters import (
        build_door_result, build_finished_reference_guide, DoorFrameEdges,
    )
    from ae_engine.sheetmetal_features import feature_surface_from_structural_result
    from ae_engine import ae, manufacturing_api

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
        fw=0.0, gap_w=0.0, gap_h=0.0,
        fold_left=19.0, fold_right=19.0,
        fold_top=19.0, fold_bottom=19.0,
        frame_edges=DoorFrameEdges(
            left=False, right=False, top=False, bottom=False,
        ),
    )
    surface = feature_surface_from_structural_result("door", structural)
    guide = build_finished_reference_guide(
        "door", structural,
        finished_width=panel.width, finished_height=panel.height,
    )
    # This preview is the same validated Vault DXF-derived manufacturing scene
    # as the CUTTING/BEND export, not a separately drawn 2D rectangle.
    render = manufacturing_api.build_inner_door_panel_render_data(panel)
    features = workspace.features_for(part_key)

    def commit():
        # Workspace is authoritative; original outer Door holes remain separate.
        workspace.stash_features(part_key, features)
        app._load_part_holes(part_key)
        app.submit_update_intent("geometry", commit=True)

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
        baseline_status_text=ae.baseline_source_label("金庫型", "門.dxf"),
    )
    return window or getattr(host, "last_unified_hole_editor", None)


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
