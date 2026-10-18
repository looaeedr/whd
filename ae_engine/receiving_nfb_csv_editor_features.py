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
    from dataclasses import replace

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
    # A stable panel ID and identical W/H/T do NOT prove this is the same
    # physical receiving Bay or quantity box. A same-size cross-Bay switch
    # must never inherit a previous CSV trial, even if its model and holes
    # appear geometrically identical. No legacy Set.switch_brand inference.
    owner_keys = (
        "_receiving_runtime_selection", "receiving_layout",
        "receiving_quantity_box", "receiving_quantity_versions",
        "receiving_quantity_selected_index", "nfb_config",
        "nfb_config_submitted", "receiving_inner_door_candidates",
    )
    if any(snapshot.get(key) != proof.snapshot.get(key) for key in owner_keys):
        raise ValueError("受電箱 Set／Bay／單只來源身分已變更，請重新檢查 CSV 開口")
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


def editor_nfb_features_from_csv(snapshot: Mapping, config, *, current_features=()):
    """Build editable CSV NFB hole drafts for the ORIGINAL Hole Editor.

    The operator chooses models and top-edge Y in the Receiving tab; the
    initial horizontal layout is an EDITOR placement, not a certified X rule.
    The operator can move each hole in the native editor before Confirm All.
    Nothing here writes the workspace, candidate, Bay, or manufacturing DXF.
    """
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import model_spec
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from .receiving_shared_settings import switch_filenames_in_layer, validate_setting
    from .sheetmetal_feature_surface import feature_is_strictly_within_surface
    from .sheetmetal_features import feature_surface_from_structural_result
    from .sheetmetal_part_adapters import build_door_result, DoorFrameEdges
    from shapely.geometry import Polygon
    from .cabinet_types import policy
    from math import isfinite

    layers = validate_setting("inner_door_layers", config["layers"])
    heights = validate_setting("inner_door_layer_heights_mm", config["layer_heights_mm"])
    models = validate_setting("inner_door_models", config["models"])
    if layers == 1 and models[1]:
        raise ValueError("單層不能將第二層 NFB 帶入編輯器")
    projected = deepcopy(dict(snapshot))
    projected["receiving_inner_door_layer_heights_mm"] = list(heights)
    panels = [p for p in policy.derive_inner_door_panels(projected)
              if str(p.cell_key).endswith(":0")]
    if len(panels) != 1:
        raise ValueError("內門開孔編輯需要唯一的上層實體內門")
    panel = panels[0]
    structural = build_door_result(
        w=panel.width, h=panel.height, t=panel.thickness,
        fw=25.0, gap_w=0.0, gap_h=0.0,
        fold_left=19.0, fold_right=19.0,
        fold_top=19.0, fold_bottom=19.0,
        frame_edges=DoorFrameEdges(left=False, right=False, top=False, bottom=False),
    )
    surface = feature_surface_from_structural_result("door", structural)
    result = []
    polygons = []
    source_hashes = {}
    previously_placed = {}
    for old in current_features:
        if not isinstance(old, ProfileFeature) or old.source_type != "NFB_CSV_SOURCE":
            continue
        params = dict(old.source_params)
        if params.get("part_id") != panel.stable_id:
            continue
        key = (params.get("layer_index"), params.get("slot_index"))
        if key not in previously_placed:
            previously_placed[key] = old
    for layer_index in range(layers):
        names = switch_filenames_in_layer(models[layer_index])
        if not names:
            continue
        y = project_nfb_inner_door_nominal_y(
            projected, panel.inner_door_id,
            layer_count=layers, slot_index=layer_index,
        )
        if y.part_id != panel.stable_id:
            raise ValueError("NFB 開口未對應目前編輯的內門")
        face_y = y.unfolded_uv_y_mm - (panel.fold_bottom - panel.thickness)
        for slot_index, ref in enumerate(names):
            parsed = parse_numeric_model_ref(ref)
            if parsed is None:
                raise ValueError("請從目前 CSV 型號清單加入 NFB")
            brand, model = parsed
            spec = model_spec(brand, model)
            if spec is None or spec.opening_corners_xy_mm is None:
                raise ValueError("NFB CSV 缺少主孔尺寸")
            if brand not in source_hashes:
                source_hashes[brand] = sha256(brand_csv_path(brand).read_bytes()).hexdigest()
            # Initial native-editor positions are only a visual starting point:
            # they must not be mistaken for a certified manufacturing X datum.
            face_x = float(panel.width) * (slot_index + 1) / (len(names) + 1)
            points = tuple(Vec2(face_x + float(x), face_y + float(y))
                           for x, y in spec.opening_corners_xy_mm)
            polygon = Polygon([(p.x, p.y) for p in points])
            feature = ProfileFeature(
                points=points, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(0., 0.), layer="CUTTING",
                source_type="NFB_CSV_SOURCE",
                source_params=(
                    ("part_id", panel.stable_id),
                    ("brand", brand), ("model", model),
                    ("layer_index", layer_index),
                    ("slot_index", slot_index),
                    ("csv_sha256", source_hashes[brand]),
                    ("y_from_top_mm", float(heights[layer_index])),
                    ("placement", "native_editor_initial"),
                ),
            )
            old = previously_placed.get((layer_index, slot_index))
            if old is not None:
                info = dict(old.source_params)
                if (info.get("brand") == brand and info.get("model") == model
                        and info.get("csv_sha256") == source_hashes[brand]
                        and info.get("y_from_top_mm") is not None):
                    # A repeat tab Confirm must never reset the X/rotation
                    # already placed by the operator on the native canvas.
                    # Only a changed height shifts its physical Y.
                    delta_y = float(info["y_from_top_mm"]) - float(heights[layer_index])
                    feature = replace(
                        old,
                        offset=Vec2(old.offset.x, old.offset.y + delta_y),
                        source_params=tuple(
                            (key, (float(heights[layer_index])
                                   if key == "y_from_top_mm" else value))
                            for key, value in old.source_params
                        ),
                    )
                    from .sheetmetal_feature_core import _rotate_local_point
                    polygon = Polygon([
                        (p.x + feature.offset.x, p.y + feature.offset.y)
                        for p in (_rotate_local_point(point, feature.rotation_deg)
                                  for point in feature.points)
                    ])
            if (not polygon.is_valid or polygon.area <= 0
                    or not feature_is_strictly_within_surface(
                        surface, feature, structural.width, structural.height
                    ) or any(polygon.intersects(other) for other in polygons)):
                raise ValueError("NFB 開口初始位置超出內門或互相重疊，請調整配置")
            polygons.append(polygon)
            result.append(feature)
    if any(sha256(brand_csv_path(brand).read_bytes()).hexdigest() != digest
           for brand, digest in source_hashes.items()):
        raise ValueError("NFB CSV 在編輯期間已更新，請重新加入")
    return tuple(result)
