---
name: 推推
description: WHD interactive Git delivery alias。只承接 executor-local workspace 已完成測試且 exact diff 已凍結的 delivery；不擁有 authoring、Drive、shared-zero 或 production authority。
whd_doc_role: CURRENT
whd_contract: workspace-tested-delivery-alias
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推

`/推推` 是 **顯式 delivery alias**，不是施工流程，也不是第二套 authority。

CURRENT 唯一路徑：

`cleanup/2d-3d-sync → executor-local repo workspace → edit/test → exact tested diff → delivery branch → PR/checks → merge/readback`

## 0. Authority boundary

- Git production X `cleanup/2d-3d-sync` 是唯一 CURRENT repository/process authority。
- 修改與測試只能在 executor-local repo workspace 完成。
- `/推推` 只能承接 **已測試、exact frozen diff** 的 Git delivery。
- Google Drive 只存 data / mirror / backup；不得作 `/推推` source、root、lane、readback hard gate 或 blocker。
- `.unpushed/docs/0`、`.unpushed/body/0`、shared-zero generation/freeze、`CANONICAL_SHARED_0_UPDATED`、Drive canonical-root sync 都是 HISTORICAL/SUPERSEDED，不得參與 CURRENT routing。
- production target 禁止 direct push；只能 delivery branch → PR → required checks → merge/readback。

## 1. 指令

保留相容指令：

- `/推推 文檔`
- `/推推 主體`

兩者只決定 **delivery scope classification**，不再映射到 Drive 或 `.unpushed` lane。

- 文檔：governance / Skill / AGENTS / SOP / docs / governance tests。
- 主體：product code / product tests / UI / renderer / geometry / manufacturing，以及與產品不可分離的必要文件。

若 planned diff 混合兩類，必須以 exact tested diff 與 issue scope 為準，不得因舊 lane 名稱拆出第二套 authoring authority。

## 2. Preconditions

delivery 前必須同時成立：

1. executor-local repo workspace 已 fresh 對齊 production X；
2. workspace mutation 已完成；
3. affected/profile tests GREEN；
4. exact diff digest 已凍結；
5. target drift 已 fresh compare/reconcile；
6. delivery path reservation 已綁 exact tested diff；
7. 本次 user authorization 只涵蓋同 repository / 同 task / 同 diff 的 delivery。

缺任何一項都不得 push/PR。

## 3. Delivery

固定：

`CREATE_DELIVERY_BRANCH → APPLY_EXACT_TESTED_DIFF → PUSH → PR → REQUIRED_CHECKS → PRE_MERGE_RECHECK → MERGE → READBACK → FINALIZE`

- branch 必須從 fresh production X 建立。
- 不得在 delivery branch 追加未測內容；若 diff 改變，回 executor workspace 重測。
- target drift 若與 touched paths / dependency impact 無關，可依 GREEN reuse contract 重用既有 GREEN；有 impact 才 retest。
- merge 後以 production readback 為完成依據。

## 4. Drive / shared-zero retirement

以下全部禁止作 CURRENT 行為：

- 從 `/Google Drive/WHD` 找施工 baseline；
- 因 Drive mount 不可見而回 blocker；
- 從 `.unpushed/docs/0` / `.unpushed/body/0` 取得 authoring authority；
- 啟動 `workspace_canonical_sync.py` 作普通或 fallback routing；
- 要求 `CANONICAL_SHARED_0_UPDATED` 才能 delivery；
- 以 Drive readback 取代 GitHub merge/readback。

若看到上述舊 evidence，只能標記 HISTORICAL/SUPERSEDED 並回 CURRENT workspace route。

## 5. Terminal authority

`MERGE_READBACK_VERIFIED → FINALIZE → DONE / RELEASED`

Drive mirror 更新是非阻塞 durability/backup 行為；缺 mirror receipt 不得保持 Issue OPEN、撤銷 DONE 或重開已完成 delivery。

machine owners：
- routing / git unlock: `tools/root_local_first_gate.py`
- Flow v2 delivery/finalization: canonical Flow v2 executables
