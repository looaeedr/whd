# 截角語意版本回退修復 — 2026-08-21

## 問題

後續指示燈／baseline resolver 更新曾以較舊的 FIX13 四檔 overlay 作為底包：

- `gui.py`
- `ae_engine/ae.py`
- `ae_engine/contracts.py`
- `ae_engine/manufacturing_api.py`

這會把已完成的 semantic CornerType 架構局部覆回舊版，造成兩個直接症狀：

1. GUI 再次出現 legacy `C01/C02/C03/C04` 與舊旋轉操作。
2. 從已知型號切換「自訂」時，封頭／封尾沒有繼承正確固定截角，會掉回全角 `CROSS / STANDARD`；實際封頭 DXF 因而少掉上方二級截角。

同一個回退也會讓 Box Body contract/API 丟失 `head_corner_policy` / `tail_corner_policy`，使 CornerType 裝配語意無法傳到箱身高度與 face mapping。

## 正確主幹

本包改以 `CORNER_TYPE_CUSTOM_INHERIT_ENDCAP_TEXT_ZHTW_20260821` 為唯一主幹，保留：

- 正式語意 CornerType：`CROSS / OVERLAY / INSERT / INSERT_OVERLAY`。
- legacy `C01~C04` 僅保留 engine boundary 相容讀取，不在新 GUI 顯示。
- 已知封頭／封尾固定規則：
  - 上方：`INSERT_OVERLAY`，貼外留肉 `1T`、嵌入留肉 `0.5T`、深度 `2T`。
  - 下方：`CROSS / EXTRA_CUT / BOTH / 0.5T`。
- 從已知型號切到「自訂」時，先複製上述實際規則作為自訂起點；不重置使用者尺寸／開孔資料。
- Box Body 繼續接收 head/tail CornerType policy，裝配高度與 face coordinate 共用同一語意來源。
- 先前已完成的指示燈盒／小門尺寸鏈、視窗中心、動態 gap、shared baseline resolver 都保留。

## 永久回歸測試

### `tests/test_corner_semantic_overlay_guard.py`

專門阻止 maintenance overlay 再次降版：

- GUI 不得出現 `CornerTypeId.C01~C04` 選項。
- GUI 不得恢復 CornerType 0°/90° 舊旋轉操作。
- 已知封頭尾 state 必須是 semantic selection。
- 已知 → 自訂必須繼承封頭尾正確語意。
- `BoxBodyPartSpec` 必須保留 `head_corner_policy` / `tail_corner_policy`。
- 實際封頭 DXF smoke：400×250、T=2、FW=25 範例必須輸出 17 點 CUTTING 輪廓並保留二級截角；回退版只有 13 點，測試必須失敗。

### `tests/test_baseline_resource_resolution.py`

保留先前 resolver 防呆：

- GUI/API 不直接拼 `基準檔` 實體路徑。
- shared indicator baseline 不硬 fallback 到固定資料夾名稱。
- resource root 切換必須同步解析。
- 0 / 多候選時明確報錯。
- 任意 shared 資料夾名稱可實際輸出盒子／小門 DXF。

## 紅燈／綠燈驗證證據

把舊 FIX13 四檔 overlay 蓋到 semantic 主幹後：

- semantic integration targeted suite：7 failures。
- `test_corner_semantic_overlay_guard.py`：4 failures / 1 pass。
- 實際錯誤封頭 CUTTING：13 points，全角退回 `CROSS / STANDARD`。

恢復 semantic 主幹後：

- `test_corner_semantic_overlay_guard.py`：5/5 pass。
- CornerType / custom inheritance / baseline resolver / EndCap 整合 targeted：46 pass（加入實際 DXF guard 後再全包驗證）。

## 交付原則

這次不再提供「只有四個 production Python」的降版 overlay。交付包包含完整 semantic runtime 檔案與永久 tests，避免新舊 CornerType 模組互相錯配。
