"""Presentation-only helpers for the hole editor."""

from __future__ import annotations

import tkinter as tk


def draw_hole_editor_hint(canvas, canvas_width, *, endcap=False):
    """Draw the existing double-click hole-editor hint without owning state."""
    text = "雙擊：開孔"
    canvas.create_text(
        canvas_width - 18,
        18,
        text=text,
        anchor=tk.NE,
        fill="#ff9f0a",
        font=("Microsoft JhengHei", 9, "bold"),
        tags=("phase6_hole_hint",),
    )
