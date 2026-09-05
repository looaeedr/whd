# PHASE6 WRAP / AssemblyJoint / Certified Relief Registry / 3D Solver v2 實作任務清單

> 日期：2026-08-29  
> 依據：`PHASE6_外部包覆_AssemblyJoint_截角資料庫_3D求解完整架構規格書_20260829.md`  
> 基準程式：`PHASE6_OVERLAY_NOMINAL_SIDE_FOLD_FIX_FULL_20260829_160848.zip`  
> 原則：TDD；既有 CERTIFIED 正確截角不得因 3D 改版而改變；Family 只提供幾何，不重新解釋 Assembly Semantics。

---

## 0. 執行順序總覽

```text
A. Joint Core ─────┬────> B. Registry v2 ─────> C. GUI 表單
                   │
                   ├────> D. 3D Solver v2 ────> E. 3D Diagnostics
                   │
                   └──────────────────────────> F. Manufacturing Integration

A/B/D/F 完成後 ──────────────────────────────> G. Migration / Save-Reload
A～G 全部完成 ───────────────────────────────> H. 全矩陣驗收 / 打包
```

### 可並行原則

- A 完成資料契約後，B 與 D 可並行。
- B 的 JSON/schema/API 穩定後，C 可開始。
- D 的 diagnostic result contract 穩定後，E 可開始。
- F 必須等 A/B/D 的 canonical contract 穩定後再全面切換。
- G、H 不得提早宣告完成。

---

# A 組 — AssemblyJoint Core（第一優先）

**主要責任：** 建立「實體對實體」的 Joint Source of Truth；WRAP 正式進入全域語意。

## A1. 建立 AssemblyJoint 資料契約

**建議檔案**
- 建立：`ae_engine/assembly_joint.py`
- 修改：`ae_engine/contracts.py`
- 測試：`tests/test_assembly_joint_contract.py`

- [x] 定義 `AssemblyJointRelation`: `INSERT / OVERLAY / INSERT_OVERLAY / WRAP`。
- [x] 定義 `AssemblyJointSource`: `INTENT_DERIVED / USER_ADDED / FAMILY_GEOMETRY / LEGACY_MIGRATED`。
- [x] 定義 `AssemblyJoint` dataclass。
- [x] 欄位至少包含：`joint_id / subject_part / target_part / subject_region / target_region / relation / contact_mode / preserve_side / relief_intent / clearance_policy / solver_constraints / source`。
- [x] WRAP invariant：subject 永遠是外部包覆者，target 永遠是被包覆者。
- [x] 禁止 relation 與方向產生雙重真值。

**驗收**
- [x] WRAP 不需要額外 `wrapper/wrapped` 欄位也能唯一決定方向。
- [x] 同一 part 可同時存在多條不同 relation 的 Joint。

## A2. 建立 Joint Semantics Registry

**建議檔案**
- 修改：`ae_engine/assembly_joint.py`
- 修改：`ae_engine/sheetmetal_geometry.py`
- 測試：`tests/test_assembly_joint_semantics.py`

- [x] INSERT Joint semantics 資料化。
- [x] OVERLAY Joint semantics 資料化。
- [x] INSERT_OVERLAY Joint semantics 資料化。
- [x] WRAP Joint semantics 資料化。
- [x] 定義 legal contact、illegal penetration、preserve side、mating direction。
- [x] Family 不得覆寫 relation 的機械語意。

**驗收**
- [x] 金庫型與受電箱相同 relation 的 semantic fields 完全一致。
- [x] Family 差異只能出現在 resolved face / dimensions / coordinates。

## A3. Assembly Intent → Joint[] Resolver

**建議檔案**
- 修改：`ae_engine/sheetmetal_geometry.py`
- 修改：`ae_engine/assembly_geometry.py`
- 測試：`tests/test_assembly_intent_to_joints.py`

- [x] INSERT 解析成預設 Joint[]。
- [x] OVERLAY 解析成預設 Joint[]。
- [x] INSERT_OVERLAY 解析成預設 Joint[]。
- [x] 保留額外 USER_ADDED WRAP，不因 Intent 改變而遺失。
- [x] 不再把單一 `assembly_type` 當成整片 EndCap 的完整接合描述。

