---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Root-local-first 入口硬閘門踩坑

## CURRENT workspace-first 覆寫規則 — 2026-10

- repository-content normal route 固定為 `WORKSPACE_DEFAULT`：使用 **executor-local repo workspace** + fresh `cleanup/2d-3d-sync` baseline 完成 author/test/exact diff，再進 delivery。
- shared `.unpushed/{docs|body}/0` / `SHARED_ZERO_FALLBACK` 已完全退出 CURRENT routing；即使看到 fresh historical drift，也只能記錄為歷史資料，不得改變 `WORKSPACE_DEFAULT`。
- Codex 常見 workspace 為 `/workspace/whd`；missing Drive mount 不是 `WORKSPACE_DEFAULT` blocker。
- 本檔較早的 Drive/shared-0 順序只保留 **HISTORICAL/SUPERSEDED** 事故脈絡，不得再作 CURRENT execution instruction。
- Git phase 仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；只允許 exact-tested-diff 的 dedicated delivery path。


## 2026-09-29 — workspace-first 與 branch-before-write 衝突（HISTORICAL/SUPERSEDED）

- **事故模式**：Flow v2 / work-root 已要求 `/Google Drive/WHD` 作 interactive workspace，但 AGENTS、Skills 與 contract tests 仍要求第一次 repository write 前先建 Git work branch。結果同一任務同時存在兩個相反順序。
- **根因**：舊 branch policy 沒有被降級成 Git-phase-only，且 tests 還把 `branch-first` 關鍵字當正向 invariant。
- **歷史修補（SUPERSEDED）**：當時曾把 shared-0 pipeline 當唯一順序；2026-10 已由上方 CURRENT workspace-only `WORKSPACE_DEFAULT` 覆寫；shared-zero route 已退休。
- **Git phase invariant**：仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；unlock 後只允許 `EXACT_TESTED_DIFF_ONLY`。
- **source freshness**：Drive full snapshot 若落後，只可作 bootstrap base；manifest 必須標示真實 source SHA/tree，未證明 current 的 touched path 不得修改。
- **remote scope**：`SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 仍依 Flow v2 remote authority；不得拿 remote mode 當 interactive content-work bypass。
- **machine owner**：`tools/root_local_first_gate.py` + `tests/process/test_root_local_first_entry_hard_gate.py`。
## 2026-10-03 — 入口 contract 已存在，但 agent 先做 generic discovery

- **事故模式**：使用者要求直接修改 WHD 流程時，agent 沒有先從 executor-local repo workspace 讀 CURRENT entry contract / root-local-first Skill，而先做 Remote Desktop、generic Drive search 或無關工具 discovery；這會把 backup/歷史資料誤當 execution authority。
- **根因**：舊規則只規範「進入 root-local-first 之後怎麼做」，沒有 machine-enforce「找到入口本身必須是第一個 routing sequence」。
- **永久規則**：每個 WHD repository-content invocation 固定先 `READ canonical entry contract → READ root-local-first Skill → ENTRY_ROUTER_READY`；READY 前 generic discovery、Remote Desktop/local search、GitHub content discovery、claim/Flow v2 discovery 全部 fail closed。
- **錯序處置**：任何 READY 前取得的 generic discovery 只能標記為 non-execution evidence；固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`，不得沿錯路續做。
- **防回歸 owner**：`tools/root_local_first_gate.py`、`WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`、`AGENTS.md`、`tests/test_root_entry_router_hard_gate.py`。

## 2026-10-03 — root authority 有了，但同名搜尋與 stale root 仍可繞過 latest 0

<!-- ROOT_PARENT_CHAIN_AND_LATEST_ZERO_PITFALL_V1 -->
- **歷史事故模式（已退休）**：舊流程曾指定 `/Google Drive/WHD` 與 `.unpushed` 作施工 authority。CURRENT 規則禁止重播此流程；任何舊 Drive Skill、frozen generation、shared-zero evidence 都只能作歷史資料，repository-content baseline 固定 fresh Git production X + executor-local repo workspace。
- **根因**：舊入口 gate 只保證先進 root-local-first，沒有把「exact parent-chain path resolution」「remote deny-by-default」「若 path 已在 0，latest 0 優先於 root」做成同一組 machine invariants。
- **歷史修補（SUPERSEDED）**：曾要求固定 Drive parent-chain + latest-0 作施工 baseline；CURRENT normal route 已固定為 executor-local `WORKSPACE_DEFAULT`；任何 shared-zero drift 都不得再切換 route。
- **remote boundary**：除「只為開工單」或使用者明確授權的 exact remote action 外，GitHub 與遠端本機預設 `DENY`；未授權時連 GitHub `READ/FETCH/COMPARE` 都不能用來找 baseline。`/推推 文檔|主體` 只打開該次 selected lane delivery window，完成／失敗退出即關閉。
- **delivery boundary**：freeze 後建立 exact fileset lock；真正 merge 前 fresh-read target 與每個 locked path；target 若碰 locked path，固定回 root/latest 0 reconcile→test→refreeze。merge readback 成功後只清本次 readback 已交付且 hash 未漂移的 locked paths，不刪 repository 實體檔；同一檔之後再改必須重新登記成新的 unpushed change。
- **錯路處置**：若先前已用 stale root／remote same-name 結果施工，該 baseline evidence 立即失效；必須回 fresh latest 0 重建 candidate，不得把舊修改直接覆蓋新 generation。
- **machine owner**：`tools/root_local_first_gate.py`；`tools/shared_unpushed_integration.py` 僅保留 HISTORICAL parser，不再擁有 CURRENT routing/finalize。
