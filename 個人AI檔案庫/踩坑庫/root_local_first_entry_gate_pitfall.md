---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Root-local-first 入口硬閘門踩坑

## CURRENT workspace-first 覆寫規則 — 2026-10

- repository-content normal route 固定為 `WORKSPACE_DEFAULT`：使用 **executor-local repo workspace** + fresh `cleanup/2d-3d-sync` baseline 完成 author/test/exact diff，再進 delivery。
- Drive/shared-zero 已退役；有無 historical drift 都固定 WORKSPACE_DEFAULT，不得啟動 shared-zero fallback、merge/freeze 或 /推推 前置。 repository-content 修改先在 executor-local repo workspace + fresh cleanup/2d-3d-sync baseline 完成 author/test，再以 exact tested diff delivery。
- Codex 常見 workspace 為 `/workspace/whd`；missing Drive mount 不是 `WORKSPACE_DEFAULT` blocker。
- 本檔較早的 Drive/shared-0 順序只保留 **HISTORICAL/SUPERSEDED** 事故脈絡，不得再作 CURRENT execution instruction。
- Git phase 仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；只允許 exact-tested-diff 的 dedicated delivery path。


## 2026-09-29 — workspace-first 與 branch-before-write 衝突（HISTORICAL/SUPERSEDED）

- **歷史事故摘要**：舊流程曾同時存在 Drive-first 與 branch-first 兩種互斥施工順序，造成同一任務出現兩套 authority。
- **CURRENT 規則**：只接受 executor-local repo workspace + fresh `cleanup/2d-3d-sync` baseline；Drive snapshot 僅可作 recovery material，不能成為施工 baseline。
- **Git phase invariant**：禁止直接寫 `cleanup/2d-3d-sync` / `main`；tested exact diff 只能經 dedicated delivery branch → PR/checks → trusted merge/readback。
- **remote scope**：`SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 仍依 Flow v2 remote authority；不得拿 remote mode 當 interactive content-work bypass。
- **machine owner**：`tools/root_local_first_gate.py` + `tests/process/test_root_local_first_entry_hard_gate.py`。
## 2026-10-03 — 入口 contract 已存在，但 agent 先做 generic discovery

- **事故模式**：使用者要求直接修改 WHD 流程時，agent 沒有先讀 canonical root entry contract / root-local-first Skill，而先做 Remote Desktop、generic Drive search、工具 discovery；即使後來回到正確 root，前段仍屬錯序。
- **根因**：舊規則只規範「進入 root-local-first 之後怎麼做」，沒有 machine-enforce「找到入口本身必須是第一個 routing sequence」。
- **永久規則**：每個 WHD repository-content invocation 固定先 `READ canonical entry contract → READ root-local-first Skill → ENTRY_ROUTER_READY`；READY 前 generic discovery、Remote Desktop/local search、GitHub content discovery、claim/Flow v2 discovery 全部 fail closed。
- **錯序處置**：任何 READY 前取得的 generic discovery 只能標記為 non-execution evidence；固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`，不得沿錯路續做。
- **防回歸 owner**：`tools/root_local_first_gate.py`、`WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json`、`AGENTS.md`、`tests/test_root_entry_router_hard_gate.py`。

## 2026-10-03 — 歷史 Drive/shared-zero authority 被 generic search 重播（HISTORICAL/SUPERSEDED）

<!-- ROOT_PARENT_CHAIN_AND_LATEST_ZERO_PITFALL_V1 -->
- **歷史事故摘要**：舊文件把 Drive/shared-zero 描述成可執行施工 authority；agent 透過 generic search 讀到舊文件後，會把歷史資料誤當 CURRENT 流程。
- **CURRENT 規則**：repository-content baseline 只取 fresh Git production X，施工與測試只在 executor-local repo workspace；任何 Drive Skill、snapshot、generation、lane 或 historical receipt 都不能改變 route。
- **禁止重播**：不得從歷史文件重建 parent-chain、latest-generation、shared lane reconcile、freeze 或 cleanup 作為 CURRENT startup/delivery gate。
- **錯路處置**：若已引用歷史 authority，該 routing evidence 立即失效；回 CURRENT entry contract + root-local-first Skill，重新以 executor-local workspace + fresh X 建立 candidate。
- **delivery boundary**：tested exact diff → dedicated delivery branch → PR/required checks → trusted merge/readback；target drift 先做 GREEN reuse impact revalidation，有影響才回 workspace 重測。
- **machine owner**：`tools/root_local_first_gate.py`；legacy shared-unpushed utilities只可作 HISTORICAL parser，不擁有 CURRENT routing/finalization。