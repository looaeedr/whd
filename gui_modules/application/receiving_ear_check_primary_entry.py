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
    group.pack(fill="x", pady=(0, 5), before=notebook)
    button = ttk.Button(
        group,
        text="固定片側板 CHECK DXF（非製造）",
        command=host.export_receiving_ear_side_check_dxf,
    )
    button.pack(fill="x", padx=3, pady=3)
    host._receiving_ear_check_primary_group = group
    host.btn_ear_side_check_dxf = button
    return button
