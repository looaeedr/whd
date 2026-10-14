# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Custom single-axis folds use the existing outside-dimension conversion."""
from collections.abc import Mapping
from phase6_custom_parts import CustomPartCatalog
from phase6_fold_profiles import _outside_profile_to_material, apply_outside_dimension_compensation, profile_to_fold_segments
from ae_engine.contracts import CustomFoldPartSpec
from dataclasses import replace

def descriptor_from_snapshot(snapshot, key):
    data = dict(snapshot or {})
    payload = data.get("custom_parts") or dict(data.get("workspace") or {}).get("custom_parts")
    item = CustomPartCatalog(payload).get(key)
    if item is None:
        raise ValueError(f"自訂板件缺少正式 Fold metadata: {key}")
    return item

def build_custom_part_profiles(snapshot, key):
    item = descriptor_from_snapshot(snapshot, key)
    raw_t = snapshot.get("t", 2)
    if isinstance(raw_t,bool):
        raise ValueError("板厚不得為布林值")
    t = float(raw_t)
    if not 0 < t < 17:
        raise ValueError("自訂板件板厚必須大於0且小於包外17")
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
    rows = profiles if profiles is not None else build_custom_part_profiles(snapshot,key)
    axis = item["fold_axis"]
    other = "Y" if axis == "X" else "X"
    if not isinstance(rows,Mapping) or not rows.get(axis) or len(rows.get(other,())) != 1:
        raise ValueError("自訂板件缺少合法單軸 Fold")
    flat = rows[other][0]
    if flat.get("angle") not in (None,0):
        raise ValueError("自訂板件另一軸不得折彎")
    if abs(float(flat.get("len",0))-item["transverse_length"])>1e-9:
        raise ValueError("自訂板件另一軸尺寸與 metadata 不一致")
    compensated = apply_outside_dimension_compensation([dict(row) for row in rows[axis]],snapshot.get("t",2))
    return CustomFoldPartSpec(physical_id=key,fold_axis=axis,
        fold_profile=tuple(replace(seg,formed_length=float(row["len"])+float(row.get("ui_len_add",0)))
                           for seg,row in zip(profile_to_fold_segments(compensated),compensated)),
        transverse_length=item["transverse_length"],thickness=float(snapshot.get("t",2)),
        features=tuple(features))
