# -*- coding: utf-8 -*-
"""Engine-owned BoxBody 2D physical source and canonical piece-ID projection.

The GUI may choose which tab to display. Only the Engine recognizes the real
BoxBody physical source and maps the selected tab to an existing material piece;
no generic fallback may replace the Receiving committed FinalScene.
"""
from __future__ import annotations


def project_receiving_box_body_2d_source(geometry):
    """Return current resolved, actually formed BoxBody source or reject."""
    box_body = geometry.part("box_body")
    render_data = box_body.render_data
    if not tuple(getattr(render_data, "pieces", ()) or ()):
        raise ValueError("受電箱側板 2D 缺少現行物理板件")
    return render_data


def project_box_body_2d_piece_inventory(render_data, selected_piece_key):
    """Map one operator-selected canonical key to an existing Engine piece.

    Preserve legacy aggregate fallback if a requested role has no real part.
    No paper-only part ID, preview mesh, or manufacturing-ready bit is created.
    """
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    keys = tuple(f"box_body:{str(piece.role)}" for piece in pieces)
    selected = None
    if selected_piece_key:
        role = selected_piece_key.split(":", 1)[1]
        selected = next(
            (piece for piece in pieces
             if str(getattr(piece, "role", "") or "") == role),
            None,
        )
    return keys, selected
