# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Custom single-axis folds use the existing outside-dimension conversion."""
from collections.abc import Mapping
import math
from phase6_custom_parts import CustomPartCatalog
from phase6_fold_profiles import _outside_profile_to_material, apply_outside_dimension_compensation, profile_to_fold_segments
from ae_engine.contracts import CustomFoldPartSpec
from dataclasses import replace

def _validated_custom_part_thickness(snapshot) -> float:
    data = dict(snapshot or {})
    raw_t = data.get("t", 2)
    if isinstance(raw_t, bool):
        raise ValueError("板厚不得為布林值")
    t = float(raw_t)
    if not math.isfinite(t) or not 0 < t < 17:
        raise ValueError("自訂板件板厚必須大於0且小於包外17")
    return t

def descriptor_from_snapshot(snapshot, key):
    data = dict(snapshot or {})
    payload = data.get("custom_parts") or dict(data.get("workspace") or {}).get("custom_parts")
    item = CustomPartCatalog(payload).get(key)
    if item is None:
        raise ValueError(f"自訂板件缺少正式 Fold metadata: {key}")
    return item

def build_custom_part_profiles(snapshot, key):
    item = descriptor_from_snapshot(snapshot, key)
    t = _validated_custom_part_thickness(snapshot)
    axis = item["fold_axis"]
    other = "Y" if axis == "X" else "X"
    # Existing engine convention: operator +90 becomes engine -90; the
    # terminal row owns no bend. Each of the two adjacent legs contributes 1T.
    rows = [{"len":17.0,"angle":-90,"phase6_key":"custom_flange"},
            {"len":100.0,"core":"CUSTOM_FACE","phase6_key":"custom_face"}]
    return {axis:_outside_profile_to_material(rows,t,preserve_precision=True),
            other:[{"len":item["transverse_length"],"core":"CUSTOM_SPAN","phase6_key":"custom_span"}]}

def custom_part_spec(snapshot, key, *, features=(), profiles=None):
    item = descriptor_from_snapshot(snapshot,key)
    t = _validated_custom_part_thickness(snapshot)
    rows = profiles if profiles is not None else build_custom_part_profiles(snapshot,key)
    axis = item["fold_axis"]
    other = "Y" if axis == "X" else "X"
    if not isinstance(rows,Mapping) or not rows.get(axis) or len(rows.get(other,())) != 1:
        raise ValueError("自訂板件缺少合法單軸 Fold")
    flat = rows[other][0]
    if not isinstance(flat, Mapping):
        raise ValueError("自訂板件缺少合法單軸 Fold")
    raw_angle = flat.get("angle")
    if isinstance(raw_angle, bool) or raw_angle not in (None, 0, 0.0):
        raise ValueError("自訂板件另一軸不得折彎")
    raw_flat_len = flat.get("len", 0)
    if isinstance(raw_flat_len, bool):
        raise ValueError("自訂板件另一軸尺寸不得為布林值")
    flat_len = float(raw_flat_len)
    if not math.isfinite(flat_len) or abs(flat_len - item["transverse_length"]) > 1e-9:
        raise ValueError("自訂板件另一軸尺寸與 metadata 不一致")
    compensated = apply_outside_dimension_compensation([dict(row) for row in rows[axis]], t)
    return CustomFoldPartSpec(physical_id=key,fold_axis=axis,
        fold_profile=tuple(replace(seg,formed_length=float(row["len"])+float(row.get("ui_len_add",0)))
                           for seg,row in zip(profile_to_fold_segments(compensated),compensated)),
        transverse_length=item["transverse_length"],thickness=t,
        features=tuple(features))
