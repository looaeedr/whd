# Phase6 3D 基準特徵製程分類與定位修正

## 問題

3D 真實 CUTTING mesh 導入基準檔 secondary geometry 後出現兩個回歸：

1. 門板 Ø13 打標圓在某些基準檔使用 `MARKING` 圖層但 entity color 為 BYLAYER，舊門板拉伸邏輯只看 color 211，導致被錯分類為 CUTTING 並在 3D 挖洞。
2. 基準 secondary geometry 與目前 3D 編輯後的 BEND 座標不一定一致，孔位可能相對折線偏移；封頭另有 raw scene 尚未做方向正規化的問題。

## 正式規則

- DXF 明確 operation layer 優先：`CUTTING / BEND / MARKING / DATUM / BLIND_HOLE`。
- color 211 僅作舊 layer-0 資料的 MARKING fallback。
- 3D material subtraction 只接受 `CUTTING`。
- `MARKING` 與 `BLIND_HOLE` 只畫在折後表面，不可挖穿板材。
- 基準檔 blank bounds 只由 structural CUTTING 決定，板外 MARKING/DATUM/BLIND_HOLE 不得改變座標原點。
- baseline secondary geometry 以 source/current BEND anchors 做剛性重定位；保留距最近對應折線/邊界的物理偏移，圓孔半徑與輪廓尺寸不縮放。
- 封頭 3D baseline 必須使用 `_build_stretched_end_cap_scene()` 的方向正規化 scene，不得使用 raw `get_stretched_end_cap_data().scene`。

## 永久 TEST

新增 `tests/test_phase6_baseline_operation_alignment.py`：

- MARKING layer + BYLAYER 的 Ø13 圓仍為 MARKING。
- BLIND_HOLE 不得變 CUTTING。
- 真 CUTTING 圓才挖洞。
- 板外 MARKING 不得污染 door baseline bounds。
- source fold 20 → target fold 30 時，距 BEND 5 mm 的孔中心由 25 → 35，半徑不變。
- baseline scene 在 material subtraction 前必須先對齊 current scene。
- 封頭 baseline 使用 orientation-normalized builder。
- MARKING circle 會投影到 3D 表面線條，但 CUTTING circle 不走 marking drawer。
