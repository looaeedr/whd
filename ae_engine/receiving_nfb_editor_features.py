# -*- coding: utf-8 -*-
"""Bring source-VERIFIED NFB inner-door openings into the original Hole Editor.

The verifier's immutable actual FinalScene, not a guessed rectangle or
provisional V5 preview, is the only authority for an automatic insertion.
This adapter only stages native Hole Editor ProfileFeatures. It does not
submit an NFBConfig, manufacture a DXF or mutate the original source.
"""
from __future__ import annotations

from .manufacturing_api import build_inner_door_panel_render_data
from .receiving_nfb_legacy_feature_bridge import existing_inner_door_feature_finalscene
from .sheetmetal_drawing import PolylinePrimitive
from .sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from .sheetmetal_geometry import Vec2


def verified_nfb_openings_to_editor_features(bundle, *, current_features):
    """Convert only the *additional* source-verified CUTTING geometry.

    A source verification is tied to one panel, one existing feature
    baseline and one actual DXF SHA. If any owner or geometry drifted, reject
    rather than duplicating manufactured CUTTING or silently using a V5 trial.
    """
    from .receiving_nfb_ui1b_bridge import NfbVerifiedDraftSubmission
    from .cabinet_types import policy as cabinet_family_policy

    if not isinstance(bundle, NfbVerifiedDraftSubmission):
        raise TypeError("受電箱主孔只能帶入來源已驗證的 NFB")
    if not bundle.verified_door.manufacturing_ready:
        raise ValueError("NFB 來源尚未通過實體與孔位驗證")
    snapshot = bundle.snapshot_at_verification
    panel_id = bundle.verified_door.part_id
    panels = [p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
              if p.stable_id == panel_id]
    if len(panels) != 1 or bundle.scope.inner_door_part_id != panel_id:
        raise ValueError("來源驗證與當前實體內門板件不一致")
    panel = panels[0]
    expected = tuple((snapshot.get("part_features") or {}).get(panel_id, ()))
    if tuple(current_features) != expected:
        # Do not let a proof for an old blank override unsaved Hole Editor
        # changes or an NFB hole already owned by a different source.
        raise ValueError("內門主頁籤已有未重新驗證的孔位變更，請先重新驗證 NFB 來源")
    canonical = build_inner_door_panel_render_data(panel)
    baseline = existing_inner_door_feature_finalscene(snapshot, panel)
    if baseline is None:
        baseline = canonical
    original = tuple(baseline.scene.primitives)
    verified = tuple(bundle.verified_door.render_data.scene.primitives)
    if verified[:len(original)] != original:
        raise ValueError("NFB 真實開孔與原內門 FinalScene 來源不一致")
    added = verified[len(original):]
    hole_ids = tuple(bundle.verified_door.physical_hole_ids)
    if not hole_ids or len(added) != len(hole_ids):
        raise ValueError("NFB 驗證孔數與實際 CUTTING 輪廓數不一致")
    source_sha = bundle.verified_door.source_sha256
    result = []
    for hole_id, polyline in zip(hole_ids, added):
        if (not isinstance(polyline, PolylinePrimitive)
                or polyline.layer != "CUTTING" or not polyline.closed
                or len(polyline.points) < 3):
            raise ValueError("NFB 來源包含不可作為原開孔編輯器主孔的圖元")
        # Native Hole Editor features store FINISHED-FACE coordinates.
        # Manufacturing's UV conversion is feature XY + fold - T.
        dx = float(panel.fold_left) - float(panel.thickness)
        dy = float(panel.fold_bottom) - float(panel.thickness)
        vertices = tuple(Vec2(float(p.x) - dx, float(p.y) - dy)
                         for p in polyline.points)
        result.append(ProfileFeature(
            points=vertices,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0.0, 0.0),
            layer="CUTTING",
            source_type="NFB_VERIFIED_SOURCE",
            source_params=(
                ("hole_id", hole_id),
                ("source_sha256", source_sha),
                ("part_id", panel_id),
            ),
        ))
    return tuple(result)
