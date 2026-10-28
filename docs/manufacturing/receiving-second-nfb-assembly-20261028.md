# 受電箱第 2 顆 NFB → 實體內門組合體（2026-10-28）

## 操作需求與唯一來源

- 一層可以放兩顆以上 NFB。**層數**與實體安裝層數是同一個權責；每顆 NFB 使用獨立 `(layer_index, slot_index, physical_hole_id)`，不得被第一顆覆蓋。
- 開孔來源：目前品牌的 NFB 數值 CSV V5 與原生 Hole Editor 的 `NFB_CSV_SOURCE`。來源型號、尺寸與操作者保存的 X/Y／旋轉先經過合法性檢查；不得從畫面畫到兩個矩形就冒充製造已通過。
- 候選版本與實體連分開：在「多連設定 → 內門版本 → 編輯 → 確定全部」只是儲存候選；**套用到高亮的連**才替換物理 NFB 孔與層數。取消／僅預覽不得改動實體連。
- 實際 **3D 組合體**不看 GUI Listbox 數量，應核對 `query_assembly_render_data().assembly_parts` 的 `inner_door:upper:panel` `render_data.material` 中有兩個真正的內孔，且 `metadata.nfb_v5_hole_ids` 為兩個不同 ID；底板／螺絲／PAD 依同一份已提交資料投影。

## 確認的缺陷

1. 舊版 `.p6fold` 的真實 Set/Bay `nfb_config` 可保存兩顆，舊版 `inner_door_models` 卻只有一顆，甚至缺少原生 `part_features`；不能因顯示清單短而直接丟掉已保存的第二顆 CSV 身份。
2. 第一次從主 GUI 打開 Set/Bay 專案時，如果只在**重用 Designer**的情況恢復 `_apply_mode_snapshot`，新建 Designer 會因單只初始值重建成一顆，失去完整載入值。
3. 新增內門候選 v1 後，`editor_saved(... keep_live=True)` 留在「即時」，再按「套用」會走 `apply_live`（只改標籤），**不會送 `apply_inner_door_candidate_to_bays`，因此實體內門組合體缺第 2 孔**。

## 修正契約

- 首次開啟與重用 Designer 都恢復同一份 `.p6fold` Set/Bay 權責，不改動原始專案檔，也不重寫其他連。
- 原生編輯器新候選可從目前選取 Bay 的已提交兩顆 NFB CSV 身份補回**缺失的模型列**；只有在已保存來源有效、原編輯器清單比已提交來源短時才補，保留更完整的原生選型；這是可取消草稿，不是自動加工／核准。
- 新內門候選「確定全部」後，UI 自動選中剛產生的版本（不直接物理套用）；操作員按「套用」時必須走 **candidate Apply**，不是 `apply_live` 標籤分支。要建立另一個獨立版本可自行切回「即時」。
- `nfb_config_submitted=True` 的舊連可透過**完整且已驗證的 CSV 原生 Features**原子替換原有 NFB；禁止用非 CSV、部分清單、無合法實體孔身份強行覆蓋。
- 錯誤、取消、Undo、候選尚未套用時，舊實體連與製造來源不變。未驗證 NFB X、合法 CENTER/PAD 與整箱 NC 輸出狀態均不得因這次 UI 修正而被推定合格。

## Windows 原生驗收

R5-2600 使用既有舊檔的**讀取副本**：
`Z:\\localX\\logs\\DC_1503_UAT_20261020_1800\\prior_real_saved_projects\\one_layer_two_models.p6fold`。

原檔：單層兩個已提交 CSV NFB 型號，舊 shared aliases 原本只有第一顆或空 Features；在原生 GUI 的多連入口顯示兩顆，按原生「確定全部」新增版本後，指定連按「套用」。實際組合體 `inner_door:upper:panel` 的 `material.interiors` 等於 2，兩個實體孔 ID 不同。需要同樣核對 Save As → GUI Reopen 的組合體孔數；CI regression 以純函式與原生 Tk 候選套用路由守護。
