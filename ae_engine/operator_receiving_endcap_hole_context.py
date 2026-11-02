# -*- coding: utf-8 -*-
"""#2517 Engine-owned Receiving physical EndCap Hole Editor input projection.

Read only. This is the original finished-face geometry and independently
validated per-Bay shared-setting hole data, not a GUI geometry fallback or an
external manufacturing/export approval. The GUI still owns all editor session
transactions and explicit multi-Bay share/unlink confirmation.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .cabinet_types.policy import canonical_family_name
from .receiving_shared_settings import setting_value
from .sheetmetal_features import (
    RectGuide, Vec2, feature_surface_from_rect,
    resolve_endcap_finished_face_guide,
)


@dataclass(frozen=True)
class ReceivingEndcapHoleEditorContext:
    role: str
    width: float
    depth: float
    surface: object
    reference_guide: RectGuide
    features: list


def project_receiving_endcap_hole_editor_context(
    snapshot, layout, *, set_index: int, bay_index: int, role: str,
) -> ReceivingEndcapHoleEditorContext:
    """Resolve the selected *physical* Bay's finished Head/Tail edit surface.

    Source data and Feature containers originate in current registered
    Receiving Set/Bay shared settings; no stale root W/D or other Bay is
    allowed to provide an invisible geometry substitution.
    """
    if not isinstance(snapshot, Mapping) or canonical_family_name(snapshot) != "受電箱":
        raise ValueError("RECEIVING_ENDCAP_HOLE_EDITOR_FAMILY_REQUIRED")
    if role not in ("head", "tail"):
        raise ValueError("RECEIVING_ENDCAP_HOLE_EDITOR_ROLE_INVALID")
    if type(set_index) is not int or type(bay_index) is not int:
        raise IndexError("組連選取超出範圍")
    if not isinstance(layout, Mapping) or not isinstance(layout.get("sets"), list):
        raise ValueError("RECEIVING_ENDCAP_HOLE_EDITOR_LAYOUT_INVALID")
    sets = layout["sets"]
    if not 0 <= set_index < len(sets):
        raise IndexError("組選取超出範圍")
    selected = sets[set_index]
    if not isinstance(selected, Mapping) or not isinstance(selected.get("bays"), list):
        raise ValueError("RECEIVING_ENDCAP_HOLE_EDITOR_SET_INVALID")
    bays = selected["bays"]
    if not 0 <= bay_index < len(bays):
        raise IndexError("連選取超出範圍")
    bay = bays[bay_index]
    if not isinstance(bay, Mapping):
        raise ValueError("RECEIVING_ENDCAP_HOLE_EDITOR_BAY_INVALID")
    width, depth = float(bay["width"]), float(bay["depth"])
    thickness = float(snapshot.get("t", 2))
    face = resolve_endcap_finished_face_guide(width, depth, thickness)
    surface = feature_surface_from_rect(
        f"{role}_finished_face", face.min_point, face.max_point,
    )
    reference = RectGuide(
        Vec2(0, 0), Vec2(width, depth), "finished_boundary",
    )
    features = setting_value(selected, bay_index, f"{role}_features")
    return ReceivingEndcapHoleEditorContext(
        role=role, width=width, depth=depth,
        surface=surface, reference_guide=reference, features=features,
    )