**驗收**
- [x] EndCap 可同時具有 `INSERT_OVERLAY + WRAP`。
- [x] 切換高階 Intent 時只更新 INTENT_DERIVED joints，不誤刪 USER_ADDED joints。

## A4. ResolvedAssemblyGraph

**建議檔案**
- 修改：`ae_engine/assembly_joint.py`
- 修改：`ae_engine/assembly_geometry.py`
- 測試：`tests/test_resolved_assembly_graph.py`

- [x] 建立 Part Node[]。
- [x] 建立 AssemblyJoint[] graph。
- [x] 檢查不存在的 part / region / mating target。
- [x] 檢查重複 joint / 衝突 joint。
- [x] 提供 corner-nearby joint query API。

**驗收**
- [x] 任何 consumer 不需再自行 `if family + assembly_type` 解讀接合。

---

# B 組 — Certified Relief Registry v2

**主要責任：** 已知正確公式優先；Rule key 升級為 Joint Signature；使用者可安全擴充。

## B1. Corner Joint Signature

**建議檔案**
- 修改：`ae_engine/certified_relief_registry.py`
- 新增/修改：`ae_engine/assembly_joint.py`
- 測試：`tests/test_corner_joint_signature.py`

- [x] 從 corner 收集 nearby joints。
- [x] 建立 canonical signature。
- [x] signature 順序無關，但 subject/target 方向不可丟失。
- [x] signature 可穩定序列化並作為 registry key。

**驗收**
- [x] `INSERT_OVERLAY + WRAP` 不會與單純 `INSERT_OVERLAY` 命中同一 rule。

## B2. Registry Rule Schema v2

**建議檔案**
- 修改：`ae_engine/certified_relief_registry.py`
- 建立：`基準檔/截角資料庫/certified_relief_rules.json`
- 建立：`基準檔/截角資料庫/certified_relief_rules.schema.json`
- 測試：`tests/test_certified_relief_registry_schema_v2.py`

- [x] Rule 加入 joint signature。
- [x] Rule 保存 `rule_id / revision / trust_level / topology_levels / formula / preconditions / source`。
- [x] 公式資料與 Python evaluator 分離。
- [x] 現有已確認 INSERT / OVERLAY / INSERT_OVERLAY 規則 migration 到 v2 schema。
- [x] 未經確認的單次 3D 數值不得 migration 為 CERTIFIED。

**驗收**
- [x] 舊已認證規則結果逐筆相同。
- [x] 純 INSERT/OVERLAY 永遠 topology=1；INSERT_OVERLAY 依正式規則 topology=2。

## B3. Safe Formula Evaluator

**建議檔案**
- 修改：`ae_engine/certified_relief_registry.py`
- 測試：`tests/test_relief_formula_evaluator.py`

- [x] 只允許白名單參數：T/FW/fold/mating width 等 resolved dimensions。
- [x] 禁止任意 Python eval。
- [x] 除零、未定義參數、負尺寸、NaN/Inf 直接拒絕。
- [x] evaluator 結果必須符合 rule topology contract。

## B4. Ambiguity / Revision / Migration

- [x] 多筆 active rule 同時命中 → `REGISTRY_AMBIGUOUS`。
- [x] 不准 ambiguity 後偷偷 fallback 3D。
- [x] revision 不存在 → 明確 migration / reject。
- [x] 已認證 rule 不可 runtime overwrite。
- [x] CERTIFIED 變更只能新增 revision。

## B5. Candidate / Promotion Backend

- [x] `PROVISIONAL_3D` 只能建立 candidate manifest。
- [x] candidate 不得直接寫入 certified JSON。
- [x] promotion 必須附回歸證據與參數範圍。
- [x] promotion 後新 rule 自動進 registry-driven matrix。

---

# C 組 — 截角資料庫 / Joint GUI 表單

**主要責任：** 使用者不用改 Python 就能新增/維護規則與 WRAP Joint。

## C1. 「截角資料庫」入口

