# 組合體干涉反投影截角設計

## 目標

把組合體 3D 中已確認的 Box Body ↔ EndCap/Tail 真實板厚干涉，反投影回 EndCap/Tail 自己的 2D 展開座標，產生可量測、可回寫 CUTTING 的實際截角；加入可調淨空 A 後重新折回 3D 驗證，直到截角區不再有非共面實體穿越。

## Source of Truth

- Box Body 保留，EndCap/Tail 負責切除。
- Fold Profile、final BEND guides、孔與 CornerType 語意仍由 AE / Manufacturing API 擁有。
- 3D Viewer 不產生製造截角公式；反投影與 relief candidate 由 `ae_engine/assembly_collision.py` 擁有。
- Assembly world transform 仍由 `ae_engine/assembly_geometry.py` 單一擁有，Viewer 與 solver 共用。
- 正式解法不能以舊固定截角尺寸當答案；舊固定截角只可提供診斷/搜尋區基準，最終尺寸必須由 3D 干涉反投影與回折驗證決定。

## 幾何流程

1. 從正式 EndCap/Tail material 建立「補回舊固定截角但保留孔」的 unrelieved material。
2. 使用 authoritative X/Y Fold Profile + final BEND guides，將 2D 三角片折成 local 3D；每個三角片同時保留原始 2D UV 三點。
3. 套用共享 Head/Tail assembly transform，建立 world-space folded mid-surface。
4. 依實際板厚 T 產生兩側 skin triangle；每個 skin triangle 保留同一組 2D UV。
5. Box Body 使用現有 world-space physical solid。對 target skin 與 Box Body solid 做非共面 triangle crossing。
6. 每個 3D intersection point 以 barycentric coordinate 精確映射回 target triangle 的 2D UV，得到 flat-space interference segments。
7. 在每個外部固定截角 component 內，用反投影交線切割 component，選取連到實體 blank corner 的干涉側材料，形成 2D collision cut polygon。
8. 淨空 A 在已驗證的正交截角級距上做精確軸向擴張：primary U/V 各 +A、secondary U +A、secondary depth 保持原級距深度；不得用一般 polygon buffer 讓斜接數值噪音污染正式尺寸。結果仍限制在 unrelieved blank 內，孔由 material difference 保留。
9. 使用 `unrelieved_material - cut_polygon` 建立新的 EndCap/Tail material，重新生成 CUTTING。
10. 將新 material 再折回 3D，只在對應 corner search zone 驗證碰撞；若仍有穿越則 candidate 不得標示 verified。

## 截角尺寸

每個 corner cut 轉為 canonical inward `(u, v)` 座標後輸出：

- `primary_u`：第一級截角寬度。
- `primary_v`：第一級截角高度。
- `secondary_u`：若存在第二級，第二級截角寬度。
- `secondary_depth`：若存在第二級，第二級深度。
- `clearance_a`：本次加入的淨空 A。

尺寸由最終 cut polygon 解析，不從舊 C03/C04 固定數值反推。

## UI / 診斷

組合體「參數解鎖」診斷區新增：

- `淨空 A` 數值輸入。
- `實際截角尺寸` 狀態文字，分別顯示封頭與封尾四角結果。
- 3D 繼續顯示紅色干涉區；套用求解後若驗證成功，狀態顯示 `3D 驗證：無干涉`。

這一階段先由診斷區計算與顯示正確尺寸；只有 solver candidate verified 才可送往正式 manufacturing relief，不允許 UI 自己改 polygon。

## 驗證條件

- 可手算單平面測件：3D 穿越邊界反投影後 2D 尺寸與手算一致。
- A 改變時，2D cut 尺寸必須同步增加。
- 標準金庫型 Head/Tail 的孔、5 道 BEND、組合方向不因求解而變更。
- 套用候選 cut 後，對應 corner search zone 的 3D 非共面穿越為 0 才能 `verified=True`。
- `config.ini` 不得修改。

## 數值穩定性與鏡像件

- 3D triangle crossing / barycentric backprojection 允許有浮點誤差，但正式截角尺寸不能把微米級剖分噪音當成機械非對稱。
- 左右角只有在 canonical cut shape 的 Hausdorff distance 已落在嚴格製造容差內時，才可用兩者 canonical union 消除數值噪音；真正非對稱幾何不得被強迫成對稱。
- A clearance 是獨立製造 policy，應在已收斂的 collision cut 上精確擴張，不能反過來改寫 3D collision envelope。
- 新 CUTTING 套回 Manufacturing API 後，BEND 必須從 authoritative Fold Profile 重新產生並依新 material 重新 clip；若新截角比舊固定截角少切，折彎線必須延伸回新增留肉，不能沿用舊截短 BEND。

## 2026-08-29 補充：單級 INSERT 的 skin-contact 校正

對真板厚 EndCap，mid-surface 兩側 ±T/2 skin 都可能與 Box Body 形成交線。**交線本身不等於 penetration**：正常 mating face/edge contact 必須先從候選 crossing envelope 排除。

單級 `INSERT` 採以下額外約束：
1. topology 永遠保持單級；多輪迭代只可調整同一 `primary_u / primary_v`。
2. 不以兩張 skin 的外側 extrema 當 relief 邊界；正式 relief 取折後實際 mating boundary 的 flat UV 回投影。
3. 不得用 `-T/2`、`-0.5T` 等固定補償硬修數值；板厚只參與 physical solid 與 contact/penetration 分類。
4. candidate 仍必須 refold verification；只有 material penetration 歸零才可 commit。
5. `INSERT_OVERLAY` 等真正二級 topology 不套「強制單級」規則。

`自訂(9)` regression（W400/H600/D250/T2/FW25）中兩側 skin 線約為 37.02 / 38.98，而真實 mating boundary 為 38.00；正式 result 為 `38×27`。這是測試證據，不是通用常數。

## 2026-08-29 補充：Diagnostic probe / topology / registry gate

### 求解前碰撞證據
組合圖「碰撞區」必須使用 relief solver **套 cut 前**的 EndCap physical probe。已套 cut 的 production material 只用於 final display 與 refold verification；不得拿 final material 再判斷「原本有沒有撞」。

### Topology ownership
Assembly Intent / legacy component 只保留合法 corner topology（單級／二級），3D solver 決定實際 U/V 尺寸。即使 `OVERLAY` X profile 為 flat，也不得跳過 topology normalization；triangle-skin 小階梯不能升格為 manufacturing secondary stage。

### Contact safety gate
Topology normalization 後的 physical skin crossing 只有同時符合：
1. crossing 位於 topology boundary 小容差帶內；
2. semantic mid-surface 無 retained-material penetration；
才可分類為 contact。禁止單純提高全域 tolerance 把真 penetration 吞掉。

### Mirror symmetry
只有 Box Body X folded profile、EndCap X folded profile 與左右 corner component 都通過幾何 mirror 判定時，左右 evidence 才可 mirror-harmonize。其目的只在補 triangle tessellation 漏採樣；真非對稱件不得被強迫對稱。

### Registry-driven acceptance
所有 assembly intent 測試直接 parametrized production `BOX_ASSEMBLY_TYPE_IDS`。新增 intent 時測試自動增加，至少驗證 Head/Tail pre-solve collision、post-solve verified、topology stage count、對稱 fixture mirror equality、2D/single3D/assembly material equality、collision overlay、Save/Reload。
