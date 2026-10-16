---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Root-local-first 入口硬閘門踩坑

> **REFERENCE／HISTORICAL（2026-09～10）**：以下是已退役入口與 root/workspace 分流事故記錄，不是現行執行規則。現行權威只看正式 X `AGENTS.md`、對應 CURRENT Skill 與受信任的 `tools/change_lane_gate.py`。`WORKSPACE_DEFAULT`、舊 root-local-first 泛用硬閘門及文中舊 machine owner 不得重啟，也不授予 DC／CoreELEC 存取。

## 當時 workspace-first 覆寫規則（HISTORICAL/SUPERSEDED，2026-10）

- repository-content normal route 固定為 `WORKSPACE_DEFAULT`：使用 **executor-local repo workspace** + fresh `cleanup/2d-3d-sync` baseline 完成 author/test/exact diff，再進 delivery。
- 外部儲存/shared-zero 已退役；有無 historical drift 都固定 WORKSPACE_DEFAULT，不得啟動 shared-zero fallback、merge/freeze 或 /推推 前置。 repository-content 修改先在 executor-local repo workspace + fresh cleanup/2d-3d-sync baseline 完成 author/test，再以 exact tested diff delivery。
- Codex 常見 workspace 為 `/workspace/whd`；missing 外部儲存 mount 不是 `WORKSPACE_DEFAULT` blocker。
- 本檔較早的 外部儲存/shared-0 順序只保留 **HISTORICAL/SUPERSEDED** 事故脈絡，不得再作 CURRENT execution instruction。
- Git phase 仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；只允許 exact-tested-diff 的 dedicated delivery path。


## 2026-09-29 — workspace-first 與 branch-before-write 衝突（HISTORICAL/SUPERSEDED）

- **歷史事故摘要**：舊流程曾同時存在 外部儲存-first 與 branch-first 兩種互斥施工順序，造成同一任務出現兩套 authority。
- **當時規則（HISTORICAL/SUPERSEDED）**：只接受 executor-local repo workspace + fresh `cleanup/2d-3d-sync` baseline；外部儲存 snapshot 僅可作 recovery material，不能成為施工 baseline。
- **Git phase invariant**：禁止直接寫 `cleanup/2d-3d-sync` / `main`；tested exact diff 只能經 dedicated delivery branch → PR/checks → trusted merge/readback。
- **歷史 machine owner（已退役）**：`tools/root_local_first_gate.py` + `tests/process/test_root_local_first_entry_hard_gate.py`。
## 2026-10-03 — 入口 contract 已存在，但 agent 先做 generic discovery（HISTORICAL/SUPERSEDED）

- **事故模式**：使用者要求直接修改 WHD 流程時，agent 沒有先讀 canonical root entry contract / root-local-first Skill，而先做 Remote Desktop、generic 外部儲存 search、工具 discovery；即使後來回到正確 root，前段仍屬錯序。
- **根因**：舊規則只規範「進入 root-local-first 之後怎麼做」，沒有 machine-enforce「找到入口本身必須是第一個 routing sequence」。
- **當時錯序處置（HISTORICAL）**：READY 前的 generic discovery 曾被分類為 non-execution evidence，並要求 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`；此舊入口 gate 已退役。今日不要求 READY／old preflight 收據，改以正式 X `AGENTS.md` 的 GitHub／雲端治理和產品分流為準。
- **歷史防回歸 owner（已退役）**：`tools/root_local_first_gate.py`、`WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json`、`AGENTS.md`、`tests/test_root_entry_router_hard_gate.py`。

## 2026-10-03 — 歷史 外部儲存/shared-zero authority 被 generic search 重播（HISTORICAL/SUPERSEDED）

<!-- ROOT_PARENT_CHAIN_AND_LATEST_ZERO_PITFALL_V1 -->
- **歷史事故摘要**：舊文件把 外部儲存/shared-zero 描述成可執行施工 authority；agent 透過 generic search 讀到舊文件後，會把歷史資料誤當 CURRENT 流程。
- **當時規則（HISTORICAL/SUPERSEDED）**：repository-content baseline 只取 fresh Git production X，施工與測試只在 executor-local repo workspace；任何 外部儲存 Skill、snapshot、generation、lane 或 historical receipt 都不能改變 route。
- **禁止重播**：不得從歷史文件重建 parent-chain、latest-generation、shared lane reconcile、freeze 或 cleanup 作為 CURRENT startup/delivery gate。
- **現行糾偏（不恢復歷史入口）**：若誤引用過時 外部儲存/shared-zero authority，應重新讀取正式 X 的 `AGENTS.md` 與對應 CURRENT Skill，依 `/派工`／`/接手`／治理直送分流修正後續操作。**不得因讀到本段就呼叫 root-local-first 或 DC／RC**；以下 executor-local workspace 只描述當時事故處置。
- **當時 delivery boundary（HISTORICAL）**：tested exact diff → dedicated branch → PR/checks → trusted merge/readback；目前是否要重測、是否需 localX 本機安全整合與是否能發布正式 X，都由現行 `AGENTS.md` 和 exact HEAD CI 決定，不由此舊 workspace-first 規則授權。
- **歷史 machine owner（已退役）**：`tools/root_local_first_gate.py`；legacy shared-unpushed utilities只可作 HISTORICAL parser，不擁有 CURRENT routing/finalization。