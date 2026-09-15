---
name: phase6-overlay-relief-basis
description: Use when modifying Phase6 OVERLAY endcap relief, flat-X topology, AssemblyJoint Graph semantics, Certified Relief Registry rules, 3D collision/backprojection, or persisted assembly relief replay.
---

# Phase6 OVERLAY：Joint Graph → STANDARD → Semantic Delta

## [CURRENT] 現行 Source of Truth

OVERLAY 不再以 `formed FW=29`、legacy Top CornerType 或高階 `assembly_type` 直接決定正式 CUTTING。現行唯一資料鏈：

```text
Canonical Dimension Model
→ Assembly Intent preset
→ Resolved AssemblyJoint Graph
→ STANDARD from real Fold Topology
→ Certified Semantic Delta
→ Resolved Manufacturing Geometry
→ 2D / 單板 3D / 組合 3D / DXF / Save-Reload / blank report
```

高階 Assembly Intent 只是操作員 preset。只要 Resolved Joint Graph 已存在，preset、legacy `assembly_type`、Top CornerType 都不得覆寫 graph/user/solver truth。

## OVERLAY topology

- EndCap 左右 X BEND 不存在；flat-X 必須在 2D、Fold Editor、單板 3D、組合 3D、DXF 一致。
- Corner resolver 讀鄰近 AssemblyJoint：TOP/BOTTOM edge + LEFT/RIGHT edge，而不是從 preset 名稱反推。
- Hybrid corner 必須保留左右差異；例如 TOP=OVERLAY、LEFT=INSERT、RIGHT=WRAP 時，左右角可以有不同 Registry HIT/MISS。

## STANDARD 母體

STANDARD 必須由實際 Fold Topology 的材料幾何推導，不能用 final polygon bbox、formed occupation 或 hard-code 常數取代。

Vault 基準 `W=400, T=2, FW material=25, side_fold=15, ytop1=16`：

- Top STANDARD：`primary_u = side_fold + FW = 40`、`primary_v = ytop1 + FW = 41`。
- Bottom STANDARD 基準：`15×15`。
- `ytop1` 缺折時，從仍存在的最內實際折線重新求 STANDARD；不得因 topology 少一折就 fallback 到 assembly enum 或 raise 成製造真值缺失。

## Certified OVERLAY rule

現行正式 rule：`ENDCAP_TOP_OVERLAY_STANDARD_V1@3`。

- `standard_ref = ENDCAP_TOP_STANDARD_V1`
- `dimension_space = MATERIAL`
- `topology_levels = 2`
- primary：`40×39`（STANDARD Y 41 套 OVERLAY `-1T` 留肉）
- secondary：`15×2`
- 公式真值來自 Certified Registry；production 不得複製第二套公式。
- runtime validator 必須驗 rule 宣告與實際 cutting topology，不得再硬寫「OVERLAY 一定 1-stage」。

`formed FW=29` 只保留作歷史/3D shadow evidence，可幫助 collision 診斷，但**不是正式 CUTTING oracle**，也不得寫回 EndCap material `FW=25`。

## Receiving bottom ownership

受電箱 Family 不得擁有自訂 assembly-derived bottom corner meaning。

- Family 只提供 target face、side/back structure、material/outside dimensions、reserve 等 geometry input。
- BOTTOM INSERT/WRAP 由 Resolved AssemblyJoint 表達。
- 沒有 BOTTOM WRAP joint 時，bottom policy 是 STANDARD；不得因 `family=受電箱` 自動猜 WRAP。
- BOTTOM WRAP HIT 使用自己的 Receiving registry trace，不能借用同零件 TOP Certified Rule。

## Persisted relief / replay

`.p6fold` 的 committed relief 是 replay cache，不是永恆製造真值。現行 replay identity 必須至少涵蓋：

- active Certified rule id/revision
- Fold Profile / formed geometry signature
- cabinet family / family structure fingerprint
- Resolved Joint Graph 的**機械語意 fingerprint**

Joint fingerprint 只包含會改變機械結果的 relation/edge/contact/preserve/clearance/solver semantics；`joint_id`、source provenance、migration origin 等不得讓機械上相同的 graph 被誤判不同。Legacy `left_side/right_side` 與 v2 `left_edge/right_edge` 已知 naming alias 必須正規化。

任何 rule revision、Fold Profile、formed FW evidence、family structure 或 Joint semantics 變更都必須使 replay stale，fresh rebuild from Registry/solver。

## Registry HIT / MISS

HIT diagnostics 至少保留：rule id、revision、relation/joint signature、owner、STANDARD reference、dimension space、evidence、pre-solve evidence、post-solve penetration。

MISS 只能建立 provisional evidence；不得把 solver 發現自動寫回 Certified Registry，也不得假裝成 CERTIFIED。

## 禁止事項

- 禁止用 `formed FW=29` 取代 STANDARD + Semantic Delta 正式公式。
- 禁止把 legacy Top CornerType 或 `assembly_type` 當 resolved geometry owner。
- 禁止讓 preset redraw/reload 覆蓋 USER_ADDED / SOLVER_CONFIRMED joints。
- 禁止把 final relieved polygon bbox 當 blank W×H。
- 禁止只修 2D renderer；Resolved Manufacturing Geometry、單板 3D、組合 3D、DXF、Save/Reload 必須同源。
- 禁止為讓舊 historical test 綠燈而倒退 production ownership。

## 必做驗證

1. Registry-driven enumerate 全部 Assembly Intent 與 Joint relation；新增 intent/relation 自動要求 regression coverage。
2. Head/Tail 獨立驗證，含 mixed Head/Tail、edge override、TOP OVERLAY + SIDE INSERT hybrid、BOTTOM WRAP。
3. OVERLAY flat-X 在 2D / Fold Editor / 單板 3D / 組合 3D / DXF 都不存在 X BEND。
4. 求解前顯示候選碰撞證據，求解後 illegal penetration = 0。
5. Certified HIT 顯示 rule id/revision/STANDARD/evidence；MISS 只能 PROVISIONAL。
6. 主 2D = 單板 3D = 組合 3D canonical material；Save→Reload 不變。
7. local corner relief 可改 area，但 blank W×H 由 material segment chain / physical piece 保持穩定。
8. 舊 schema-1 side-only Joint Graph migration 成 explicit four-edge v2，但 explicit/user joint 必須優先，且不得猜新 WRAP。
9. `config.ini` SHA256 必須保持 release baseline 原值。

## 歷史證據（已 superseded）

2026-08-29 文件中 `formed FW=29 → top X CUT=29`、`ENDCAP_TOP_OVERLAY_STANDARD_V1@2`、replay contract v2，保留作 migration / historical fixture evidence；它們不再是 2026-09-01 runtime specification。

## 3D 完整性聯動

OVERLAY relief、Joint Graph、STANDARD、Certified Registry、replay 或 3D placement 有任何變更時，必須同步執行 `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md` 的 true-thickness、pre/post collision、2D/單板3D/組合3D、Save/Reload gate。
