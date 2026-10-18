# -*- coding: utf-8 -*-
"""#1901: CSV is the current NFB opening source for the original Hole Editor.

Consume the existing physical V5 FinalScene geometry (including its real
panel datum and collision checks), not original DXF files, fake model-name
geometry or a second hole renderer. This transfers validated geometry into
an *editor draft*. Manufacturing approval remains a separate step.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from .cabinet_types import policy as receiving_policy
from .receiving_nfb_numeric_catalog import brand_csv_path
from .receiving_nfb_v5_configured_inner_door import NfbV5ConfiguredInnerDoorTrial
from .receiving_nfb_ui1a_edits import editable_nfb_draft
from .sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from .sheetmetal_geometry import Vec2


def invalidate_csv_editor_proof(editor, popup=None):
    """Fail closed before every CSV re-check, including unsuccessful retries.

    The previous typed proof must never survive a new invalid world-X input,
    missing CSV/model, changed geometry, or source/face/collision error.
    The caller can restage a fresh proof only after its *entire* new check
    succeeds. This only touches the transient original Hole Editor state.
    """
    if editor is not None:
        editor._receiving_csv_door_proof = None
    if popup is not None:
        popup._receiving_v5_trial = None
        popup._receiving_v5_base_trial = None


def csv_checked_world_values_match(checked, fields) -> bool:
    """A post-check text change cannot keep the cached physical X proof."""
    from math import isfinite

    if not isinstance(checked, Mapping) or not isinstance(fields, Mapping):
        return False
    if set(checked) != set(fields):
        return False
    try:
        observed = {uid: float(field.get().strip())
                    for uid, field in fields.items()}
    except (ValueError, TypeError, AttributeError):
        return False
    return (all(isfinite(v) for v in observed.values())
            and observed == checked)


@dataclass(frozen=True)
class NfbCsvHoleEditorProof:
    trial: NfbV5ConfiguredInnerDoorTrial
    snapshot: dict
    draft: dict
    baseline_features: tuple
    csv_hashes: tuple[tuple[str, str], ...]


def _csv_hashes(trial):
    brands = {pattern.brand for pattern in trial.patterns}
    if not brands:
        raise ValueError("NFB CSV 必須有至少一個有效開孔")
    try:
        return tuple(sorted(
            (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
            for brand in brands
        ))
    except OSError as exc:
        raise ValueError("NFB 數值 CSV 來源不存在，不能帶入開孔") from exc


def stage_csv_openings(trial, *, snapshot: Mapping, draft, current_features):
    """Capture CSV bytes, actual panel and exact editor baseline at preview."""
    if not isinstance(trial, NfbV5ConfiguredInnerDoorTrial):
        raise TypeError("NFB CSV 開孔必須使用真實內門 FinalScene")
    if (not trial.patterns or len(trial.patterns) != len(trial.hole_ids)
            or len(set(trial.hole_ids)) != len(trial.hole_ids)
            or trial.manufacturing_ready
            or trial.render_data.metadata.get("nfb_trial_export_approved") is not False
            or trial.render_data.metadata.get("nfb_v5_hole_ids") != trial.hole_ids):
        raise ValueError("NFB CSV 來源未通過內門實體／碰撞驗算")
    panels = [panel for panel in receiving_policy.derive_inner_door_panels(snapshot)
              if panel.stable_id == trial.part_id]
    if len(panels) != 1:
        raise ValueError("NFB CSV 主孔不屬於此片實體內門")
    previous = tuple((snapshot.get("part_features") or {}).get(trial.part_id, ()))
    if tuple(current_features) != previous:
        raise ValueError("內門已有不同的主編輯器孔位，請重新檢查 CSV 開口")
    return NfbCsvHoleEditorProof(
        trial=trial, snapshot=deepcopy(dict(snapshot)),
        draft=deepcopy(editable_nfb_draft(draft)),
        baseline_features=tuple(current_features),
        csv_hashes=_csv_hashes(trial),
    )


def csv_openings_to_editor_features(
    proof, *, snapshot: Mapping, draft, current_features,
):
    """Recheck the real CSV source and geometry before importing typed holes."""
    if not isinstance(proof, NfbCsvHoleEditorProof):
        raise ValueError("尚未驗證 NFB CSV 內門主孔，請先檢查孔位")
    trial = proof.trial
    if (tuple(current_features) != proof.baseline_features
            or editable_nfb_draft(draft) != proof.draft):
        raise ValueError("NFB 型號／旋轉／開孔編輯已變更，請重新檢查 CSV")
    if _csv_hashes(trial) != proof.csv_hashes:
        raise ValueError("NFB 數值 CSV 已更新，請重新檢查孔位")
    if (tuple((snapshot.get("part_features") or {}).get(trial.part_id, ()))
            != proof.baseline_features):
        raise ValueError("內門已保存的孔位與預覽時不同")
    original = [p for p in receiving_policy.derive_inner_door_panels(proof.snapshot)
                if p.stable_id == trial.part_id]
    live = [p for p in receiving_policy.derive_inner_door_panels(snapshot)
            if p.stable_id == trial.part_id]
    if len(original) != 1 or len(live) != 1 or original[0] != live[0]:
        raise ValueError("內門實體尺寸／安裝基準已改變，請重新計算 CSV 孔")
    for key in ("model", "active_mode", "w", "h", "d", "t", "fw",
                "receiving_inner_door_layer_heights_mm", "inner_doors",
                "door_layout_columns"):
        if snapshot.get(key) != proof.snapshot.get(key):
            raise ValueError("箱體或內門的實體定位已變更")
    panel = live[0]
    # The established real-part V5 trial already validated every polygon against
    # this door's unfolded core, other holes, each other, and FinalScene material.
    dx = float(panel.fold_left) - float(panel.thickness)
    dy = float(panel.fold_bottom) - float(panel.thickness)
    features = []
    for hole_id, pattern in zip(trial.hole_ids, trial.patterns):
        if (pattern.datum.part_id != trial.part_id or pattern.feature != "opening"
                or not pattern.opening_uv_mm or len(pattern.opening_uv_mm) != 4):
            raise ValueError("NFB CSV 實體開口數量或板件錯誤")
        csv_sha = dict(proof.csv_hashes)[pattern.brand]
        vertices = tuple(Vec2(float(x)-dx, float(y)-dy)
                         for x, y in pattern.opening_uv_mm)
        features.append(ProfileFeature(
            points=vertices,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0., 0.), layer="CUTTING",
            source_type="NFB_CSV_SOURCE",
            source_params=(
                ("hole_id", hole_id),
                ("part_id", trial.part_id),
                ("brand", pattern.brand),
                ("model", pattern.model),
                ("csv_sha256", csv_sha),
            ),
        ))
    return tuple(features)