**建議檔案**
- 修改：`fold_designer_bridge.py`
- 視現有 GUI 結構決定是否建立 focused panel module；不得只為縮檔硬拆。
- 測試：`tests/test_relief_registry_form.py`

- [x] 新增「截角資料庫」入口。
- [x] 顯示 rule list：ID / revision / trust / signature / topology / active。
- [x] 支援搜尋與篩選。

## C2. Rule 編輯表單

- [x] 盤體適用條件。
- [x] 板件 / corner region。
- [x] Joint Signature。
- [x] topology level。
- [x] 第一級 X/Y 公式。
- [x] 第二級 X/Y 公式（僅 topology=2）。
- [x] preconditions。
- [x] symmetry。
- [x] source / 備註。
- [x] revision 自動管理。

## C3. 即時公式預覽

- [x] 輸入測試參數即時計算。
- [x] 顯示第一/第二級結果。
- [x] 顯示缺少參數與公式錯誤。
- [x] 顯示 rule topology 是否合法。

## C4. 安全操作流程

- [x] `驗證公式`。
- [x] `預覽 2D`。
- [x] `預覽組合 3D`。
- [x] `儲存候選`。
- [x] `執行回歸`。
- [x] `認證新 Revision`。
- [x] 禁止直接覆蓋既有 CERTIFIED revision。

## C5. Joint 編輯表單

- [x] 顯示 subject part。
- [x] target part。
- [x] relation：INSERT / OVERLAY / INSERT_OVERLAY / WRAP。
- [x] subject/target region。
- [x] clearance policy。
- [x] source。
- [x] WRAP 選定後 UI 明確顯示「subject 包覆 target」。
- [x] USER_ADDED joint 可新增/刪除；INTENT_DERIVED 預設不可直接破壞語意。

---

# D 組 — 3D Discovery Solver v2

**主要責任：** Registry MISS 才求未知；以 Joint 機械語意求解，不再用 triangle bbox 猜公式。

## D1. Joint-local Collision Classifier

**建議檔案**
- 修改：`ae_engine/assembly_collision.py`
- 修改：`ae_engine/assembly_geometry.py`
- 測試：`tests/test_joint_local_collision_classifier.py`

- [x] collision 綁定 joint_id。
- [x] 區分 legal contact / illegal penetration。
- [x] contact face 上的接觸不算非法穿透。
- [x] WRAP 能知道外包者與被包覆者。

## D2. Preserve / Relief Ownership

- [x] INSERT：依插入者/ mating zone 語意決定避讓。
- [x] OVERLAY：合法外貼接觸保留；穿透才處理。
- [x] INSERT_OVERLAY：外貼區 preserve + 插入區 relief。
- [x] WRAP：wrapper 優先保留，wrapped 依 policy 避讓。

## D3. Local Coordinate / Backprojection

- [x] 建立 joint-local frame。
- [x] 從真實 penetration region 回投 flat pattern。
- [x] 禁止直接用 triangle intersection bbox 當截角公式。
- [x] 保存幾何證據供 diagnostics。

## D4. Topology Fitter

- [x] 將 backprojection fit 成 1-stage / 2-stage corner topology。
- [x] 不得違反 Assembly/Rule topology contract。
- [x] 無法穩定 fit → solver failed，不得硬猜。

## D5. Zero-Penetration Verification

- [x] replay candidate geometry。
- [x] 重新組裝 solids。
- [x] 驗證非法 penetration=0。
- [x] 合法 contact 不得因 tolerance 被當 collision。
- [x] 結果輸出 residual / evidence。

## D6. Registry HIT / MISS Gate

- [x] HIT CERTIFIED → 不進 discovery，只 shadow validate。
- [x] MISS + fallback enabled → Discovery Solver。
- [x] MISS + fallback disabled → 明確 UNKNOWN。
- [x] `ENGINE_CONFLICT` 只診斷，不覆蓋 CERTIFIED canonical。

---

# E 組 — 3D Diagnostics

## E1. Joint 選取與資訊面板

- [x] 可選 joint_id。
- [x] 顯示 subject / target / relation / source。
- [x] 顯示 Registry HIT/MISS、rule_id、revision、trust。

