# 截角類型語意與裝配實作計畫

> **給代理工作者：** 實作此計畫時，必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐項執行。核取方塊 `- [x]` 表示該項已完成。

**目標：** 將截角類型升級為唯一的截角／裝配語意來源，並把參數化 GUI、箱身高度、孔位基準與 contract/API 串成同一條資料流。

**架構：** `ae_engine.sheetmetal_geometry` 擁有截角語意與裝配推導；板件 adapter 只把 WHD 參數轉成結構；contract/API 只傳遞 policy；GUI/Bridge 只編輯與保存製造語意選擇。`fold_designer_original.py` 保持只負責 renderer，不承擔製造規則。

**技術：** Python、dataclasses、Enum、Tkinter、pytest、ezdxf、Shapely（既有相依套件）。

**設計規格：** `docs/superpowers/specs/2026-08-21-corner-type-semantic-assembly-design.md`

## 全域限制

- 截角類型本身就是裝配關係，不新增獨立裝配旗標。
- 新 GUI 不顯示 `C01~C04` 或 `0°/90°` 作為截角操作。
- `C01~C04` 僅保留舊資料輸入相容。
- 嵌入貼外第二級 CUTTING 維持 `側折 + 留肉量`；`FW - 留肉量` 只代表兩級之間剩餘材料。
- `fold_designer_original.py` 不得改製造幾何；只允許加入全域文字倍率。
- 共享指示燈盒／小門的截角類型固定唯讀。
- 所有正式程式行為變更都必須先有會失敗的回歸測試。
- 使用者可見的新介面、錯誤訊息與交付說明使用繁體中文；內部程式識別字保留既有英文 API 名稱。

---

### 任務 1：建立新的截角語意模型

**檔案：**
- 修改：`ae_engine/sheetmetal_geometry.py`
- 測試：`tests/test_corner_semantics.py`

**介面：**
- 產出：`CrossCornerMode`、`CornerDirection`、新的 `CornerTypeId`、參數化 `CornerTypeSelection`、`normalize_corner_selection()`。
- 保留：舊 `C01..C04`、`VAULT_C01..VAULT_C04` 相容常數。

- [x] 先寫 `C01~C04` 相容轉換的失敗測試。
- [x] 先寫十字標準／留肉／多切方向與 `xT` 的失敗測試。
- [x] 實作新語意 enum 與參數欄位。
- [x] 僅在引擎邊界轉換舊 `C01~C04`。
- [x] 驗證截角幾何測試通過。

### 任務 2：修正貼外／嵌入／嵌入貼外截角幾何

**檔案：**
- 修改：`ae_engine/sheetmetal_geometry.py`
- 測試：`tests/test_corner_semantics.py`

**介面：**
- 輸入：新的 `CornerTypeSelection`。
- 產出：單級貼外／嵌入與二級嵌入貼外的 `resolve_corner_relief()` 結果。

- [x] 先寫貼外只能在高方向留肉的失敗測試。
- [x] 先寫嵌入只能在高方向多切的失敗測試。
- [x] 先寫回歸測試，確認嵌入貼外第二級 CUTTING 回到 `側折 + 0.5T`。
- [x] 更新金庫型固定 `C04` 的相容幾何。
- [x] 驗證第二級深度仍為 `2T`；`側折15/T2/0.5T` 時位置為 `16mm`。

### 任務 3：由截角類型決定箱身高度

**檔案：**
- 修改：`ae_engine/sheetmetal_geometry.py`
- 修改：`ae_engine/sheetmetal_part_adapters.py`
- 測試：`tests/test_corner_semantics.py`

**介面：**
- 產出：`corner_outer_thickness_factor()`、`endcap_outer_thickness_factor()`、`box_body_vertical_offsets()`、`box_body_height_from_corner_policies()`。
- `build_box_body_result(..., head_corner_policy, tail_corner_policy)` 使用這些結果。

- [x] 先寫 `H-2T / H-T / H` 的失敗測試。
- [x] 無 policy 時維持既有金庫型 `H-2T`。
- [x] 實作由 policy 推導箱身高度。
- [x] 驗證上下純嵌入時箱身為完整 `H`。

### 任務 4：箱身孔位與面特徵使用同一套裝配偏移

