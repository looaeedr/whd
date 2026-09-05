# Phase6 2D / 3D 即時 Canonical 同步設計

## 目標
移除 Fold Designer 的「確定／取消」交易式 draft，讓 3D 編輯即時寫回主 GUI 的唯一 canonical state；2D、3D 組合體、DXF/NC 全部只由同一份 Manufacturing PartSpec → PartRenderData 重建。

## 已確認問題
1. 3D 目前有自己的 draft state，主 GUI 2D 有 committed state，兩者可以不同步。
2. `自訂(6).p6fold` 可出現 `assembly_type=INSERT_OVERLAY`，但保存的 assembly relief source 仍是舊 `INSERT`。
3. 3D solver 曾直接使用自己的 `solved_render_data`，2D/DXF 則透過 `resolved_assembly_relief_cuts` replay，形成雙 Source of Truth。
4. 3D dynamic relief 可以出現 Head 已驗證、Tail 未驗證的半套套用，組合體因此混用新舊幾何。
5. 2D replay 曾把四角全部 restore，造成與 3D solved material 差 512 mm²（兩片 16×16）。

## 新規則
### 1. 單一 canonical state
- Fold Designer 不再擁有可延後提交的 production draft。
- W/H/D/T/FW、組合方式、CornerType、Fold Profile、板件存在狀態、EndCap FW、淨空 A 等實際編輯，在 debounce/完成編輯後立即 publish 到主 GUI canonical state。
- 主 GUI 立即更新 Manufacturing state；不自動寫磁碟。

### 2. 移除確定／取消
- 3D 頂列只保留「還原初始值」；移除「確定」「取消」。
- 關閉 3D 視窗只關閉視窗，不 rollback。
- `還原初始值` 是顯式回復操作，且回復結果立即同步 canonical state。
- 存檔仍由「檔案」選單明確執行。

### 3. 3D 只顯示 authoritative Manufacturing geometry
- dynamic relief solver 只產生 verified cut polygon，不得直接把 `solution.solved_render_data` 當 production render。
- verified cut 必須寫入 canonical `assembly_relief_state`，再由主 GUI Manufacturing provider 重建 EndCap PartRenderData。
- 2D、3D、DXF/NC 使用完全相同的 PartSpec / Manufacturing replay helper。

### 4. Head/Tail dynamic relief 原子提交
- 同一輪求解 Head 與 Tail 都成功且 3D refold verified 才一起 commit 新 cuts。
- 任一片失敗：Head/Tail 都不更新 canonical relief；組合體仍顯示目前 canonical 2D geometry，只顯示診斷錯誤。
- 不允許 Head 新、Tail 舊或反之的半套狀態。

### 5. stale relief 自動失效
- relief source fingerprint 至少包含 W/H/D/T/FW、組合方式、Head/Tail Fold Profile。
- fingerprint 不符就視為 stale，不得 replay 到 2D/3D/DXF。
- 3D 可重新求解；只有整組 atomic verified 後才寫回新 fingerprint + cuts。

## 同步介面
新增 Fold Designer `on_live_sync(payload)` callback。payload 使用既有完整 transaction payload 格式，避免新增第二套欄位 mapping。主 GUI 以 `_apply_fold_designer_live_snapshot(payload)` 套用，但不呼叫 draft confirm/cancel。

Fold Designer 任何 production state 改變後呼叫 `_phase6_publish_live_state()`；publish 有 re-entrancy guard，避免主 GUI `update_calculations()` 反向通知造成迴圈。

## 關閉與存檔
- 開 3D：從主 GUI current snapshot 建立 UI 工作副本，但它不是可 rollback 的 production draft。
- live edit：立即 publish。
- 關閉：flush pending settings + save current fold editor + publish once，然後 destroy。
- Save/Save As：因 canonical 已同步，主 GUI project save 直接存目前狀態。

## 驗收
1. 頂列沒有「確定」「取消」。
2. 真按 3D 編輯後，不關 3D、不按任何確認，主 GUI state 已改。
3. 同一 EndCap 的主 2D authoritative material 與 3D assembly render material symmetric difference area = 0。
4. `自訂(6).p6fold` 改組合方式後，舊 relief source 不得繼續使用。
5. Head/Tail 一成功一失敗時，canonical relief 完全不變，兩片 3D 都沿用 canonical geometry。
6. Head/Tail 都成功時，兩片 cuts 同一次 commit；2D/3D/DXF replay 一致。
7. `config.ini` 不因即時同步自動改寫。

## 2026-08-29 補充：截角尺寸顯示也屬 canonical geometry consumer
- 組合圖左側的「所有板金截角尺寸」、單板 2D 尺寸、單板 3D 尺寸必須量同一份 canonical `PartRenderData.material`。
- 板件「是否顯示於組合圖」只是 renderer visibility state；不得改 PartSpec、relief state、DXF/NC 或 production material。
- 「回2D截角」只切換目前板件至主 2D 截角頁；返回前同步目前 live state，不建立 confirm/cancel transaction。
- 任何一個 consumer 顯示 40/39、另兩個顯示 38，視為 canonical chain 破裂，不允許用 rounding 或顯示格式修補。