## E2. 幾何診斷顯示

- [x] 合法 contact region。
- [x] 非法 penetration region。
- [x] preserve region。
- [x] relief candidate region。
- [x] insertion / wrap direction arrow。

## E3. Solver Evidence

- [x] 顯示 pre-solve collision。
- [x] 顯示 candidate topology / 尺寸。
- [x] 顯示 post-solve residual。
- [x] ENGINE_CONFLICT 同時顯示 Certified vs 3D shadow 差異。

---

# F 組 — Manufacturing Integration

**主要責任：** 全部 consumer 只讀 Canonical / Resolved Manufacturing Geometry。

## F1. Canonical Result Contract

**建議檔案**
- 修改：`ae_engine/manufacturing_api.py`
- 修改：`ae_engine/contracts.py`
- 測試：`tests/test_resolved_manufacturing_geometry.py`

- [x] 定義 `ResolvedManufacturingGeometry`。
- [x] 包含 parts / joints / corners / relief rule metadata / diagnostics summary。
- [x] 不允許 downstream 自行重新求 assembly relief。

## F2. 2D / Single3D / Assembly3D

- [x] 主 2D 改讀 canonical。
- [x] 單板 3D 改讀 canonical。
- [x] 組合 3D 改讀 canonical。
- [x] 三者 material geometry equality regression。

## F3. FinalScene

- [x] `phase6_final_scene_view.py` 只讀 canonical solved geometry。
- [x] diagnostic probe 與 production material 保持角色分離。

## F4. DXF / NC

- [x] DXF 使用同一 corner / relief geometry。
- [x] NC 使用同一 corner / relief geometry。
- [x] 不得有 exporter 私自重算截角。
- [x] 診斷 NC（若存在）仍明確標示不可生產。

---

# G 組 — Save / Reload / Legacy Migration

## G1. Joint Graph Serialization

- [x] 保存 AssemblyJoint[]。
- [x] 保存 source。
- [x] 保存 USER_ADDED WRAP。
- [x] 重載後 joint graph equality。

## G2. Rule Metadata Serialization

- [x] 保存 `rule_id / revision / trust_level / signature`。
- [x] reload 時重新驗證 revision 是否存在。
- [x] revision 過期不得默默採舊 cut。

## G3. Legacy 專案 Migration

- [x] 舊 `assembly_type` 解析成 Intent-derived joints。
- [x] 舊上方 CornerType 仍是機械真值來源。
- [x] 無 WRAP 資料的舊檔不得自行猜 WRAP。
- [x] migration 有 version tag，可重複載入不重複新增 joint。

---

# H 組 — 自動回歸 / 驗收 / 交付

## H1. Registry-driven Matrix

- [x] 每一筆 active certified rule 自動進測試。
- [x] 每個 Assembly Intent 自動進 matrix。
- [x] 每個 Joint relation（含 WRAP）自動進 matrix。
- [x] 禁止手工白名單成為唯一覆蓋來源。

## H2. 每個認證案例固定驗證

- [x] Registry lookup 唯一命中。
- [x] topology 正確。
- [x] 公式 evaluator 正確。
- [x] 2D = Single3D = Assembly3D。
- [x] Save/Reload 相同。
- [x] DXF/NC 使用同一 canonical geometry。
- [x] shadow 3D 無非法 penetration。
- [x] ENGINE_CONFLICT 不改 canonical。

## H3. 必保護既有基準案例

- [x] `自訂(9)` INSERT：38×27、單級。
- [x] `自訂(10)` INSERT_OVERLAY：目前已確認 C04 規則與二級拓撲不得被 3D 改寫。
- [x] OVERLAY：單級、X Fold 不存在；flat-X manufacturing U basis 必須為 0，legacy nominal side 只可作 metadata，U residual 由 FW 自身提供。
- [x] `config.ini` 不修改。

> 注意：實際數字只作已確認 regression fixture；資料庫正式規則保存參數公式與適用條件，不保存「看到一次就寫死」的尺寸。

## H4. 最終 Definition of Done