**檔案：**
- 修改：`ae_engine/sheetmetal_features.py`
- 修改：`ae_engine/ae.py`
- 測試：`tests/test_corner_semantics.py`

**介面：**
- `BoxBodyFaceContext` 保存 `bottom_outer_offset` 與 `top_outer_offset`。
- `box_body_face_contexts_from_strip()` 使用封頭／封尾 policy。

- [x] 先寫貼外與純嵌入成品面／展開座標映射的失敗測試。
- [x] 移除垂直方向固定 `2T` 的假設，改用 policy 推導偏移。
- [x] 基準固定特徵與使用者面特徵都使用相同偏移。
- [x] 驗證真實結構 CUTTING 高度與同一份 policy 一致。

### 任務 5：對外 contract 與製造 API 傳遞

**檔案：**
- 修改：`ae_engine/contracts.py`
- 修改：`ae_engine/manufacturing_api.py`
- 修改：`ae_engine/ae.py`
- 測試：`tests/test_corner_semantics.py`

**介面：**
- `BoxBodyPartSpec.head_corner_policy`
- `BoxBodyPartSpec.tail_corner_policy`
- `ae.export_box_body_dxf(..., head_corner_policy, tail_corner_policy)`

- [x] 先寫 API 傳遞失敗測試。
- [x] 在 `BoxBodyPartSpec` 增加兩個 policy 欄位。
- [x] 經 `_box_body_export()` 與 AE exporter／場景建立器一路傳遞。
- [x] 驗證 API 邊界不自行重建或改寫 policy。

### 任務 6：保存完整截角參數與 INI 狀態

**檔案：**
- 修改：`ae_engine/corner_type_ui.py`
- 修改：`phase6_settings_center.py`
- 修改：`gui.py`
- 修改：`fold_designer_bridge.py`
- 測試：`tests/test_corner_ui_integration.py`

**介面：**
- 原始狀態完整保留 `type_id`、`cross_mode`、`direction`、`amount_t`、`secondary_retain_t`、`secondary_depth_t`。

- [x] 先寫 INI 來回保存失敗測試。
- [x] 先寫 GUI 快照／還原失敗測試。
- [x] 先寫 Bridge 正規化失敗測試。
- [x] 修正 `apply_manual_corner_selection()`，讓左右相同／分離操作不洗掉參數。
- [x] 驗證保存、載入、還原均保留全部語意欄位。

### 任務 7：把舊 C 代碼／旋轉 UI 換成繁體中文製造語意控制

**檔案：**
- 修改：`gui.py`
- 修改：`fold_designer_bridge.py`
- 測試：`tests/test_corner_ui_integration.py`

**介面：**
- 可編輯類型顯示：十字截角／貼外型／嵌入型／嵌入貼外型。
- 動態欄位只顯示該類型真正可用的製造參數。

- [x] 從新 UI 移除 `C01~C05` 選擇器。
- [x] 移除 `0°/90°` 截角選擇器。
- [x] 加入十字方式、方向與 `xT` 控制。
- [x] 加入貼外／嵌入單一 `xT` 控制。
- [x] 加入嵌入貼外的貼外留肉／嵌入留肉／深度控制。
- [x] 修正切到「多切」時預設回到「寬＋高、0.5T」，不沿用舊狀態。
- [x] 已知固定板件以繁體中文顯示唯讀截角摘要。
- [x] 指示燈盒／小門即使箱型為「自訂」仍固定不可編輯。

### 任務 8：GUI 建立箱身規格時帶入封頭／封尾截角 policy

**檔案：**
- 修改：`gui.py`
- 測試：`tests/test_corner_ui_integration.py`

**介面：**
- `_box_body_part_spec()` 從與封頭／封尾相同的 GUI 狀態推導 `head_corner_policy` 與 `tail_corner_policy`。

- [x] 先寫規格建立失敗測試。
- [x] 把兩份 policy 傳入 `BoxBodyPartSpec`。
- [x] 實際輸出 DXF 驗證 `H=600, T=2` 且上下純嵌入時 CUTTING 高度為 `600mm`。

### 任務 9：驗證與接手文件

**檔案：**
- 建立：`docs/superpowers/verification/2026-08-21-corner-type-semantic-assembly-verification.md`
- 建立：`修改日誌/20260821.md`

