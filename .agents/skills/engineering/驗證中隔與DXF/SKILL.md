---
name: 驗證中隔與DXF
description: 使用者要求「驗中隔」「驗目前中隔」「中隔完整驗收」「DXF反驗證」「Save→Reload 驗收」時，執行目前 branch / current production state 的中隔 canonical、relief、placement、DXF reopen、Save→Reload 一致性驗收。
---

# 驗證中隔與 DXF

## 何時使用

使用者出現下列任一要求時，直接套用本 Skill，不要只解釋：

- `驗中隔` / `驗目前中隔` / `查目前中隔對不對`
- `中隔完整驗收` / `跑中隔完整驗收`
- `DXF反驗證` / `驗輸出的DXF` / `DXF存出去再驗`
- `Save→Reload 驗收` / `存檔再讀回來驗`

## 使用者操作語意

### A. 驗目前中隔

**不需要先存專案。** 直接驗 current production state：

1. canonical Final Material / bounds / span；
2. fixed-hole authoritative datum、孔數、孔徑、孔到 physical edge；
3. relief / chamfer / collision/backprojection；
4. 3D authoritative placement、FW face flush、core inward；
5. 2D / 3D / DXF owner 是否仍同源。

### B. DXF 反驗證

這個模式需要先把 DXF 實際輸出成檔案，但**不等於先存 `.p6fold` 專案**：

1. 由 canonical `PartRenderData` / resolved physical part 輸出 DXF；
2. 用 `ezdxf.readfile()` 重新打開實際檔案；
3. 從檔案重新抽 CUTTING / BEND / holes / layers；
4. 與 canonical Final Material / fold guides / feature metadata 比；
5. `MISSING_PART / EXTRA_PART / CUTTING_MISMATCH / BEND_MISMATCH / HOLE_MISMATCH / LAYER_MISMATCH / UNCLOSED_CONTOUR` 任一出現即 FAIL。

### C. 完整中隔驗收

完整驗收 = A + B + Save→Reload parity：

1. current state 直接驗；
2. DXF export → reopen → compare；
3. `.p6fold` Save → Reload；
4. Reload 後再次比較 Final Material、孔 signature、relief metadata、placement、dynamic physical-part identity；
5. `config.ini` SHA256 前後必須一致。

## Current Divider focused acceptance

目前正式驗收族至少包含：

```text
tests/test_issue38_receiving_divider_baseline.py
tests/test_issue39_divider_relief.py
tests/test_issue40_divider_6p4_shared_datum.py
tests/test_phase6_t16_receiving_placement.py
tests/test_dm3_divider_canonical_relief_contract.py
tests/test_dm4_divider_resolved_sinks.py
tests/test_issue41_persistence_parity.py
tests/test_multipart_dxf_acceptance.py
tests/test_dxf_acceptance.py
```

需要實際數值時，再加：

```text
tests/test_issue63_regression_red.py::test_issue63_resolved_divider_matches_resolved_head_tail_middle_and_hole_edge_parity
tests/test_issue63_regression_red.py::test_issue63_divider_candidate_preserves_uv_shape_and_sweeps_skin_to_solid_boundary
tests/test_issue39_divider_relief.py::test_t3_family_solver_commits_verified_relief_and_preserves_mating_contact
```

## 必須回報的結果

不要只回 `PASS`。至少回報：

- branch + tested head SHA；
- run_id + terminal status；
- 各測試族 PASS / FAIL；
- `T`、Final Material bounds / span；
- resolved middle segment / head / tail parity；
- fixed-hole 數量、直徑、physical-edge offset；
- FW material / outside dimension 與 flush planes；
- pre/post collision、illegal penetration、retained mating contact；
- skin→solid sweep 的 `T/2`、expected / actual cut area、under/overcut；
- DXF reopen parity；
- Save→Reload parity；
- `config.ini` before/after SHA。

## Remote QA 規則

- 只要建立 GitHub Actions run，就必須鎖定同一 `run_id + head_sha` 輪詢到 `completed`。
- `queued / in_progress` 不得停在回報狀態。
- Preflight / install / import / dependency failure 不能冒充產品 FAIL。
- 一次性驗收 workflow / evidence 用完必須刪除，並反讀確認不存在。
- 驗收前後 production/test blob 若有 drift，舊 GREEN 失效，必須重跑。

## 驗證與 production 邊界

**驗證只能判對錯，不能反向成為 production 計算來源。**

- `0.001` boolean fringe、`47/26`、`10/100`、`1 mm`、middle segment、pytest expected 都只能是 oracle / tolerance / evidence。
- production relief / hole / placement / thickness 只能由 canonical state、authoritative `T`、AssemblyJoint/Fold topology、DXF 授權 datum、physical collision/backprojection、certified semantics 推導。
- 若驗證看到 A 與 B 差多少，禁止把 `B-A` 直接寫成 production 補償。

## UI 邊界

- 目前這個 Skill 是 **AI / 工程驗收入口**，不是 GUI 內已新增一顆「驗證中隔」按鈕。
- 2D Engineering Drawing 標註會在既有 preview 路徑自動使用 shared AnnotationPlan。
- DXF reopen acceptance 與 Save→Reload parity 屬驗收流程；若要做成 GUI 一鍵按鈕，需另開 UI 功能工單。
