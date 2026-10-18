# -*- coding: utf-8 -*-
"""#1503 real 3D-primary placement for CHECK-only EAR side DXF.

The old BoxCalculator left panel is intentionally not mounted in the
Phase6PrimaryApplication production startup. Keep this action independent
of the manufacturing export, and do not graft the legacy panel back.
"""
from tkinter import ttk


def mount_primary_receiving_ear_side_check(host):
    """Mount the source-gated CHECK action in the live Fold Designer sidebar."""
    designer = getattr(host, "fold_designer_app", None)
    left = getattr(designer, "left", None)
    notebook = getattr(designer, "main_nb", None)
    if left is None or notebook is None:
        raise ValueError("EAR_CHECK_PRIMARY_3D_WORKSPACE_MISSING")

    existing = getattr(host, "btn_ear_side_check_dxf", None)
    if existing is not None and existing.winfo_exists():
        return existing

    group = ttk.LabelFrame(
        left, text="受電箱固定片｜側板打標檢查", padding=5,
    )
    # The primary bridge intentionally unpacks the legacy main_nb. Tk cannot
    # pack(before=unpacked_widget). Anchor to an ACTUALLY packed primary panel.
    live_panels = tuple(
        child for child in left.winfo_children()
        if child.winfo_manager() == "pack"
    )
    if live_panels:
        group.pack(fill="x", pady=(0, 5), before=live_panels[-1])
    else:
        group.pack(fill="x", pady=(0, 5))
    button = ttk.Button(
        group,
        text="固定片側板 CHECK DXF（非製造）",
        command=host.export_receiving_ear_side_check_dxf,
    )
    button.pack(fill="x", padx=3, pady=3)
    # Source-verified manufacturing position marks, SIDE sheets only.
    # Keep a separate action from the CHECK and full-cabinet export.
    mfg_button = ttk.Button(
        group, text="側板正式 MARKING DXF（僅左右側板）",
        command=host.export_receiving_ear_side_manufacturing_dxf,
    )
    mfg_button.pack(fill="x", padx=3, pady=3)
    host.btn_ear_side_mfg_dxf = mfg_button
    host._receiving_ear_check_primary_group = group
    host.btn_ear_side_check_dxf = button
    return button
