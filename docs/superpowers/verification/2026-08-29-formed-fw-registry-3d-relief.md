# Phase6 OVERLAY Formed-FW Registry / 3D Relief Verification

## Scope

本驗證以使用者實際 `金庫型貼外.p6fold` 為 regression fixture。目標不是再補一條 UI 公式，而是把 OVERLAY 上方裝配避讓正式收斂到 `Fold Profile → formed FW → Certified Registry → 3D shadow validation → ResolvedManufacturingGeometry → persistence replay` 同一條 Source of Truth。

Portable fixture：`tests/fixtures/vault_overlay_w400_t2_fw25.p6fold`。

## Manufacturing truth

Fixture：`W=400, T=2, nominal/material FW=25, assembly=OVERLAY`。

- EndCap X topology=flat，沒有左右 X BEND。
- EndCap nominal FW 保持 25；它仍負責 EndCap 自身 Y residual。
- Box Body `fw_left/fw_right` Fold Profile 材料段為 25；依目前實際相鄰真折彎與 T 解析後，formed FW occupation=29。
- 上方 X CUT=formed FW=29/側；單側 `29+371=400`；左右都截後中央 342。
- 上方 V=`ytop1 + EndCapFW - 1T = 16+25-2 = 39`。formed FW 不得寫回 EndCap frame_width。
- 下方 `CROSS / EXTRA_CUT / WIDTH / 1.5T`：3/側，中央 394。

歷史 40/320 與 25/350 均為 superseded regression oracle。

## Registry / 3D contract

`ENDCAP_TOP_OVERLAY_STANDARD_V1` 已升 revision 2：

- `geometry_inputs` 明確包含 `BOX_BODY_FORMED_FW`。
- X formula 使用 `primary_u = mating_width`；Registry 不硬寫 29。
- formed FW 從目前 Box Body Fold Profile + T 解析。
- solver `shadow_validation` 保存 `geometry_inputs` 與 `formed_fw_by_corner` evidence。
- Head / Tail 都命中同一 certified rule；post-solve residual pair count=0。
- `ResolvedReliefRuleTrace` 保留 rule revision 與 geometry evidence，供 2D/3D/export/audit 共用。

## Persistence contract v2

`assembly_relief` 是 cache，不是永恆製造真值。現行 source signature 至少包含：

- `relief_contract_version=2`
- `box_body_formed_fw.left/right`
- Box Body / EndCap Fold Profile fingerprints
- assembly intent / W-H-D-T-FW scalar signature
- per-part `registry_rules.{rule_id, revision}`

使用者原始檔保存的是舊 revision-1 / versionless 40-mm relief。Fresh load 在**尚未開 3D**前即拒絕重播 stale cuts，主 2D 重新由現行 geometry contract 得到上方 29/342。

## TDD evidence

新 contract 測試在修改 production code 前得到四個 RED：

1. Registry 未宣告 formed-FW geometry input。
2. 舊 40-mm committed relief 仍被重播。
3. OVERLAY rule revision 仍為 1。
4. serialized relief source 未保存 active registry revision。

完成實作後 focused contract 全部轉 GREEN。

## Fresh regression evidence in isolated source tree

- Assembly / Joint / Collision / Certified Registry / Resolved Manufacturing affected core：`165 passed`（僅 Shapely resolution deprecation warnings）。
- Registry-driven GUI matrix：`3 passed`，INSERT / OVERLAY / INSERT_OVERLAY 各一。
- 實檔 + 2D / single3D / assembly / shared dimensions / Tail native orientation / Save-Reload：`81 passed`（僅 CJK font warnings）。
- Head / Tail certified shadow：`verified=True`，`residual_pair_count=0`，formed-FW evidence=29/29。
- 主 2D / single-part 3D / assembly canonical material 的 symmetric difference area=0。

## Release gate

正式封包必須從 FULL fresh extract 後重跑本驗證，不得用工作目錄結果冒充交付結果。UPDATE 必須累積包含 `個人AI檔案庫/**`、本 spec/plan/verification/test 與 release mandatory artifacts，且不得包含 `config.ini`。
