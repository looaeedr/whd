# -*- coding: utf-8 -*-
"""Lightweight, data-driven inner-door configuration thumbnail for Tk Canvas.

This visualizes layer counts, model names and switch multiplicity only.
The little glyphs are inventory markers, NOT DXF hole positions or dimensions.
It must never request 3D geometry, DXF decoding or manufacturing.
"""
from __future__ import annotations

from ae_engine import manufacturing_api


def inner_door_preview_rows(config):
    """Compatible read-only model-ref rows, projected by the public Engine."""
    layers = manufacturing_api.resolve_receiving_inner_door_preview_inventory(config)
    return tuple(layer.model_refs for layer in layers)

def paint_inner_door_thumbnail(canvas, config, *, title="內門配置"):
    """Draw a small visual inventory, returning exact per-layer file lists.

    Can be safely called repeatedly during UI edits; Canvas owns only images.
    """
    inventory = manufacturing_api.resolve_receiving_inner_door_preview_inventory(config)
    rows = tuple(layer.model_refs for layer in inventory)
    canvas.delete("all")
    width = max(230, int(canvas.winfo_width()), int(canvas.cget("width")))
    height = max(154, int(canvas.winfo_height()), int(canvas.cget("height")))
    canvas.create_rectangle(0, 0, width, height, fill="#1a2734", outline="")
    canvas.create_text(12, 13, text=title, anchor="w",
                       fill="#f1f5f9", font=("TkDefaultFont", 10, "bold"))
    if config is None:
        canvas.create_text(width / 2, height / 2, text="尚未選擇候選版本",
                           fill="#a3b4c7", font=("TkDefaultFont", 10))
    else:
        for idx, names in enumerate(rows):
            y = 31 + idx * 54
            canvas.create_rectangle(
                12, y, width - 12, y + 49, fill="#24384b",
                outline="#69859b", width=1,
            )
            canvas.create_text(21, y + 11, anchor="w",
                               text=f"第 {idx+1} 層  ·  {len(names)} 顆",
                               fill="#e5f0fa", font=("TkDefaultFont", 9, "bold"))
            if names:
                # Marks deliberately indicate quantity only, never X/Y positions.
                marks = min(9, len(names))
                for n in range(marks):
                    x = width - 21 - (marks - n) * 12
                    canvas.create_rectangle(
                        x, y + 6, x + 9, y + 17,
                        fill="#f1bc68", outline="#f6dba8",
                    )
                if len(names) > marks:
                    canvas.create_text(width - 22, y + 11,
                                       text=f"+{len(names)-marks}", anchor="e",
                                       fill="#f1bc68", font=("TkDefaultFont", 8))
                # Engine retains true stored-reference multiplicity, including V5.
                summary = "、".join(
                    f"{label}×{count}" if count > 1 else label
                    for label, count in inventory[idx].display_counts
                )
                # Clip the DISPLAY description, not the persisted filename.
                if len(summary) > 32:
                    summary = summary[:31] + "…"
            else:
                summary = "尚未配置開關"
            canvas.create_text(21, y + 34, anchor="w", text=summary,
                               fill="#cbd5e1", font=("TkDefaultFont", 9))
    canvas.create_text(
        12, height - 11, anchor="w", text="配置示意，非實際開孔位置",
        fill="#9fb0bf", font=("TkDefaultFont", 8),
    )
    canvas._receiving_inner_preview_rows = rows
    return rows