- [x] WRAP 是 Global AssemblyJoint relation。
- [x] 同一 Part 可同時有多條不同 Joint。
- [x] Corner lookup 使用 Joint Signature。
- [x] 已知公式優先；MISS 才 3D Discovery。
- [x] CERTIFIED 不可被 3D 修改。
- [x] 外部 JSON 可由 GUI 安全維護。
- [x] 新 rule / intent / joint 自動進回歸矩陣。
- [x] 3D 能分 legal contact / illegal penetration。
- [x] WRAP 能正確處理 wrapper preserve / wrapped relief。
- [x] 2D / 3D / FinalScene / DXF / NC / Save-Reload 共用唯一 canonical geometry。
- [x] FULL / UPDATE 使用同一 Asia/Taipei 時間戳。
- [x] UPDATE = 實際差異檔 + `release_required_artifacts.json` 指定的 mandatory verification artifacts；不得因檔案在本版未變更而省略核心驗收測試。
- [x] `unzip -t` 通過。
- [x] FULL / UPDATE 實際解壓逐檔 SHA256 比對通過；UPDATE 另驗證 mandatory gate artifacts 全數存在。

---

# 任務分配建議

| 工作組 | 主責 | 可並行時機 | 依賴 |
|---|---|---|---|
| A Joint Core | Assembly/Geometry | 先做 | 無 |
| B Registry v2 | Manufacturing/Rules | A1/A2 API 固定後 | A |
| C GUI | GUI/Bridge | B schema/API 固定後 | A+B |
| D 3D Solver v2 | Geometry/Solver | A2/A4 後可與 B 並行 | A |
| E Diagnostics | 3D UI/Renderer | D result contract 固定後 | A+D |
| F Manufacturing | 2D/3D/DXF/NC | canonical API 固定後 | A+B+D |
| G Migration | Project State | A+B contracts 固定後 | A+B |
| H Verification | Regression/Delivery | 全程持續，最後收口 | A～G |

---

# 建議實作批次

## Batch 1 — 不碰 UI，先建立真值層

- [x] A1～A4
- [x] B1～B4
- [x] G1～G3 serialization contract

**完成後才允許進 Batch 2。**

## Batch 2 — Registry 可用 + 表單

- [x] B5
- [x] C1～C5
- [x] H1 registry-driven matrix

## Batch 3 — 3D Solver v2

- [x] D1～D6
- [x] E1～E3

## Batch 4 — 全製造資料鏈切換

- [x] F1～F4
- [x] H2/H3

## Batch 5 — 最終驗收交付

- [x] H4 全項
- [x] 文件/AI handoff/踩坑庫更新
- [x] FULL + UPDATE 打包
- [x] 解壓逐檔 SHA256 驗證



---

# 2026-08-29 實作完成紀錄

- A～E：完成。WRAP 已成為 Global AssemblyJoint relation；Joint Graph / Signature / Registry v2 / 表單 / 3D Discovery / Diagnostics 已接線。
- F：2D / Single3D / Assembly3D / FinalScene / DXF 已共用 `ResolvedManufacturingGeometry`；目前專案沒有 production NC sink，因此 NC 項目為 **N/A（未存在，未假造 exporter）**。
- G：Joint Graph、USER_ADDED WRAP、rule_id/revision/trust/joint_signature 已可 Save/Reload；legacy 不猜 WRAP。
- H：registry-driven matrix、實檔 9/10、OVERLAY、collision/final scene、DXF canonical 路徑皆完成 fresh regression。
- Fresh evidence：新架構專屬 61 passed；H/canonical 54 passed；Save/Reload/WRAP 7 passed；幾何製造鏈 118 passed。
- `自訂(9)`：INSERT 38×27 單級，CERTIFIED，2D=assembly diff 0。
- `自訂(10)`：INSERT_OVERLAY 40×23 + 16×4 二級，CERTIFIED，2D=assembly diff 0。
- OVERLAY：W400/T2/FW25 fixture 的 Head/Tail 為 25×39 單級，CERTIFIED；上方中央 span 350。
- `config.ini` SHA256 與 160848 基準一致。
