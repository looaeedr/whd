# -*- coding: utf-8 -*-
"""Engine ownership of physical Box Body multipart 3D outside-W datum (#2517).

Moved from the original FinalScene projector with its real left SIDE origin
exception. This decides source provenance, never constructs a preview mesh.
"""
from __future__ import annotations

def resolve_box_body_formed_width_datum(pieces):
    """Distinguish all-preview stubs from a corrupt partially located Box Body."""
    from math import isfinite

    widths = []
    for piece in pieces:
        raw = getattr(piece, "formed_w_end", 0.0)
        if isinstance(raw, bool):
            raise ValueError("BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID")
        try:
            width = float(raw or 0.0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID") from exc
        if not isfinite(width):
            raise ValueError("BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID")
        widths.append(width)
    total = max(widths, default=0.0)
    if total <= 0.0:
        # Preserve the original preview-only placeholder fallback.
        return None
    for piece, width in zip(pieces, widths):
        if width > 0.0:
            continue
        # The canonical three-piece side/back type puts the left SIDE panel
        # on outside-W=0, while its physical material span is formed_outer_width.
        # This is not a missing W-split datum. Require both source anchors.
        legitimate_left_side = False
        if width == 0.0 and str(getattr(piece, "role", "")) == "left_side":
            start = getattr(piece, "formed_w_start", None)
            span = getattr(piece, "formed_outer_width", None)
            try:
                legitimate_left_side = (
                    not isinstance(start, bool)
                    and not isinstance(span, bool)
                    and float(start) == 0.0
                    and isfinite(float(span))
                    and float(span) > 0.0
                )
            except (TypeError, ValueError, OverflowError):
                legitimate_left_side = False
        if not legitimate_left_side:
            raise ValueError("BOX_BODY_PIECE_OUTSIDE_DATUM_INCOMPLETE")
    return total

