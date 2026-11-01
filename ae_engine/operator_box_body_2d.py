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

from dataclasses import dataclass


@dataclass(frozen=True)
class BoxBodyAssemblyPanelPiece:
    """Read-only operator evidence from one actual physical BoxBody sheet."""

    part_key: str
    formed_width: float
    formed_height: float
    blank_width: float
    blank_height: float
    source_render_data: object | None


def project_box_body_assembly_panel_piece_rows(render_data):
    """Project actual BoxBody pieces once; GUI only labels and formats rows.

    The source render data for the same physical piece is carried through
    unchanged for the existing certified corner readback. A legacy piece
    without a role keeps its explicit source key; do not invent geometry.
    """
    rows = []
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        key = f"box_body:{role}" if role else str(getattr(piece, "key", "") or "")
        formed_width, formed_height = (
            float(value) for value in tuple(piece.formed_outer_dimensions)
        )
        blank_width, blank_height = (
            float(value) for value in tuple(piece.material_dimensions)
        )
        rows.append(BoxBodyAssemblyPanelPiece(
            part_key=key,
            formed_width=formed_width,
            formed_height=formed_height,
            blank_width=blank_width,
            blank_height=blank_height,
            source_render_data=getattr(piece, "render_data", None),
        ))
    return tuple(rows)
