# -*- coding: utf-8 -*-
"""#2517 Receiving EAR side 2D/3D display-source context (not manufacture).

This immutable context validates a source-current Receiving family, submitted
NFB state, and stale primary-vs-FoldDesigner source claims. It also fingerprints
the *actual* Box Body physical render pieces and their baseline/source SHA for
display-only cache invalidation. Canonical EAR UV/MARKING comes only from the
existing public Engine projection and remains non-manufacturing.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256


_SIDE_KEYS = frozenset(("box_body:left_side", "box_body:right_side"))


@dataclass(frozen=True)
class ReceivingEarSideDisplayContext:
    should_project: bool
    physical_piece_key: str
    dimensions: tuple[float, float, float] | None = None
    sheet_thickness: float | None = None
    source_stamp: str | None = None


def resolve_receiving_ear_side_display_context(
    snapshot, piece_key, aggregate_render_data=None, *, main_mirror=None,
) -> ReceivingEarSideDisplayContext:
    """Source-truth and exact physical cache identity for read-only UI.

    aggregate_render_data may be omitted for a cheap 3D preflight before the
    caller resolves the actual box_body part. No returned field approves DXF.
    """
    key = str(piece_key)
    if not isinstance(snapshot, Mapping):
        raise TypeError("EAR_SIDE_DISPLAY_REQUIRES_SOURCE_SNAPSHOT")
    if key not in _SIDE_KEYS or snapshot.get("model") not in ("受電箱", "RECEIVING"):
        return ReceivingEarSideDisplayContext(False, key)
    if snapshot.get("nfb_config_submitted") is not True:
        if main_mirror is not None and (
            not isinstance(main_mirror, Mapping)
            or main_mirror.get("nfb_config_submitted") is True
        ):
            raise ValueError("EAR_2D_PREVIEW_PRIMARY_SOURCE_DRIFT")
        return ReceivingEarSideDisplayContext(False, key)
    dimensions = (
        float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"]),
    )
    t = float(snapshot["t"])
    if aggregate_render_data is None:
        return ReceivingEarSideDisplayContext(True, key, dimensions, t)
    owners = tuple(
        (p.role, (p.render_data.metadata or {}).get("baseline_source_sha256"),
         repr(tuple(p.render_data.scene.primitives or ())))
        for p in tuple(getattr(aggregate_render_data, "pieces", ()) or ())
    )
    stamp = sha256(repr((snapshot, key, owners)).encode("utf-8")).hexdigest()
    return ReceivingEarSideDisplayContext(True, key, dimensions, t, stamp)
