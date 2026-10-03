---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Root-local-first 入口硬閘門踩坑

## 2026-09-29 — workspace-first 與 branch-before-write 同時 CURRENT

- **事故模式**：Flow v2 / work-root 已要求 `/Google Drive/WHD` 作 interactive workspace，但 AGENTS、Skills 與 contract tests 仍要求第一次 repository write 前先建 Git work branch。結果同一任務同時存在兩個相反順序。
- **根因**：舊 branch policy 沒有被降級成 Git-phase-only，且 tests 還把 `branch-first` 關鍵字當正向 invariant。
- **永久規則**：interactive/default content work 唯一順序為 `ROOT_SOURCE_CURRENT → UNPUSHED_LANE_CLASSIFIED → LATEST_0_BASE_BOUND → ROOT_MUTATIONS_COMPLETE → MERGE_TO_0_OR_CONFLICT_CHECKPOINT → POST_MERGE_0_TEST_CLASSIFIED → POST_MERGE_0_TESTS_GREEN → LANE_MANIFEST_FROZEN → DELIVERY_PATHS_RESERVED → GIT_WRITE_UNLOCKED`；root 施工不做 pre-write reservation；`LANE_MANIFEST_FROZEN` 後才取得 delivery reservation，fresh Git delivery branch 只在 unlock 後建立。
- **Git phase invariant**：仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；unlock 後只允許 `EXACT_TESTED_DIFF_ONLY`。
- **source freshness**：Drive full snapshot 若落後，只可作 bootstrap base；manifest 必須標示真實 source SHA/tree，未證明 current 的 touched path 不得修改。
- **remote scope**：`SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 仍依 Flow v2 remote authority；不得拿 remote mode 當 interactive content-work bypass。
- **machine owner**：`tools/root_local_first_gate.py` + `tests/process/test_root_local_first_entry_hard_gate.py`。
## 2026-10-03 — 入口 contract 已存在，但 agent 先做 generic discovery

- **事故模式**：使用者要求直接修改 WHD 流程時，agent 沒有先讀 canonical root entry contract / root-local-first Skill，而先做 Remote Desktop、generic Drive search、工具 discovery；即使後來回到正確 root，前段仍屬錯序。
- **根因**：舊規則只規範「進入 root-local-first 之後怎麼做」，沒有 machine-enforce「找到入口本身必須是第一個 routing sequence」。
- **永久規則**：每個 WHD repository-content invocation 固定先 `READ canonical entry contract → READ root-local-first Skill → ENTRY_ROUTER_READY`；READY 前 generic discovery、Remote Desktop/local search、GitHub content discovery、claim/Flow v2 discovery 全部 fail closed。
- **錯序處置**：任何 READY 前取得的 generic discovery 只能標記為 non-execution evidence；固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`，不得沿錯路續做。
- **防回歸 owner**：`tools/root_local_first_gate.py`、`WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`、`AGENTS.md`、`tests/test_root_entry_router_hard_gate.py`。

## 2026-10-03 — root authority 有了，但同名搜尋與 stale root 仍可繞過 latest 0

<!-- ROOT_PARENT_CHAIN_AND_LATEST_ZERO_PITFALL_V1 -->
- **事故模式**：repository-content 任務已指定 `/Google Drive/WHD` 為 canonical root，agent 仍先用 GitHub／全域 Drive 搜尋同名 `SKILL.md`；回到 root 後又直接拿 root 當 baseline，而 `.unpushed/docs/0` 的 frozen generation 已比 root 新，形成「找到對資料夾卻仍用 stale file」的第二條繞路。
- **根因**：舊入口 gate 只保證先進 root-local-first，沒有把「exact parent-chain path resolution」「remote deny-by-default」「若 path 已在 0，latest 0 優先於 root」做成同一組 machine invariants。
- **永久規則**：repository-content 找檔／讀 baseline 必須從 `/Google Drive/WHD` 沿 exact parent chain 定位；全域同名搜尋只能是 `CANDIDATE_ONLY`，不得直接成為 baseline。path 已存在於 `.unpushed/{lane}/0` 時，以 fresh latest `generation + hash` 為施工 base；worker 完成後再 fresh-read latest 0，才允許三方合併。
- **remote boundary**：除「只為開工單」或使用者明確授權的 exact remote action 外，GitHub 與遠端本機預設 `DENY`；未授權時連 GitHub `READ/FETCH/COMPARE` 都不能用來找 baseline。`/推推 文檔|主體` 只打開該次 selected lane delivery window，完成／失敗退出即關閉。
- **delivery boundary**：freeze 後建立 exact fileset lock；真正 merge 前 fresh-read target 與每個 locked path；target 若碰 locked path，固定回 root/latest 0 reconcile→test→refreeze。merge readback 成功後只清本次 readback 已交付且 hash 未漂移的 locked paths，不刪 repository 實體檔；同一檔之後再改必須重新登記成新的 unpushed change。
- **錯路處置**：若先前已用 stale root／remote same-name 結果施工，該 baseline evidence 立即失效；必須回 fresh latest 0 重建 candidate，不得把舊修改直接覆蓋新 generation。
- **machine owners**：`tools/root_local_first_gate.py`（path resolution + remote authority）、`tools/shared_unpushed_integration.py`（latest-0/fileset lock/pre-merge recheck/finalize）、`WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json` 與對應 contract tests。