- [x] 執行截角語意與 GUI 回歸測試。
- [x] 編譯修改過的 Python 模組。
- [x] 實際輸出純嵌入箱身 DXF 做製造 smoke test。
- [x] 驗證金庫型封頭尾仍有 5 條 BEND，第二級使用新留肉算法。
- [x] 驗證 `fold_designer_original.py` 只有文字倍率差異，Renderer 幾何／操作模型未改。
- [x] 從使用者本次上傳的精確基準產生 patch，並實際乾淨套用驗證。

### 任務 10：繁體中文可讀性防退化

**檔案：**
- 修改：`gui.py`
- 修改：`fold_designer_bridge.py`
- 修改：Superpowers 文件與修改日誌
- 建立：`tests/test_traditional_chinese_handoff.py`

- [x] 使用者可見的截角名稱與操作欄位保持繁體中文。
- [x] Superpowers 與交付文件章節名稱改成繁體中文。
- [x] 新增測試防止截角 GUI 再出現英文操作名稱或舊 C 代碼選單。
- [x] 明確記錄：程式內部識別字保留英文，使用者介面與說明使用繁體中文。

### 任務 11：修正封頭尾 C04 二級截角誤解

**檔案：**
- 修改：`ae_engine/sheetmetal_geometry.py`
- 修改：`tests/test_corner_semantics.py`
- 建立：`tests/test_endcap_regression_and_text_scale.py`

- [x] 先重現錯誤：原錯誤規格會得到 `39mm`。
- [x] 將正式二級 CUTTING 恢復為 `側折 + 嵌入留肉量`。
- [x] 固定金庫型 ReliefConfig 相容路徑同步恢復 `側折 + 0.5T`。
- [x] 驗證 `FW=25/T=2/側折=15` 時二級為 `16mm`、深度 `4mm`。

### 任務 12：全域文字大小小／中／大

**檔案：**
- 建立：`ui_text_scale.py`
- 修改：`phase6_settings_center.py`
- 修改：`gui.py`
- 修改：`fold_designer_bridge.py`
- 修改：`fold_designer_original.py`（只限文字倍率）
- 修改：`ae_engine/ae.py`
- 測試：`tests/test_endcap_regression_and_text_scale.py`

- [x] 加入 `ui_text_size` 全域設定，預設 `small`。
- [x] 定義小=`1.0×`、中=`1.2×`、大=`1.4×`。
- [x] 主 GUI 標題列加入「文字大小」選擇器。
- [x] 3D 折彎設計器全域設定加入同一選擇器。
- [x] Tk/ttk/Canvas 使用同一控制器；新建立的 Canvas 文字也跟隨倍率。
- [x] Matplotlib 2D/3D 標註與刻度套用同一倍率。
- [x] 選擇保存到 `[UI] text_size`，下次啟動沿用。
- [x] 驗證只改文字，不改 CAD/DXF 幾何。


### 任務 13：把「未知類型」改為「自訂」並繼承目前資料

**檔案：**
- 修改：`ae_engine/corner_type_ui.py`
- 修改：`gui.py`
- 修改：`fold_designer_bridge.py`
- 測試：`tests/test_custom_model_inheritance.py`

**介面：**
- 使用者可見名稱：`自訂`。
- 舊 `未知類型` 僅相容讀取。
- `known_model_corner_state()` 提供目前已知固定板件的實際截角狀態，作為自訂起點。

- [x] 先寫「自訂名稱＋舊字串相容」失敗測試。
- [x] 先寫金庫型固定截角複製失敗測試。
- [x] 先寫主 GUI 金庫型→自訂不重置尺寸／孔位物件的失敗測試。
- [x] 先寫 3D Bridge 已知→自訂不可恢復舊自訂草稿的失敗測試。
- [x] 模型清單只顯示「自訂」，舊 `未知類型` 正規化為「自訂」。
- [x] 主 GUI 切入自訂時複製固定截角並保留目前其他資料。
- [x] 3D Bridge 切入自訂時使用相同固定截角複製規則。
- [x] 實際 Tk smoke 重跑原 `draw_box_body()` 失敗路徑，確認不再拋裝配語意錯誤。
